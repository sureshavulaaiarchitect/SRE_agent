import structlog
from configs.config import settings

logger = structlog.get_logger(__name__)

async def call_openai(prompt: str) -> str:
    """Call OpenAI API and return the raw text response."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.0
    )
    return response.choices[0].message.content
