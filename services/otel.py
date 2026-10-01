"""Small OpenTelemetry boundary for the MyOTA HTTP services.

The application keeps its Prometheus-compatible business metrics because they
are useful during a collector outage.  Request traces and OTLP metrics are
exported asynchronously when the OpenTelemetry SDK is installed and enabled.
Telemetry is deliberately best-effort: a collector outage must not take an
API endpoint down.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class _Request:
    telemetry: "Telemetry"
    method: str
    path: str
    started: float
    span: Any = None
    finished: bool = False

    def finish(self, status: int, route: str | None = None) -> None:
        if self.finished:
            return
        self.finished = True
        duration_ms = (time.perf_counter() - self.started) * 1000
        attrs = {"http.request.method": self.method, "http.route": route or self.path,
                 "http.response.status_code": status}
        try:
            self.telemetry.requests.add(1, attrs)
            self.telemetry.duration.record(duration_ms, attrs)
            if self.span:
                self.span.set_attribute("http.request.method", self.method)
                self.span.set_attribute("url.path", self.path)
                self.span.set_attribute("http.route", route or self.path)
                self.span.set_attribute("http.response.status_code", status)
                self.span.end()
        except Exception:
            # Exporters run outside the request's correctness path.
            return


class Telemetry:
    def __init__(self, service_name: str, tracer: Any = None, meter: Any = None) -> None:
        self.service_name = service_name
        self.tracer = tracer
        self.requests = meter.create_counter("myota.http.server.requests", unit="{request}") if meter else _NoopInstrument()
        self.duration = meter.create_histogram("myota.http.server.duration", unit="ms") if meter else _NoopInstrument()

    def start_request(self, method: str, path: str) -> _Request:
        span = None
        if self.tracer:
            try:
                span = self.tracer.start_span(f"{method} {path}")
            except Exception:
                span = None
        return _Request(self, method, path, time.perf_counter(), span)


class _NoopInstrument:
    def add(self, *_: Any, **__: Any) -> None:
        return

    def record(self, *_: Any, **__: Any) -> None:
        return


_lock = threading.Lock()
_telemetry: dict[str, Telemetry] = {}
_disabled = {"", "0", "false", "no", "off"}


def telemetry_for(service_name: str) -> Telemetry:
    with _lock:
        if service_name in _telemetry:
            return _telemetry[service_name]
        if os.environ.get("MYOTA_OTEL_ENABLED", "0").strip().lower() in _disabled:
            value = Telemetry(service_name)
            _telemetry[service_name] = value
            return value
        try:
            from opentelemetry import metrics, trace
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
            resource = Resource.create({
                "service.name": service_name,
                "service.namespace": os.environ.get("OTEL_SERVICE_NAMESPACE", "myota"),
                "deployment.environment": os.environ.get("MYOTA_ENV", "development"),
            })
            tracer_provider = TracerProvider(resource=resource)
            tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=not endpoint.startswith("https://"))))
            trace.set_tracer_provider(tracer_provider)
            metric_reader = PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=endpoint, insecure=not endpoint.startswith("https://")),
                export_interval_millis=int(os.environ.get("MYOTA_OTEL_METRIC_INTERVAL_MS", "15000")),
            )
            metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))
            value = Telemetry(service_name, trace.get_tracer("myota.http"), metrics.get_meter("myota.http"))
        except Exception:
            # This also covers local unit tests that intentionally omit the SDK.
            value = Telemetry(service_name)
        _telemetry[service_name] = value
        return value
