from __future__ import annotations

import importlib.util
from pathlib import Path

POSTGRES_DSN_PATH = Path(__file__).resolve().parents[1] / "packages" / "harness" / "deerflow" / "runtime" / "postgres_dsn.py"

spec = importlib.util.spec_from_file_location("deerflow_postgres_dsn", POSTGRES_DSN_PATH)
assert spec is not None and spec.loader is not None
postgres_dsn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(postgres_dsn)
normalize_postgres_conn_string = postgres_dsn.normalize_postgres_conn_string


def test_normalize_postgres_conn_string_strips_sqlalchemy_driver_suffix():
    assert normalize_postgres_conn_string("postgresql+psycopg://user:pass@example:5432/db") == "postgresql://user:pass@example:5432/db"
    assert normalize_postgres_conn_string("postgresql+asyncpg://user:pass@example:5432/db") == "postgresql://user:pass@example:5432/db"
    assert normalize_postgres_conn_string("postgres+psycopg://user:pass@example:5432/db") == "postgresql://user:pass@example:5432/db"


def test_normalize_postgres_conn_string_leaves_native_psycopg_dsn_unchanged():
    assert normalize_postgres_conn_string("postgresql://user:pass@example:5432/db") == "postgresql://user:pass@example:5432/db"
