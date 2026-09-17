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
