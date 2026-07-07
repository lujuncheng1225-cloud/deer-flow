from __future__ import annotations


def normalize_postgres_conn_string(conn_string: str) -> str:
    """Return a psycopg/libpq-compatible DSN from common SQLAlchemy URLs."""

    if conn_string.startswith("postgresql+"):
        return "postgresql://" + conn_string.split("://", 1)[1]
    if conn_string.startswith("postgres+"):
        return "postgresql://" + conn_string.split("://", 1)[1]
    return conn_string
