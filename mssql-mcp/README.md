# MSSQL MCP Server — 部署手冊

> 讓 Claude AI / Open WebUI 能直接讀寫 Microsoft SQL Server，支援離線部署於客戶環境。

---

## 目錄

- [架構說明](#架構說明)
- [系統需求](#系統需求)
- [離線安裝包（推薦）](#離線安裝包推薦)
- [設定說明](#設定說明)
- [MCP 工具清單](#mcp-工具清單)
- [Claude Code 整合](#claude-code-整合)
- [Open WebUI 整合](#open-webui-整合)
- [驗證與測試](#驗證與測試)
- [常見問題](#常見問題)

---

## 架構說明

```
Claude Code / Claude Desktop
        │  HTTPS (SSE)
        ▼
  MCP Server (Ubuntu/Linux)
  Port 7001 — Bearer Token 驗證
        │  TCP 1433
        ▼
  Microsoft SQL Server
  (混合驗證 / SQL 驗證)
```

MCP Server 以 **SSE（Server-Sent Events）** 傳輸，與 Claude 通訊。  
SQL Server 可在 Windows 或 Linux 上，支援 SQL 驗證與 Windows 整合驗證。

---

## 系統需求

### MCP Server 主機（Ubuntu / Linux）

| 項目 | 需求 |
|------|------|
| OS | Ubuntu 20.04 / 22.04 LTS（推薦）或 RHEL 8/9 |
| Python | 3.11 以上 |
| 記憶體 | 512 MB 以上 |
| 磁碟 | 2 GB 以上 |
| 網路 | 能連到 SQL Server TCP 1433 |

### SQL Server

| 項目 | 需求 |
|------|------|
| 版本 | SQL Server 2017 以上（含 Azure SQL、SQL Server on Linux）|
| 驗證 | SQL 驗證（混合模式）或 Windows 整合驗證（需 Kerberos）|
| 防火牆 | 允許 MCP Server IP 連入 TCP 1433 |

---

## 離線安裝包（推薦）

### 步驟一：在有網路的機器打包（一次）

```bash
# 在 Linux x86_64 機器（需有網路）
cd mssql-mcp
bash prepare-offline-bundle.sh
```

產生 `mssql-mcp-offline.tar.gz`，約 200–300 MB，包含：
- Python 3.11 standalone（無需目標機器有 Python）
- 所有 Python 套件 wheel（mcp、fastmcp、mcpo、pyodbc 等）
- Microsoft ODBC Driver 18（Ubuntu 20.04 / 22.04）
- MCP Server 程式碼
- Systemd service 設定

將此檔案存入 **USB 隨身碟**或共用儲存空間。

---

### 步驟二：在客戶機器安裝（離線、互動式）

```bash
# 複製 tar.gz 到客戶 Linux 機器後
tar -xzf mssql-mcp-offline.tar.gz
cd mssql-mcp-offline
sudo bash install.sh
```

`install.sh` 會逐步詢問：
- SQL Server IP、Port、資料庫名稱
- 帳號 / 密碼
- 是否允許寫入（DML）
- 是否啟用 Open WebUI 橋接（mcpo）
- MCP Server 埠號

完成後自動顯示 `.mcp.json` 設定範例與 Open WebUI Tool Server URL。

---

### 支援的作業系統

| OS | 版本 | 支援 |
|----|------|------|
| Ubuntu | 20.04 LTS | ✓ |
| Ubuntu | 22.04 LTS | ✓ |
| Debian | 11 / 12 | ✓（使用 ubuntu22 ODBC）|
| RHEL / Rocky / Alma | 8 / 9 | 需手動補充 RPM 套件 |

---

## 設定說明

設定檔位置：`/opt/mssql-mcp/.env`

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `MSSQL_SERVER` | SQL Server IP 或主機名稱 | 必填 |
| `MSSQL_PORT` | TCP Port | `1433` |
| `MSSQL_DATABASE` | 預設資料庫 | `master` |
| `MSSQL_USERNAME` | SQL 登入帳號 | `sa` |
| `MSSQL_PASSWORD` | 密碼 | 必填 |
| `MSSQL_AUTH_TYPE` | `sql` 或 `windows` | `sql` |
| `ALLOW_WRITE` | 允許 INSERT/UPDATE/DELETE | `true` |
| `ALLOW_DDL` | 允許 CREATE/DROP/ALTER | `false` |
| `MAX_ROWS` | 查詢最大回傳列數 | `1000` |
| `QUERY_TIMEOUT` | 查詢逾時秒數 | `30` |

---

## MCP 工具清單

| 工具名稱 | 說明 | 範例 |
|---------|------|------|
| `mssql_test_connection` | 測試連線，回傳版本 | — |
| `mssql_execute_query` | 執行 SELECT 查詢 | `SELECT TOP 10 * FROM dbo.Users` |
| `mssql_execute_statement` | 執行 INSERT/UPDATE/DELETE | `DELETE FROM dbo.Logs WHERE ts < '2024-01-01'` |
| `mssql_list_databases` | 列出所有使用者資料庫 | — |
| `mssql_list_schemas` | 列出指定 DB 的 Schema | database=`AdventureWorks` |
| `mssql_list_tables` | 列出資料表與檢視表 | database=`AdventureWorks`, schema=`HumanResources` |
| `mssql_describe_table` | 查看欄位、PK、索引 | table=`Employee`, database=`AdventureWorks` |

---

## Claude Code 整合

### 設定 `.mcp.json`

```json
{
  "mcpServers": {
    "mssql": {
      "type": "sse",
      "url": "https://<MCP_SERVER_IP>:7001/sse",
      "headers": {
        "Authorization": "Bearer <YOUR_API_KEY>"
      }
    }
  }
}
```

**若與 vcf-lab MCP 共機（10.0.0.65）：**

```json
{
  "mcpServers": {
    "vcf-lab": {
      "type": "sse",
      "url": "https://10.0.0.65:7000/sse",
      "headers": { "Authorization": "Bearer <YOUR_TOKEN>" }
    },
    "mssql": {
      "type": "sse",
      "url": "https://10.0.0.65:7001/sse",
      "headers": { "Authorization": "Bearer <YOUR_TOKEN>" }
    }
  }
}
```

> 自簽憑證需在 Claude Code 設定中停用憑證驗證，或將 cert.pem 加入系統信任清單。

### Claude Desktop 設定

`claude_desktop_config.json` 加入相同的 `mcpServers` 區塊。

---

## Open WebUI 整合

安裝時選擇啟用 mcpo（Open WebUI 橋接），安裝完成後：

1. 開啟 Open WebUI → 右上角頭像 → **Admin Panel**
2. 左側 **Settings** → **Tools**
3. 點 **+** 新增 Tool Server
4. URL 填入：`http://<MCP_SERVER_IP>:8001`
5. 儲存後重整頁面

Open WebUI 會自動載入 7 個 MSSQL 工具，開對話時勾選即可使用。

---

## 驗證與測試

### 1. 測試 MCP Server HTTPS 端點

```bash
curl -sk \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  https://<MCP_SERVER_IP>:7001/sse
```

正常回應：`event: endpoint` 開頭的 SSE 訊息

### 2. 測試 SQL Server 連線（在 MCP Server 上）

```bash
# 使用 sqlcmd（需安裝 mssql-tools18）
/opt/mssql-tools18/bin/sqlcmd \
  -S <SQL_SERVER_IP> \
  -U sa \
  -P '<SA_PASSWORD>' \
  -Q "SELECT @@VERSION"
```

### 3. 在 Claude 中測試

```
請幫我測試 MSSQL 連線
→ Claude 呼叫 mssql_test_connection
```

```
列出所有資料庫
→ Claude 呼叫 mssql_list_databases
```

---

## 常見問題

### Q: 連線錯誤 `[08001] Unable to connect`

- 確認 SQL Server TCP/IP 已啟用（SQL Server 組態管理員 → 通訊協定）
- 確認 Windows 防火牆允許 TCP 1433
- 確認 SQL Server Browser 服務已啟動（具名執行個體需要）

### Q: 錯誤 `[28000] Login failed for user 'sa'`

- 確認 SQL Server 為混合驗證模式（非僅 Windows 驗證）
- 確認 sa 帳號未被停用：`ALTER LOGIN sa ENABLE;`

### Q: `ODBC Driver 18 for SQL Server` 找不到

```bash
odbcinst -q -d   # 列出已安裝驅動程式
cat /etc/odbcinst.ini
```

重新安裝 ODBC Driver（參考離線安裝步驟 B2）

### Q: 自簽憑證造成 Claude Code 連線失敗

在 Claude Code settings 加入：
```json
"env": {
  "NODE_TLS_REJECT_UNAUTHORIZED": "0"
}
```

或將 cert.pem 匯入系統憑證：
```bash
sudo cp /opt/vcf-mcp/cert.pem /usr/local/share/ca-certificates/mssql-mcp.crt
sudo update-ca-certificates
```

### Q: 服務啟動失敗

```bash
sudo journalctl -u mssql-mcp --no-pager -n 50
```

常見原因：PYTHONPATH 未設定、.env 路徑錯誤、port 7001 被佔用。

---

## 目錄結構

```
mssql-mcp/
├── README.md                   # 本說明文件
├── requirements.txt            # Python 相依套件
├── pyproject.toml              # 套件設定
├── setup-ubuntu.sh             # 線上安裝腳本
├── .env.example                # 設定範例
├── mcp_config_example.json     # Claude MCP 設定範例
└── src/
    └── mssql_mcp/
        ├── __init__.py
        ├── server.py           # FastMCP Server 主程式
        └── database.py         # MSSQL 連線與查詢邏輯
```
