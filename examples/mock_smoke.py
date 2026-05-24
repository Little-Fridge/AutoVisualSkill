"""Offline smoke test for AutoVisualSkill.

This script uses the bundled mock subagent backend, so it does not require an
API key. It verifies that the graph can produce the standard artifact files.
"""

from __future__ import annotations

import os
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from autovisualskill.main import run


def main() -> None:
    os.environ["AUTOVISUALSKILL_LLM_BACKEND"] = "subagent"
    os.environ["AUTOVISUALSKILL_SUBAGENT_CMD"] = f"{sys.executable} {ROOT / 'tools' / 'mock_subagent_backend.py'}"

    output_dir = ROOT / "skill_output" / "mock_smoke"
    result = run(
        user_goal="Create a concise skill for checking whether an experiment report is reproducible.",
        input_files=[],
        output_dir=str(output_dir),
        enable_web_research=False,
    )

    required_files = [
        "skill.md",
        "manifest.json",
        "assets_manifest.json",
        "run_config.json",
        "web_sources.json",
        "provenance.json",
        "warnings.json",
        "errors.json",
        "final_state.json",
    ]
    required_dirs = ["assets"]
    missing = [name for name in required_files if not (output_dir / name).exists()]
    missing += [name for name in required_dirs if not (output_dir / name).is_dir()]
    if missing:
        raise SystemExit(f"Smoke test failed; missing files: {missing}")

    errors = json.loads((output_dir / "errors.json").read_text(encoding="utf-8"))
    warnings = json.loads((output_dir / "warnings.json").read_text(encoding="utf-8"))
    if errors or warnings:
        raise SystemExit(f"Smoke test failed; errors={errors}, warnings={warnings}")

    print(f"Smoke test passed. Artifact directory: {result['output_dir']}")


if __name__ == "__main__":
    main()
