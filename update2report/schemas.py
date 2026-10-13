from pydantic import BaseModel, Field

class UpdateBundle(BaseModel):
    person: str = Field(min_length=1)
    project: str = Field(min_length=1)
    done: list[str] = Field(default_factory=list)
    next: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    due_dates: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
