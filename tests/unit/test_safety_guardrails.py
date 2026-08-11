"""Unit tests for Safety Guardrails — covers acceptance criteria #5, #14."""
import pytest
from agent.safety_guardrails import SafetyGate, BLOCKED, WHITELIST

def test_blocked_action_always_rejected():
    """Criteria #5: delete_namespace is ALWAYS rejected."""
    gate = SafetyGate()
    for action in BLOCKED:
        result = gate.validate(action)
        assert not result.approved
        assert result.reason == "PERMANENTLY_BLOCKED"

def test_whitelisted_action_requires_approval():
    """All whitelisted actions must require engineer approval."""
    gate = SafetyGate()
    for action in ["restart_pod", "scale_deployment", "rollback_deployment", "increase_limits"]:
        result = gate.validate(action)
        assert result.approved
        assert result.requires_human

def test_unknown_action_rejected():
    """Actions not in whitelist are rejected."""
    gate = SafetyGate()
    result = gate.validate("some_unknown_action")
    assert not result.approved
    assert result.reason == "NOT_IN_WHITELIST"

def test_rate_limit_enforcement():
    """Criteria #14: 11th restart_pod in one hour is rejected."""
    gate = SafetyGate()
    for _ in range(10):
        r = gate.validate("restart_pod")
        assert r.approved
        gate.record_execution("restart_pod")
    # 11th attempt
    r = gate.validate("restart_pod")
    assert not r.approved
    assert r.reason == "ACTION_RATE_LIMIT_EXCEEDED"

def test_manual_review_no_approval_needed():
    """manual_review does not require human approval."""
    gate = SafetyGate()
    result = gate.validate("manual_review")
    assert result.approved
    assert not result.requires_human
