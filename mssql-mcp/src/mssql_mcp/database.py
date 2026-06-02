"""MSSQL database connection and query execution manager."""

import os
import re
import pyodbc
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

# 安全設定
ALLOW_WRITE = os.getenv("ALLOW_WRITE", "true").lower() == "true"
ALLOW_DDL = os.getenv("ALLOW_DDL", "false").lower() == "true"
MAX_ROWS = int(os.getenv("MAX_ROWS", "1000"))
QUERY_TIMEOUT = int(os.getenv("QUERY_TIMEOUT", "30"))

# DDL 關鍵字（當 ALLOW_DDL=false 時拒絕）
_DDL_PATTERN = re.compile(
    r"^\s*(CREATE|DROP|ALTER|TRUNCATE|RENAME)\s+",
    re.IGNORECASE | re.MULTILINE,
)

# DML 寫入關鍵字（當 ALLOW_WRITE=false 時拒絕）
_DML_WRITE_PATTERN = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|MERGE)\s+",
    re.IGNORECASE | re.MULTILINE,
)


def _build_connection_string(database: str | None = None) -> str:
    server = os.getenv("MSSQL_SERVER", "localhost")
    port = os.getenv("MSSQL_PORT", "1433")
    db = database or os.getenv("MSSQL_DATABASE", "master")
    auth_type = os.getenv("MSSQL_AUTH_TYPE", "sql").lower()

    driver = "ODBC Driver 18 for SQL Server"
    base = f"DRIVER={{{driver}}};SERVER={server},{port};DATABASE={db};TrustServerCertificate=yes;"

    if auth_type == "windows":
        return base + "Trusted_Connection=yes;"
    else:
        username = os.getenv("MSSQL_USERNAME", "sa")
        password = os.getenv("MSSQL_PASSWORD", "")
        return base + f"UID={username};PWD={password};"


@contextmanager
def get_connection(database: str | None = None):
    conn_str = _build_connection_string(database)
    conn = pyodbc.connect(conn_str, timeout=QUERY_TIMEOUT)
    conn.timeout = QUERY_TIMEOUT
    try:
        yield conn
    finally:
        conn.close()


def _check_sql_permissions(sql: str) -> None:
    """Raise if the SQL violates configured permission settings."""
    if _DDL_PATTERN.search(sql) and not ALLOW_DDL:
        raise PermissionError("DDL 操作 (CREATE/DROP/ALTER) 已被停用，請設定 ALLOW_DDL=true 以啟用。")
    if _DML_WRITE_PATTERN.search(sql) and not ALLOW_WRITE:
        raise PermissionError("DML 寫入操作 (INSERT/UPDATE/DELETE) 已被停用，請設定 ALLOW_WRITE=true 以啟用。")


def execute_query(sql: str, database: str | None = None) -> dict:
    """Execute a SELECT query and return rows as list of dicts."""
    _check_sql_permissions(sql)
    with get_connection(database) as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
        if cursor.description is None:
            return {"columns": [], "rows": [], "row_count": 0}
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchmany(MAX_ROWS)
        result_rows = [dict(zip(columns, row)) for row in rows]
        return {
            "columns": columns,
            "rows": result_rows,
            "row_count": len(result_rows),
            "truncated": len(result_rows) == MAX_ROWS,
        }


def execute_statement(sql: str, database: str | None = None) -> dict:
    """Execute a DML statement (INSERT/UPDATE/DELETE) and return affected row count."""
    _check_sql_permissions(sql)
    with get_connection(database) as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
        affected = cursor.rowcount
        conn.commit()
        return {"affected_rows": affected, "success": True}


def list_databases() -> list[str]:
    """Return list of user databases on the server."""
    result = execute_query(
        "SELECT name FROM sys.databases WHERE database_id > 4 ORDER BY name"
    )
    return [row["name"] for row in result["rows"]]


def list_schemas(database: str) -> list[str]:
    """Return list of schemas in the given database."""
    result = execute_query(
        "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA ORDER BY SCHEMA_NAME",
        database=database,
    )
    return [row["SCHEMA_NAME"] for row in result["rows"]]


def list_tables(database: str, schema: str | None = None) -> list[dict]:
    """Return list of tables/views in the given database."""
    where = f"AND TABLE_SCHEMA = '{schema}'" if schema else ""
    result = execute_query(
        f"""
        SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
        FROM INFORMATION_SCHEMA.TABLES
        WHERE 1=1 {where}
        ORDER BY TABLE_SCHEMA, TABLE_NAME
        """,
        database=database,
    )
    return result["rows"]


def describe_table(table: str, database: str, schema: str = "dbo") -> dict:
    """Return column definitions, primary keys, and indexes for a table."""
    columns_sql = f"""
        SELECT
            c.COLUMN_NAME,
            c.DATA_TYPE,
            c.CHARACTER_MAXIMUM_LENGTH,
            c.NUMERIC_PRECISION,
            c.NUMERIC_SCALE,
            c.IS_NULLABLE,
            c.COLUMN_DEFAULT,
            c.ORDINAL_POSITION
        FROM INFORMATION_SCHEMA.COLUMNS c
        WHERE c.TABLE_NAME = '{table}' AND c.TABLE_SCHEMA = '{schema}'
        ORDER BY c.ORDINAL_POSITION
    """

    pk_sql = f"""
        SELECT kcu.COLUMN_NAME
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
            ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            AND tc.TABLE_NAME = kcu.TABLE_NAME
        WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
          AND tc.TABLE_NAME = '{table}'
          AND tc.TABLE_SCHEMA = '{schema}'
        ORDER BY kcu.ORDINAL_POSITION
    """

    index_sql = f"""
        SELECT
            i.name AS index_name,
            i.type_desc,
            i.is_unique,
            STRING_AGG(c.name, ', ') WITHIN GROUP (ORDER BY ic.key_ordinal) AS columns
        FROM sys.indexes i
        JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
        JOIN sys.tables t ON i.object_id = t.object_id
        JOIN sys.schemas s ON t.schema_id = s.schema_id
        WHERE t.name = '{table}' AND s.name = '{schema}'
          AND i.is_primary_key = 0
        GROUP BY i.name, i.type_desc, i.is_unique
        ORDER BY i.name
    """

    columns = execute_query(columns_sql, database=database)["rows"]
    pk_result = execute_query(pk_sql, database=database)["rows"]
    primary_keys = [row["COLUMN_NAME"] for row in pk_result]

    try:
        indexes = execute_query(index_sql, database=database)["rows"]
    except Exception:
        indexes = []

    return {
        "table": f"{schema}.{table}",
        "database": database,
        "columns": columns,
        "primary_keys": primary_keys,
        "indexes": indexes,
    }


def test_connection() -> dict:
    """Verify the database connection is working."""
    try:
        result = execute_query("SELECT @@VERSION AS version, @@SERVERNAME AS server_name")
        row = result["rows"][0] if result["rows"] else {}
        return {"connected": True, "server": row.get("server_name"), "version": row.get("version", "")[:80]}
    except Exception as e:
        return {"connected": False, "error": str(e)}
