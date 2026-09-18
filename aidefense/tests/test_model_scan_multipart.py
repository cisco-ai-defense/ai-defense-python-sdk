# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import MagicMock, patch

import pytest
import requests

from aidefense.config import Config
from aidefense.exceptions import SDKError, ScanTimeoutError
from aidefense.modelscan.model_scan import (
    DEFAULT_SCAN_TIMEOUT_SECONDS,
    RETRY_COUNT_FOR_SCANNING,
    WAIT_TIME_SECS_SUCCESSIVE_SCAN_INFO_CHECK,
    ModelScanClient,
    _ConsoleStatusSpinner,
)
from aidefense.modelscan.model_scan_base import (
    MAX_FILE_SIZE_BYTES,
    ModelScan,
    _BoundedFileReader,
    _ConsoleUploadProgress,
)
from aidefense.modelscan.models import (
    CreateScanObjectRequest,
    CreateScanObjectResponse,
    GetMultipartUploadPartUrlsResponse,
    MultipartUpload,
    MultipartUploadPartUrl,
)
from aidefense.request_handler import HttpMethod


TEST_API_KEY = "0" * 64


@pytest.fixture(autouse=True)
def reset_config_singleton():
    Config._instances = {}
    yield
    Config._instances = {}


@pytest.fixture
def model_scan():
    client = ModelScan(api_key=TEST_API_KEY, request_handler=MagicMock())
    client.make_request = MagicMock()
    return client


def multipart_create_response(part_size_bytes=4):
    return CreateScanObjectResponse(
        object_id="object-id",
        multipart_upload=MultipartUpload(
            upload_id="upload-id",
            part_size_bytes=part_size_bytes,
        ),
    )


def part_urls(part_numbers, suffix=""):
    return GetMultipartUploadPartUrlsResponse(
        parts=[
            MultipartUploadPartUrl(
                part_number=part_number,
                upload_url=(
                    f"https://bucket.s3.us-west-2.amazonaws.com/object"
                    f"?partNumber={part_number}{suffix}"
                ),
            )
            for part_number in part_numbers
        ]
    )


def test_create_multipart_scan_object_opts_in(model_scan):
    model_scan.make_request.return_value = {
        "object_id": "object-id",
        "multipart_upload": {
            "upload_id": "upload-id",
            "part_size_bytes": "67108864",
        },
    }

    response = model_scan.create_multipart_scan_object(
        "scan-id", CreateScanObjectRequest(file_name="model.pkl", size=10)
    )

    assert response.multipart_upload.part_size_bytes == 67_108_864
    model_scan.make_request.assert_called_once_with(
        method=HttpMethod.POST,
        path="scans/scan-id/objects",
        data={
            "file_name": "model.pkl",
            "size": 10,
            "use_multipart_upload": True,
        },
    )


def test_upload_file_requests_urls_in_32_part_batches_and_completes(
    model_scan, tmp_path
):
    file_path = tmp_path / "model.safetensors"
    file_path.write_bytes(b"x" * 33)
    model_scan.create_multipart_scan_object = MagicMock(
        return_value=multipart_create_response(part_size_bytes=1)
    )
    model_scan.get_multipart_upload_part_urls = MagicMock(
        side_effect=lambda _scan_id, _object_id, request: part_urls(
            request.part_numbers
        )
    )
    model_scan._upload_multipart_part = MagicMock(
        side_effect=lambda _path, part_number, *_args, **_kwargs: f'"etag-{part_number}"'
    )
    model_scan.complete_multipart_upload = MagicMock()
    model_scan.abort_multipart_upload = MagicMock()

    assert model_scan.upload_file(file_path=file_path, scan_id="scan-id") is True

    requested_batches = [
        invocation.args[2].part_numbers
        for invocation in model_scan.get_multipart_upload_part_urls.call_args_list
    ]
    assert requested_batches == [list(range(1, 33)), [33]]
    complete_request = model_scan.complete_multipart_upload.call_args.args[2]
    assert [part.part_number for part in complete_request.parts] == list(range(1, 34))
    assert [part.etag for part in complete_request.parts] == [
        f'"etag-{part_number}"' for part_number in range(1, 34)
    ]
    model_scan.abort_multipart_upload.assert_not_called()


