"""Parsing ids that arrive in paths and bodies."""

import uuid

from fastapi import HTTPException


def path_uuid(value: str, what: str) -> uuid.UUID:
    """`value` as a UUID, or a 404 naming `what` when it cannot be one.

    The SQLite models key rows by UUID. Without this, a malformed id from a
    stale link or a typo raised ValueError and became a 500.
    """
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=404, detail=f"{what} not found") from None
