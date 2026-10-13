from pydantic import BaseModel, Field, field_validator

class UpdateBundle(BaseModel):
    person: str = Field(min_length=1)
    project: str = Field(min_length=1)
    done: list[str] = Field(default_factory=list)
    next: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    due_dates: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)

    @field_validator('person', mode='before')
    @classmethod
    def normalize_person(cls, value):
        return value.strip() if isinstance(value, str) and value.strip() else 'Unknown'

    @field_validator('project', mode='before')
    @classmethod
    def normalize_project(cls, value):
        return value.strip() if isinstance(value, str) and value.strip() else 'Unassigned'

    @field_validator('done', 'next', 'blockers', 'due_dates', mode='before')
    @classmethod
    def normalize_list_fields(cls, value):
        if value is None: return []
        if isinstance(value, str): return [value] if value.strip() else []
        return value
