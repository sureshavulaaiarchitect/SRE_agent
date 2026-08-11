import json
import re
import time
import asyncio
from typing import Literal, Optional, Union
from dataclasses import dataclass

import structlog
from configs.config import settings
from ai.prompts import build_analysis_prompt
from ai.backends import AIResponseSchema
from infrastructure.evidence_collector import Evidence
from observability.metrics_collector import ai_response_latency, circuit_breaker_state, ai_used_total

logger = structlog.get_logger(__name__)

@dataclass
class RootCauseResult:
    root_cause: str
    confidence: str
    action: str
    explanation: str
    ai_used: bool = False
    source: str = "ai_engine"

def parse_ai_response(response) -> dict:
    """
    Robust parser (FIX3):
    - handles dict/string/markdown/partial JSON
    - Pydantic validation
    - Strict fallback if fails
    """
    if isinstance(response, dict):
        try:
            return AIResponseSchema(**response).model_dump()
        except:
            pass

    if not isinstance(response, str):
        return fallback_response("Invalid response type")

    cleaned = response.strip()
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return AIResponseSchema(**data).model_dump()
    except Exception:
        pass

    # Regex JSON extraction for partial
    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned, re.DOTALL)
    if match:
        try:
            return AIResponseSchema(**json.loads(match.group(0))).model_dump()
        except Exception:
            pass

    return fallback_response(str(cleaned)[:200])

def fallback_response(reason: str) -> dict:
    """Fallback used when the LLM returns unparseable output.

    Keep this conservative: do not trigger automated remediation when parsing failed.
    """
    return {
        "root_cause": "parsing_failed_but_recovered",
        "confidence": "low",
        "action": "manual_investigation",
        "explanation": f"LLM response could not be parsed as valid JSON (sample='{reason}'). Falling back safely.",
        "ai_used": False
    }

def rule_based_rca(reason: str, pod_name: str) -> dict:
    """FIX4+6: Deterministic STRICT mapping. NEVER manual_investigation for known issues."""
    reason_lower = (reason or "").lower()
    
    if any(k in reason_lower for k in ["crashloopbackoff", "back-off restarting", "error", "containercannotrun"]):
        return {
            "root_cause": "Container crash detected",
            "confidence": "high",
            "action": "restart_pod",
            "explanation": f"Pod {pod_name} matches crash patterns (CrashLoopBackOff/Error/ContainerCannotRun). restart_pod is safe first action.",
            "ai_used": False
        }
    elif "oomkilled" in reason_lower:
        return {
            "root_cause": "OOMKilled - memory limit exceeded",
            "confidence": "high",
            "action": "increase_limits",
            "explanation": f"Pod {pod_name} killed by OOM (exit 137). Increase memory limits prevents recurrence.",
            "ai_used": False
        }
    elif any(k in reason_lower for k in ["imagepullbackoff", "errimagepull"]):
        return {
            "root_cause": "ImagePullBackOff - cannot pull image",
            "confidence": "high",
            "action": "rollback_deployment",
            "explanation": f"Pod {pod_name} cannot pull image. Deployment rollback to working revision.",
            "ai_used": False
        }
    else:
        return fallback_response(f"Unknown reason: {reason}")

# ---------------------------------------------------------------------------
# Module-level circuit breaker state — shared across ALL AIRootCauseEngine
# instances and persisted for the lifetime of the process.  asyncio.Lock
# prevents concurrent coroutines from racing on reads + writes.
# ---------------------------------------------------------------------------
_cb_lock: asyncio.Lock = asyncio.Lock()
_cb_failure_count: int = 0
_cb_last_failure_time: float = 0.0
_cb_state: Literal["CLOSED", "OPEN", "HALF-OPEN"] = "CLOSED"


