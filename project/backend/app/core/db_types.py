"""
Database Type Compatibility
===========================
Portable types that work with both PostgreSQL and SQLite.
"""

import json
from typing import Any

from sqlalchemy import TypeDecorator, String, Text
from sqlalchemy.types import CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB as PG_JSONB


class GUID(TypeDecorator):
    """
    Platform-independent GUID type.
    Uses PostgreSQL's UUID type when available, otherwise stores as CHAR(32).
    """
    impl = CHAR
    cache_ok = True
    
    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))
    
    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            return str(value)
    
    def process_result_value(self, value, dialect):
        if value is None:
            return value
        import uuid
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


class JSON(TypeDecorator):
    """
    Platform-independent JSON type.
    Uses PostgreSQL's JSONB when available, otherwise stores as Text with JSON encoding.
    """
    impl = Text
    cache_ok = True
    
    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_JSONB())
        else:
            return dialect.type_descriptor(Text())
    
    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value
        return json.dumps(value)
    
    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, dict) or isinstance(value, list):
            return value
        return json.loads(value)
