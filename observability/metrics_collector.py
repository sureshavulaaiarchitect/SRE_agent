from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
    CollectorRegistry
)
from fastapi import APIRouter
from fastapi.responses import Response

# Use custom registry (important for production / multi-process safety)
registry = CollectorRegistry()

router = APIRouter(tags=["observability"])

# ==============================
# COUNTERS (events)
# ==============================

incidents_detected_total = Counter(
    "sre_incidents_detected_total",
    "Total incidents detected",
    ["cluster_id", "incident_type"],
    registry=registry
)

incidents_resolved_total = Counter(
    "sre_incidents_resolved_total",
    "Total incidents resolved",
    ["cluster_id", "incident_type", "action"],
    registry=registry
)

remediation_actions_total = Counter(
    "sre_remediation_actions_total",
    "Total remediation actions attempted",
    ["action", "result"],  # result = success / failed
    registry=registry
)

safety_gate_blocked_total = Counter(
    "sre_safety_gate_blocked_total",
    "Total actions blocked by safety gate",
    ["action", "reason"],
    registry=registry
)

# ==============================
# HISTOGRAMS (latency)
# ==============================

investigation_time_seconds = Histogram(
    "sre_investigation_time_seconds",
    "Full investigation pipeline latency",
    ["cluster_id", "incident_type"],
    registry=registry,
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30)
)

mttr_seconds = Histogram(
    "sre_mttr_seconds",
    "Mean time to recovery (seconds)",
    ["cluster_id", "incident_type"],
    registry=registry,
    buckets=(5, 10, 30, 60, 120, 300, 600)
)

ai_response_latency = Histogram(
    "sre_ai_response_latency_seconds",
    "AI root cause analysis latency",
    ["backend"],
    registry=registry,
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30)
)

# ==============================
# GAUGES (state)
# ==============================

active_incidents = Gauge(
    "sre_active_incidents",
    "Currently active/open incidents",
    ["cluster_id"],
    registry=registry
)

websocket_active_connections = Gauge(
    "sre_websocket_active_connections",
    "Number of active WebSocket connections",
    registry=registry
)

circuit_breaker_state = Gauge(
    "sre_circuit_breaker_state",
    "State of the AI circuit breaker (1=CLOSED, 0=OPEN/HALF-OPEN)",
    ["backend"],
    registry=registry
)

ollama_failures_total = Counter(
    "sre_ollama_failures_total",
    "Total number of Ollama API failures",
    ["reason"],
    registry=registry
)

# This is optional — only useful if you compute it manually
remediation_success_rate = Gauge(
    "sre_remediation_success_rate",
    "Remediation success ratio",
    ["cluster_id"],
    registry=registry
)

errors_total = Counter(
    "sre_errors_total",
    "Total errors in the system",
    ["module", "error_type"],
    registry=registry
)

ai_used_total = Counter(
    "sre_ai_used_total",
    "AI engine usage tracking",
    ["used", "reason"],
    registry=registry
)

# ==============================
# METRICS ENDPOINT
# ==============================

@router.get("/metrics")
async def metrics():
    """
    Prometheus scrape endpoint
    Example: http://localhost:8080/metrics
    """
    try:
        data = generate_latest(registry)
        return Response(
            data,
            media_type=CONTENT_TYPE_LATEST
        )
    except Exception as e:
        from fastapi import HTTPException
        # Return empty metrics if registry fails
        return Response(
            b"",
            media_type=CONTENT_TYPE_LATEST
        )