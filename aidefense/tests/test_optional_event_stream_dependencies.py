# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path
import subprocess
import sys

from aidefense.exceptions import SDKError
from aidefense.runtime.event_stream import EventStreamError


def test_event_stream_errors_use_the_sdk_error_hierarchy():
    assert issubclass(EventStreamError, SDKError)


def test_base_sdk_import_does_not_require_streaming_dependencies():
    package_root = Path(__file__).resolve().parents[2]
    script = (
        "import builtins\n"
        "original = builtins.__import__\n"
        "def blocked(name, *args, **kwargs):\n"
        "    if name == 'grpc' or name.startswith('google.protobuf'):\n"
        "        raise ModuleNotFoundError(name)\n"
        "    return original(name, *args, **kwargs)\n"
        "builtins.__import__ = blocked\n"
        "import aidefense\n"
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(package_root)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=package_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
