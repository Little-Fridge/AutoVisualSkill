from autovisualskill.media.web_search import search_web
from autovisualskill.state import GraphState
from autovisualskill.utils import append_records, issue_record, provenance_record


def _queries_from_notes(user_goal: str, notes: list[str], max_queries: int) -> list[str]:
    queries: list[str] = []
    for note in notes:
        note = note.strip()
        if note:
            queries.append(f"{user_goal} {note}")
    if not queries:
        queries.append(user_goal)
    return queries[:max_queries]


def run(state: GraphState) -> dict:
    config = state.get("run_config", {})
    max_results = int(config.get("max_web_results", 5))
    queries = state.get("search_queries") or _queries_from_notes(
        state["user_goal"], state.get("missing_context_notes", []), max_results
    )
    queries = queries[:max_results]

    sources: list[dict] = []
    snippets: list[str] = []
    warnings: list[dict] = []

    for query in queries:
        try:
            results = search_web(query, max_results=max(1, max_results // max(len(queries), 1)))
        except Exception as exc:
            warnings.append(issue_record("research_context", "Web search failed", query=query, error=str(exc)))
            continue

        for result in results:
            if len(sources) >= max_results:
                break
            source = {
                "query": query,
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "content": result.get("content", ""),
            }
            sources.append(source)
            snippets.append(
                f"[{len(sources)}] {source['title']}\nURL: {source['url']}\nSummary: {source['content']}"
            )

    if not sources and not warnings:
        warnings.append(
            issue_record(
                "research_context",
                "No web sources collected",
                reason="Missing TAVILY_API_KEY or search returned no results",
            )
        )

    return {
        "web_context": "\n\n".join(snippets),
        "web_sources": sources,
        "warnings": append_records(state, "warnings", warnings),
        "provenance": append_records(
            state,
            "provenance",
            [provenance_record("research_context", "searched_web", queries=queries, source_count=len(sources))],
        ),
    }
