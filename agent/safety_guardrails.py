from dataclasses import dataclass
from typing import Optional
import time
import structlog

logger = structlog.get_logger(__name__)

WHITELIST: dict[str, dict] = {
    # All mutating remediation actions require a human approval step.
    # Set requires_approval=True so incidents reach 'awaiting_approval' status
    # before the K8s executor touches anything.
    "restart_pod":            {"requires_approval": True,  "max_per_hour": 10},
    "scale_deployment":       {"requires_approval": True,  "max_per_hour": 5},
    "rollback_deployment":    {"requires_approval": True,  "max_per_hour": 3},
    "increase_limits":        {"requires_approval": True,  "max_per_hour": 2},
    # Informational / no-op — no approval needed
    "manual_review":          {"requires_approval": False, "max_per_hour": 999},
    "manual_investigation":   {"requires_approval": False, "max_per_hour": 999},
    "none":                   {"requires_approval": False, "max_per_hour": 999},
}

# Permanently blocked — no exceptions ever
BLOCKED: set[str] = {
    "delete_deployment",
    "delete_namespace",
    "delete_node",
    "delete_cluster"
}

@dataclass
class GateResult:
    approved:       bool
    reason:         str
    requires_human: bool = False

class SafetyGate:
    def __init__(self):
        # {action: [timestamps]}
        self._rate_window: dict[str, list[float]] = {}
        # {pod_key: [timestamps]}
        self._pod_history: dict[str, list[float]] = {}

    def validate(self, action: str, context: dict = None) -> GateResult:
        """Main gate — check blocked list, whitelist, and rate limits."""
        if action in BLOCKED:
            logger.warning("Safety gate: permanently blocked action attempted", action=action)
            return GateResult(approved=False, reason="PERMANENTLY_BLOCKED", requires_human=False)

        if action not in WHITELIST:
            logger.warning("Safety gate: action not in whitelist", action=action)
            return GateResult(approved=False, reason="NOT_IN_WHITELIST", requires_human=False)

        # 1. Pod-specific rate limit (3 actions per 5 min)
        if context and "pod_name" in context and "namespace" in context:
            if self._pod_rate_limit_exceeded(context["namespace"], context["pod_name"]):
                logger.warning("Safety gate: pod rate limit exceeded", pod=context["pod_name"])
                return GateResult(approved=False, reason="POD_RATE_LIMIT_EXCEEDED", requires_human=False)

        # 2. Global action rate limit
        if self._rate_limit_exceeded(action):
            logger.warning("Safety gate: action rate limit exceeded", action=action)
            return GateResult(approved=False, reason="ACTION_RATE_LIMIT_EXCEEDED", requires_human=False)

        rules = WHITELIST[action]
        logger.info("Safety gate: action approved", action=action, requires_human=rules["requires_approval"])
        return GateResult(
            approved=True,
            reason="APPROVED",
            requires_human=rules["requires_approval"]
        )

    def record_execution(self, action: str, context: dict = None):
        """Record an executed action for rate limiting."""
        now = time.time()
        
        # Action-wide history
        window = self._rate_window.setdefault(action, [])
        window.append(now)

        # Pod-specific history
        if context and "pod_name" in context and "namespace" in context:
            pod_key = f"{context['namespace']}/{context['pod_name']}"
            pod_history = self._pod_history.setdefault(pod_key, [])
            pod_history.append(now)

    def _rate_limit_exceeded(self, action: str) -> bool:
        now = time.time()
        one_hour_ago = now - 3600
        window = self._rate_window.get(action, [])
        # Prune old timestamps
        window = [t for t in window if t > one_hour_ago]
        self._rate_window[action] = window
        max_per_hour = WHITELIST[action]["max_per_hour"]
        return len(window) >= max_per_hour

    def _pod_rate_limit_exceeded(self, namespace: str, pod_name: str) -> bool:
        now = time.time()
        five_min_ago = now - 300
        pod_key = f"{namespace}/{pod_name}"
        window = self._pod_history.get(pod_key, [])
        # Prune
        window = [t for t in window if t > five_min_ago]
        self._pod_history[pod_key] = window
        return len(window) >= 3

# Singleton instance
safety_gate = SafetyGate()
