"""Shared test fixtures and helpers."""
import pytest
from infrastructure.evidence_collector import collect_evidence

@pytest.fixture
def sample_evidence():
    # Mock collect_evidence response
    return {
        "pod_name": "api-server-7d9f-xkq2p",
        "namespace": "production",
        "logs": "Error: cannot start application\\nExit code 1",
        "events": [{"reason": "BackOff", "message": "Back-off restarting failed container", "count": 5, "type": "Warning"}],
        "describe": "Status: Pending\\nRestart Count: 5",
        "reason": "CrashLoopBackOff",
        "exit_code": 1
    }

@pytest.fixture
def oom_evidence():
    return {
        "pod_name": "memory-heavy-pod",
        "namespace": "default",
        "logs": "Killed\\n",
        "events": [{"reason": "OOMKilled", "message": "Container exceeded memory limit", "count": 1, "type": "Warning"}],
        "describe": "OOMKilled",
        "reason": "OOMKilled",
        "exit_code": 137
    }

