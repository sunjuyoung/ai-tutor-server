from collections.abc import AsyncGenerator

from openai import AsyncOpenAI

from app.core.config import settings

_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


async def chat_stream(
    system_prompt: str,
    messages: list[dict[str, str]],
    model: str = "gpt-4o",
    temperature: float = 0.8,
    max_tokens: int = 500,
) -> AsyncGenerator[str]:
    client = get_openai_client()
    all_messages = [{"role": "system", "content": system_prompt}] + messages

    stream = await client.chat.completions.create(
        model=model,
        messages=all_messages,
        stream=True,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
