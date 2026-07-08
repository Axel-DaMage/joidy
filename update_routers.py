import os
import re

# Update notes.py
with open('api/routers/notes.py', 'r') as f:
    content = f.read()

if 'from services.sanitizer import sanitize_title, sanitize_content' not in content:
    content = content.replace('from pydantic import BaseModel, field_validator', 'from pydantic import BaseModel, field_validator\nfrom services.sanitizer import sanitize_title, sanitize_content')

# Replace the field_validators logic to call sanitize
content = re.sub(
    r'@field_validator\("title"\)\s+@classmethod\s+def title_not_empty\(cls, v: str\) -> str:\s+v = v\.strip\(\)\s+if not v:\s+raise ValueError\("Title cannot be empty"\)\s+if len\(v\) > 500:\s+raise ValueError\("Title must be 500 characters or fewer"\)\s+return v',
    '@field_validator("title")\n    @classmethod\n    def title_not_empty(cls, v: str) -> str:\n        return sanitize_title(v)',
    content
)

content = re.sub(
    r'@field_validator\("content"\)\s+@classmethod\s+def content_max_length\(cls, v: str\) -> str:\s+if len\(v\) > 500_000:\s+raise ValueError\("Content must be 500,000 characters or fewer"\)\s+return v',
    '@field_validator("content")\n    @classmethod\n    def content_max_length(cls, v: str) -> str:\n        return sanitize_content(v)',
    content
)

content = re.sub(
    r'@field_validator\("title"\)\s+@classmethod\s+def title_not_empty\(cls, v: str \| None\) -> str \| None:\s+if v is None:\s+return v\s+v = v\.strip\(\)\s+if not v:\s+raise ValueError\("Title cannot be empty"\)\s+if len\(v\) > 500:\s+raise ValueError\("Title must be 500 characters or fewer"\)\s+return v',
    '@field_validator("title")\n    @classmethod\n    def title_not_empty(cls, v: str | None) -> str | None:\n        if v is None:\n            return v\n        return sanitize_title(v)',
    content
)

content = re.sub(
    r'@field_validator\("content"\)\s+@classmethod\s+def content_max_length\(cls, v: str \| None\) -> str \| None:\s+if v is not None and len\(v\) > 500_000:\s+raise ValueError\("Content must be 500,000 characters or fewer"\)\s+return v',
    '@field_validator("content")\n    @classmethod\n    def content_max_length(cls, v: str | None) -> str | None:\n        if v is None:\n            return v\n        return sanitize_content(v)',
    content
)

with open('api/routers/notes.py', 'w') as f:
    f.write(content)


# Update goals.py
with open('api/routers/goals.py', 'r') as f:
    content = f.read()

if 'from services.sanitizer import sanitize_title, sanitize_content' not in content:
    content = content.replace('from pydantic import BaseModel, Field, field_validator', 'from pydantic import BaseModel, Field, field_validator\nfrom services.sanitizer import sanitize_title, sanitize_content')

content = re.sub(
    r'@field_validator\("title"\)\s+@classmethod\s+def title_not_empty\(cls, v: str\) -> str:\s+v = v\.strip\(\)\s+if not v:\s+raise ValueError\("Title cannot be empty"\)\s+if len\(v\) > 255:\s+raise ValueError\("Title must be less than 255 characters"\)\s+return v',
    '@field_validator("title")\n    @classmethod\n    def title_not_empty(cls, v: str) -> str:\n        return sanitize_title(v)',
    content
)

content = re.sub(
    r'@field_validator\("description"\)\s+@classmethod\s+def description_length\(cls, v: str \| None\) -> str \| None:\s+if v and len\(v\) > 10_000:\s+raise ValueError\("Description too long"\)\s+return v',
    '@field_validator("description")\n    @classmethod\n    def description_length(cls, v: str | None) -> str | None:\n        if v is None:\n            return v\n        return sanitize_content(v)',
    content
)

content = re.sub(
    r'@field_validator\("title"\)\s+@classmethod\s+def title_not_empty\(cls, v: str \| None\) -> str \| None:\s+if v is None:\s+return v\s+v = v\.strip\(\)\s+if not v:\s+raise ValueError\("Title cannot be empty"\)\s+return v',
    '@field_validator("title")\n    @classmethod\n    def title_not_empty(cls, v: str | None) -> str | None:\n        if v is None:\n            return v\n        return sanitize_title(v)',
    content
)

with open('api/routers/goals.py', 'w') as f:
    f.write(content)

