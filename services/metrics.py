"""Small dependency-free Prometheus registry for local and Kubernetes probes."""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Mapping


def _labels(labels: Mapping[str, object]) -> str:
    if not labels:
        return ""
    escaped = []
    for key in sorted(labels):
        value = str(labels[key]).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        escaped.append(f'{key}="{value}"')
    return "{" + ",".join(escaped) + "}"


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counters: defaultdict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}

    def inc(self, name: str, labels: Mapping[str, object] | None = None, value: float = 1) -> None:
        key = (name, tuple(sorted((str(k), str(v)) for k, v in (labels or {}).items())))
        with self._lock:
            self._counters[key] += value

    def set_gauge(self, name: str, value: float, labels: Mapping[str, object] | None = None) -> None:
        key = (name, tuple(sorted((str(k), str(v)) for k, v in (labels or {}).items())))
        with self._lock:
            self._gauges[key] = value

    def render(self, extra: Mapping[str, float] | None = None) -> str:
        lines: list[str] = []
        with self._lock:
            values = [(name, dict(labels), value) for (name, labels), value in self._counters.items()]
            values += [(name, dict(labels), value) for (name, labels), value in self._gauges.items()]
        for name, labels, value in sorted(values, key=lambda item: (item[0], sorted(item[1].items()))):
            lines.append(f"{name}{_labels(labels)} {value:g}")
        for name, value in sorted((extra or {}).items()):
            lines.append(f"{name} {float(value):g}")
        return "\n".join(lines) + "\n"


METRICS = MetricsRegistry()
