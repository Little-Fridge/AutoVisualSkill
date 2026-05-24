from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VisualPriorSpec(BaseModel):
    """Describe a reusable visual prior.

    Static priors produce reusable image assets. Dynamic priors describe a
    runtime visual-state protocol, such as rendering counted anchors back onto
    the task image. The authoring agent records the dynamic protocol but does
    not execute it.
    """

    model_config = ConfigDict(strict=True)

    name: str
    prior_kind: Literal["static", "dynamic"] = "static"
    strategy: Literal["source", "crop", "overlay", "search", "draw", "api", "renderer"]
    content_description: str

    # crop strategy fields.
    source_frame_index: int = -1
    crop_region_description: str = ""

    # search strategy fields.
    search_query: str = ""

    # draw strategy fields.
    draw_instructions: str = ""

    # visual-first design contract fields. These keep prior images focused on
    # information that is genuinely easier to express spatially than in prose.
    visual_rationale: str = ""
    visual_encodings: list[str] = []
    text_exclusions: list[str] = []
    forbidden_elements: list[str] = []
    max_text_tokens: int = 12

    # external image-generation API strategy fields.
    image_generation_prompt: str = ""
    image_generation_model: str = ""
    image_generation_size: str = "1024x1024"

    # dynamic renderer strategy fields.
    renderer_name: str = ""
    renderer_description: str = ""
    renderer_inputs: list[str] = []
    renderer_outputs: list[str] = []


class ParameterDef(BaseModel):
    """One input parameter for the generated skill."""

    model_config = ConfigDict(strict=True)

    name: str
    type: str
    description: str


class BindingProtocol(BaseModel):
    """How text rules, visual priors, and task inputs are bound together."""

    model_config = ConfigDict(strict=True)

    image_roles: list[str] = []
    coordinate_system: str = ""
    text_to_visual_binding: list[str] = []
    task_binding_rules: list[str] = []
    anti_leakage_rules: list[str] = []


class RuntimeProtocol(BaseModel):
    """How an external agent should execute the skill."""

    model_config = ConfigDict(strict=True)

    mode: Literal["single_turn", "iterative_loop"] = "single_turn"
    state_schema: str = ""
    update_rule: str = ""
    stop_condition: str = ""
    renderer_spec: str = ""


class SkillBlueprint(BaseModel):
    """The complete skill blueprint produced by the design_skill node."""

    model_config = ConfigDict(strict=True)

    name: str
    skill_type: Literal["text", "visual"]
    visual_skill_kind: Literal["text", "static", "dynamic", "interleaved"] = "text"
    prior_kind: Literal["none", "static", "dynamic"] = "none"
    bottleneck: Literal["none", "protocol_ambiguity", "perceptual_tracking", "mixed"] = "none"
    description: str
    declarative_textual_logic: list[str] = []
    visual_prior_specs: list[VisualPriorSpec]
    binding_protocol: BindingProtocol = Field(default_factory=BindingProtocol)
    runtime_protocol: RuntimeProtocol = Field(default_factory=RuntimeProtocol)
    parameters: list[ParameterDef]
    execution_steps: list[str]
    usage_constraints: list[str] = []
    output_format: str
