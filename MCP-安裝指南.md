# MCP Server 離線安裝指南

> 適用版本：vcf-mcp v1 / mssql-mcp v1  
> 支援 OS：Ubuntu 20.04 / 22.04、RHEL / Rocky / AlmaLinux 8+  
> 架構：x86_64（不支援 ARM）

---

## 目錄

1. [整體架構說明](#1-整體架構說明)
2. [系統需求](#2-系統需求)
3. [準備離線安裝包（有網路機器）](#3-準備離線安裝包有網路機器)
4. [傳輸到目標機器](#4-傳輸到目標機器)
5. [安裝 VCF MCP Server](#5-安裝-vcf-mcp-server)
6. [安裝 MSSQL MCP Server](#6-安裝-mssql-mcp-server)
7. [客戶端設定（Claude / Open WebUI）](#7-客戶端設定claude--open-webui)
8. [維運指令](#8-維運指令)
9. [常見問題排查](#9-常見問題排查)

---

## 1. 整體架構說明

```
┌─────────────────────────────────────────────────────────┐
│  客戶機器（Ubuntu / RHEL）                              │
│                                                         │
│  ┌──────────────────┐    ┌──────────────────────────┐   │
│  │  vcf-mcp         │    │  mssql-mcp               │   │
│  │  HTTPS port 7000 │    │  HTTPS port 7001         │   │
│  │  VMware VCF API  │    │  SQL Server / pyodbc     │   │
│  └────────┬─────────┘    └──────────┬───────────────┘   │
│           │                         │                   │
│  ┌────────┴─────────────────────────┴───────────────┐   │
│  │  /opt/vcf-mcp/                                   │   │
│  │    cert.pem、key.pem（SSL 自簽憑證）             │   │
│  │    keys.json（API Keys，兩個 MCP 共用）          │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
         ↑ HTTPS Bearer Token
┌────────────────────────────────────────┐
│  Claude Code / Claude Desktop          │
│  Open WebUI（透過 mcpo bridge port 800x）│
└────────────────────────────────────────┘
```

- **vcf-mcp**：操作 VMware Cloud Foundation（vCenter、SDDC Manager、VCF Installer、Aria Operations、ESXi SSH）
- **mssql-mcp**：操作 Microsoft SQL Server（查詢、寫入、結構瀏覽）
- 兩個 Server 共用同一組 SSL 憑證與 API Keys（存放於 `/opt/vcf-mcp/`）
- **先裝 vcf-mcp，再裝 mssql-mcp**（因為 mssql-mcp 借用 vcf-mcp 的憑證目錄）

---

## 2. 系統需求

### 打包機器（有網路，用來產生離線包）

| 項目 | 需求 |
|------|------|
| OS | Linux x86_64（Ubuntu / CentOS / Debian 均可） |
| 工具 | `curl`、`tar` |
| 磁碟 | 至少 1 GB 可用空間 |
| 網路 | 可連 GitHub、pypi.org、packages.microsoft.com |

> ⚠️ 不能在 Windows 上打包。需要真正的 Linux 環境。

### 目標機器（客戶端，無網路）

| 項目 | 需求 |
|------|------|
| OS | Ubuntu 20.04 / 22.04 或 RHEL / Rocky 8+ |
| 架構 | x86_64 |
| 磁碟 | 至少 3 GB 可用空間（/opt 分區） |
| 記憶體 | 建議 2 GB 以上 |
| 權限 | root（或 sudo） |
| 工具 | `tar`、`openssl`、`systemd` |
| 端口 | 7000（vcf-mcp）、7001（mssql-mcp）、8000/8001（mcpo，選填） |

---

## 3. 準備離線安裝包（有網路機器）

在**有網路的 Linux 機器**上執行，各產生一個 tar.gz。

### 3.1 vcf-mcp 離線包

```bash
# 確認在 vcf-mcp/ 目錄內
cd vcf-mcp/
ls vcf_mcp_server.py    # 應存在

bash prepare-offline-bundle.sh
# 完成後產生：vcf-mcp-offline.tar.gz（約 78 MB）
```

打包步驟說明：
1. 下載 uv（Python 版本管理器）
2. 下載 Python 3.11 standalone
3. 下載 Python 套件（manylinux wheels，離線可用）
4. 複製 server 程式碼與 service 模板
5. 打包成 tar.gz

### 3.2 mssql-mcp 離線包

```bash
# 確認在 mssql-mcp/ 目錄內
cd mssql-mcp/
ls src/mssql_mcp/       # 應存在

bash prepare-offline-bundle.sh
# 完成後產生：mssql-mcp-offline.tar.gz（約 81 MB）
```

額外步驟：下載 Microsoft ODBC Driver 18 的 .deb 套件（Ubuntu 20.04 & 22.04）

---

## 4. 傳輸到目標機器

### 方式 A：USB / 光碟

```bash
cp vcf-mcp-offline.tar.gz  /media/usb/
cp mssql-mcp-offline.tar.gz /media/usb/
```

### 方式 B：SCP（從有網路的 Windows 跳板機）

```cmd
pscp vcf-mcp-offline.tar.gz  root@<目標IP>:/root/
pscp mssql-mcp-offline.tar.gz root@<目標IP>:/root/
```

### 方式 C：SCP（Linux）

```bash
scp vcf-mcp-offline.tar.gz  root@<目標IP>:/root/
scp mssql-mcp-offline.tar.gz root@<目標IP>:/root/
```

---

## 5. 安裝 VCF MCP Server

> ⚠️ **先安裝 vcf-mcp，再安裝 mssql-mcp。**

### 5.1 解壓與執行

```bash
cd /root
tar -xzf vcf-mcp-offline.tar.gz
cd vcf-mcp-offline
sudo bash install.sh
```

### 5.2 互動問題說明

腳本會依序詢問以下資訊：

| 問題 | 說明 | 範例 |
|------|------|------|
| 環境名稱 | 用於識別此客戶環境 | `CustomerA-Prod` |
| vCenter IP | vCenter Server IP 位址 | `192.168.1.101` |
| vCenter FQDN | 選填，若有 DNS 可填 | `vcenter.domain.com` |
| vCenter SSO 帳號 | 預設 administrator@vsphere.local | （Enter 跳過用預設值）|
| vCenter 密碼 | 輸入時不顯示字元 | `YourPassword` |
| SDDC Manager IP | SDDC Manager 位址 | `192.168.1.5` |
| SDDC Manager 密碼 | 輸入時不顯示 | `YourPassword` |
| VCF Installer IP | 選填，無則 Enter 跳過 | `192.168.1.4` 或 Enter |
| VCF Installer 帳號 | 選填，預設 admin@local | （Enter 跳過）|
| VCF Installer 密碼 | 選填，有填 IP 才問 | |
| Aria Operations IP | 選填，無則 Enter 跳過 | Enter |
| ESXi/Linux SSH 密碼 | root 帳號的 SSH 密碼 | `VMware1!` |
| DNS Server IP | 用於 DNS 查詢工具 | `192.168.1.200` |
| ESXi 主機列表 | 逗號分隔，選填 | `192.168.1.11,192.168.1.12` |
| MCP Port | 預設 7000 | Enter 或 `7000` |
| 啟用 Open WebUI 橋接 | mcpo bridge (port 8000) | Enter=Y 或 `n` |
| 確認安裝 | Enter=確認 | Enter |

> 💡 **注意**：vCenter 與 SDDC Manager 有可能密碼不同，請向客戶分別確認。

### 5.3 安裝後驗證

```bash
# 服務狀態
systemctl status vcf-mcp
systemctl status vcf-mcpo   # 若有啟用 mcpo

# API 連線測試（TOKEN 從安裝輸出複製）
TOKEN="<安裝完成後顯示的 Bearer Token>"
curl -sk https://localhost:7000/sse \
  -H "Authorization: Bearer $TOKEN" \
  -o /dev/null -w "%{http_code}\n"
# 預期輸出：200

# 測試無 Token（應拒絕）
curl -sk https://localhost:7000/sse -o /dev/null -w "%{http_code}\n"
# 預期輸出：401
```

### 5.4 安裝產生的檔案

| 路徑 | 說明 |
|------|------|
| `/opt/vcf-mcp/vcf_mcp_server.py` | MCP Server 主程式 |
| `/opt/vcf-mcp/venv/` | Python 虛擬環境 |
| `/opt/vcf-mcp/.env` | 環境設定（chmod 600） |
| `/opt/vcf-mcp/cert.pem` | SSL 憑證（10 年自簽）|
| `/opt/vcf-mcp/key.pem` | SSL 私鑰（chmod 600）|
| `/opt/vcf-mcp/keys.json` | API Keys（chmod 600）|
| `/etc/systemd/system/vcf-mcp.service` | systemd service |
| `/etc/systemd/system/vcf-mcpo.service` | Open WebUI 橋接 service |

---

## 6. 安裝 MSSQL MCP Server

### 6.1 解壓與執行

```bash
cd /root
tar -xzf mssql-mcp-offline.tar.gz
cd mssql-mcp-offline
sudo bash install.sh
```

### 6.2 互動問題說明

| 問題 | 說明 | 範例 |
|------|------|------|
| SQL Server IP / 主機名稱 | MSSQL Server 位址 | `192.168.1.70` |
| SQL Server Port | 預設 1433 | Enter 或 `1433` |
| 預設資料庫 | 預設 master | Enter 或 `AdventureWorks` |
| SQL 帳號 | 預設 sa | Enter 或 `myuser` |
| SQL 密碼 | 輸入時不顯示 | `YourSqlPass` |
| 允許 DML 寫入 | INSERT/UPDATE/DELETE 是否開放 | Enter=Y 或 `n` |
| 允許 DDL | CREATE/DROP/ALTER 是否開放 | Enter=N 或 `y` |
| 查詢最大列數 | 預設 1000 | Enter 或 `5000` |
| 啟用 Open WebUI 橋接 | mcpo bridge (port 8001) | Enter=Y 或 `n` |
| MCP Port | 預設 7001 | Enter 或 `7001` |
| 確認安裝 | Enter=確認 | Enter |

> 💡 SQL Server 需開啟混合驗證模式（SQL Server and Windows Authentication），並允許 TCP 1433 防火牆。

### 6.3 安裝後驗證

```bash
# 服務狀態
systemctl status mssql-mcp
systemctl status mssql-mcpo

# API 連線測試（與 vcf-mcp 共用同一個 TOKEN）
TOKEN="<Bearer Token>"
curl -sk https://localhost:7001/sse \
  -H "Authorization: Bearer $TOKEN" \
  -o /dev/null -w "%{http_code}\n"
# 預期：200
```

### 6.4 安裝產生的檔案

| 路徑 | 說明 |
|------|------|
| `/opt/mssql-mcp/mssql_mcp/` | MCP Server 套件 |
| `/opt/mssql-mcp/venv/` | Python 虛擬環境 |
| `/opt/mssql-mcp/.env` | SQL 連線設定（chmod 600）|
| `/opt/vcf-mcp/cert.pem` | 共用 vcf-mcp 的 SSL 憑證 |
| `/opt/vcf-mcp/keys.json` | 共用 vcf-mcp 的 API Keys |

---

## 7. 客戶端設定（Claude / Open WebUI）

### 7.1 取得 Bearer Token

安裝完成時畫面會顯示 Token。若需要重新查詢：

```bash
cat /opt/vcf-mcp/keys.json
# 輸出範例：{"admin": "ILnx5ohq04A92X01Sk9rw9Uvjk8f0Nbd02a8wuIFZbw"}
```

### 7.2 Claude Code（命令列）

在客戶電腦的 `.mcp.json` 加入：

```json
{
  "mcpServers": {
    "vcf": {
      "type": "sse",
      "url": "https://<MCP_SERVER_IP>:7000/sse",
      "headers": {
        "Authorization": "Bearer <TOKEN>"
      }
    },
    "mssql": {
      "type": "sse",
      "url": "https://<MCP_SERVER_IP>:7001/sse",
      "headers": {
        "Authorization": "Bearer <TOKEN>"
      }
    }
  }
}
```

> 因為使用自簽憑證，需在 Claude Code 設定中啟用 `allowInsecureRequests: true`，或在 `.mcp.json` 加入 `"insecure": true`。

### 7.3 Claude Desktop

在 Claude Desktop 設定檔（`claude_desktop_config.json`）加入同樣的 `mcpServers` 區塊。

### 7.4 Open WebUI（透過 mcpo bridge）

1. 登入 Open WebUI Admin
2. Settings → Tools → 新增 Tool Server
3. 填入 URL：
   - vcf-mcp：`http://<MCP_SERVER_IP>:8000`
   - mssql-mcp：`http://<MCP_SERVER_IP>:8001`

> mcpo bridge 使用 HTTP（非 HTTPS），且無需 Token（Token 由 mcpo 轉發）。

### 7.5 新增 API Key（多位使用者）

```bash
# 在 MCP Server 上產生新 Key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# 加入 keys.json（範例）
cat /opt/vcf-mcp/keys.json
# 改成：{"admin": "原本的key", "user2": "新生成的key"}

# 重啟服務讓新 Key 生效
systemctl restart vcf-mcp mssql-mcp
```

---

## 8. 維運指令

### 服務管理

```bash
# 查看狀態
systemctl status vcf-mcp mssql-mcp vcf-mcpo mssql-mcpo

# 重啟（修改 .env 後必須重啟）
systemctl restart vcf-mcp
systemctl restart mssql-mcp

# 即時 log
journalctl -u vcf-mcp -f
journalctl -u mssql-mcp -f

# 查看最近 50 行 log
journalctl -u vcf-mcp -n 50 --no-pager
```

### 修改設定

```bash
# vcf-mcp 設定
vi /opt/vcf-mcp/.env
systemctl restart vcf-mcp

# mssql-mcp 設定
vi /opt/mssql-mcp/.env
systemctl restart mssql-mcp
```

### 手動測試 API

```bash
TOKEN=$(python3 -c "import json; d=json.load(open('/opt/vcf-mcp/keys.json')); print(list(d.values())[0])")

# vcf-mcp 連線測試
curl -sk https://localhost:7000/sse \
  -H "Authorization: Bearer $TOKEN" \
  -o /dev/null -w "vcf-mcp: HTTP %{http_code}\n"

# mssql-mcp 連線測試
curl -sk https://localhost:7001/sse \
  -H "Authorization: Bearer $TOKEN" \
  -o /dev/null -w "mssql-mcp: HTTP %{http_code}\n"
```

---

## 9. 常見問題排查

### 安裝阶段

---

**Q: `bash prepare-offline-bundle.sh` 中途停止，沒有錯誤訊息**

可能原因：`set -e` 觸發，某個子命令失敗。  
排查：
```bash
bash -x prepare-offline-bundle.sh 2>&1 | tee /tmp/bundle_debug.log
```
常見觸發點：
- curl 下載超時（連不到 GitHub / packages.microsoft.com）
- grep 找不到 .deb 連結（網頁結構變更）

---

**Q: 安裝時顯示 `找不到 uv binary`**

表示不在正確的解壓目錄內執行。  
```bash
# 確認在 mssql-mcp-offline/ 或 vcf-mcp-offline/ 目錄內
ls uv/uv    # 應該存在
sudo bash install.sh
```

---

**Q: `Python 3.11 安裝失敗，找不到 python3.11 binary`**

bundle 中的 Python standalone 解壓失敗，或 bundle 不完整。  
```bash
ls python-install/    # 應有 cpython-3.11.x-linux-x86_64-gnu/ 目錄
# 若空的，重新解壓 tar.gz
tar -xzf <bundle>.tar.gz
```

---

**Q: pip 離線安裝失敗，顯示 `No matching distribution found`**

bundle 的 packages/pip/ 缺少對應平台的 wheel。  
```bash
ls packages/pip/ | wc -l    # 應有 84~90 個 .whl 檔
```
若數量不足，需在有網路的機器重新執行 `prepare-offline-bundle.sh`。

---

**Q: ODBC Driver 安裝後 `pyodbc.connect()` 仍失敗**

確認 ODBC Driver 是否正確安裝：
```bash
odbcinst -q -d
# 應顯示：[ODBC Driver 18 for SQL Server]
```
若未顯示，手動安裝：
```bash
# Ubuntu 20.04
cd packages/odbc/ubuntu20
ACCEPT_EULA=Y dpkg -i libodbc*.deb
ACCEPT_EULA=Y dpkg -i unixodbc*.deb
ACCEPT_EULA=Y dpkg -i msodbcsql18*.deb
dpkg --configure -a
```

---

**Q: SELinux 阻擋連線（RHEL / Rocky）**

症狀：服務啟動成功但 curl 無回應。  
```bash
# 檢查 SELinux
getenforce
sestatus | grep httpd_can_network_connect

# 修復
setsebool -P httpd_can_network_connect 1
systemctl restart vcf-mcp mssql-mcp
```

---

**Q: `systemctl` 指令不可用（容器環境）**

MCP Server 設計為在完整 Linux 系統（有 systemd）上執行，不支援 Docker 容器（除非使用 `--privileged` + systemd）。  
若必須使用容器，可手動啟動：
```bash
# 手動前景執行
source /opt/vcf-mcp/.env
/opt/vcf-mcp/venv/bin/python /opt/vcf-mcp/vcf_mcp_server.py

# 或用 nohup 背景執行
nohup /opt/vcf-mcp/venv/bin/python /opt/vcf-mcp/vcf_mcp_server.py \
  > /var/log/vcf-mcp.log 2>&1 &
```

---

### 服務啟動問題

---

**Q: 服務啟動後立刻停止（`Active: failed`）**

```bash
journalctl -u vcf-mcp -n 30 --no-pager
```
常見原因：
1. `/opt/vcf-mcp/keys.json` 不存在或格式錯誤
2. `/opt/vcf-mcp/cert.pem` 不存在
3. `.env` 格式錯誤（密碼含特殊字元未加引號）

密碼含特殊字元處理：
```bash
# .env 中含 ! @ # $ 等字元，需加引號
vi /opt/vcf-mcp/.env
# 改成：
VCENTER_PASS="P@ssw0rd!Special"
```

---

**Q: 端口被佔用（`Address already in use`）**

```bash
# 找出誰在用 7000 或 7001
ss -tlnp | grep -E '7000|7001'

# 若是舊版服務殘留
systemctl stop vcf-mcp
kill -9 $(lsof -ti:7000)
systemctl start vcf-mcp
```

---

**Q: 服務啟動但 curl 回傳 502 / 503**

Python 套件安裝不完整。重新安裝套件：
```bash
cd /path/to/extracted/bundle
/opt/vcf-mcp/venv/bin/pip install \
  --no-index \
  --find-links packages/pip \
  mcp fastmcp "uvicorn[standard]" python-dotenv cryptography
systemctl restart vcf-mcp
```

---

### 連線與認證問題

---

**Q: Claude Code / Desktop 連線顯示 SSL 錯誤**

因使用自簽憑證，需在客戶端允許不安全連線。  
Claude Code `.mcp.json`：
```json
{
  "mcpServers": {
    "vcf": {
      "type": "sse",
      "url": "https://<IP>:7000/sse",
      "headers": { "Authorization": "Bearer <TOKEN>" },
      "insecure": true
    }
  }
}
```

---

**Q: curl 回傳 401**

Token 不正確或未帶 Token：
```bash
# 確認 Token
cat /opt/vcf-mcp/keys.json

# 測試語法
curl -sk https://localhost:7000/sse \
  -H "Authorization: Bearer 你的Token" \
  -o /dev/null -w "%{http_code}"
```

---

**Q: vCenter / SDDC Manager 工具呼叫失敗，顯示 401**

密碼錯誤。注意：vCenter 與 SDDC Manager 密碼可能不同。  
```bash
vi /opt/vcf-mcp/.env
# 修改對應的 PASS 欄位
systemctl restart vcf-mcp
```
手動驗證：
```bash
# 測試 vCenter
curl -sk -X POST https://<VCENTER_IP>/api/session \
  -u '<USER>:<PASS>' -o /dev/null -w "%{http_code}"
# 應回傳 201

# 測試 SDDC Manager
curl -sk -X POST https://<SDDC_IP>/v1/tokens \
  -H "Content-Type: application/json" \
  -d '{"username":"<USER>","password":"<PASS>"}' \
  -o /dev/null -w "%{http_code}"
# 應回傳 200
```

---

**Q: SQL Server 連線失敗**

1. 確認 SQL Server 開啟混合驗證：  
   SSMS → Server Properties → Security → SQL Server and Windows Authentication mode

2. 確認 sa 帳號已啟用：  
   SSMS → Security → Logins → sa → Status → Login = Enabled

3. 確認 TCP/IP 已啟用：  
   SQL Server Configuration Manager → Protocols → TCP/IP = Enabled

4. 確認防火牆允許 1433：
   ```bash
   # 從 MCP Server 測試
   timeout 5 bash -c "echo >/dev/tcp/<SQL_IP>/1433" && echo "OK" || echo "FAIL"
   ```

---

**Q: mssql_execute_query 顯示「權限不足」**

帳號沒有讀取該資料庫的權限，或 `ALLOW_WRITE=false` 但執行了 DML。  
```bash
cat /opt/mssql-mcp/.env
# 確認 ALLOW_WRITE 設定
```

---

### Log 分析

常見錯誤訊息對照：

| Log 訊息 | 原因 | 解法 |
|----------|------|------|
| `API keys file not found: /opt/vcf-mcp/keys.json` | keys.json 不存在 | 重新安裝或手動建立 |
| `Invalid keys file: must be non-empty JSON object` | keys.json 格式錯誤 | `echo '{"admin":"<新key>"}' > /opt/vcf-mcp/keys.json` |
| `SSL: CERTIFICATE_VERIFY_FAILED` | 客戶端未忽略自簽憑證 | 加 `-k` 或 `insecure: true` |
| `Connection timeout` | MCP Server IP 或 Port 不通 | 確認防火牆、IP、Port |
| `pyodbc.Error: ('01000', ...` | ODBC Driver 問題 | 重裝 ODBC Driver 18 |
| `ModuleNotFoundError: No module named 'mcp'` | Python 套件安裝失敗 | 重新 pip install 離線套件 |

---

## 附錄：快速確認清單

安裝完成後，逐項確認：

```
[ ] vcf-mcp service active
[ ] mssql-mcp service active
[ ] curl 7000 回傳 200（有 Token）
[ ] curl 7000 回傳 401（無 Token）
[ ] curl 7001 回傳 200（有 Token）
[ ] curl 7001 回傳 401（無 Token）
[ ] vCenter token 取得成功
[ ] SQL Server 連線測試成功
[ ] Claude Code .mcp.json 已設定
[ ] Bearer Token 已記錄備份
[ ] /opt/vcf-mcp/keys.json 已備份
```

---

*文件版本：2026-05  |  最後更新：安裝測試後*

---

## 10. Open WebUI 安裝（含 mcpo，離線環境）

> Open WebUI 是使用者與 AI 模型對話的網頁介面，透過 mcpo 橋接 MCP Server，讓 AI 可以直接呼叫 vCenter / SQL 工具。

### 整體元件

| 容器 | Port | 功能 |
|------|------|------|
| `open-webui` | 3000 | 使用者介面（對話、管理） |
| `mcpo` | 8000 | MCP → OpenAPI 協議轉換 |
| `pipelines` | 9099 | 進階 Pipeline（選裝） |

> ⚠️ **先安裝 vcf-mcp + mssql-mcp（第 5、6 節），再裝 Open WebUI。**  
> mcpo 需要連到 MCP Server 的 SSL 憑證。

---

### 10.1 系統需求

| 項目 | 需求 |
|------|------|
| OS | Ubuntu 20.04 / 22.04（建議），RHEL/Rocky 8+ 亦可 |
| CPU | 4 核心以上 |
| 記憶體 | **建議 16 GB**（open-webui 映像含 embedding 模型） |
| 磁碟 | 至少 **20 GB** 可用（映像 open-webui 4.8GB + mcpo 0.5GB + pipelines 3.4GB） |
| 軟體 | Docker 24+、Docker Compose v2 |
| 網路 | 可連到 MCP Server（10.0.0.65:7000 / 7001） |
| 同機或不同機 | Open WebUI 可與 MCP Server 同機，也可分開 |

---

### 10.2 準備離線 Docker 映像（有網路機器）

在**有網路的 Linux 機器**上執行。

```bash
mkdir -p /opt/openwebui-offline
cd /opt/openwebui-offline

# 拉取三個映像
docker pull ghcr.io/open-webui/open-webui:main
docker pull ghcr.io/open-webui/mcpo:main
docker pull ghcr.io/open-webui/pipelines:main    # 選填

# 打包成 tar 檔（約 8 GB 合計）
docker save ghcr.io/open-webui/open-webui:main   -o open-webui.tar     # ~4.8 GB
docker save ghcr.io/open-webui/mcpo:main          -o mcpo.tar           # ~0.5 GB
docker save ghcr.io/open-webui/pipelines:main     -o pipelines.tar      # ~3.4 GB（選填）

ls -lh *.tar
```

> 💡 若只需要 Open WebUI + mcpo（不需要 Pipelines），可略過 `pipelines.tar`。

---

### 10.3 安裝 Docker（目標機器，無網路）

> 若目標機器已有 Docker，可跳過此節。

#### Ubuntu（離線 .deb 安裝）

在**有網路機器**先下載：

```bash
# Ubuntu 22.04
mkdir docker-debs && cd docker-debs
apt-get download \
  docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin \
  iptables libip6tc2 libnetfilter-conntrack3 \
  libxtables12 pigz 2>/dev/null || true

# 也可用官方離線安裝包
curl -fsSL https://download.docker.com/linux/ubuntu/dists/jammy/pool/stable/amd64/ \
  -o /tmp/docker-index.html
# 手動下載 .deb 較複雜，建議用下方 static binary 方式
```

**更簡單：Docker Static Binary（單檔）**

```bash
# 在有網路機器下載（約 70 MB）
curl -O https://download.docker.com/linux/static/stable/x86_64/docker-28.1.1.tgz
curl -O https://github.com/docker/compose/releases/download/v2.35.0/docker-compose-linux-x86_64

# 傳到目標機器後安裝
tar -xzf docker-28.1.1.tgz
cp docker/* /usr/local/bin/
chmod +x /usr/local/bin/docker*

# 安裝 compose plugin
mkdir -p /usr/local/lib/docker/cli-plugins
cp docker-compose-linux-x86_64 /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# 建立 docker group 與啟動
groupadd docker 2>/dev/null || true
dockerd &    # 背景啟動，或設定 systemd service（見下方）
```

**設定 dockerd 為 systemd service：**

```bash
cat > /etc/systemd/system/docker.service << 'EOF'
[Unit]
Description=Docker Application Container Engine
After=network-online.target

[Service]
Type=notify
ExecStart=/usr/local/bin/dockerd
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now docker
docker info    # 確認正常
```

---

### 10.4 傳輸映像到目標機器

```bash
# SCP（Linux / Mac）
scp open-webui.tar mcpo.tar pipelines.tar root@<目標IP>:/opt/

# PSCP（Windows 跳板機）
pscp open-webui.tar  root@<目標IP>:/opt/
pscp mcpo.tar        root@<目標IP>:/opt/
pscp pipelines.tar   root@<目標IP>:/opt/
```

---

### 10.5 載入 Docker 映像（目標機器）

```bash
docker load -i /opt/open-webui.tar
docker load -i /opt/mcpo.tar
docker load -i /opt/pipelines.tar    # 若有下載

# 確認映像已載入
docker images
# 應顯示：
# ghcr.io/open-webui/open-webui   main   ...   4.76GB
# ghcr.io/open-webui/mcpo         main   ...   538MB
# ghcr.io/open-webui/pipelines    main   ...   3.35GB
```

---

### 10.6 建立目錄結構

```bash
mkdir -p /opt/open-webui/mcpo/certs

# 目錄結構：
# /opt/open-webui/
# ├── docker-compose.yml
# ├── mcpo/
# │   ├── config.json        ← MCP 連線設定
# │   └── certs/
# │       └── vcf-mcp.pem    ← MCP Server 的 SSL 憑證（信任用）
```

---

### 10.7 複製 MCP Server SSL 憑證

mcpo 連線到 MCP Server 時需要信任自簽憑證：

```bash
# 從 MCP Server（10.0.0.65）複製憑證
scp root@10.0.0.65:/opt/vcf-mcp/cert.pem /opt/open-webui/mcpo/certs/vcf-mcp.pem

# 若無 SSH 存取，用 openssl 直接抓憑證
openssl s_client -connect 10.0.0.65:7000 -showcerts </dev/null 2>/dev/null \
  | openssl x509 -outform PEM \
  > /opt/open-webui/mcpo/certs/vcf-mcp.pem

echo '[OK]' && cat /opt/open-webui/mcpo/certs/vcf-mcp.pem | head -3
# 應顯示：-----BEGIN CERTIFICATE-----
```

---

### 10.8 設定 mcpo config.json

```bash
# 取得 MCP Server 的 Bearer Token
# （若已安裝 vcf-mcp，在 MCP Server 上執行）
ssh root@10.0.0.65 "cat /opt/vcf-mcp/keys.json"
# 輸出範例：{"admin": "ILnx5ohq04A92X01Sk9rw9Uvjk8f0Nbd02a8wuIFZbw"}
```

用實際 Token 建立 config.json：

```bash
cat > /opt/open-webui/mcpo/config.json << 'EOF'
{
  "mcpServers": {
    "vcf-lab": {
      "type": "sse",
      "url": "https://10.0.0.65:7000/sse",
      "headers": {
        "Authorization": "Bearer 這裡填入實際的Bearer_Token"
      }
    },
    "mssql-lab": {
      "type": "sse",
      "url": "https://10.0.0.65:7001/sse",
      "headers": {
        "Authorization": "Bearer 這裡填入實際的Bearer_Token"
      }
    }
  }
}
EOF
```

> 💡 兩個 MCP Server 共用同一個 Token（存在 `/opt/vcf-mcp/keys.json`）。

---

### 10.9 建立 docker-compose.yml

```bash
cat > /opt/open-webui/docker-compose.yml << 'EOF'
services:
  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    container_name: open-webui
    restart: always
    ports:
      - "3000:8080"
    volumes:
      - open-webui:/app/backend/data
    environment:
      - WEBUI_NAME=Open WebUI
      # Ollama：若有本地 Ollama，填入 IP:Port（多個用分號分隔）
      - OLLAMA_BASE_URL=http://10.0.0.63:11434;http://10.0.0.67:11434
      # 若無 Ollama，可設為空字串或刪除這行
      # - OLLAMA_BASE_URL=

  mcpo:
    image: ghcr.io/open-webui/mcpo:main
    container_name: mcpo
    restart: always
    ports:
      - "8000:8000"
    volumes:
      - ./mcpo/config.json:/app/config.json:ro
      - ./mcpo/certs/vcf-mcp.pem:/certs/vcf-mcp.pem:ro
    environment:
      - SSL_CERT_FILE=/certs/vcf-mcp.pem
      - REQUESTS_CA_BUNDLE=/certs/vcf-mcp.pem
    command: ["--host", "0.0.0.0", "--port", "8000", "--api-key", "openwebui-mcpo-secret",
              "--config", "/app/config.json"]

  pipelines:
    image: ghcr.io/open-webui/pipelines:main
    container_name: pipelines
    restart: always
    ports:
      - "9099:9099"
    volumes:
      - pipelines:/app/pipelines
    environment:
      - PIPELINES_API_KEY=pipelines-secret

volumes:
  open-webui:
  pipelines:
EOF
```

> ⚠️ `openwebui-mcpo-secret` 是 mcpo 的 API Key，之後 Open WebUI 設定 Tool Server 時需要用到，可改成自訂字串。

---

### 10.10 啟動服務

```bash
cd /opt/open-webui

# 啟動全部容器
docker compose up -d

# 確認狀態
docker compose ps
# 應顯示：
# open-webui   running   0.0.0.0:3000->8080/tcp
# mcpo         running   0.0.0.0:8000->8000/tcp
# pipelines    running   0.0.0.0:9099->9099/tcp

# 查看 log
docker compose logs -f --tail=50
```

---

### 10.11 建立 Admin 帳號（首次啟動）

1. 瀏覽器開 `http://<伺服器IP>:3000`
2. 第一次進入會顯示「**Get Started**」按鈕
3. 點擊後填入管理員資料：
   - **Name**：任意名稱（例：kosten）
   - **Email**：你的 Email（例：`admin@company.com`）
   - **Password**：設定密碼（建議 12+ 字元）
4. 點「**Create Admin Account**」
5. 第一個帳號自動成為 admin

> 💡 此帳號的 Email + Password 就是以後登入用的憑證，請記下來。

---

### 10.12 設定 LLM 連線

登入 Open WebUI 後：右上角頭像 → **Admin Panel** → **Settings** → **Connections**

#### 方式 A：Gemini（Google，需網路）

在 **OpenAI API** 區塊點 **+**：

| 欄位 | 值 |
|------|----|
| URL | `https://generativelanguage.googleapis.com/v1beta/openai` |
| API Key | Google AI Studio 產生的 Key（`https://aistudio.google.com`） |

儲存後，模型選單會出現 `gemini-2.5-flash` 等選項。

#### 方式 B：Ollama（本地，不需網路）

在 **Ollama API** 區塊確認 URL 正確：

```
http://10.0.0.63:11434
http://10.0.0.67:11434
```

點旁邊 ↺ 更新按鈕，若連線成功會顯示可用模型列表（如 `llama3.2`、`qwen2.5` 等）。

> 💡 Ollama 完全離線，不需要網路，適合空氣隔離環境。

---

### 10.13 設定 Tool Server（接 MCP）

Admin Panel → **Settings** → **Integrations** → **Manage Tool Servers** → **＋**

加入兩筆：

**第一筆 — VCF Lab：**

| 欄位 | 值 |
|------|----|
| Name | `VCF Lab` |
| URL | `http://<Open-WebUI-IP>:8000/vcf-lab` |
| API Key | `openwebui-mcpo-secret`（與 docker-compose.yml 一致） |

**第二筆 — MSSQL Lab：**

| 欄位 | 值 |
|------|----|
| Name | `MSSQL Lab` |
| URL | `http://<Open-WebUI-IP>:8000/mssql-lab` |
| API Key | `openwebui-mcpo-secret` |

儲存後出現 **「Connections saved successfully」** 即完成。

---

### 10.14 在對話中啟用工具

每次新對話都需要手動啟用工具：

1. 輸入框左下角點 **🔗 工具圖示**（⚡ 或 🔧）
2. 展開 **Tools** → 勾選 **VCF Lab** 和 **MSSQL Lab**（toggle 變綠）
3. 輸入框顯示 `🔗 2` 表示工具已啟用
4. 直接用自然語言提問即可

```
範例問題：
• 幫我列出 vCenter 上所有的 VM 名稱和電源狀態
• SQL Server 的 master 資料庫有哪些 table？
• SDDC Manager 目前有哪些 Domain？
• 查一下 ESXi 主機 10.0.1.10 的 CPU 使用率
```

---

### 10.15 Open WebUI 密碼重設

忘記密碼時，直接用 Python + bcrypt 改 SQLite DB：

```bash
# SSH 進 Open WebUI 所在的機器
ssh root@10.0.0.64

# 執行密碼重設（換成你的 Email 和新密碼）
docker exec open-webui python3 -c "
import sqlite3, bcrypt
new_pw = '你的新密碼'
email  = 'your_email@example.com'

hashed = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
c = sqlite3.connect('/app/backend/data/webui.db')
c.execute('UPDATE auth SET password=? WHERE email=?', (hashed, email))
c.commit()
print('rows updated:', c.total_changes)
"
# 輸出：rows updated: 1  → 成功
```

---

### 10.16 維運指令

```bash
# 查看容器狀態
cd /opt/open-webui && docker compose ps

# 重啟
docker compose restart

# 只重啟 mcpo（修改 config.json 後）
docker compose restart mcpo

# 查 log
docker compose logs open-webui --tail=50 -f
docker compose logs mcpo --tail=50 -f

# 停止全部
docker compose down

# 更新映像（有網路環境）
docker compose pull
docker compose up -d
```

---

### 10.17 常見問題

---

**Q: 瀏覽器開 3000 port 沒反應**

```bash
# 確認容器在跑
docker compose ps

# 確認 port 監聽
ss -tlnp | grep 3000

# 查錯誤 log
docker compose logs open-webui --tail=30
```

---

**Q: mcpo 顯示 `SSL certificate verify failed`**

憑證路徑或內容不正確：
```bash
# 確認憑證存在且格式正確
cat /opt/open-webui/mcpo/certs/vcf-mcp.pem | head -3
# 應顯示：-----BEGIN CERTIFICATE-----

# 確認 docker-compose.yml 的 volume 路徑對應
grep pem /opt/open-webui/docker-compose.yml
```

---

**Q: Tool Server 加入後工具清單是空的**

mcpo 無法連到 MCP Server，查 log：
```bash
docker compose logs mcpo --tail=30
```
常見原因：
- MCP Server 沒有在跑（`systemctl status vcf-mcp`）
- config.json Bearer Token 不正確
- 防火牆阻擋 7000 / 7001 port

---

**Q: 更改 mcpo config.json 後工具沒有更新**

```bash
# 重啟 mcpo 讀取新設定
cd /opt/open-webui && docker compose restart mcpo

# 確認工具已更新
curl -s -H 'Authorization: Bearer openwebui-mcpo-secret' \
  http://localhost:8000/openapi.json | python3 -c \
  'import json,sys; d=json.load(sys.stdin); print(d["info"]["description"])'
```

---

## 附錄 B：離線安裝全套清單

從零到一需要準備的所有檔案：

| 檔案 | 大小（約） | 用途 |
|------|-----------|------|
| `vcf-mcp-offline.tar.gz` | 78 MB | VCF MCP Server |
| `mssql-mcp-offline.tar.gz` | 81 MB | MSSQL MCP Server |
| `open-webui.tar` | 4.8 GB | Open WebUI Docker 映像 |
| `mcpo.tar` | 538 MB | mcpo Docker 映像 |
| `pipelines.tar` | 3.4 GB | Pipelines Docker 映像（選填）|
| `docker-28.x.x.tgz` | 70 MB | Docker Engine（若目標機無 Docker）|
| `docker-compose-linux-x86_64` | 20 MB | Docker Compose v2 |

**總計（含 Pipelines）：約 9 GB**  
**最小安裝（不含 Pipelines）：約 5.5 GB**

---

## 附錄 C：快速安裝順序

```
1. 安裝 Docker（若無）
2. 載入 Docker 映像（docker load）
3. 安裝 vcf-mcp     → bash install.sh
4. 安裝 mssql-mcp   → bash install.sh
5. 複製 SSL 憑證    → /opt/open-webui/mcpo/certs/vcf-mcp.pem
6. 設定 config.json → /opt/open-webui/mcpo/config.json（填 Bearer Token）
7. 建立 docker-compose.yml → /opt/open-webui/
8. docker compose up -d
9. 瀏覽器開 :3000 → 建立 Admin 帳號
10. Settings → Connections → 設定 LLM（Gemini / Ollama）
11. Settings → Integrations → 加入 Tool Server（vcf-lab / mssql-lab）
12. 對話框啟用 Tools → 開始使用
```

---

*文件版本：2026-06  |  最後更新：補充 Open WebUI 完整安裝流程*
