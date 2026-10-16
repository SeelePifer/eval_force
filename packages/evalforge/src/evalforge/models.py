from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExpectedCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    arguments_subset: dict[str, Any] = Field(default_factory=dict)


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["qa", "rag", "tools"] = "qa"
    input: str
    expected: str
    expected_chunk_ids: list[str] = Field(default_factory=list)
    corpus: str | None = None
    expected_calls: list[ExpectedCall] = Field(default_factory=list)
    tool_stubs: dict[str, dict[str, str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_type_fields(self) -> Self:
        if self.type == "rag" and (not self.corpus or not self.expected_chunk_ids):
            raise ValueError("rag cases require corpus and expected_chunk_ids")
        if self.type == "tools" and (not self.expected_calls or not self.tool_stubs):
            raise ValueError("tool cases require expected_calls and tool_stubs")
        return self


class TargetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    provider: Literal["mock", "openai"]
    model: str
    prompt: str
    fixtures: str | None = None
    base_url: str | None = None
    api_key_env: str = "OPENAI_API_KEY"


class GateConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quality_min: float = 0.8
    quality_drop_max: float = 0.05
    cost_increase_max: float = 0.2
    latency_p95_ms: float = 4000


class JudgeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    provider: Literal["mock", "openai"] = "mock"
    model: str = "mock-judge"
    rubric_version: str = "v1"
    fixtures: str | None = None
    fixture_target: str = "judge"
    base_url: str | None = None
    api_key_env: str = "OPENAI_API_KEY"


class EvalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: str
    targets: list[TargetConfig]
    gate: GateConfig = Field(default_factory=GateConfig)
    baseline: str | None = None
    pricing: str = "pricing.yaml"
    seed: int = 0
    temperature: float = 0
    top_k: int = 3
    judge: JudgeConfig = Field(default_factory=JudgeConfig)

    @model_validator(mode="after")
    def check_targets(self) -> Self:
        names = [target.name for target in self.targets]
        if len(names) != len(set(names)):
            raise ValueError("target names must be unique")
        if not names:
            raise ValueError("at least one target is required")
        return self


class ModelPrice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_per_million: float
    output_per_million: float


class PricingTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    models: dict[str, ModelPrice]


class Chunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    text: str


class CaseScore(BaseModel):
    normalized_exact: float
    contains: float
    token_f1: float
    answer_quality: float
    quality: float
    retrieval_recall: float | None = None
    tool_match: float | None = None


class ToolCallRecord(BaseModel):
    name: str
    arguments: dict[str, Any]


class CaseResult(BaseModel):
    case_id: str
    case_type: Literal["qa", "rag", "tools"]
    output: str
    expected: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    cost_usd: float
    scores: CaseScore
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    judge_score: float | None = None


class TargetSummary(BaseModel):
    quality: float
    cost_usd: float
    prompt_tokens: int
    completion_tokens: int
    latency_p95_ms: float
    retrieval_recall: float | None = None
    tool_match: float | None = None


class GateReason(BaseModel):
    code: str
    message: str


class GateVerdict(BaseModel):
    passed: bool
    reasons: list[GateReason] = Field(default_factory=list)


class TargetManifest(BaseModel):
    name: str
    model: str
    provider: str
    prompt_sha256: str
    temperature: float


class Manifest(BaseModel):
    dataset_sha256: str
    pricing_version: str
    seed: int
    temperature: float
    judge_rubric_version: str | None = None
    targets: list[TargetManifest]


class TargetResult(BaseModel):
    name: str
    model: str
    prompt_sha256: str
    summary: TargetSummary
    gate: GateVerdict
    cases: list[CaseResult]


class EvalRun(BaseModel):
    manifest: Manifest
    passed: bool
    targets: list[TargetResult]
