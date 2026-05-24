import base64
import json
import mimetypes
import os
import time
from typing import Any, Type, TypeVar

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from openai import OpenAI
from pydantic import BaseModel

from autovisualskill.llm.subagent_client import (
    call_subagent,
    call_subagent_structured,
    subagent_backend_enabled,
)

T = TypeVar("T", bound=BaseModel)

_llm_instance: ChatOpenAI | None = None
_llm_config: tuple[str, str | None, str | None, float, float | None, int] | None = None
_responses_client: OpenAI | None = None
_responses_config: tuple[str | None, str | None, float | None] | None = None


def _get_llm(temperature: float = 0.0) -> ChatOpenAI:
    global _llm_config, _llm_instance
    model = os.environ.get("LLM_MODEL_NAME", "gpt-4o")
    base_url = os.environ.get("LLM_BASE_URL") or None
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or None
    timeout_value = os.environ.get("LLM_TIMEOUT", "")
    timeout = float(timeout_value) if timeout_value else None
    max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "8192"))
    config = (model, base_url, api_key, temperature, timeout, max_tokens)
    if _llm_instance is None or _llm_config != config:
        _llm_instance = ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        _llm_config = config
    return _llm_instance


def _responses_backend_enabled() -> bool:
    return os.environ.get("LLM_API_STYLE", "").lower() in {
        "responses",
        "openai_responses",
    }


def _get_responses_client() -> OpenAI:
    global _responses_client, _responses_config
    base_url = os.environ.get("LLM_BASE_URL") or None
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or None
    timeout_value = os.environ.get("LLM_TIMEOUT", "")
    timeout = float(timeout_value) if timeout_value else None
    config = (base_url, api_key, timeout)
    if _responses_client is None or _responses_config != config:
        _responses_client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )
        _responses_config = config
    return _responses_client


def _retry_attempts() -> int:
    raw = os.environ.get("LLM_RETRY_ATTEMPTS", "3")
    try:
        return max(1, int(raw))
    except ValueError:
        return 3


def _is_retryable_llm_error(exc: Exception) -> bool:
    retryable_names = {
        "APIConnectionError",
        "APITimeoutError",
        "RateLimitError",
        "InternalServerError",
        "RemoteProtocolError",
        "ConnectError",
        "ReadError",
        "ReadTimeout",
        "TimeoutException",
    }
    return any(cls.__name__ in retryable_names for cls in type(exc).mro())


def _invoke_with_retries(fn):
    attempts = _retry_attempts()
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:
            if attempt >= attempts - 1 or not _is_retryable_llm_error(exc):
                raise
            time.sleep(min(2 ** attempt, 8))
    raise RuntimeError("unreachable LLM retry state")


def image_to_base64(path: str) -> str:
    mime_type, _ = mimetypes.guess_type(path)
    if mime_type is None:
        mime_type = "image/png"
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return f"data:{mime_type};base64,{data}"


def call_llm(messages: list, temperature: float = 0.0) -> str:
    if subagent_backend_enabled():
        return call_subagent(messages, temperature=temperature)

    if _responses_backend_enabled():
        return _call_llm_responses(messages, temperature=temperature)

    llm = _get_llm(temperature)
    resp = _invoke_with_retries(lambda: llm.invoke(messages))
    return resp.content


def call_llm_structured(
    messages: list,
    response_model: Type[T],
    temperature: float = 0.0,
) -> T:
    if subagent_backend_enabled():
        return call_subagent_structured(
            messages,
            response_model,
            temperature=temperature,
        )

    if os.environ.get("LLM_FORCE_JSON_PROMPT", "").lower() in {"1", "true", "yes"}:
        return _call_llm_structured_schema_prompt(
            messages,
            response_model,
            temperature=temperature,
        )

    if _responses_backend_enabled():
        return _call_llm_structured_schema_prompt(
            messages,
            response_model,
            temperature=temperature,
        )

    llm = _get_llm(temperature)
    structured = llm.with_structured_output(response_model)
    return _invoke_with_retries(lambda: structured.invoke(messages))


def _call_llm_responses(messages: list, temperature: float = 0.0) -> str:
    client = _get_responses_client()
    model = os.environ.get("LLM_MODEL_NAME", "gpt-4o")
    max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "8192"))
    kwargs: dict[str, Any] = {
        "model": model,
        "input": _messages_to_responses_input(messages),
        "max_output_tokens": max_tokens,
    }
    if temperature:
        kwargs["temperature"] = temperature
    response = _invoke_with_retries(lambda: client.responses.create(**kwargs))
    return _extract_responses_text(response)


def _messages_to_responses_input(messages: list) -> list[dict[str, Any]]:
    payload = []
    for message in messages:
        role = _message_role(message)
        content = getattr(message, "content", message)
        payload.append(
            {
                "role": role,
                "content": _content_to_responses_parts(content),
            }
        )
    return payload


def _message_role(message: Any) -> str:
    role = getattr(message, "type", None) or getattr(message, "role", None)
    role_map = {
        "human": "user",
        "ai": "assistant",
        "system": "system",
        "developer": "developer",
        "user": "user",
        "assistant": "assistant",
    }
    return role_map.get(str(role), "user")


def _content_to_responses_parts(content: Any) -> list[dict[str, Any]]:
    if isinstance(content, str):
        return [{"type": "input_text", "text": content}]
    if not isinstance(content, list):
        return [{"type": "input_text", "text": str(content)}]

    parts: list[dict[str, Any]] = []
    for item in content:
        if isinstance(item, str):
            parts.append({"type": "input_text", "text": item})
            continue
        if not isinstance(item, dict):
            parts.append({"type": "input_text", "text": str(item)})
            continue

        item_type = item.get("type")
        if item_type in {"input_text", "input_image"}:
            parts.append(item)
        elif item_type == "text":
            parts.append({"type": "input_text", "text": item.get("text", "")})
        elif item_type == "image_url":
            image_url = item.get("image_url", "")
            if isinstance(image_url, dict):
                image_url = image_url.get("url", "")
            parts.append({"type": "input_image", "image_url": image_url})
        else:
            parts.append({"type": "input_text", "text": json.dumps(item, ensure_ascii=False)})
    return parts or [{"type": "input_text", "text": ""}]


def _extract_responses_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text

    texts: list[str] = []
    for output in getattr(response, "output", []) or []:
        for content in getattr(output, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                texts.append(text)
            elif isinstance(content, dict) and content.get("text"):
                texts.append(content["text"])
    if texts:
        return "\n".join(texts)
    return str(response)


def _call_llm_structured_schema_prompt(
    messages: list,
    response_model: Type[T],
    temperature: float = 0.0,
) -> T:
    schema = response_model.model_json_schema()
    instruction = (
        "Return exactly one valid JSON object matching this JSON Schema. "
        "Do not wrap the JSON in Markdown fences and do not include extra prose.\n\n"
        f"JSON Schema:\n{json.dumps(schema, ensure_ascii=False)}"
    )
    schema_messages = list(messages) + [HumanMessage(content=instruction)]
    raw = call_llm(schema_messages, temperature=temperature)
    payload = _extract_json_payload(raw)
    return response_model.model_validate(payload)


def _extract_json_payload(raw: str) -> object:
    text = raw.strip()
    if not text:
        raise ValueError("LLM returned empty content for structured JSON parsing")
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for idx, char in enumerate(text):
            if char not in "[{":
                continue
            try:
                payload, _end = decoder.raw_decode(text[idx:])
                return payload
            except json.JSONDecodeError:
                continue
        raise
