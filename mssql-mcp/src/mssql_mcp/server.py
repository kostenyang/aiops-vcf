"""
MSSQL MCP Server
Runs on Ubuntu 10.0.0.65, port 7001.
Exposes Microsoft SQL Server operations as MCP tools for Claude.

Tools:
  mssql_test_connection   - 測試 MSSQL 連線
  mssql_execute_query     - 執行 SELECT 查詢
  mssql_execute_statement - 執行 INSERT/UPDATE/DELETE
  mssql_list_databases    - 列出所有使用者資料庫
  mssql_list_schemas      - 列出指定 DB 的 Schema
  mssql_list_tables       - 列出資料表與檢視表
  mssql_describe_table    - 查看資料表結構

Start: python3 -m mssql_mcp.server
Port:  https://0.0.0.0:7001/sse
"""

import json
import os
import pathlib
import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from . import database as db

# ── API Keys ── 從 /opt/vcf-mcp/keys.json 載入（與 vcf-lab MCP Server 共用）
API_KEYS_FILE = pathlib.Path("/opt/vcf-mcp/keys.json")

def _load_api_keys() -> dict[str, str]:
    if not API_KEYS_FILE.exists():
        raise RuntimeError(f"API keys file not found: {API_KEYS_FILE}")
    with API_KEYS_FILE.open() as f:
        keys = json.load(f)
    if not isinstance(keys, dict) or not keys:
        raise RuntimeError("Invalid keys file: must be non-empty JSON object")
    return keys

API_KEYS: dict[str, str] = _load_api_keys()

SSL_CERTFILE = "/opt/vcf-mcp/cert.pem"
SSL_KEYFILE  = "/opt/vcf-mcp/key.pem"
MCP_PORT     = int(os.getenv("MCP_PORT", "7001"))

mcp = FastMCP(
    "mssql-mcp",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)


# ── API Key Middleware (SSE-safe，與 vcf-lab MCP 相同模式) ───────────────────
class APIKeyMiddleware:
    def __init__(self, app):
        self.app = app
        self._VALID = frozenset(API_KEYS.values())

    def _extract_token(self, scope) -> str:
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        auth = headers.get(b"authorization", b"").decode()
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        qs = scope.get("query_string", b"").decode()
        for part in qs.split("&"):
            if part.startswith("api_key="):
                return part[8:]
        return ""

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            if self._extract_token(scope) not in self._VALID:
                await send({
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        [b"content-type", b"application/json"],
                        [b"www-authenticate", b'Bearer realm="mssql-mcp"'],
                    ],
                })
                await send({"type": "http.response.body",
                            "body": b'{"error":"Unauthorized"}'})
                return
        await self.app(scope, receive, send)


# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def mssql_test_connection() -> str:
    """
    測試 MSSQL 資料庫連線是否正常，回傳伺服器名稱與版本資訊。
    用於確認 MCP Server 能正常連到 SQL Server。
    """
    result = db.test_connection()
    return json.dumps(result, ensure_ascii=False, indent=2, default=str)


@mcp.tool()
def mssql_execute_query(sql: str, database: str = "") -> str:
    """
    執行 SELECT 查詢並回傳結果（最多 1000 列）。

    sql      : 要執行的 SELECT SQL 語句
    database : 目標資料庫名稱（留空則使用預設 DB）

    Examples:
      mssql_execute_query("SELECT TOP 10 * FROM dbo.Users")
      mssql_execute_query("SELECT name, create_date FROM sys.databases", "master")
    """
    try:
        result = db.execute_query(sql, database=database or None)
        return json.dumps(result, ensure_ascii=False, indent=2, default=str)
    except PermissionError as e:
        return json.dumps({"error": "權限不足", "detail": str(e)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def mssql_execute_statement(sql: str, database: str = "") -> str:
    """
    執行 DML 語句（INSERT、UPDATE、DELETE、MERGE）並回傳影響列數。
    需要在 .env 設定 ALLOW_WRITE=true 才能使用。

    sql      : 要執行的 DML SQL 語句
    database : 目標資料庫名稱（留空則使用預設 DB）

    Examples:
      mssql_execute_statement("INSERT INTO dbo.Logs (msg, ts) VALUES ('test', GETDATE())")
      mssql_execute_statement("UPDATE dbo.Config SET value='1' WHERE key='enabled'", "AppDB")
      mssql_execute_statement("DELETE FROM dbo.TempData WHERE created_at < DATEADD(day,-7,GETDATE())")
    """
    try:
        result = db.execute_statement(sql, database=database or None)
        return json.dumps(result, ensure_ascii=False, indent=2, default=str)
    except PermissionError as e:
        return json.dumps({"error": "權限不足", "detail": str(e)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def mssql_list_databases() -> str:
    """
    列出 SQL Server 上所有使用者資料庫（排除 master/model/msdb/tempdb）。
    """
    try:
        databases = db.list_databases()
        return json.dumps({"databases": databases, "count": len(databases)},
                          ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def mssql_list_schemas(database: str) -> str:
    """
    列出指定資料庫中的所有 Schema。

    database : 資料庫名稱
    Example: mssql_list_schemas("AdventureWorks")
    """
    try:
        schemas = db.list_schemas(database)
        return json.dumps({"schemas": schemas, "count": len(schemas)},
                          ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def mssql_list_tables(database: str, schema: str = "") -> str:
    """
    列出指定資料庫中的所有資料表與檢視表，可選擇篩選特定 Schema。

    database : 資料庫名稱
    schema   : 篩選特定 Schema（選填，如 'dbo'）

    Examples:
      mssql_list_tables("AdventureWorks")
      mssql_list_tables("AdventureWorks", "HumanResources")
    """
    try:
        tables = db.list_tables(database, schema=schema or None)
        return json.dumps({"tables": tables, "count": len(tables)},
                          ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def mssql_describe_table(table: str, database: str, schema: str = "dbo") -> str:
    """
    取得資料表的詳細結構：欄位定義、資料類型、Primary Key、索引。

    table    : 資料表名稱
    database : 資料庫名稱
    schema   : Schema 名稱（預設為 'dbo'）

    Examples:
      mssql_describe_table("Users", "AppDB")
      mssql_describe_table("Employee", "AdventureWorks", "HumanResources")
    """
    try:
        result = db.describe_table(table, database, schema)
        return json.dumps(result, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    print(f"Starting MSSQL MCP Server on https://0.0.0.0:{MCP_PORT}/sse")
    print(f"API keys loaded: {list(API_KEYS.keys())}")
    uvicorn.run(
        APIKeyMiddleware(mcp.sse_app()),
        host="0.0.0.0",
        port=MCP_PORT,
        ssl_keyfile=SSL_KEYFILE,
        ssl_certfile=SSL_CERTFILE,
    )


if __name__ == "__main__":
    main()
