from pydantic import BaseModel, ConfigDict, Field


class AssetEntry(BaseModel):
    model_config = ConfigDict(strict=True)

    filename: str
    prior_name: str = ""
    prior_kind: str = "static"
    strategy: str
    description: str
    width: int
    height: int


class AssetManifest(BaseModel):
    model_config = ConfigDict(strict=True)

    skill_name: str
    skill_type: str = ""
    visual_skill_kind: str = ""
    prior_kind: str = ""
    bottleneck: str = ""
    visual_prior_specs: list[dict] = Field(default_factory=list)
    binding_protocol: dict = Field(default_factory=dict)
    runtime_protocol: dict = Field(default_factory=dict)
    usage_constraints: list[str] = Field(default_factory=list)
    assets: list[AssetEntry]
