"""
research/fields.py

Database-agnostic VectorField.

On PostgreSQL with pgvector: creates a proper vector(N) column.
On SQLite (unit-test fallback): creates a TEXT column; vectors round-trip
as JSON strings so field access still returns Python lists.

The migration file always references *this* class, so it works in both
environments at runtime — no separate test-migration needed.
"""

import json

from django.db import models


class VectorField(models.Field):
    """
    vector(dimensions) on Postgres / TEXT on SQLite.

    Usage::

        from research.fields import VectorField
        embedding = VectorField(dimensions=384, null=True)
    """

    def __init__(self, *args, dimensions: int = 384, **kwargs):
        self.dimensions = dimensions
        kwargs.setdefault("null", True)
        kwargs.setdefault("blank", True)
        super().__init__(*args, **kwargs)

    # ------------------------------------------------------------------
    # Django internal plumbing
    # ------------------------------------------------------------------

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        # Always serialise as THIS class so migrations are env-agnostic.
        path = "research.fields.VectorField"
        kwargs["dimensions"] = self.dimensions
        return name, path, args, kwargs

    def db_type(self, connection):
        if connection.vendor == "postgresql":
            return f"vector({self.dimensions})"
        # SQLite and everything else
        return "text"

    # ------------------------------------------------------------------
    # Python ↔ DB conversion
    # ------------------------------------------------------------------

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        if isinstance(value, list):
            return value
        # SQLite stores as JSON string
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value

    def to_python(self, value):
        if value is None or isinstance(value, list):
            return value
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value

    def get_prep_value(self, value):
        if value is None:
            return None
        if isinstance(value, list):
            if self.dimensions and len(value) != self.dimensions:
                raise ValueError(
                    f"VectorField expects {self.dimensions} dimensions, "
                    f"got {len(value)}"
                )
            # Postgres driver accepts a Python list directly for vector columns;
            # SQLite needs a JSON string.
            return value  # Django/psycopg2 handles the Postgres cast
        return value

    def get_db_prep_value(self, value, connection, prepared=False):
        value = self.get_prep_value(value)
        if value is None:
            return None
        if connection.vendor != "postgresql" and isinstance(value, list):
            return json.dumps(value)
        return value