def test_upload_file_prefetches_next_url_batch_before_current_batch_drains(
    model_scan, tmp_path
):
    file_path = tmp_path / "model.safetensors"
    file_path.write_bytes(b"x" * 65)
    first_part_started = Event()
    release_first_part = Event()
    second_batch_requested = Event()
    third_batch_requested = Event()
    model_scan.create_multipart_scan_object = MagicMock(
        return_value=multipart_create_response(part_size_bytes=1)
    )

    def get_part_urls(_scan_id, _object_id, request):
        if request.part_numbers == list(range(33, 65)):
            second_batch_requested.set()
        elif request.part_numbers == [65]:
            third_batch_requested.set()
        return part_urls(request.part_numbers)

    def upload_part(_path, part_number, *_args, **_kwargs):
        if part_number == 1:
            first_part_started.set()
            release_first_part.wait(timeout=10)
        return f'"etag-{part_number}"'

    model_scan.get_multipart_upload_part_urls = MagicMock(side_effect=get_part_urls)
    model_scan._upload_multipart_part = MagicMock(side_effect=upload_part)
    model_scan.complete_multipart_upload = MagicMock()

    with ThreadPoolExecutor(max_workers=1) as caller:
        result = caller.submit(
            model_scan.upload_file,
            "scan-id",
            file_path,
            max_concurrency=1,
            show_progress=False,
        )
        assert first_part_started.wait(timeout=5)
        try:
            assert second_batch_requested.wait(timeout=5)
            assert third_batch_requested.wait(timeout=0.2) is False
        finally:
            release_first_part.set()

        assert result.result(timeout=10) is True


def test_upload_file_reports_successfully_uploaded_bytes(model_scan, tmp_path):
    file_path = tmp_path / "model.safetensors"
    file_path.write_bytes(b"x" * 10)
    model_scan.create_multipart_scan_object = MagicMock(
        return_value=multipart_create_response(part_size_bytes=4)
    )
    model_scan.get_multipart_upload_part_urls = MagicMock(
        side_effect=lambda _scan_id, _object_id, request: part_urls(
            request.part_numbers
        )
    )
    model_scan._upload_multipart_part = MagicMock(
        side_effect=lambda _path, part_number, *_args, **_kwargs: f'"etag-{part_number}"'
    )
    progress_updates = []

    assert (
        model_scan.upload_file(
            "scan-id",
            file_path,
            show_progress=False,
            progress_callback=lambda uploaded, total: progress_updates.append(
                (uploaded, total)
            ),
        )
        is True
    )

    assert progress_updates[0] == (0, 10)
    assert progress_updates[-1] == (10, 10)
    assert [uploaded for uploaded, _ in progress_updates] == sorted(
        uploaded for uploaded, _ in progress_updates
    )


def test_console_upload_progress_renders_bar(capsys):
    progress = _ConsoleUploadProgress(width=10)

    progress(5, 10)
    progress(10, 10)

    output = capsys.readouterr().err
    assert "50.0%" in output
    assert "100.0%" in output
    assert "[##########]" in output


def test_console_status_spinner_renders_waiting_message(capsys):
    spinner = _ConsoleStatusSpinner()

    with patch("aidefense.modelscan.model_scan.sleep") as mock_sleep:
        spinner.wait(0.2)
    spinner.close()

    output = capsys.readouterr().err
    assert "Upload complete. Waiting for scan status" in output
    assert mock_sleep.call_count == 2


def test_default_scan_timeout_is_ten_minutes():
    assert RETRY_COUNT_FOR_SCANNING == 120
    assert WAIT_TIME_SECS_SUCCESSIVE_SCAN_INFO_CHECK == 5
    assert DEFAULT_SCAN_TIMEOUT_SECONDS == 10 * 60


def test_upload_file_refreshes_expired_part_url(model_scan, tmp_path):
    file_path = tmp_path / "model.pkl"
    file_path.write_bytes(b"data")
    model_scan.create_multipart_scan_object = MagicMock(
        return_value=multipart_create_response(part_size_bytes=4)
    )
    model_scan.get_multipart_upload_part_urls = MagicMock(
        side_effect=[part_urls([1]), part_urls([1], suffix="&refreshed=true")]
    )
    expired_response = requests.Response()
    expired_response.status_code = 403
    expired_response._content = b"<Code>ExpiredToken</Code>"
    expired_error = requests.HTTPError(response=expired_response)
    model_scan._upload_multipart_part = MagicMock(
        side_effect=[expired_error, '"etag-1"']
    )
    model_scan.complete_multipart_upload = MagicMock()

    with patch("aidefense.modelscan.model_scan_base.sleep") as mock_sleep:
        assert model_scan.upload_file("scan-id", file_path) is True

    assert model_scan.get_multipart_upload_part_urls.call_count == 2
    refreshed_request = model_scan.get_multipart_upload_part_urls.call_args_list[
        1
    ].args[2]
    assert refreshed_request.part_numbers == [1]
    mock_sleep.assert_called_once_with(0.5)


