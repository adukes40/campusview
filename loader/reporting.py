import re
from pathlib import Path

from psycopg import ClientCursor, sql

READER = "campusview_reader"
SQL_PATH = Path(__file__).resolve().parents[1] / "reporting.sql"

_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE = re.compile(r"--[^\n]*")


class MissingReader(Exception):
    pass


def _has_sql(text: str) -> bool:
    return bool(_LINE.sub("", _BLOCK.sub("", text)).strip())


def drop_views(conn) -> None:
    conn.execute("CREATE SCHEMA IF NOT EXISTS reporting")
    rows = conn.execute(
        """
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'reporting' AND c.relkind = 'v'
        """
    ).fetchall()
    for (name,) in rows:
        conn.execute(
            sql.SQL("DROP VIEW IF EXISTS {}.{} CASCADE").format(
                sql.Identifier("reporting"), sql.Identifier(name)
            )
        )


def apply_views(conn) -> None:
    if conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (READER,)).fetchone() is None:
        raise MissingReader()
    text = SQL_PATH.read_text(encoding="utf-8")
    if _has_sql(text):
        with ClientCursor(conn) as cur:
            cur.execute(text)
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA reporting TO {}").format(sql.Identifier(READER)))
    conn.execute(
        sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA reporting TO {}").format(sql.Identifier(READER))
    )
