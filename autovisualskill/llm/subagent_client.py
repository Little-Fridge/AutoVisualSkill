import json
import os
import shlex
import subprocess
from typing import Any, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_SUBAGENT_BACKENDS = {"subagent", "codex_subagent", "external_subagent"}


def subagent_backend_enabled() -> bool:
    backend = os.environ.get("AUTOVISUALSKILL_LLM_BACKEND", "").strip().lower()
    return backend in _SUBAGENT_BACKENDS


def call_subagent(messages: list, temperature: float = 0.0) -> str:
    payload = {
        "mode": "chat",
        "temperature": temperature,
        "messages": [_serialize_message(message) for message in messages],
    }
    result = _invoke_subagent(payload)
    if isinstance(result, dict):
        for key in ("content", "text", "output"):
            value = result.get(key)
            if isinstance(value, str):
                return value
        return json.dumps(result, ensure_ascii=False)
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False)


def call_subagent_structured(
    messages: list,
    response_model: Type[T],
    temperature: float = 0.0,
) -> T:
    payload = {
        "mode": "structured",
        "schema_name": response_model.__name__,
        "schema": response_model.model_json_schema(),
        "temperature": temperature,
        "messages": [_serialize_message(message) for message in messages],
    }
    result = _invoke_subagent(payload)

    if isinstance(result, dict) and "data" in result:
        result = result["data"]
    elif isinstance(result, dict) and "content" in result and isinstance(result["content"], str):
        result = _parse_json_payload(result["content"])
    elif isinstance(result, str):
        result = _parse_json_payload(result)

    return response_model.model_validate(result)


def _invoke_subagent(payload: dict[str, Any]) -> Any:
    command = os.environ.get("AUTOVISUALSKILL_SUBAGENT_CMD", "").strip()
    if not command:
        raise RuntimeError(
            "AUTOVISUALSKILL_LLM_BACKEND is set to subagent, but AUTOVISUALSKILL_SUBAGENT_CMD is empty"
        )

    timeout = float(os.environ.get("AUTOVISUALSKILL_SUBAGENT_TIMEOUT", "600"))
    completed = subprocess.run(
        shlex.split(command),
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        detail = stderr or stdout or f"exit code {completed.returncode}"
        raise RuntimeError(f"Subagent command failed: {detail[:2000]}")

    output = completed.stdout.strip()
    if not output:
        raise RuntimeError("Subagent command returned empty stdout")

    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return output


def _serialize_message(message: Any) -> dict[str, Any]:
    role = _message_role(message)
    content = getattr(message, "content", message)
    return {"role": role, "content": _json_safe(content)}


def _message_role(message: Any) -> str:
    type_name = message.__class__.__name__.lower()
    if "system" in type_name:
        return "system"
    if "human" in type_name:
        return "user"
    if "ai" in type_name or "assistant" in type_name:
        return "assistant"
    return "user"


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(k): _json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_json_safe(item) for item in value]
        return str(value)


def _parse_json_payload(raw: str) -> Any:
    text = raw.strip()
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
