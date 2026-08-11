"""Unit tests for Incident Router — covers acceptance criteria #1, #13."""
import pytest
from detection.watcher import IncidentEvent
from agent.incident_router import IncidentRouter, IncidentType
from datetime import datetime

def make_event(reason: str) -> IncidentEvent:
    return IncidentEvent(
        event_type="ADDED",
        reason=reason,
        message="test",
        pod_name="test-pod-abc",
        namespace="default",
        node_name="node-1",
        cluster_id="test-cluster",
        timestamp=datetime.utcnow(),
        raw_event={}
    )

def test_crash_loop_classified_correctly():
    """CrashLoopBackOff → POD_CRASH."""
    router = IncidentRouter()
    result = router.classify(make_event("CrashLoopBackOff"))
    assert result == IncidentType.POD_CRASH

def test_oom_classified_correctly():
    """OOMKilled → OOM_KILLED."""
    router = IncidentRouter()
    result = router.classify(make_event("OOMKilled"))
    assert result == IncidentType.OOM_KILLED

def test_image_pull_classified_correctly():
    """ImagePullBackOff → IMAGE_PULL_ERROR."""
    router = IncidentRouter()
    result = router.classify(make_event("ImagePullBackOff"))
    assert result == IncidentType.IMAGE_PULL_ERROR

def test_unknown_event_returns_unknown():
    """Criteria #13: Unknown reason → UNKNOWN type."""
    router = IncidentRouter()
    result = router.classify(make_event("SomeRandomReason"))
    assert result == IncidentType.UNKNOWN

def test_route_returns_playbook_path():
    """Route returns correct playbook file path."""
    router = IncidentRouter()
    path = router.route(IncidentType.POD_CRASH)
    assert "pod_crash" in path