def test_upload_file_aborts_when_a_part_fails(model_scan, tmp_path):
    file_path = tmp_path / "model.pkl"
    file_path.write_bytes(b"data")
    model_scan.create_multipart_scan_object = MagicMock(
        return_value=multipart_create_response(part_size_bytes=4)
    )
    model_scan.get_multipart_upload_part_urls = MagicMock(return_value=part_urls([1]))
    model_scan._upload_multipart_part = MagicMock(side_effect=SDKError("upload failed"))
    model_scan.abort_multipart_upload = MagicMock()

    with pytest.raises(SDKError, match="Multipart upload part 1 failed"):
        model_scan.upload_file("scan-id", file_path)

    abort_request = model_scan.abort_multipart_upload.call_args.args[2]
    assert abort_request.upload_id == "upload-id"


def test_upload_part_streams_only_the_requested_file_range(model_scan, tmp_path):
    file_path = tmp_path / "model.pkl"
    file_path.write_bytes(b"0123456789")
    response = MagicMock(status_code=200, headers={"ETag": '"etag-2"'})

    def fake_put(url, data, headers, timeout, allow_redirects):
        assert url.startswith("https://bucket.s3.us-west-2.amazonaws.com/")
        assert data.read() == b"4567"
        assert headers == {
            "Content-Length": "4",
            "Content-Type": "application/octet-stream",
        }
        assert timeout == model_scan.config.timeout
        assert allow_redirects is False
        return response

    with patch("aidefense.modelscan.model_scan_base.requests.put", fake_put):
        etag = model_scan._upload_multipart_part(
            file_path,
            part_number=2,
            part_size_bytes=4,
            file_size=10,
            upload_url=(
                "https://bucket.s3.us-west-2.amazonaws.com/object" "?partNumber=2"
            ),
        )

    assert etag == '"etag-2"'


def test_bounded_file_reader_supports_requests_length_probing(tmp_path):
    file_path = tmp_path / "model.bin"
    file_path.write_bytes(b"abcdefghij")

    with _BoundedFileReader(file_path, offset=2, length=5) as reader:
        assert len(reader) == 5
        assert reader.read(2) == b"cd"
        assert reader.tell() == 2
        assert reader.seek(0) == 0
        assert reader.read() == b"cdefg"
        assert reader.read() == b""


@pytest.mark.parametrize("max_concurrency", [0, 33, True, 1.5])
def test_upload_file_rejects_invalid_concurrency(model_scan, tmp_path, max_concurrency):
    file_path = tmp_path / "model.pkl"
    file_path.write_bytes(b"data")

    with pytest.raises(ValueError, match="max_concurrency"):
        model_scan.upload_file("scan-id", file_path, max_concurrency=max_concurrency)


def test_upload_part_rejects_non_s3_presigned_url(model_scan, tmp_path):
    file_path = tmp_path / "model.pkl"
    file_path.write_bytes(b"data")

    with pytest.raises(SDKError, match="invalid multipart upload URL"):
        model_scan._upload_multipart_part(
            file_path,
            part_number=1,
            part_size_bytes=4,
            file_size=4,
            upload_url="https://attacker.example/upload",
        )


def test_empty_file_is_rejected_before_scan_object_creation(model_scan, tmp_path):
    file_path = tmp_path / "empty.pkl"
    file_path.touch()

    with pytest.raises(ValueError, match="must not be empty"):
        model_scan.upload_file("scan-id", file_path)


def test_multipart_upload_defers_file_size_limit_to_service(model_scan, tmp_path):
    file_path = tmp_path / "large-model.safetensors"
    with file_path.open("wb") as model_file:
        model_file.truncate(MAX_FILE_SIZE_BYTES + 1)
    model_scan._upload_file_multipart = MagicMock(return_value=True)

    assert model_scan.upload_file("scan-id", file_path, show_progress=False) is True

    model_scan._upload_file_multipart.assert_called_once()


def test_legacy_upload_retains_client_side_file_size_limit(model_scan, tmp_path):
    file_path = tmp_path / "large-model.safetensors"
    with file_path.open("wb") as model_file:
        model_file.truncate(MAX_FILE_SIZE_BYTES + 1)
    model_scan.create_scan_object = MagicMock()

    with pytest.raises(ValueError, match="File size exceeds limit"):
        model_scan.upload_file(
            "scan-id",
            file_path,
            use_multipart_upload=False,
            show_progress=False,
        )

    model_scan.create_scan_object.assert_not_called()


