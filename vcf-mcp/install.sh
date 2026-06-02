#!/usr/bin/env bash
# install.sh — VCF MCP Server 離線安裝腳本
# 必須在 vcf-mcp-offline/ 目錄內以 root 執行
# 用法: sudo bash install.sh
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }
step()  { echo -e "\n${CYAN}${BOLD}━━ $* ${NC}"; }
ask()   { echo -e "${YELLOW}${BOLD}>>> $*${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/vcf-mcp"
UV_BIN="$SCRIPT_DIR/uv/uv"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   VCF MCP Server — 離線安裝                                 ║"
echo "║   VMware Cloud Foundation ↔ Claude AI / Open WebUI          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
[[ -f "$SCRIPT_DIR/BUNDLE_INFO.txt" ]] && echo "" && cat "$SCRIPT_DIR/BUNDLE_INFO.txt"
echo ""

[[ "$EUID" -ne 0 ]] && error "請以 root 執行: sudo bash install.sh"
[[ ! -f "$UV_BIN" ]] && error "找不到 uv binary，請確認在 vcf-mcp-offline/ 目錄內執行"

# 偵測 OS
if [[ -f /etc/os-release ]]; then
  source /etc/os-release
  OS_ID="${ID:-unknown}"
  OS_VERSION_ID="${VERSION_ID:-0}"
else
  OS_ID="unknown"; OS_VERSION_ID="0"
fi
info "作業系統: ${PRETTY_NAME:-$OS_ID $OS_VERSION_ID}"

# ── 互動式設定 ────────────────────────────────────────────────────────────────
step "設定 VCF 環境基本資訊"
echo ""
ask "環境名稱 (例: CustomerA-Prod, Lab-VCF91) [VCF-Management]:"
read -rp "  > " ENVIRONMENT_NAME
ENVIRONMENT_NAME="${ENVIRONMENT_NAME:-VCF-Management}"

# ── vCenter ───────────────────────────────────────────────────────────────────
step "設定 vCenter"
echo ""
ask "vCenter IP 位址:"
read -rp "  > " VCENTER_IP
[[ -z "$VCENTER_IP" ]] && error "vCenter IP 不能為空"

ask "vCenter FQDN (選填，例: vcenter.domain.com):"
read -rp "  > " VCENTER_FQDN

ask "vCenter SSO 帳號 [administrator@vsphere.local]:"
read -rp "  > " VCENTER_USER
VCENTER_USER="${VCENTER_USER:-administrator@vsphere.local}"

ask "vCenter 密碼:"
read -rsp "  > " VCENTER_PASS; echo ""
[[ -z "$VCENTER_PASS" ]] && error "vCenter 密碼不能為空"

# ── SDDC Manager ──────────────────────────────────────────────────────────────
step "設定 SDDC Manager"
echo ""
ask "SDDC Manager IP 位址:"
read -rp "  > " SDDC_MANAGER_IP
[[ -z "$SDDC_MANAGER_IP" ]] && error "SDDC Manager IP 不能為空"

ask "SDDC Manager 密碼 (帳號同 vCenter: $VCENTER_USER):"
read -rsp "  > " SDDC_MANAGER_PASS; echo ""
[[ -z "$SDDC_MANAGER_PASS" ]] && error "SDDC Manager 密碼不能為空"

# ── VCF Installer ─────────────────────────────────────────────────────────────
step "設定 VCF Installer / Cloud Builder (選填)"
echo ""
ask "VCF Installer IP (無則按 Enter 跳過):"
read -rp "  > " VCF_INSTALLER_IP
VCF_INSTALLER_USER="admin@local"
VCF_INSTALLER_PASS=""
if [[ -n "$VCF_INSTALLER_IP" ]]; then
  ask "VCF Installer 帳號 [admin@local]:"
  read -rp "  > " VCF_INSTALLER_USER
  VCF_INSTALLER_USER="${VCF_INSTALLER_USER:-admin@local}"
  ask "VCF Installer 密碼:"
  read -rsp "  > " VCF_INSTALLER_PASS; echo ""
fi

# ── Aria Operations ───────────────────────────────────────────────────────────
step "設定 Aria Operations / vRealize Operations (選填)"
echo ""
ask "Aria Operations IP (無則按 Enter 跳過):"
read -rp "  > " VROPS_IP
VROPS_PASS=""
if [[ -n "$VROPS_IP" ]]; then
  ask "Aria Operations 密碼 (帳號: admin):"
  read -rsp "  > " VROPS_PASS; echo ""
fi

# ── SSH & Network ─────────────────────────────────────────────────────────────
step "設定 SSH 與網路"
echo ""
ask "ESXi / Linux 主機預設 SSH 密碼 (root 帳號):"
read -rsp "  > " DEFAULT_SSH_PASS; echo ""

ask "DNS Server IP (用於 check_dns 工具):"
read -rp "  > " DNS_SERVER

ask "ESXi 主機 IP 列表 (逗號分隔，選填):"
read -rp "  例: 192.168.1.11,192.168.1.12 > " ESXI_HOSTS

# ── 服務設定 ──────────────────────────────────────────────────────────────────
step "設定服務選項"
echo ""
ask "MCP Server HTTPS 端口 [7000]:"
read -rp "  > " MCP_PORT
MCP_PORT="${MCP_PORT:-7000}"

ask "啟用 Open WebUI 橋接 (mcpo, HTTP port 8000)? [Y/n]:"
read -rp "  > " _mcpo
ENABLE_MCPO="true"
[[ "$_mcpo" =~ ^[Nn] ]] && ENABLE_MCPO="false"

# ── 摘要確認 ─────────────────────────────────────────────────────────────────
echo ""
echo "──────────────────────────────────────────────────────────"
echo "  安裝摘要"
echo "──────────────────────────────────────────────────────────"
echo "  安裝路徑:      $INSTALL_DIR"
echo "  環境名稱:      $ENVIRONMENT_NAME"
echo "  vCenter:       $VCENTER_IP  ($VCENTER_USER)"
[[ -n "$VCENTER_FQDN" ]] && echo "  vCenter FQDN:  $VCENTER_FQDN"
echo "  SDDC Manager:  $SDDC_MANAGER_IP"
[[ -n "$VCF_INSTALLER_IP" ]] && echo "  VCF Installer: $VCF_INSTALLER_IP  ($VCF_INSTALLER_USER)"
[[ -n "$VROPS_IP" ]] && echo "  Aria Ops:      $VROPS_IP"
echo "  DNS Server:    ${DNS_SERVER:-'(未設定)'}"
[[ -n "$ESXI_HOSTS" ]] && echo "  ESXi Hosts:    $ESXI_HOSTS"
echo "  MCP 端口:      $MCP_PORT (HTTPS/SSE)"
echo "  Open WebUI:    $([[ "$ENABLE_MCPO" == "true" ]] && echo '啟用 (HTTP port 8000)' || echo '停用')"
echo "──────────────────────────────────────────────────────────"
echo ""
ask "確認安裝? [Y/n]:"
read -rp "  > " _c
[[ "$_c" =~ ^[Nn] ]] && { echo "取消安裝"; exit 0; }

# ══════════════════════════════════════════════════════════════════════════════
step "1/5 安裝 uv"
cp "$UV_BIN" /usr/local/bin/uv
chmod +x /usr/local/bin/uv
info "uv $(/usr/local/bin/uv --version)"

# ══════════════════════════════════════════════════════════════════════════════
step "2/5 安裝 Python 3.11 (standalone)"
export UV_PYTHON_INSTALL_DIR="/root/.local/share/uv/python"
mkdir -p "$UV_PYTHON_INSTALL_DIR"

PYTHON_STANDALONE=$(find "$SCRIPT_DIR/python-install" -name "python3.11" -type f 2>/dev/null | head -1)
if [[ -n "$PYTHON_STANDALONE" ]]; then
  BUNDLE_PY_DIR=$(dirname "$(dirname "$PYTHON_STANDALONE")")
  DEST_NAME=$(basename "$BUNDLE_PY_DIR")
  cp -r "$BUNDLE_PY_DIR" "$UV_PYTHON_INSTALL_DIR/$DEST_NAME" 2>/dev/null || true
  PYTHON311=$(find "$UV_PYTHON_INSTALL_DIR" -name "python3.11" -type f | head -1)
else
  warn "bundle 中無 Python standalone，嘗試 uv 安裝（需要網路）..."
  UV_PYTHON_INSTALL_DIR="$UV_PYTHON_INSTALL_DIR" /usr/local/bin/uv python install 3.11 2>&1 | tail -3
  PYTHON311=$(find "$UV_PYTHON_INSTALL_DIR" -name "python3.11" -type f | head -1)
fi

[[ -z "$PYTHON311" ]] && error "Python 3.11 安裝失敗，找不到 python3.11 binary"
info "Python: $($PYTHON311 --version)  →  $PYTHON311"

# ══════════════════════════════════════════════════════════════════════════════
step "3/5 安裝 MCP Server"
mkdir -p "$INSTALL_DIR"
cp "$SCRIPT_DIR/vcf_mcp_server.py" "$INSTALL_DIR/"

"$PYTHON311" -m venv "$INSTALL_DIR/venv"
info "venv Python: $($INSTALL_DIR/venv/bin/python --version)"

"$INSTALL_DIR/venv/bin/pip" install \
  --no-index \
  --find-links "$SCRIPT_DIR/packages/pip" \
  --quiet \
  mcp fastmcp "uvicorn[standard]" paramiko requests urllib3 python-dotenv cryptography mcpo \
  2>&1 | grep -v "^$" || true
info "Python 套件安裝完成"

# SELinux policy (RHEL/Rocky/AlmaLinux)
if command -v getenforce &>/dev/null && [[ "$(getenforce)" != "Disabled" ]]; then
  warn "偵測到 SELinux，設定 httpd_can_network_connect..."
  setsebool -P httpd_can_network_connect 1 2>/dev/null || true
fi

# ══════════════════════════════════════════════════════════════════════════════
step "4/5 建立設定檔與憑證"

# .env
cat > "$INSTALL_DIR/.env" << ENVEOF
ENVIRONMENT_NAME=${ENVIRONMENT_NAME}

VCENTER_IP=${VCENTER_IP}
VCENTER_FQDN=${VCENTER_FQDN:-}
VCENTER_USER=${VCENTER_USER}
VCENTER_PASS=${VCENTER_PASS}

VCF_INSTALLER_IP=${VCF_INSTALLER_IP:-}
VCF_INSTALLER_USER=${VCF_INSTALLER_USER}
VCF_INSTALLER_PASS=${VCF_INSTALLER_PASS:-}

SDDC_MANAGER_IP=${SDDC_MANAGER_IP}
SDDC_MANAGER_USER=${VCENTER_USER}
SDDC_MANAGER_PASS=${SDDC_MANAGER_PASS}

VROPS_IP=${VROPS_IP:-}
VROPS_USER=admin
VROPS_PASS=${VROPS_PASS:-}

DEFAULT_SSH_USER=root
DEFAULT_SSH_PASS=${DEFAULT_SSH_PASS:-}

DNS_SERVER=${DNS_SERVER:-}
ESXI_HOSTS=${ESXI_HOSTS:-}

MCP_PORT=${MCP_PORT}
ENVEOF
chmod 600 "$INSTALL_DIR/.env"
info ".env 建立完成 (chmod 600)"

# SSL 憑證
if [[ ! -f "$INSTALL_DIR/cert.pem" ]]; then
  openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout "$INSTALL_DIR/key.pem" \
    -out    "$INSTALL_DIR/cert.pem" \
    -subj "/CN=vcf-mcp-server" 2>/dev/null
  chmod 600 "$INSTALL_DIR/key.pem"
  info "SSL 憑證產生完成 (有效期 10 年)"
else
  info "使用現有 SSL 憑證 ($INSTALL_DIR/cert.pem)"
fi

# API Key
if [[ ! -f "$INSTALL_DIR/keys.json" ]]; then
  NEW_KEY=$("$INSTALL_DIR/venv/bin/python" -c "import secrets; print(secrets.token_urlsafe(32))")
  echo "{\"admin\": \"${NEW_KEY}\"}" > "$INSTALL_DIR/keys.json"
  chmod 600 "$INSTALL_DIR/keys.json"
  echo ""
  warn "★  API Key 已產生，請立即記錄以下資訊："
  echo "    Bearer Token: ${NEW_KEY}"
  echo ""
else
  info "使用現有 API Keys ($INSTALL_DIR/keys.json)"
  NEW_KEY=$("$INSTALL_DIR/venv/bin/python" -c \
    "import json; d=json.load(open('$INSTALL_DIR/keys.json')); print(list(d.values())[0])" \
    2>/dev/null || echo "(請至 $INSTALL_DIR/keys.json 查看)")
fi

# ══════════════════════════════════════════════════════════════════════════════
step "5/5 建立 systemd Services"

install_service() {
  local name="$1"
  local src="$SCRIPT_DIR/services/${name}.service"
  local dst="/etc/systemd/system/${name}.service"
  sed "s|INSTALL_DIR_PLACEHOLDER|${INSTALL_DIR}|g" "$src" > "$dst"
}

install_service "vcf-mcp"
systemctl daemon-reload
systemctl enable vcf-mcp
systemctl restart vcf-mcp
sleep 2
if systemctl is-active --quiet vcf-mcp; then
  info "vcf-mcp service 啟動成功"
else
  warn "vcf-mcp service 啟動失敗，請檢查: journalctl -u vcf-mcp -n 30"
fi

if [[ "$ENABLE_MCPO" == "true" ]]; then
  install_service "vcf-mcpo"
  systemctl enable vcf-mcpo
  systemctl restart vcf-mcpo
  sleep 2
  if systemctl is-active --quiet vcf-mcpo; then
    info "vcf-mcpo service 啟動成功"
  else
    warn "vcf-mcpo service 啟動失敗，請檢查: journalctl -u vcf-mcpo -n 30"
  fi
fi

# 連線驗證
echo ""
warn "驗證 MCP Server 連線..."
sleep 2
HTTP_CODE=$(curl -sk --max-time 5 \
  "https://localhost:${MCP_PORT}/sse" \
  -H "Authorization: Bearer ${NEW_KEY}" \
  -o /dev/null -w "%{http_code}" 2>/dev/null) || true
if [[ "${HTTP_CODE:0:3}" == "200" ]]; then
  info "MCP Server HTTPS 連線驗證成功 (HTTP 200)"
else
  warn "連線回傳 HTTP ${HTTP_CODE:0:3}（可能仍在啟動中），請稍後手動確認："
  warn "  curl -sk https://localhost:${MCP_PORT}/sse -H 'Authorization: Bearer ${NEW_KEY}'"
fi

# ══════════════════════════════════════════════════════════════════════════════
SERVER_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   安裝完成！                                                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  ┌─ Claude Code / Claude Desktop ───────────────────────────────"
echo "  │  MCP URL:   https://${SERVER_IP}:${MCP_PORT}/sse"
echo "  │  Token:     Bearer ${NEW_KEY}"
echo "  │"
echo "  │  .mcp.json 範例："
echo "  │  {"
echo "  │    \"mcpServers\": {"
echo "  │      \"vcf\": {"
echo "  │        \"type\": \"sse\","
echo "  │        \"url\": \"https://${SERVER_IP}:${MCP_PORT}/sse\","
echo "  │        \"headers\": { \"Authorization\": \"Bearer ${NEW_KEY}\" }"
echo "  │      }"
echo "  │    }"
echo "  │  }"
if [[ "$ENABLE_MCPO" == "true" ]]; then
echo "  │"
echo "  ├─ Open WebUI ─────────────────────────────────────────────────"
echo "  │  Tool Server URL: http://${SERVER_IP}:8000"
echo "  │  Admin → Settings → Tools → 新增上方 URL"
fi
echo "  │"
echo "  └─ 維運指令 ───────────────────────────────────────────────────"
echo "     systemctl status vcf-mcp"
echo "     journalctl -u vcf-mcp -f"
[[ "$ENABLE_MCPO" == "true" ]] && echo "     systemctl status vcf-mcpo"
echo ""
echo "  設定檔:  $INSTALL_DIR/.env"
echo "  API Keys: $INSTALL_DIR/keys.json"
echo ""
echo "  新增客戶端 API Key："
echo "    python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
echo "    # 加入 $INSTALL_DIR/keys.json 後 systemctl restart vcf-mcp"
echo ""
