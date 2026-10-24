"""Bedrock client behaviour with the runtime client replaced by FakeBedrock."""

import json

import pytest
from botocore.exceptions import ClientError

from app.core.config import settings
from app.services.bedrock_client import _is_retryable, bedrock_client
from app.services.embedding_service import embedding_service


def client_error(code):
    return ClientError({"Error": {"Code": code, "Message": code}}, "Converse")


@pytest.fixture
def no_backoff(monkeypatch):
    """Skip tenacity's exponential wait between retries."""

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(bedrock_client.generate.retry, "sleep", no_sleep)


async def test_generate_sends_model_prompt_and_system(bedrock):
    bedrock.reply("Hello Asha")
    text = await bedrock_client.generate(
        "Say hi", system_prompt="Be brief", temperature=0.3, max_tokens=50
    )
    assert text == "Hello Asha"
    call = bedrock.calls[0]
    assert call["modelId"] == settings.BEDROCK_MODEL_ID
    assert call["system"] == [{"text": "Be brief"}]
    assert call["inferenceConfig"] == {"maxTokens": 50, "temperature": 0.3}


async def test_generate_uses_configured_defaults(bedrock):
    bedrock.reply("ok")
    await bedrock_client.generate("x")
    call = bedrock.calls[0]
    assert "system" not in call
    assert call["inferenceConfig"] == {
        "maxTokens": settings.BEDROCK_MAX_TOKENS,
        "temperature": settings.BEDROCK_TEMPERATURE,
    }


async def test_empty_content_returns_empty_string(bedrock, monkeypatch):
    monkeypatch.setattr(bedrock, "converse", lambda **kw: {"output": {"message": {"content": []}}})
    assert await bedrock_client.generate("x") == ""


@pytest.mark.parametrize(
    "raw",
    ['{"a": 1}', '```json\n{"a": 1}\n```', '```\n{"a": 1}\n```', '  {"a": 1}  '],
)
async def test_generate_json_strips_markdown_fences(bedrock, raw):
    bedrock.reply(raw)
    assert await bedrock_client.generate_json("give json") == {"a": 1}
    assert "Return ONLY valid JSON" in bedrock.prompts[0]
    assert bedrock.calls[0]["inferenceConfig"]["temperature"] == 0.1


async def test_generate_json_raises_on_prose(bedrock):
    bedrock.reply("Sure, here you go")
    with pytest.raises(json.JSONDecodeError):
        await bedrock_client.generate_json("give json")


async def test_throttling_is_retried(bedrock, no_backoff):
    bedrock.reply(client_error("ThrottlingException"), "second try")
    assert await bedrock_client.generate("x") == "second try"
    assert len(bedrock.calls) == 2


async def test_auth_errors_are_not_retried(bedrock, no_backoff):
    bedrock.reply(client_error("AccessDeniedException"), "never used")
    with pytest.raises(ClientError):
        await bedrock_client.generate("x")
    assert len(bedrock.calls) == 1


def test_only_transient_errors_are_retryable():
    assert _is_retryable(client_error("ServiceUnavailableException"))
    assert not _is_retryable(client_error("ValidationException"))
    assert not _is_retryable(ValueError("x"))


async def test_stream_generate_yields_chunks_in_order(bedrock):
    bedrock.reply("Streaming works fine")
    chunks = [c async for c in bedrock_client.stream_generate("x", system_prompt="s")]
    assert "".join(chunks) == "Streaming works fine"
    assert len(chunks) > 1
    assert bedrock.calls[0]["system"] == [{"text": "s"}]


async def test_stream_generate_reraises_worker_errors(bedrock):
    bedrock.reply(client_error("ValidationException"))
    with pytest.raises(ClientError):
        [c async for c in bedrock_client.stream_generate("x")]


async def test_embedding_truncates_long_text(bedrock):
    bedrock.embedding = [0.5, 0.25]
    assert await embedding_service.embed_text("a" * 30000) == [0.5, 0.25]
    body = json.loads(bedrock.calls[0]["body"])
    assert len(body["inputText"]) == 25000
    assert bedrock.calls[0]["modelId"] == settings.BEDROCK_EMBED_MODEL_ID


async def test_embedding_batch_returns_one_vector_per_text(bedrock, monkeypatch):
    import asyncio

    async def no_sleep(_s):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    vectors = await embedding_service.embed_texts([f"t{i}" for i in range(12)], batch_size=5)
    assert len(vectors) == 12
    assert len(bedrock.calls) == 12


def test_combine_texts_for_embedding_includes_every_field():
    text = embedding_service.combine_texts_for_embedding(
        "job-scout", "Ranks postings", ["Python", "AWS"], ["500 postings a day"]
    )
    assert "Title: job-scout" in text
    assert "Technologies: Python, AWS" in text
    assert "500 postings a day" in text
