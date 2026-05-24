import json
import os
import shutil

from PIL import Image

from autovisualskill.models.manifest import AssetEntry, AssetManifest
from autovisualskill.models.skill import SkillBlueprint
from autovisualskill.state import GraphState
from autovisualskill.utils import append_records, provenance_record, sanitize_filename


def _copy_asset(path: str, assets_dir: str, index: int) -> str:
    filename = sanitize_filename(os.path.basename(path), default=f"asset_{index}", suffix=".png")
    dest = os.path.join(assets_dir, filename)
    if os.path.exists(dest):
        stem, ext = os.path.splitext(filename)
        filename = f"{stem}_{index}{ext}"
        dest = os.path.join(assets_dir, filename)
    shutil.copy2(path, dest)
    return filename


def run(state: GraphState) -> dict:
    blueprint = SkillBlueprint.model_validate_json(state["skill_blueprint"])

    config = state.get("run_config", {})
    output_dir = config.get("output_dir") or state.get("output_dir") or os.path.join(os.getcwd(), "skill_output")
    assets_dir = os.path.join(output_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)

    with open(os.path.join(output_dir, "skill.md"), "w", encoding="utf-8") as f:
        f.write(state["skill_md_content"])

    entries: list[AssetEntry] = []
    static_specs = [
        spec
        for spec in blueprint.visual_prior_specs
        if spec.prior_kind == "static" and spec.strategy != "renderer"
    ]
    for i, path in enumerate(state["visual_prior_paths"]):
        filename = _copy_asset(path, assets_dir, i)
        dest = os.path.join(assets_dir, filename)

        with Image.open(dest) as img:
            width, height = img.size

        strategy = "draw"
        prior_name = ""
        prior_kind = "static"
        if i < len(static_specs):
            strategy = static_specs[i].strategy
            prior_name = static_specs[i].name
            prior_kind = static_specs[i].prior_kind

        desc = state["visual_prior_descriptions"][i] if i < len(state["visual_prior_descriptions"]) else ""

        entries.append(
            AssetEntry(
                filename=filename,
                prior_name=prior_name,
                prior_kind=prior_kind,
                strategy=strategy,
                description=desc,
                width=width,
                height=height,
            )
        )

    manifest = AssetManifest(
        skill_name=blueprint.name,
        skill_type=blueprint.skill_type,
        visual_skill_kind=blueprint.visual_skill_kind,
        prior_kind=blueprint.prior_kind,
        bottleneck=blueprint.bottleneck,
        visual_prior_specs=[spec.model_dump() for spec in blueprint.visual_prior_specs],
        binding_protocol=blueprint.binding_protocol.model_dump(),
        runtime_protocol=blueprint.runtime_protocol.model_dump(),
        usage_constraints=blueprint.usage_constraints,
        assets=entries,
    )

    with open(os.path.join(output_dir, "manifest.json"), "w", encoding="utf-8") as f:
        f.write(manifest.model_dump_json(indent=2))

    with open(os.path.join(output_dir, "assets_manifest.json"), "w", encoding="utf-8") as f:
        f.write(manifest.model_dump_json(indent=2))

    provenance = append_records(
        state,
        "provenance",
        [provenance_record("package_artifact", "packaged_artifact", output_dir=os.path.abspath(output_dir))],
    )
    final_state = {**state, "output_dir": os.path.abspath(output_dir), "provenance": provenance}
    for name, payload in {
        "run_config.json": config,
        "web_sources.json": state.get("web_sources", []),
        "provenance.json": provenance,
        "warnings.json": state.get("warnings", []),
        "errors.json": state.get("errors", []),
        "final_state.json": final_state,
    }.items():
        with open(os.path.join(output_dir, name), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    return {"output_dir": os.path.abspath(output_dir), "provenance": provenance}
