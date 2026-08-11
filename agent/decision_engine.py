import structlog
from typing import Any

logger = structlog.get_logger(__name__)

class RemediationDecisionEngine:
    def __init__(self):
        # Maps root cause keywords to remediation action keys
        self.decision_map = {
            "image_pull_error": "rollback_deployment",
            "crash_loop": "restart_pod",
            "oom_killed": "scale_deployment",
            "pending_pod": "scale_deployment",
            "evicted": "restart_pod",
            "completed": "none"
        }
        self.VALID_ACTIONS = [
            "restart_pod",
            "rollback_deployment",
            "scale_deployment",
            "recreate_workload",
            "manual_investigation"
        ]

    def merge_results(self, rule_result, ai_result) -> dict:
        """Standardized merge logic (Phase 7)."""
        # Priority mapping for "SAFER" action selection
        # Lower index = Higher priority (safer)
        PRIORITY = ["restart_pod", "scale_deployment", "rollback_deployment", "manual_investigation"]
        
        def get_action_priority(action):
            try:
                return PRIORITY.index(action)
            except ValueError:
                return len(PRIORITY)

        # 1. Fallback if both fail
        if not rule_result and not ai_result:
            return {
                "root_cause": "Unknown",
                "confidence": "low",
                "recommended_action": "manual_investigation",
                "explanation": "Both rule and AI engines failed to produce results.",
                "source": "fallback"
            }

        rule_action = getattr(rule_result, "recommended_action", None) or (rule_result.get("recommended_action") if isinstance(rule_result, dict) else None)
        ai_action = getattr(ai_result, "recommended_action", None) or (ai_result.get("recommended_action") if isinstance(ai_result, dict) else None)

        # 2. Extract actions safely
        rule_action = getattr(rule_result, "recommended_action", None) or (rule_result.get("recommended_action") if isinstance(rule_result, dict) else None)
        
        # AI Result handling (handles both 'action' and 'recommended_action')
        ai_action = None
        if ai_result:
            if isinstance(ai_result, dict):
                ai_action = ai_result.get("action") or ai_result.get("recommended_action")
            else:
                ai_action = getattr(ai_result, "action", None) or getattr(ai_result, "recommended_action", None)

        # 3. Fallback: If AI fails, use Rule engine
        if not ai_result or not ai_action:
            logger.warning("ai_fallback_triggered", reason="AI result missing or invalid")
            if rule_result:
                 return self._format_result(rule_result, "rule_fallback")
            return self._format_result({}, "fallback_final")

        # 4. Case: Rule only (if ai_result somehow passed but is empty)
        if rule_result and not ai_action:
            return self._format_result(rule_result, "rule")

        # 5. Deployment Safety Check (as requested)
        # If action is 'restart_pod', ensure it's a managed workload (handled by controller)
        # We check owner_ref if provided in the evidence (passed via result dicts sometimes)
        owner_ref = (ai_result.get("owner_ref") if isinstance(ai_result, dict) else getattr(ai_result, "owner_ref", None)) or \
                    (rule_result.get("owner_ref") if isinstance(rule_result, dict) else getattr(rule_result, "owner_ref", None))
        
        if ai_action == "restart_pod" and owner_ref and "deployment" not in owner_ref.lower() and "replicaset" not in owner_ref.lower():
            logger.warning("remediation_restricted", reason="restart_pod requested for non-deployment pod", owner=owner_ref)
            ai_action = "manual_investigation"
            # Update the ai_result to reflect this change
            if isinstance(ai_result, dict):
                ai_result["action"] = "manual_investigation"
                ai_result["explanation"] = (ai_result.get("explanation", "") + " (Safety: Restricted restart to Deployments only)").strip()
            # Note: if it's a Pydantic object, we might need to handle it differently, 
            # but _format_result will pick it up if we pass the modified ai_action there.

        # 6. Case: Both agree
        if rule_action == ai_action:
            res = self._format_result(rule_result, "combined")
            res["confidence"] = "high"
            return res

        # 7. Case: Conflict -> Choose SAFER action
        rule_prio = get_action_priority(rule_action)
        ai_prio = get_action_priority(ai_action)

        if rule_prio <= ai_prio:
            res = self._format_result(rule_result, "conflict_resolved_rule")
            res["explanation"] += f" (Conflict with AI: {ai_action}; chose rule as safer)"
            return res
        else:
            # Transfer the possibly modified ai_action back
            if isinstance(ai_result, dict):
                 ai_result["recommended_action"] = ai_action
            res = self._format_result(ai_result, "conflict_resolved_ai")
            res["explanation"] += f" (Conflict with Rule: {rule_action}; chose AI as safer)"
            return res

    def _format_result(self, result, source: str) -> dict:
        def get_field(obj, field, default):
            if isinstance(obj, dict):
                return obj.get(field, default)
            return getattr(obj, field, default)
        
        return {
            "root_cause": get_field(result, "root_cause", "unknown"),
            "confidence": get_field(result, "confidence", "low"),
            "recommended_action": get_field(result, "action", get_field(result, "recommended_action", "manual_investigation")),
            "explanation": get_field(result, "explanation", "Standard analysis"),
            "source": f"decision_engine/{source}"
        }


    def decide(self, root_cause: str, pattern_match: Any = None, ai_result: Any = None) -> str:

        """
        Determine the best remediation action based on findings from both Rule (Pattern) and AI engines.
        """
        selected_action = "manual_investigation"
        
        if pattern_match and hasattr(pattern_match, 'confidence') and pattern_match.confidence == "high":
            selected_action = getattr(pattern_match, 'recommended_action', "manual_investigation")
            logger.info("Decision engine: Using high-confidence pattern match", action=selected_action)
        elif ai_result and hasattr(ai_result, 'recommended_action') and ai_result.recommended_action != "manual_investigation":
            selected_action = ai_result.recommended_action
            logger.info("Decision engine: Using AI recommendation", action=selected_action)
        elif pattern_match and hasattr(pattern_match, 'recommended_action'):
            selected_action = pattern_match.recommended_action
            logger.info("Decision engine: Using lower-confidence pattern match", action=selected_action)
        else:
            # Keyword-based fallback
            root_cause_lower = root_cause.lower() if root_cause else "unknown"
            if "image" in root_cause_lower:
                selected_action = "rollback_deployment"
            elif "oom" in root_cause_lower or "memory" in root_cause_lower:
                selected_action = "scale_deployment"
            elif "crash" in root_cause_lower or "terminated" in root_cause_lower:
                selected_action = "restart_pod"
            elif "pending" in root_cause_lower or "unschedulable" in root_cause_lower:
                selected_action = "scale_deployment"
            elif "cpu" in root_cause_lower:
                selected_action = "scale_deployment"
            else:
                selected_action = self.decision_map.get(root_cause_lower, "manual_investigation")
            logger.info("Decision engine: Using keyword fallback", action=selected_action, root_cause=root_cause)

        if selected_action not in self.VALID_ACTIONS:
            logger.warning(f"Invalid action '{selected_action}' not in VALID_ACTIONS, fallback to 'manual_investigation'")
            selected_action = "manual_investigation"
        
        return selected_action

# Singleton instance
decision_engine = RemediationDecisionEngine()