def test_legacy_single_part_upload_remains_available(model_scan, tmp_path):
    file_path = tmp_path / "model.pkl"
    file_path.write_bytes(b"data")
    model_scan.create_scan_object = MagicMock(
        return_value=(
            "object-id",
            "https://bucket.s3.us-west-2.amazonaws.com/object?signature=test",
        )
    )
    response = MagicMock()

    with patch(
        "aidefense.modelscan.model_scan_base.requests.request",
        return_value=response,
    ) as mock_request:
        assert (
            model_scan.upload_file("scan-id", file_path, use_multipart_upload=False)
            is True
        )

    assert mock_request.call_args.kwargs["method"] == HttpMethod.PUT
    response.raise_for_status.assert_called_once_with()


def test_scan_file_uses_multipart_upload_and_forwards_concurrency(tmp_path):
    file_path = tmp_path / "model.pkl"
    file_path.write_bytes(b"data")
    client = ModelScanClient(api_key=TEST_API_KEY, request_handler=MagicMock())
    client.register_scan = MagicMock(return_value=MagicMock(scan_id="scan-id"))
    client.upload_file = MagicMock(return_value=True)
    client.trigger_scan = MagicMock()
    expected_scan_info = MagicMock()
    client._ModelScanClient__get_scan_info_wait_until_status = MagicMock(
        return_value=expected_scan_info
    )

    progress_callback = MagicMock()
    result = client.scan_file(
        file_path,
        max_concurrency=4,
        show_progress=False,
        progress_callback=progress_callback,
        show_status_spinner=False,
        scan_timeout_seconds=600,
    )

    assert result is expected_scan_info
    client.upload_file.assert_called_once_with(
        "scan-id",
        file_path,
        use_multipart_upload=True,
        max_concurrency=4,
        show_progress=False,
        progress_callback=progress_callback,
    )
    client.trigger_scan.assert_called_once_with("scan-id")
    wait_call = client._ModelScanClient__get_scan_info_wait_until_status.call_args
    assert wait_call.kwargs["timeout_seconds"] == 600
    assert wait_call.kwargs["show_spinner"] is False


def test_scan_file_defers_file_size_limit_to_multipart_service(tmp_path):
    file_path = tmp_path / "large-model.safetensors"
    with file_path.open("wb") as model_file:
        model_file.truncate(MAX_FILE_SIZE_BYTES + 1)
    client = ModelScanClient(api_key=TEST_API_KEY, request_handler=MagicMock())
    client.register_scan = MagicMock(return_value=MagicMock(scan_id="scan-id"))
    client.upload_file = MagicMock(return_value=True)
    client.trigger_scan = MagicMock()
    expected_scan_info = MagicMock()
    client._ModelScanClient__get_scan_info_wait_until_status = MagicMock(
        return_value=expected_scan_info
    )

    result = client.scan_file(
        file_path,
        show_progress=False,
        show_status_spinner=False,
    )

    assert result is expected_scan_info
    client.register_scan.assert_called_once_with()
    client.upload_file.assert_called_once_with(
        "scan-id",
        file_path,
        use_multipart_upload=True,
        max_concurrency=10,
        show_progress=False,
        progress_callback=None,
    )


def test_scan_timeout_preserves_scan_and_explains_status_retrieval(tmp_path):
    file_path = tmp_path / "model.pkl"
    file_path.write_bytes(b"data")
    client = ModelScanClient(api_key=TEST_API_KEY, request_handler=MagicMock())
    client.register_scan = MagicMock(return_value=MagicMock(scan_id="scan-id"))
    client.upload_file = MagicMock(return_value=True)
    client.trigger_scan = MagicMock()
    client.get_scan = MagicMock(
        return_value=MagicMock(scan_status_info=MagicMock(status="IN_PROGRESS"))
    )
    client.cleanup_scan_data = MagicMock()

    with patch("aidefense.modelscan.model_scan.monotonic", side_effect=[0.0, 2.0]):
        with pytest.raises(ScanTimeoutError) as error_info:
            client.scan_file(
                file_path,
                show_progress=False,
                show_status_spinner=False,
                scan_timeout_seconds=1,
            )

    assert error_info.value.scan_id == "scan-id"
    assert error_info.value.timeout_seconds == 1
    assert 'client.get_scan("scan-id", GetScanStatusRequest())' in str(error_info.value)
    client.cleanup_scan_data.assert_not_called()
