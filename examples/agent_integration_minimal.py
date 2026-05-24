"""Build a minimal VLM-agent payload from an AutoVisualSkill artifact.

This example does not call any model provider. It shows the adapter layer that
most downstream agents need: read skill.md, read manifest.json, collect assets,
and decide how the generated skill should be attached to a VLM call.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_skill_artifact(skill_dir: Path) -> dict[str, Any]:
    """Load the generated skill directory without project-specific imports."""
    manifest_path = skill_dir / "manifest.json"
    skill_path = skill_dir / "skill.md"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest.json: {manifest_path}")
    if not skill_path.exists():
        raise FileNotFoundError(f"Missing skill.md: {skill_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    skill_md = skill_path.read_text(encoding="utf-8")
    assets = []
    for item in manifest.get("assets", []):
        asset_path = skill_dir / "assets" / item["filename"]
        if asset_path.exists():
            assets.append(
                {
                    "path": str(asset_path),
                    "prior_name": item.get("prior_name", ""),
                    "prior_kind": item.get("prior_kind", ""),
                    "strategy": item.get("strategy", ""),
                    "description": item.get("description", ""),
                    "width": item.get("width"),
                    "height": item.get("height"),
                }
            )

    return {"skill_dir": str(skill_dir), "skill_md": skill_md, "manifest": manifest, "assets": assets}


def infer_visual_skill_kind(manifest: dict[str, Any]) -> str:
    kind = manifest.get("visual_skill_kind") or manifest.get("skill_type") or ""
    prior_kind = manifest.get("prior_kind") or ""
    if kind in {"static", "dynamic", "interleaved", "text"}:
        return kind
    if prior_kind == "dynamic":
        return "dynamic"
    if prior_kind == "static":
        return "static"
    return "text"


def build_agent_payload(artifact: dict[str, Any], task_image: str | None, user_query: str) -> dict[str, Any]:
    manifest = artifact["manifest"]
    kind = infer_visual_skill_kind(manifest)
    prior_kind = manifest.get("prior_kind", "")

    messages = [
        {
            "role": "system",
            "content": (
                "You are a VLM agent using an AutoVisualSkill artifact. "
                "Treat skill.md as the task-specific visual reasoning protocol. "
                "Use manifest.json as integration metadata, not as user-facing prose."
            ),
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_query},
                {"type": "text", "text": "Generated skill.md:\n\n" + artifact["skill_md"]},
            ],
        },
    ]

    if task_image:
        messages[1]["content"].append({"type": "image_path", "path": task_image})

    for asset in artifact["assets"]:
        messages[1]["content"].append(
            {
                "type": "image_path",
                "path": asset["path"],
                "name": asset["prior_name"],
                "description": asset["description"],
            }
        )

    runtime_hint = {
        "static": (
            "Attach the visual-prior assets with the task image in one VLM call. "
            "Ask the model to apply the visual convention shown by the prior."
        ),
        "dynamic": (
            "Run an outer loop. After each VLM call, parse the model's state update, "
            "render that state onto the original task image, then send the updated "
            "image into the next call."
        ),
        "interleaved": (
            "Preserve the order of frames or screenshots. Require each reasoning step "
            "to cite or stay adjacent to the visual evidence it depends on."
        ),
        "text": "No visual prior is required; use skill.md as a text skill.",
    }.get(kind, "Use skill.md and manifest.json as the generated skill contract.")

    return {
        "visual_skill_kind": kind,
        "prior_kind": prior_kind,
        "skill_name": manifest.get("skill_name", ""),
        "runtime_hint": runtime_hint,
        "runtime_protocol": manifest.get("runtime_protocol", {}),
        "binding_protocol": manifest.get("binding_protocol", {}),
        "usage_constraints": manifest.get("usage_constraints", []),
        "asset_count": len(artifact["assets"]),
        "messages": messages,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_dir", type=Path, help="Generated skill directory containing skill.md and manifest.json.")
    parser.add_argument("--task-image", default=None, help="Optional user task image to attach to the VLM payload.")
    parser.add_argument(
        "--query",
        default="Apply this generated visual skill to the attached task.",
        help="User query to include in the VLM payload.",
    )
    args = parser.parse_args()

    artifact = load_skill_artifact(args.skill_dir)
    payload = build_agent_payload(artifact, args.task_image, args.query)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
