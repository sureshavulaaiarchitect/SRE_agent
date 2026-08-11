"""Unit tests for Pattern Detection Layer — covers acceptance criteria #2."""
import pytest
from agent.pattern_layer import PatternDetectionLayer

def make_evidence(**kwargs):
    defaults = dict(
        pod_name="test-pod", namespace="default",
        phase="Running",
        logs="", events=[], describe="", reason="unknown",
        exit_code=None, 
        image="nginx:latest", 
        memory_limit=None
    )
    defaults.update(kwargs)
    return defaults

def test_exit_code_1_crash_pattern():
    """Criteria #2: exit_code=1 + restart_count≥3 → fast path, no LLM."""
    layer = PatternDetectionLayer()
    ev = make_evidence(exit_code=1)
    match = layer.check(ev)
    assert match is not None
    assert match.recommended_action == "restart_pod"
    assert match.confidence == "high"

def test_oom_pattern_from_reason():
    """Test new rule engine OOMKilled."""
    layer = PatternDetectionLayer()
    ev = make_evidence(reason="OOMKilled", exit_code=137, memory_limit="256Mi")
    match = layer.check(ev)
    assert match is not None
    assert "Container killed due to memory limit" in match.root_cause
    assert match.recommended_action == "scale"

def test_crashloop_pattern_from_reason():
    layer = PatternDetectionLayer()
    ev = make_evidence(reason="CrashLoopBackOff")
    match = layer.check(ev)
    assert match is not None
    assert "crashing repeatedly" in match.root_cause
    assert match.recommended_action == "restart_pod"

def test_imagepull_pattern_from_reason():
    layer = PatternDetectionLayer()
    ev = make_evidence(reason="ImagePullBackOff")
    match = layer.check(ev)
    assert match is not None
    assert "Invalid or missing container image" in match.root_cause

def test_no_match_returns_none():
    """Criteria #2: No matching pattern → returns None (go to AI engine)."""
    layer = PatternDetectionLayer()
    ev = make_evidence(exit_code=0)
    match = layer.check(ev)
    assert match is None

