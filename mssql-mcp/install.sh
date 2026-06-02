#!/usr/bin/env bash
# install.sh — MSSQL MCP Server 離線安裝腳本
# 必須在 mssql-mcp-offline/ 目錄內以 root 執行
# 用法: sudo bash install.sh
set -euo pipefail

# ── 顏色與工具函式 ────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
BOLD='\033[1m'
info()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
error()   { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }
step()    { echo -e "\n${CYAN}${BOLD}━━ $* ${NC}"; }
ask()     { echo -e "${YELLOW}${BOLD}>>> $*${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/mssql-mcp"
CERT_DIR="/opt/vcf-mcp"
UV_BIN="$SCRIPT_DIR/uv/uv"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   MSSQL MCP Server — 離線安裝                       ║"
echo "║   SQL Server ↔ Claude AI / Open WebUI               ║"
echo "╚══════════════════════════════════════════════════════╝"
[[ -f "$SCRIPT_DIR/BUNDLE_INFO.txt" ]] && echo "" && cat "$SCRIPT_DIR/BUNDLE_INFO.txt"
echo ""

# ── 前置檢查 ─────────────────────────────────────────────────────────────────
[[ "$EUID" -ne 0 ]] && error "請以 root 執行: sudo bash install.sh"
[[ ! -f "$UV_BIN" ]] && error "找不到 uv binary，請確認在 mssql-mcp-offline/ 目錄內執行"

# 偵測 OS
if [[ -f /etc/os-release ]]; then
  source /etc/os-release
  OS_ID="${ID:-unknown}"
  OS_VERSION_ID="${VERSION_ID:-0}"
else
  OS_ID="unknown"; OS_VERSION_ID="0"
fi
info "作業系統: ${PRETTY_NAME:-$OS_ID $OS_VERSION_ID}"

# ── 互動式設定收集 ────────────────────────────────────────────────────────────
step "設定 SQL Server 連線"
echo ""
ask "SQL Server IP 或主機名稱 (例: 10.0.0.70):"
read -rp "  > " MSSQL_SERVER
[[ -z "$MSSQL_SERVER" ]] && error "SQL Server 位址不能為空"

ask "SQL Server Port [1433]:"
read -rp "  > " MSSQL_PORT
MSSQL_PORT="${MSSQL_PORT:-1433}"

ask "預設資料庫 [master]:"
read -rp "  > " MSSQL_DATABASE
MSSQL_DATABASE="${MSSQL_DATABASE:-master}"

ask "SQL 帳號 [sa]:"
read -rp "  > " MSSQL_USERNAME
MSSQL_USERNAME="${MSSQL_USERNAME:-sa}"

ask "SQL 密碼:"
read -rsp "  > " MSSQL_PASSWORD
echo ""
[[ -z "$MSSQL_PASSWORD" ]] && error "密碼不能為空"

echo ""
step "設定功能選項"
ask "允許 DML 寫入 (INSERT/UPDATE/DELETE)? [Y/n]:"
read -rp "  > " _w; ALLOW_WRITE="true"; [[ "$_w" =~ ^[Nn] ]] && ALLOW_WRITE="false"

ask "允許 DDL 操作 (CREATE/DROP/ALTER)? [Y/n]:"
read -rp "  > " _d; ALLOW_DDL="true"; [[ "$_d" =~ ^[Nn] ]] && ALLOW_DDL="false"

ask "查詢最大回傳列數 [1000]:"
read -rp "  > " MAX_ROWS; MAX_ROWS="${MAX_ROWS:-1000}"

echo ""
step "設定服務選項"
ask "要啟用 Open WebUI 橋接 (mcpo, port 8001)? [Y/n]:"
read -rp "  > " _mcpo; ENABLE_MCPO="true"; [[ "$_mcpo" =~ ^[Nn] ]] && ENABLE_MCPO="false"

ask "MCP Server SSE port [7001]:"
read -rp "  > " MCP_PORT; MCP_PORT="${MCP_PORT:-7001}"

# ── 摘要確認 ─────────────────────────────────────────────────────────────────
echo ""
echo "──────────────────────────────────────────────"
echo "  安裝摘要"
echo "──────────────────────────────────────────────"
echo "  安裝路徑:    $INSTALL_DIR"
echo "  SQL Server:  ${MSSQL_SERVER}:${MSSQL_PORT}"
echo "  資料庫:      $MSSQL_DATABASE"
echo "  帳號:        $MSSQL_USERNAME"
echo "  允許寫入:    $ALLOW_WRITE"
echo "  允許 DDL:    $ALLOW_DDL"
echo "  MCP 端口:    $MCP_PORT (HTTPS)"
echo "  Open WebUI:  $([[ "$ENABLE_MCPO" == "true" ]] && echo '啟用 (port 8001)' || echo '停用')"
echo "──────────────────────────────────────────────"
echo ""
ask "確認安裝? [Y/n]:"
read -rp "  > " _c; [[ "$_c" =~ ^[Nn] ]] && { echo "取消安裝"; exit 0; }

# ══════════════════════════════════════════════════════════════════════════════
step "1/6 安裝 uv"
cp "$UV_BIN" /usr/local/bin/uv
chmod +x /usr/local/bin/uv
info "uv $(/usr/local/bin/uv --version)"

# ══════════════════════════════════════════════════════════════════════════════
step "2/6 安裝 Python 3.11 (standalone)"
export UV_PYTHON_INSTALL_DIR="/root/.local/share/uv/python"
mkdir -p "$UV_PYTHON_INSTALL_DIR"

PYTHON_STANDALONE=$(find "$SCRIPT_DIR/python-install" -name "python3.11" -type f 2>/dev/null | head -1)
if [[ -n "$PYTHON_STANDALONE" ]]; then
  # 從 bundle 複製 Python
  BUNDLE_PY_DIR=$(dirname "$(dirname "$PYTHON_STANDALONE")")
  DEST_NAME=$(basename "$BUNDLE_PY_DIR")
  cp -r "$BUNDLE_PY_DIR" "$UV_PYTHON_INSTALL_DIR/$DEST_NAME" 2>/dev/null || true
  PYTHON311=$(find "$UV_PYTHON_INSTALL_DIR" -name "python3.11" -type f | head -1)
else
  warn "bundle 中無 Python standalone，嘗試 uv 安裝..."
  UV_PYTHON_INSTALL_DIR="$UV_PYTHON_INSTALL_DIR" /usr/local/bin/uv python install 3.11 2>&1 | tail -3
  PYTHON311=$(find "$UV_PYTHON_INSTALL_DIR" -name "python3.11" -type f | head -1)
fi

[[ -z "$PYTHON311" ]] && error "Python 3.11 安裝失敗，找不到 python3.11 binary"
info "Python: $($PYTHON311 --version)  →  $PYTHON311"

# ══════════════════════════════════════════════════════════════════════════════
step "3/6 安裝 Microsoft ODBC Driver 18"

install_odbc_ubuntu() {
  local pkg_dir="$1"
  if [[ ! -d "$pkg_dir" ]] || [[ -z "$(ls -A $pkg_dir 2>/dev/null)" ]]; then
    warn "找不到 ODBC Driver 套件 ($pkg_dir)，跳過"
    return
  fi
  if odbcinst -q -d 2>/dev/null | grep -q "ODBC Driver 18"; then
    info "ODBC Driver 18 已安裝，跳過"; return
  fi
  # 按順序安裝
  for pattern in "libodbc*" "unixodbc*" "odbcinst*" "msodbcsql18*" "mssql-tools*"; do
    for f in "$pkg_dir"/$pattern; do
      [[ -f "$f" ]] && ACCEPT_EULA=Y dpkg -i "$f" 2>/dev/null || true
    done
  done
  dpkg --configure -a 2>/dev/null || true
  if odbcinst -q -d 2>/dev/null | grep -q "ODBC Driver 18"; then
    info "ODBC Driver 18 安裝完成"
  else
    warn "ODBC Driver 安裝可能不完整，請手動驗證: odbcinst -q -d"
  fi
}

install_odbc_rhel() {
  local pkg_dir="$1"
  if [[ ! -d "$pkg_dir" ]] || [[ -z "$(ls -A $pkg_dir 2>/dev/null)" ]]; then
    warn "找不到 ODBC Driver 套件 ($pkg_dir)，跳過"; return
  fi
  ACCEPT_EULA=Y rpm -i "$pkg_dir"/*.rpm 2>/dev/null || true
  info "ODBC Driver RPM 安裝完成"
}

case "$OS_ID" in
  ubuntu)
    VER_MAJOR="${OS_VERSION_ID%%.*}"
    if   [[ "$VER_MAJOR" -ge 22 ]]; then
      install_odbc_ubuntu "$SCRIPT_DIR/packages/odbc/ubuntu22"
    elif [[ "$VER_MAJOR" -ge 20 ]]; then
      install_odbc_ubuntu "$SCRIPT_DIR/packages/odbc/ubuntu20"
    else
      warn "Ubuntu ${OS_VERSION_ID} 未測試，嘗試 ubuntu20 套件"
      install_odbc_ubuntu "$SCRIPT_DIR/packages/odbc/ubuntu20"
    fi ;;
  debian)     install_odbc_ubuntu "$SCRIPT_DIR/packages/odbc/ubuntu22" ;;
  rhel|centos|rocky|almalinux)
    install_odbc_rhel "$SCRIPT_DIR/packages/odbc/rhel" ;;
  *)
    warn "未知 OS: $OS_ID，跳過 ODBC Driver 安裝，請手動安裝" ;;
esac

# ══════════════════════════════════════════════════════════════════════════════
step "4/6 安裝 MCP Server"
mkdir -p "$INSTALL_DIR"
cp -r "$SCRIPT_DIR/src/mssql_mcp" "$INSTALL_DIR/"

# 建立 virtualenv
"$PYTHON311" -m venv "$INSTALL_DIR/venv"
info "venv Python: $($INSTALL_DIR/venv/bin/python --version)"

# 離線安裝套件
"$INSTALL_DIR/venv/bin/pip" install \
  --no-index \
  --find-links "$SCRIPT_DIR/packages/pip" \
  --quiet \
  mcp fastmcp pyodbc "uvicorn[standard]" python-dotenv paramiko mcpo 2>&1 | grep -v "^$" || true
info "Python 套件安裝完成"

# ══════════════════════════════════════════════════════════════════════════════
step "5/6 建立設定檔與憑證"

# .env
cat > "$INSTALL_DIR/.env" << ENVEOF
MSSQL_SERVER=${MSSQL_SERVER}
MSSQL_PORT=${MSSQL_PORT}
MSSQL_DATABASE=${MSSQL_DATABASE}
MSSQL_USERNAME=${MSSQL_USERNAME}
MSSQL_PASSWORD=${MSSQL_PASSWORD}
MSSQL_AUTH_TYPE=sql
ALLOW_WRITE=${ALLOW_WRITE}
ALLOW_DDL=${ALLOW_DDL}
MAX_ROWS=${MAX_ROWS}
QUERY_TIMEOUT=30
MCP_PORT=${MCP_PORT}
ENVEOF
chmod 600 "$INSTALL_DIR/.env"
info ".env 建立完成"

# SSL 憑證
mkdir -p "$CERT_DIR"
if [[ ! -f "$CERT_DIR/cert.pem" ]]; then
  openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout "$CERT_DIR/key.pem" \
    -out "$CERT_DIR/cert.pem" \
    -subj "/CN=mssql-mcp-server" 2>/dev/null
  chmod 600 "$CERT_DIR/key.pem"
  info "SSL 憑證產生完成"
else
  info "使用現有 SSL 憑證"
fi

# API Key
if [[ ! -f "$CERT_DIR/keys.json" ]]; then
  NEW_KEY=$("$INSTALL_DIR/venv/bin/python" -c "import secrets; print(secrets.token_urlsafe(32))")
  echo "{\"admin\": \"${NEW_KEY}\"}" > "$CERT_DIR/keys.json"
  chmod 600 "$CERT_DIR/keys.json"
  echo ""
  warn "★  API Key 已產生，請記錄以下資訊:"
  echo "    Bearer Token: ${NEW_KEY}"
  echo ""
else
  info "使用現有 API Keys ($CERT_DIR/keys.json)"
  NEW_KEY=$(python3 -c "import json; d=json.load(open('$CERT_DIR/keys.json')); print(list(d.values())[0])" 2>/dev/null || echo "(請至 $CERT_DIR/keys.json 查看)")
fi

# ══════════════════════════════════════════════════════════════════════════════
step "6/6 建立 systemd Services"

# 替換佔位符並安裝 service 檔
install_service() {
  local name="$1"
  local src="$SCRIPT_DIR/services/${name}.service"
  local dst="/etc/systemd/system/${name}.service"
  sed "s|INSTALL_DIR_PLACEHOLDER|${INSTALL_DIR}|g" "$src" > "$dst"
  # 替換 MCP port
  sed -i "s|--port 7001|--port ${MCP_PORT}|g" "$dst"
}

install_service "mssql-mcp"
systemctl daemon-reload
systemctl enable mssql-mcp
systemctl restart mssql-mcp
sleep 2
if systemctl is-active --quiet mssql-mcp; then
  info "mssql-mcp service 啟動成功"
else
  warn "mssql-mcp service 啟動失敗，請檢查: journalctl -u mssql-mcp -n 30"
fi

if [[ "$ENABLE_MCPO" == "true" ]]; then
  install_service "mssql-mcpo"
  systemctl enable mssql-mcpo
  systemctl restart mssql-mcpo
  sleep 2
  if systemctl is-active --quiet mssql-mcpo; then
    info "mssql-mcpo service 啟動成功"
  else
    warn "mssql-mcpo service 啟動失敗，請檢查: journalctl -u mssql-mcpo -n 30"
  fi
fi

# 測試 SQL Server 連線
echo ""
warn "測試 SQL Server 連線..."
CONN_RESULT=$("$INSTALL_DIR/venv/bin/python" -c "
import sys; sys.path.insert(0, '$INSTALL_DIR')
import os; os.environ.update({'MSSQL_SERVER':'$MSSQL_SERVER','MSSQL_PORT':'$MSSQL_PORT','MSSQL_DATABASE':'$MSSQL_DATABASE','MSSQL_USERNAME':'$MSSQL_USERNAME','MSSQL_PASSWORD':'$MSSQL_PASSWORD','MSSQL_AUTH_TYPE':'sql'})
from mssql_mcp.database import test_connection
r = test_connection()
print('OK' if r.get('connected') else 'FAIL: ' + r.get('error',''))
" 2>/dev/null) || CONN_RESULT="FAIL: 無法執行連線測試"
if [[ "$CONN_RESULT" == "OK" ]]; then
  info "SQL Server 連線測試成功"
else
  warn "SQL Server 連線測試: $CONN_RESULT"
  warn "請確認 SQL Server 防火牆允許 TCP ${MSSQL_PORT}，帳號密碼正確"
fi

# ══════════════════════════════════════════════════════════════════════════════
SERVER_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   安裝完成！                                             ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  ┌─ Claude Code / Claude Desktop ─────────────────────────"
echo "  │  MCP URL:    https://${SERVER_IP}:${MCP_PORT}/sse"
echo "  │  Token:      Bearer ${NEW_KEY}"
echo "  │"
echo "  │  .mcp.json:"
echo "  │  {"
echo "  │    \"mcpServers\": {"
echo "  │      \"mssql\": {"
echo "  │        \"type\": \"sse\","
echo "  │        \"url\": \"https://${SERVER_IP}:${MCP_PORT}/sse\","
echo "  │        \"headers\": { \"Authorization\": \"Bearer ${NEW_KEY}\" }"
echo "  │      }"
echo "  │    }"
echo "  │  }"
if [[ "$ENABLE_MCPO" == "true" ]]; then
echo "  │"
echo "  ├─ Open WebUI ──────────────────────────────────────────"
echo "  │  Tool Server URL: http://${SERVER_IP}:8001"
echo "  │  Admin → Settings → Tools → 新增 → URL 填入上方"
fi
echo "  │"
echo "  └── 狀態指令 ──────────────────────────────────────────"
echo "      systemctl status mssql-mcp"
echo "      journalctl -u mssql-mcp -f"
[[ "$ENABLE_MCPO" == "true" ]] && echo "      systemctl status mssql-mcpo"
echo ""
