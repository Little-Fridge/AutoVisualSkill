import os
import re
from urllib.parse import urljoin

import requests
from PIL import Image


def capture_url(url: str, output_path: str, full_page: bool = True) -> str:
    """
    Capture a URL screenshot with Playwright's sync API.

    Saves the screenshot to output_path and returns an absolute path.
    """
    from playwright.sync_api import sync_playwright

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 960})
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.screenshot(path=output_path, full_page=full_page)
        browser.close()
    return os.path.abspath(output_path)


def fetch_url_text(url: str, timeout: int = 20, max_chars: int = 12000) -> str:
    """Fetch visible-ish page text for lightweight URL context."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AutoVisualSkill/0.1; +https://example.invalid/autovisualskill)"
    }
    resp = requests.get(url, timeout=timeout, headers=headers)
    resp.raise_for_status()
    html = resp.text
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text("\n")
    except Exception:
        text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def fetch_url_images(
    url: str,
    output_dir: str,
    *,
    timeout: int = 20,
    max_images: int = 8,
    min_width: int = 180,
    min_height: int = 100,
) -> list[dict]:
    """Extract useful raster images from a tutorial/documentation URL.

    Returns records with local paths plus lightweight semantic metadata. Images
    are source materials, not generated priors; downstream nodes may reuse them
    as visual assets when the webpage itself provides the relevant visual
    demonstration.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AutoVisualSkill/0.1; +https://example.invalid/autovisualskill)"
    }
    resp = requests.get(url, timeout=timeout, headers=headers)
    resp.raise_for_status()

    try:
        from bs4 import BeautifulSoup
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    os.makedirs(output_dir, exist_ok=True)

    records: list[dict] = []
    seen: set[str] = set()
    for img in soup.find_all("img"):
        src = (
            img.get("src")
            or img.get("data-src")
            or img.get("data-original")
            or img.get("data-lazy-src")
        )
        if not src:
            continue

        srcset = img.get("srcset")
        if srcset:
            first_srcset = srcset.split(",")[0].strip().split(" ")[0]
            src = first_srcset or src

        image_url = urljoin(url, src)
        if image_url in seen:
            continue
        seen.add(image_url)

        ext = os.path.splitext(image_url.split("?")[0])[1].lower()
        if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue

        try:
            image_resp = requests.get(image_url, timeout=timeout, headers=headers)
            image_resp.raise_for_status()
        except Exception:
            continue

        raw_path = os.path.join(output_dir, f"url_image_{len(records)}{ext}")
        with open(raw_path, "wb") as f:
            f.write(image_resp.content)

        try:
            with Image.open(raw_path) as pil_img:
                width, height = pil_img.size
                pil_img.verify()
        except Exception:
            try:
                os.remove(raw_path)
            except OSError:
                pass
            continue

        if width < min_width or height < min_height:
            try:
                os.remove(raw_path)
            except OSError:
                pass
            continue

        caption = ""
        parent = img.find_parent("figure")
        if parent is not None:
            caption_tag = parent.find("figcaption")
            if caption_tag is not None:
                caption = re.sub(r"\s+", " ", caption_tag.get_text(" ")).strip()

        records.append(
            {
                "path": os.path.abspath(raw_path),
                "url": image_url,
                "alt": re.sub(r"\s+", " ", img.get("alt", "")).strip(),
                "caption": caption,
                "width": width,
                "height": height,
            }
        )
        if len(records) >= max_images:
            break

    return records
