import base64
import os
from typing import Any
from urllib.parse import urlparse

import requests


def _is_gemini_style_base_url(base_url: str) -> bool:
    parsed = urlparse(base_url)
    text = base_url.lower()
    return (
        "generativelanguage.googleapis.com" in parsed.netloc.lower()
        or ":generatecontent" in text
        or "/generatecontent" in text
    )


def _resolve_gemini_endpoint(base_url: str, model: str) -> str:
    trimmed = base_url.rstrip("/")
    if ":generateContent" in trimmed or ":generatecontent" in trimmed.lower():
        return trimmed
    if "/models/" in trimmed:
        return f"{trimmed}:generateContent"
    return f"{trimmed}/models/{model or 'gemini-2.5-flash-image-preview'}:generateContent"


def _resolve_endpoint(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if not trimmed:
        raise ValueError("image_generation_base_url is required for api visual priors")

    known_suffixes = ("/images/generations", ":generateContent")
    if trimmed.endswith(known_suffixes):
        return trimmed
    if trimmed.endswith("/v1"):
        return f"{trimmed}/images/generations"
    return f"{trimmed}/v1/images/generations"


def _decode_data_url_or_base64(value: str) -> bytes:
    if value.startswith("data:"):
        _, payload = value.split(",", 1)
    else:
        payload = value
    return base64.b64decode(payload)


def _find_image_payload(payload: Any) -> tuple[bytes | None, str | None]:
    if isinstance(payload, dict):
        for key in ("b64_json", "image_base64", "image", "data"):
            value = payload.get(key)
            if isinstance(value, str) and len(value) > 100:
                try:
                    return _decode_data_url_or_base64(value), None
                except Exception:
                    pass

        for key in ("url", "image_url"):
            value = payload.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return None, value

        inline_data = payload.get("inlineData") or payload.get("inline_data")
        if isinstance(inline_data, dict):
            value = inline_data.get("data")
            if isinstance(value, str):
                try:
                    return _decode_data_url_or_base64(value), None
                except Exception:
                    pass

        for value in payload.values():
            image_bytes, image_url = _find_image_payload(value)
            if image_bytes or image_url:
                return image_bytes, image_url

    if isinstance(payload, list):
        for item in payload:
            image_bytes, image_url = _find_image_payload(item)
            if image_bytes or image_url:
                return image_bytes, image_url

    return None, None


def _download_image(url: str, output_path: str, timeout: float) -> None:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    with open(output_path, "wb") as f:
        f.write(response.content)


def generate_image_via_api(
    *,
    prompt: str,
    output_path: str,
    base_url: str,
    api_key: str,
    model: str = "nanobanana",
    size: str = "1024x1024",
    timeout: float = 120.0,
) -> str:
    """Generate one image using an OpenAI-compatible image API.

    Providers differ slightly, so this helper accepts either a root base URL
    (e.g. https://host/v1) or a full /images/generations endpoint, and parses
    common base64, data URL, and returned-image-URL response shapes.
    """
    if not prompt.strip():
        raise ValueError("image_generation_prompt is required for api visual priors")
    if not api_key.strip():
        raise ValueError("AUTOVISUALSKILL_IMAGE_API_KEY is required for api visual priors")

    if _is_gemini_style_base_url(base_url):
        return _generate_image_via_gemini_api(
            prompt=prompt,
            output_path=output_path,
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout=timeout,
        )

    endpoint = _resolve_endpoint(base_url)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    request_payload = {
        "model": model or "nanobanana",
        "prompt": prompt,
        "size": size or "1024x1024",
        "n": 1,
        "response_format": "b64_json",
    }

    response = requests.post(endpoint, headers=headers, json=request_payload, timeout=timeout)
    response.raise_for_status()

    image_bytes, image_url = _find_image_payload(response.json())
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if image_bytes:
        with open(output_path, "wb") as f:
            f.write(image_bytes)
    elif image_url:
        _download_image(image_url, output_path, timeout=timeout)
    else:
        raise ValueError("Image-generation API response did not contain an image payload")

    return os.path.abspath(output_path)


def _generate_image_via_gemini_api(
    *,
    prompt: str,
    output_path: str,
    base_url: str,
    api_key: str,
    model: str,
    timeout: float,
) -> str:
    endpoint = _resolve_gemini_endpoint(base_url, model)
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }
    request_payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }
    response = requests.post(endpoint, headers=headers, json=request_payload, timeout=timeout)
    response.raise_for_status()

    image_bytes, image_url = _find_image_payload(response.json())
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if image_bytes:
        with open(output_path, "wb") as f:
            f.write(image_bytes)
    elif image_url:
        _download_image(image_url, output_path, timeout=timeout)
    else:
        raise ValueError("Gemini image-generation response did not contain an image payload")

    return os.path.abspath(output_path)
