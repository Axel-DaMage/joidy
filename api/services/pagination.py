"""Pagination metadata helpers for list endpoints (#579).

Provides non-breaking pagination metadata via HTTP headers so that:
- Existing clients that expect a plain JSON array continue to work.
- New clients can read `X-Total-Count` and `X-Has-More` headers to
  determine if more data is available without making an extra request.

Header conventions:
- `X-Total-Count`: total number of items matching the query (before pagination).
- `X-Has-More`: "true" if there are more items beyond the current page.
- `X-Page-Size`: the limit applied to this response.
- `X-Page-Offset`: the offset applied to this response.
"""

from fastapi import Response


def add_pagination_headers(
    response: Response,
    total: int,
    limit: int,
    offset: int,
) -> None:
    """Add X-Total-Count, X-Has-More, X-Page-Size, X-Page-Offset headers.

    Args:
        response: The FastAPI Response object to attach headers to.
        total: Total number of items matching the query (before pagination).
        limit: The limit applied to this response.
        offset: The offset applied to this response.
    """
    has_more = (offset + limit) < total
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Has-More"] = "true" if has_more else "false"
    response.headers["X-Page-Size"] = str(limit)
    response.headers["X-Page-Offset"] = str(offset)
