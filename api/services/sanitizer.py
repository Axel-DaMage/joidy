"""
Input sanitization utilities for Joidy API.

Prevents XSS, injection, and data corruption in user-supplied inputs.
"""

import re

# Dangerous HTML tags/attributes pattern
_SCRIPT_PATTERN = re.compile(
    r"<\s*script[^>]*>.*?</\s*script\s*>",
    re.IGNORECASE | re.DOTALL,
)
_EVENT_HANDLER_PATTERN = re.compile(
    r"\bon\w+\s*=\s*[\"'][^\"']*[\"']",
    re.IGNORECASE,
)

# Max lengths per field type
MAX_TITLE_LENGTH = 500
MAX_CONTENT_LENGTH = 500_000  # 500KB of text
MAX_TAG_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 10_000


def sanitize_html(text: str) -> str:
    """Remove dangerous HTML constructs while preserving markdown."""
    text = _SCRIPT_PATTERN.sub("", text)
    text = _EVENT_HANDLER_PATTERN.sub("", text)
    return text


def sanitize_title(title: str) -> str:
    """Sanitize and validate a title string."""
    title = title.strip()
    if not title:
        raise ValueError("Title cannot be empty")
    if len(title) > MAX_TITLE_LENGTH:
        title = title[:MAX_TITLE_LENGTH]
    return sanitize_html(title)


def sanitize_content(content: str) -> str:
    """Sanitize note/goal content — allows markdown but removes scripts."""
    if len(content) > MAX_CONTENT_LENGTH:
        content = content[:MAX_CONTENT_LENGTH]
    return sanitize_html(content)


def sanitize_tag(tag_name: str) -> str:
    """Sanitize and normalize a tag name."""
    tag_name = tag_name.strip().lower()
    # Only allow alphanumeric, hyphens, underscores, spaces
    tag_name = re.sub(r"[^\w\s\-]", "", tag_name, flags=re.UNICODE)
    if len(tag_name) > MAX_TAG_LENGTH:
        tag_name = tag_name[:MAX_TAG_LENGTH]
    return tag_name


def sanitize_color(color: str) -> str:
    """Validate CSS hex color."""
    color = color.strip()
    if not re.match(r"^#[0-9a-fA-F]{3,8}$", color):
        return "#888888"  # Safe default
    return color


def sanitize_emoji(emoji: str) -> str:
    """Limit emoji field length."""
    return emoji[:20] if emoji else "🔴"
