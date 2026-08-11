import pytest
from agent.decision_engine import RemediationDecisionEngine
from agent.pattern_layer import PatternMatch
from ai.root_cause_engine import RootCauseResult

def test_decision_engine_prioritizes_high_confidence_rule():
    engine = RemediationDecisionEngine()
    pattern = PatternMatch(
        root_cause="oom_killed",
        recommended_action="scale_deployment",
        confidence="high",
        confidence_score=0.9
    )
    ai = RootCauseResult(
        root_cause="cpu_spike",
        confidence="medium",
        recommended_action="restart_pod",
        explanation="AI thinks it's CPU"
    )
    
    # Pattern is high confidence, so it should win
    action = engine.decide("oom", pattern, ai)
    assert action == "scale_deployment"

def test_decision_engine_uses_ai_when_rule_is_low_confidence():
    engine = RemediationDecisionEngine()
    pattern = PatternMatch(
        root_cause="unknown",
        recommended_action="manual_investigation",
        confidence="low",
        confidence_score=0.2
    )
    ai = RootCauseResult(
        root_cause="image_pull_error",
        confidence="high",
        recommended_action="rollback_deployment",
        explanation="AI found image issue"
    )
    
    # Rule is low, AI is good
    action = engine.decide("unknown", pattern, ai)
    assert action == "rollback_deployment"

def test_decision_engine_fallback_to_keywords():
    engine = RemediationDecisionEngine()
    
    # No rule, no AI
    action = engine.decide("Memory usage exceeded limit", None, None)
    assert action == "scale_deployment"
    
    action = engine.decide("CrashLoopBackOff", None, None)
    assert action == "restart_pod"

def test_merge_results_fallback():
    engine = RemediationDecisionEngine()
    fallback = engine.merge_results(None, None)
    assert fallback["recommended_action"] == "manual_investigation"
    assert fallback["confidence"] == "low"