class AIRootCauseEngine:

    def __init__(self, backend: Optional[Literal["ollama", "openai", "anthropic"]] = None):
        self.backend = backend or settings.AI_BACKEND
        circuit_breaker_state.labels(backend=self.backend).set(
            1 if _cb_state == "CLOSED" else 0
        )

    async def _update_state(self, new_state: Literal["CLOSED", "OPEN", "HALF-OPEN"]):
        global _cb_state
        if _cb_state != new_state:
            logger.info(
                "CIRCUIT BREAKER STATE TRANSITION",
                old_state=_cb_state,
                new_state=new_state,
                backend=self.backend,
            )
            _cb_state = new_state
            circuit_breaker_state.labels(backend=self.backend).set(
                1 if new_state == "CLOSED" else 0
            )

    async def _check_circuit(self) -> bool:
        """Returns True if a call should be attempted, False if circuit is OPEN."""
        async with _cb_lock:
            if _cb_state == "OPEN":
                if time.time() - _cb_last_failure_time > settings.CIRCUIT_BREAKER_RESET_TIMEOUT:
                    await self._update_state("HALF-OPEN")
                    return True
                return False
            return True

    async def _record_failure(self):
        global _cb_failure_count, _cb_last_failure_time
        async with _cb_lock:
            _cb_failure_count += 1
            _cb_last_failure_time = time.time()
            if _cb_failure_count >= settings.CIRCUIT_BREAKER_THRESHOLD:
                await self._update_state("OPEN")

    async def _record_success(self):
        global _cb_failure_count
        async with _cb_lock:
            _cb_failure_count = 0
            await self._update_state("CLOSED")

    async def analyze(self, evidence: Union[Evidence, dict]) -> Optional[RootCauseResult]:
        def get_val(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        pod_name = get_val(evidence, "pod_name", "unknown")
        reason = get_val(evidence, "reason", "unknown")

        # 1. Health check (Only for Ollama) - FIX1 handled in backend
        if self.backend == "ollama":
            from ai.backends.ollama import check_ollama_health
            if not await check_ollama_health():
                logger.warning("Ollama unhealthy - rule fallback", pod=pod_name)
                ai_used_total.labels(used=False, reason="ollama_unhealthy").inc()
                res_dict = rule_based_rca(reason, pod_name)
                return RootCauseResult(**res_dict)

        if not await self._check_circuit():
            logger.warning("Circuit breaker OPEN - rule fallback", pod=pod_name)
            ai_used_total.labels(used=False, reason="circuit_breaker").inc()
            res_dict = rule_based_rca(reason, pod_name)
            return RootCauseResult(**res_dict)

        prompt = build_analysis_prompt(evidence)
        logger.info("AI analysis started", backend=self.backend, pod=pod_name)

        start_time = time.time()
        max_retries = 3  # FIX2: Exactly 3 retries
        timeout = settings.AI_REQUEST_TIMEOUT

        for attempt in range(max_retries):
            try:
                raw = await asyncio.wait_for(self._call_llm(prompt), timeout=timeout)
                await self._record_success()

                duration = time.time() - start_time
                ai_response_latency.labels(backend=self.backend).observe(duration)
                ai_used_total.labels(used=True, reason="success").inc()

                parsed_data = parse_ai_response(raw)
                result = RootCauseResult(
                    root_cause=parsed_data.get("root_cause", "unknown"),
                    confidence=parsed_data.get("confidence", "low"),
                    action=parsed_data.get("action") or parsed_data.get("recommended_action", "manual_investigation"),
                    explanation=parsed_data.get("explanation", "AI analysis complete"),
                    ai_used=True,
                    source="ai_engine"
                )
                logger.info("AI success", pod=pod_name, root_cause=result.root_cause, action=result.action)
                return result

            except Exception as e:
                await self._record_failure()
                import random

                wait_time = (2 ** attempt) + random.uniform(0, 1)  # exponential backoff + jitter

                logger.warning(f"AI attempt {attempt+1}/3 failed", error=str(e), pod=pod_name, retry_in=f"{wait_time:.1f}s")

                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("All 3 AI retries failed; rule fallback", pod=pod_name)
                    ai_used_total.labels(used=False, reason="retries_exhausted").inc()
                    res_dict = rule_based_rca(str(reason), str(pod_name))
                    return RootCauseResult(**res_dict)

    async def _call_llm(self, prompt: str):
        if self.backend == "ollama":
            from ai.backends.ollama import generate
            return await generate(prompt)
        elif self.backend == "openai":
            from ai.backends.openai import call_openai
            return await call_openai(prompt)
        elif self.backend == "anthropic":
            from ai.backends.anthropic import call_anthropic
            return await call_anthropic(prompt)
        raise ValueError(f"Unknown backend: {self.backend}")

