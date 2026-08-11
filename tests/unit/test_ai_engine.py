"""Unit tests for AI Root Cause Engine — covers acceptance criteria #4."""
import pytest
from ai.root_cause_engine import AIRootCauseEngine
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_valid_json_returns_result(sample_evidence):
    """Criteria #4: Valid JSON from LLM -> parsed correctly."""
    engine = AIRootCauseEngine(backend="ollama")
    valid_response = '''{
        "root_cause": "Container OOM killed",
        "confidence": "high",
        "recommended_action": "increase_limits",
        "explanation": "The container exceeded its memory limit."
    }'''
    with patch("ai.backends.ollama.check_ollama_health", return_value=True):
        with patch.object(engine, "_call_llm", new=AsyncMock(return_value=valid_response)):
            result = await engine.analyze(sample_evidence)
            assert result.root_cause == "Container OOM killed"
            assert result.confidence == "high"
            assert result.recommended_action == "increase_limits"

@pytest.mark.asyncio
async def test_invalid_json_returns_manual_review(sample_evidence):
    """Criteria #4: Garbage from LLM -> PARSE_ERROR + manual_investigation, no crash."""
    engine = AIRootCauseEngine(backend="ollama")
    with patch("ai.backends.ollama.check_ollama_health", return_value=True):
        with patch.object(engine, "_call_llm", new=AsyncMock(return_value="this is not json at all !!!")):
            result = await engine.analyze(sample_evidence)
            assert result.root_cause == "parsing_failed_but_recovered"
            assert result.recommended_action == "manual_investigation"
            assert result.confidence == "low"

@pytest.mark.asyncio
async def test_llm_failure_returns_manual_investigation(sample_evidence):
    """LLM call failure -> returns manual_investigation gracefully."""
    engine = AIRootCauseEngine(backend="ollama")
    with patch("ai.backends.ollama.check_ollama_health", return_value=True):
        with patch.object(engine, "_call_llm", new=AsyncMock(side_effect=RuntimeError("connection refused"))):
            result = await engine.analyze(sample_evidence)
            assert result.recommended_action == "manual_investigation"

