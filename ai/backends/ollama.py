import httpx
import json
import structlog
import asyncio
import re
from configs.config import settings
from pydantic import BaseModel, Field, ValidationError

logger = structlog.get_logger(__name__)


class AIResponseSchema(BaseModel):
    root_cause: str = Field(..., min_length=5)
    confidence: str = Field(..., pattern=r"^(high|medium|low)$")
    action: str = Field(
        ...,
        pattern=r"^(restart_pod|increase_limits|rollback_deployment|manual_investigation|scale_deployment)$"
    )
    explanation: str = Field(..., min_length=10)


from observability.metrics_collector import ollama_failures_total

async def check_ollama_health() -> bool:
    """Check Ollama health via /api/tags."""
    url = f"{settings.OLLAMA_BASE_URL}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                logger.info("ollama_health_ok")
                return True
            else:
                logger.warning("ollama_health_failed", status_code=response.status_code)
                return False
    except Exception as e:
        logger.error("ollama_health_failed", error=str(e))
        return False
    return False

async def generate(prompt: str) -> dict:
    """
    Call Ollama safely with:
    - exponential backoff retry
    - strict JSON payload
    - robust response parsing
    """
    model_name = "qwen2.5:14b"
    url = "http://host.docker.internal:11434/api/generate"
    
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False
    }

    last_error = None
    for i in range(3):
        try:
            # 1. Health check before each attempt (optional but safer)
            if not await check_ollama_health():
                logger.warning("ollama_health_check_failed", attempt=i+1)
            
            logger.info("AI analysis started", attempt=i+1, model=model_name)
            
            async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT) as client:
                response = await client.post(url, json=payload)
                
                if response.status_code == 404:
                    logger.error("ollama_api_failed", error="404 Not Found - Check model name or endpoint")
                    raise httpx.HTTPStatusError("404 Not Found", request=response.request, response=response)
                
                response.raise_for_status()
                data = response.json()

                # Parse response strictly using data["response"]
                raw = data["response"].strip()
                if not raw:
                    logger.error("ollama_api_failed", error="Empty response")
                    raise ValueError("Empty response from Ollama")

                # Clean response (remove markdown fences if model misbehaves)
                if raw.startswith("```"):
                    raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.IGNORECASE)
                    raw = re.sub(r'\s*```$', '', raw)
                    raw = raw.strip()

                try:
                    parsed_json = json.loads(raw)
                    validated = AIResponseSchema(**parsed_json)
                    logger.info("AI response received", root_cause=validated.root_cause)
                    return validated.model_dump()
                except (json.JSONDecodeError, ValidationError, KeyError) as e:
                    logger.error("ollama_parsing_failed", error=str(e), raw=str(raw)[:100])
                    raise e

        except Exception as e:
            last_error = e
            logger.error("ollama_api_failed", attempt=i+1, error=str(e))
            try:
                ollama_failures_total.labels(reason=type(e).__name__).inc()
            except Exception:
                pass # Metrics are optional
            
            if i < 2: # Don't sleep after the last attempt
                wait_time = 2 ** i
                logger.info(f"Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)

    logger.error("ai_fallback_triggered", error="All retries failed")
    if last_error is not None:
        raise last_error
    raise RuntimeError("AI analysis failed to produce a result")