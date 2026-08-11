import structlog
from configs.config import settings

logger = structlog.get_logger(__name__)

async def call_anthropic(prompt: str) -> str:
    """Call Anthropic Claude API and return the raw text response."""
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = await client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text
