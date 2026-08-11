from typing import Dict, Any, Optional
import structlog

logger = structlog.get_logger(__name__)

# FIX5: STRICT deterministic mappings
CRASH_REASONS = {
    "crashloopbackoff", "error", "containercannotrun", "backoff", "terminated", "crash"
}
OOM_REASONS = {"oomkilled", "memory_limit_exceeded", "exit 137"}
IMAGE_REASONS = {"imagepullbackoff", "errimagepull", "imagepull"}

ACTION_MAP = {
    "restart_pod": ["container crash", "pod crash", "crashloopbackoff", "error"],
    "increase_limits": ["oomkilled", "memory", "exit 137"],
    "rollback_deployment": ["imagepullbackoff", "image pull"],
    "scale_deployment": ["pending", "unschedulable", "cpu"]
}

# safer action priority (lower index = safer/more proactive)
ACTION_PRIORITY = [
    "restart_pod",
    "scale_deployment",
    "increase_limits",
    "rollback_deployment",
    "manual_investigation",
]

HIGH_CONFIDENCE = "high"
MEDIUM_CONFIDENCE = "medium"
LOW_CONFIDENCE = "low"

def _max_confidence(c1: str, c2: str) -> str:
    """Correct confidence comparison: high > medium > low."""
    ranks = {HIGH_CONFIDENCE: 3, MEDIUM_CONFIDENCE: 2, LOW_CONFIDENCE: 1}
    r1 = ranks.get(c1, 0)
    r2 = ranks.get(c2, 0)
    return c1 if r1 >= r2 else c2

def _get_priority(action: Optional[str]) -> int:
    if action in ACTION_PRIORITY:
        return ACTION_PRIORITY.index(action)
    return len(ACTION_PRIORITY)

def _is_valid(result: Optional[Dict[str, Any]]) -> bool:
    return bool(result and isinstance(result.get("recommended_action"), str))

def _get_effective_root_cause(rule: Dict, ai: Dict) -> str:
    """Get best root_cause from rule or ai."""
    for source in [ai, rule]:
        if source.get("root_cause"):
            return source["root_cause"].lower()
    return "unknown"

def merge_results(rule: Optional[Dict], ai: Optional[Dict]) -> Dict:
    """
    IF AI confidence = high → use AI
    ELSE → fallback to Rule Engine
    """
    if ai and ai.get("confidence") == "high":
        logger.info("Decision: Using AI (high confidence)")
        return {
            "root_cause": ai.get("root_cause", "unknown"),
            "confidence": "high",
            "recommended_action": ai.get("recommended_action", "manual_investigation"),
            "explanation": ai.get("explanation", "AI provided high confidence analysis"),
            "source": "ai"
        }
    
    if rule and rule.get("recommended_action"):
        logger.info("Decision: Fallback to Rule Engine")
        return {
            "root_cause": rule.get("root_cause", "unknown"),
            "confidence": rule.get("confidence", "low"),
            "recommended_action": rule.get("recommended_action", "manual_investigation"),
            "explanation": rule.get("explanation", "Fallback to Rule Engine"),
            "source": "rule"
        }
    
    logger.info("Decision: Fallback to manual investigation")
    return {
        "root_cause": "Unknown",
        "confidence": "low",
        "recommended_action": "manual_investigation",
        "explanation": "Both AI and Rule Engine failed to provide a confident result",
        "source": "fallback"
    }

# Global instance for compatibility
class DecisionEngineWrapper:
    def merge_results(self, rule, ai):
        return merge_results(rule, ai)

decision_engine = DecisionEngineWrapper()
