# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

import logging
from contextlib import contextmanager

import pytest

from aidefense.runtime.event_stream import (
    EventStreamClient,
    ReasonCode,
    StreamConfigurationError,
    StreamObserver,
)
from aidefense.config import Config


class Metrics:
    def __init__(self):
        self.events = []
        self.active = []
        self.latencies = []

    def record(self, reason, attributes):
        self.events.append((reason, attributes))

    def active_streams(self, delta):
        self.active.append(delta)

    def latency(self, seconds, outcome):
        self.latencies.append((seconds, outcome))


class Tracer:
    def __init__(self):
        self.spans = []

    @contextmanager
    def start_as_current_span(self, name, attributes):
        self.spans.append((name, attributes))
        yield


def test_configuration_failure_has_stable_metric_and_no_secret(monkeypatch, caplog):
    metrics = Metrics()
    tracer = Tracer()
    observer = StreamObserver(metrics=metrics, tracer=tracer)
    monkeypatch.setenv("AI_DEFENSE_EVENT_STREAM_ENDPOINT", "localhost:443")
    monkeypatch.delenv("AI_DEFENSE_EVENT_STREAM_API_KEY", raising=False)
    monkeypatch.delenv("AI_DEFENSE_API_MODE_LLM_API_KEY", raising=False)

    with caplog.at_level(logging.ERROR), pytest.raises(StreamConfigurationError):
        EventStreamClient.from_env(observer=observer)

    assert metrics.events == [(ReasonCode.CONFIGURATION_INVALID.value, {})]
    assert "api_key" not in caplog.text


def test_observer_failures_never_change_inspection_control_flow():
    class BrokenMetrics:
        def record(self, *_):
            raise RuntimeError("metrics unavailable")

        def active_streams(self, *_):
            raise RuntimeError("metrics unavailable")

        def latency(self, *_):
            raise RuntimeError("metrics unavailable")

    observer = StreamObserver(metrics=BrokenMetrics())
    observer.event(ReasonCode.STREAM_STARTED, attributes={"sequence": 1})
    observer.active_streams(1)
    observer.latency(0.1, "completed")


def test_debug_lifecycle_records_do_not_change_metric_volume(caplog):
    logger = logging.getLogger("aidefense-test-debug-lifecycle")
    logger.setLevel(logging.DEBUG)
    metrics = Metrics()
    observer = StreamObserver(logger=logger, metrics=metrics)

    with caplog.at_level(logging.DEBUG, logger=logger.name):
        observer.debug(
            ReasonCode.RESULT_PARSED,
            attributes={
                "stream_correlation_id": "sdk-generated",
                "through_sequence": 4,
                "sequence_count": 3,
            },
        )
        observer.debug(
            ReasonCode.CLEANUP_COMPLETED,
            attributes={
                "stream_correlation_id": "sdk-generated",
                "outcome": "completed",
            },
        )

    assert ReasonCode.RESULT_PARSED.value in caplog.text
    assert ReasonCode.CLEANUP_COMPLETED.value in caplog.text
    assert metrics.events == []


def test_shared_config_supplies_logger_tracer_and_metrics(caplog):
    Config._instances = {}
    logger = logging.getLogger("aidefense-test-event-stream")
    logger.setLevel(logging.DEBUG)
    metrics = Metrics()
    tracer = Tracer()
    try:
        config = Config(
            runtime_base_url="https://inspect.example",
            logger=logger,
            tracer=tracer,
            metrics=metrics,
        )

        with caplog.at_level(logging.DEBUG, logger=logger.name):
            client = EventStreamClient(api_key="secret", config=config)
            client.observer.event(
                ReasonCode.STREAM_STARTED,
                attributes={"stream_correlation_id": "sdk-generated"},
            )
            with client.observer.span(
                "aidefense.stream.test", {"stream_correlation_id": "sdk-generated"}
            ):
                pass

        assert ReasonCode.STREAM_CONFIGURED.value in caplog.text
        assert ReasonCode.STREAM_STARTED.value in caplog.text
        assert metrics.events == [
            (
                ReasonCode.STREAM_STARTED.value,
                {"stream_correlation_id": "sdk-generated"},
            )
        ]
        assert tracer.spans == [
            (
                "aidefense.stream.test",
                {"stream_correlation_id": "sdk-generated"},
            )
        ]
        assert "secret" not in caplog.text
    finally:
        Config._instances = {}
