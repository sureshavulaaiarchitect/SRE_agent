import json
from typing import Optional, Dict
from dataclasses import dataclass
from configs.config import settings
import structlog

logger = structlog.get_logger(__name__)

@dataclass
class PatternMatch:
    root_cause:         str
    recommended_action: str
    confidence:         str
    confidence_score:   float
    source:             str = "pattern_db"

class PatternDetectionLayer:
    _patterns_cache = None

    def __init__(self):
        if PatternDetectionLayer._patterns_cache is None:
            try:
                with open(settings.PATTERNS_PATH) as f:
                    PatternDetectionLayer._patterns_cache = json.load(f).get("patterns", [])
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.warning("Failed to load pattern database", error=str(e))
                PatternDetectionLayer._patterns_cache = []
        
        self.patterns = PatternDetectionLayer._patterns_cache
        self.CONFIDENCE_MAP = {"high": 0.9, "medium": 0.5, "low": 0.2}

    def check(self, evidence: dict) -> Optional[PatternMatch]:
        """Check known patterns before calling LLM. Returns None if no match. Adapted for dict evidence."""
        # First try rule-based reason check
        rule_result = self.run_rules(evidence)
        if rule_result:
            pm = PatternMatch(
                root_cause=rule_result["root_cause"],
                recommended_action=rule_result["recommended_action"],
                confidence=rule_result["confidence"],
                confidence_score=self.CONFIDENCE_MAP.get(rule_result["confidence"], 0.5),
                source="rule_engine"
            )
            logger.info("Rule engine match", root_cause=pm.root_cause)
            return pm
        
        # Fallback to JSON patterns
        for pattern in self.patterns:
            if self._matches(pattern["conditions"], evidence):
                logger.info("Pattern match found", root_cause=pattern["root_cause"])
                return PatternMatch(
                    root_cause=pattern["root_cause"],
                    recommended_action=pattern["recommended_action"],
                    confidence=pattern["confidence"],
                    confidence_score=self.CONFIDENCE_MAP.get(pattern["confidence"], 0.0),
                )
        return None  # Fall through to AI engine

    def run_rules(self, evidence: dict) -> Optional[dict]:
        """STEP 3: Simple rule engine based on reason field."""
        reason = str(evidence.get("reason", "")).strip()
        reason_lower = reason.lower()

        if "crashloopbackoff" in reason_lower:
            return {
                "root_cause": "Application is crashing repeatedly (CrashLoopBackOff)",
                "confidence": "high",
                "recommended_action": "restart_pod",
                "explanation": "CrashLoopBackOff pattern detected in reason field",
                "source": "rule"
            }

        elif "oomkilled" in reason_lower:
            return {
                "root_cause": "Container killed due to memory limit (OOMKilled)",
                "confidence": "high",
                "recommended_action": "scale",
                "explanation": "OOMKilled pattern detected in reason field",
                "source": "rule"
            }

        elif "imagepullbackoff" in reason_lower:
            return {
                "root_cause": "Invalid or missing container image (ImagePullBackOff)",
                "confidence": "high",
                "recommended_action": "rollback_deployment",
                "explanation": "ImagePullBackOff pattern detected in reason field",
                "source": "rule"
            }
        
        elif "error" in reason_lower:
            return {
                "root_cause": "Container reported error state",
                "confidence": "high",
                "recommended_action": "restart_pod",
                "explanation": "Error pattern detected in reason field. Safest initial action is restart_pod.",
                "source": "rule"
            }

        # Exit-code based rules (fallback when reason is unknown)
        exit_code = evidence.get("exit_code")
        if exit_code == 137:
            return {
                "root_cause": "Container killed due to memory limit (OOMKilled - exit 137)",
                "confidence": "high",
                "recommended_action": "scale",
                "explanation": "Exit code 137 indicates OOM kill. Increase memory limits.",
                "source": "rule"
            }
        if exit_code is not None and exit_code != 0:
            return {
                "root_cause": "Container crash detected (non-zero exit code)",
                "confidence": "high",
                "recommended_action": "restart_pod",
                "explanation": f"Non-zero exit code {exit_code} indicates container crash. restart_pod is safest initial action.",
                "source": "rule"
            }

        return None

    def _matches(self, conditions: dict, evidence: dict) -> bool:
        for key, expected_value in conditions.items():
            value = evidence.get(key)
            if key == "exit_code" and value != expected_value:
                return False
            elif key == "restart_count_gte" and (value or 0) < expected_value:
                return False
            elif key == "memory_limit_set" and (value is not None) != expected_value:
                return False
            elif key == "log_contains" and expected_value not in evidence.get('logs', ''):
                return False
        return True

