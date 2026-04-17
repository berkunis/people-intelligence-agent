"""Prometheus metrics. Every agent call updates these counters/histograms.

Design: the CLI is short-lived (one query per invocation), so we push metrics
to a Pushgateway at the end of each run instead of hosting a scrape target.
If PIA_PUSHGATEWAY_URL is unset, metrics are still recorded in-memory and a
textual dump is logged — useful for tests.

The dashboards in infra/grafana/dashboards/ read these exact metric names.
"""

from __future__ import annotations

import logging
import os

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Histogram,
    pushadd_to_gateway,
)

logger = logging.getLogger(__name__)

REGISTRY = CollectorRegistry()

# Counters
agent_queries_total = Counter(
    "pia_agent_queries_total",
    "Total agent questions answered.",
    labelnames=("role", "model", "outcome"),
    registry=REGISTRY,
)
agent_tool_calls_total = Counter(
    "pia_agent_tool_calls_total",
    "Tool invocations by name and outcome.",
    labelnames=("tool", "outcome"),
    registry=REGISTRY,
)
agent_refusals_total = Counter(
    "pia_agent_refusals_total",
    "Refusals by reason (rbac, k_anonymity, bytes_budget, ...).",
    labelnames=("reason",),
    registry=REGISTRY,
)
agent_tokens_total = Counter(
    "pia_agent_tokens_total",
    "Tokens consumed (input+output).",
    labelnames=("direction",),  # in | out
    registry=REGISTRY,
)
agent_cost_usd_total = Counter(
    "pia_agent_cost_usd_total",
    "Cumulative $ spent on LLM calls.",
    labelnames=("model",),
    registry=REGISTRY,
)

# Histograms
agent_latency_seconds = Histogram(
    "pia_agent_latency_seconds",
    "End-to-end agent latency per question.",
    buckets=(1, 2, 5, 10, 15, 20, 30, 60, 120),
    labelnames=("role",),
    registry=REGISTRY,
)
agent_tool_calls_per_query = Histogram(
    "pia_agent_tool_calls_per_query",
    "Tool-call count per question.",
    buckets=(1, 2, 3, 5, 8, 12),
    labelnames=("role",),
    registry=REGISTRY,
)

def push_to_gateway() -> None:
    """Push current registry to Pushgateway. Silent no-op if not configured."""
    url = os.getenv("PIA_PUSHGATEWAY_URL", "http://localhost:9091")
    if not url:
        return
    try:
        pushadd_to_gateway(url, job="pia-agent", registry=REGISTRY)
    except Exception as e:  # noqa: BLE001
        logger.warning("pushgateway push failed (%s): %s", url, e)
