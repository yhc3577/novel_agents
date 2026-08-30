"""审查/去味链路输出契约（D8：US-21/22，§5.1 契约清单）。"""

from pydantic import BaseModel, Field


class ReviewFinding(BaseModel):
    reviewer: str = Field(default="", description="plot/character/style/rhythm")
    severity: str = Field(..., pattern="^(blocking|warning)$")
    type: str = Field(..., min_length=1)
    quote: str = Field(default="")
    reason: str = Field(..., min_length=1)
    suggestion: str = Field(default="")


class ReviewerOutput(BaseModel):
    findings: list[ReviewFinding] = Field(default_factory=list)


class ReviewSummary(BaseModel):
    score: int = Field(..., ge=0, le=100)
    verdict: str = Field(..., min_length=1)
    must_fix: list[str] = Field(default_factory=list)
    advice: str = Field(default="")


class DeslopOut(BaseModel):
    rewritten: str = Field(..., min_length=1)
    note: str = Field(default="")
