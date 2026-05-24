import os

import requests


def search_images(query: str, max_results: int = 5) -> list[dict]:
    """
    Search images through Tavily.

    Returns [{"url": str, "title": str, "description": str}, ...].
    """
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        return []
    from tavily import TavilyClient

    client = TavilyClient(api_key=api_key)
    results = client.search(
        query=query,
        search_depth="basic",
        include_images=True,
        max_results=max_results,
    )

    images: list[dict] = []
    for img_url in results.get("images", []):
        images.append({"url": img_url, "title": "", "description": query})

    for result in results.get("results", []):
        url = result.get("url", "")
        if url.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            images.append(
                {
                    "url": url,
                    "title": result.get("title", ""),
                    "description": result.get("content", ""),
                }
            )

    return images[:max_results]


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """
    Search general web context through Tavily.

    Returns [{"url": str, "title": str, "content": str}, ...].
    """
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        return []
    from tavily import TavilyClient

    client = TavilyClient(api_key=api_key)
    results = client.search(
        query=query,
        search_depth="basic",
        include_answer=True,
        include_images=False,
        max_results=max_results,
    )

    items: list[dict] = []
    answer = results.get("answer", "")
    if answer:
        items.append({"url": "", "title": "Tavily answer", "content": answer})

    for result in results.get("results", []):
        items.append(
            {
                "url": result.get("url", ""),
                "title": result.get("title", ""),
                "content": result.get("content", ""),
            }
        )

    return items[:max_results]


def download_image(url: str, output_path: str, timeout: int = 15) -> str:
    """Download an image to disk and return its absolute path."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    resp = requests.get(url, timeout=timeout, stream=True)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)
    return os.path.abspath(output_path)
