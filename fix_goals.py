import re

with open('api/routers/goals.py', 'r') as f:
    content = f.read()

# Add import if missing
if 'from services.sanitizer import' not in content:
    content = content.replace('from pydantic import BaseModel, field_validator', 'from pydantic import BaseModel, field_validator\nfrom services.sanitizer import sanitize_title, sanitize_content, sanitize_color, sanitize_emoji')

content = re.sub(
    r'@field_validator\("title"\)\s+@classmethod\s+def title_not_empty\(cls, v: str\) -> str:\s+v = v\.strip\(\)\s+if not v:\s+raise ValueError\("Title cannot be empty"\)\s+if len\(v\) > 500:\s+raise ValueError\("Title must be 500 characters or fewer"\)\s+return v',
    '@field_validator("title")\n    @classmethod\n    def title_not_empty(cls, v: str) -> str:\n        return sanitize_title(v)',
    content
)

content = re.sub(
    r'@field_validator\("color"\)\s+@classmethod\s+def validate_color\(cls, v: str\) -> str:\s+if not re\.match\(r\'\^#\[0-9a-fA-F\]\{3,8\}\$\', v\.strip\(\)\):\s+return "#c8a96e"\s+return v\.strip\(\)',
    '@field_validator("color")\n    @classmethod\n    def validate_color(cls, v: str) -> str:\n        return sanitize_color(v)',
    content
)

content = re.sub(
    r'@field_validator\("fail_emoji"\)\s+@classmethod\s+def validate_emoji\(cls, v: str\) -> str:\s+return v\[:20\] if v else "🔴"',
    '@field_validator("fail_emoji")\n    @classmethod\n    def validate_emoji(cls, v: str) -> str:\n        return sanitize_emoji(v)',
    content
)

content = re.sub(
    r'@field_validator\("description"\)\s+@classmethod\s+def validate_description\(cls, v: str\) -> str:\s+if len\(v\) > 10_000:\s+raise ValueError\("Description must be 10,000 characters or fewer"\)\s+return v',
    '@field_validator("description")\n    @classmethod\n    def validate_description(cls, v: str) -> str:\n        return sanitize_content(v)',
    content
)

# For GoalUpdate:
content = re.sub(
    r'@field_validator\("title"\)\s+@classmethod\s+def title_not_empty\(cls, v: str \| None\) -> str \| None:\s+if v is None:\s+return v\s+v = v\.strip\(\)\s+if not v:\s+raise ValueError\("Title cannot be empty"\)\s+if len\(v\) > 500:\s+raise ValueError\("Title must be 500 characters or fewer"\)\s+return v',
    '@field_validator("title")\n    @classmethod\n    def title_not_empty(cls, v: str | None) -> str | None:\n        if v is None:\n            return v\n        return sanitize_title(v)',
    content
)

content = re.sub(
    r'@field_validator\("description"\)\s+@classmethod\s+def validate_description\(cls, v: str \| None\) -> str \| None:\s+if v is not None and len\(v\) > 10_000:\s+raise ValueError\("Description must be 10,000 characters or fewer"\)\s+return v',
    '@field_validator("description")\n    @classmethod\n    def validate_description(cls, v: str | None) -> str | None:\n        if v is None:\n            return v\n        return sanitize_content(v)',
    content
)

content = re.sub(
    r'@field_validator\("color"\)\s+@classmethod\s+def validate_color\(cls, v: str \| None\) -> str \| None:\s+if v is None:\s+return v\s+if not re\.match\(r\'\^#\[0-9a-fA-F\]\{3,8\}\$\', v\.strip\(\)\):\s+return "#c8a96e"\s+return v\.strip\(\)',
    '@field_validator("color")\n    @classmethod\n    def validate_color(cls, v: str | None) -> str | None:\n        if v is None:\n            return v\n        return sanitize_color(v)',
    content
)

content = re.sub(
    r'@field_validator\("fail_emoji"\)\s+@classmethod\s+def validate_emoji\(cls, v: str \| None\) -> str \| None:\s+if v is None:\s+return v\s+return v\[:20\] if v else "🔴"',
    '@field_validator("fail_emoji")\n    @classmethod\n    def validate_emoji(cls, v: str | None) -> str | None:\n        if v is None:\n            return v\n        return sanitize_emoji(v)',
    content
)

with open('api/routers/goals.py', 'w') as f:
    f.write(content)
