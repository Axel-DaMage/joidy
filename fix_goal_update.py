import re

with open('api/routers/goals.py', 'r') as f:
    content = f.read()

# Add validators to GoalUpdate
goal_update_class = """class GoalUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    temporality: GoalTemporality | None = None
    measurement_type: GoalMeasurement | None = None
    target_value: float | None = None
    current_value: float | None = None
    state: GoalState | None = None
    fail_config: GoalFailConfig | None = None
    fail_emoji: str | None = None
    color: str | None = None
    theme: str | None = None
    note_id: int | None = None
    tag_id: int | None = None
    max_assignment_days: int | None = None
    content: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return sanitize_title(v)

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return sanitize_content(v)

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return sanitize_color(v)

    @field_validator("fail_emoji")
    @classmethod
    def validate_emoji(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return sanitize_emoji(v)

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return sanitize_content(v)
"""

content = re.sub(
    r'class GoalUpdate\(BaseModel\):.*?content: str \| None = None',
    goal_update_class,
    content,
    flags=re.DOTALL
)

with open('api/routers/goals.py', 'w') as f:
    f.write(content)
