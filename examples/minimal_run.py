"""Minimal live AutoVisualSkill example.

Set LLM_API_KEY and optionally LLM_BASE_URL / LLM_MODEL_NAME before running.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from autovisualskill.main import run


result = run(
    user_goal="Generate a visual skill for dense object counting with dynamic point anchors.",
    input_files=[],
    output_root=str(ROOT / "skill_output"),
    temp_root=str(ROOT / ".autovisualskill_tmp"),
    enable_web_research=False,
)

print(f"Skill artifact saved to: {result['output_dir']}")
