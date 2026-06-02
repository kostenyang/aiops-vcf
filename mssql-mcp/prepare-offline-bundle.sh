#!/usr/bin/env bash
# prepare-offline-bundle.sh
# 在有網路的機器執行，產生完整離線安裝包
# 需求: Linux x86_64, curl, tar
# 用法: bash prepare-offline-bundle.sh
set -euo pipefail

BUNDLE_NAME="mssql-mcp-offline"
BUNDLE_DIR="$BUNDLE_NAME"
PYTHON_VERSION="3.11"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }
step()  { echo -e "\n${GREEN}━━ $* ${NC}"; }

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   MSSQL MCP Server — 離線安裝包準備工具     ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── 前置檢查 ─────────────────────────────────────────────────────────────────
command -v curl &>/dev/null || error "需要 curl"
command -v tar  &>/dev/null || error "需要 tar"

# ── 清除舊 bundle ─────────────────────────────────────────────────────────────
rm -rf "$BUNDLE_DIR"
mkdir -p "$BUNDLE_DIR"/{packages/{pip,odbc/ubuntu20,odbc/ubuntu22},uv,src,services}

# ── Step 1: 下載 uv ────────────────────────────────────────────────────────────
step "1/6 下載 uv（Python 版本管理器）"
UV_URL="https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz"
curl -sSL "$UV_URL" -o /tmp/uv.tar.gz
tar -xzf /tmp/uv.tar.gz -C /tmp/
cp /tmp/uv-x86_64-unknown-linux-gnu/uv "$BUNDLE_DIR/uv/"
chmod +x "$BUNDLE_DIR/uv/uv"
UV="$BUNDLE_DIR/uv/uv"
info "uv $($UV --version)"

# ── Step 2: 下載 Python 3.11 standalone ───────────────────────────────────────
step "2/6 下載 Python ${PYTHON_VERSION} standalone"
export UV_PYTHON_INSTALL_DIR="$BUNDLE_DIR/python-install"
"$UV" python install "$PYTHON_VERSION" 2>&1 | tail -3
PYTHON_BIN=$(find "$BUNDLE_DIR/python-install" -name "python3.11" -type f | head -1)
[[ -z "$PYTHON_BIN" ]] && error "Python 3.11 下載失敗"
info "Python: $($PYTHON_BIN --version)  →  $PYTHON_BIN"

# ── Step 3: 下載 Python 套件 (wheels) ─────────────────────────────────────────
step "3/6 下載 Python 套件"
"$PYTHON_BIN" -m pip download --quiet \
  "mcp[cli]>=1.0.0" \
  "fastmcp>=0.1.0" \
  "pyodbc>=5.0.0" \
  "uvicorn[standard]>=0.30.0" \
  "python-dotenv>=1.0.0" \
  "paramiko>=3.0.0" \
  "mcpo>=0.0.1" \
  -d "$BUNDLE_DIR/packages/pip" \
  --python-version 3.11 \
  --platform manylinux_2_17_x86_64 \
  --only-binary=:all: 2>/dev/null || \
"$PYTHON_BIN" -m pip download --quiet \
  "mcp[cli]>=1.0.0" \
  "fastmcp>=0.1.0" \
  "pyodbc>=5.0.0" \
  "uvicorn[standard]>=0.30.0" \
  "python-dotenv>=1.0.0" \
  "paramiko>=3.0.0" \
  "mcpo>=0.0.1" \
  -d "$BUNDLE_DIR/packages/pip"
info "$(ls $BUNDLE_DIR/packages/pip | wc -l) 個套件"

# ── Step 4: 下載 ODBC Driver ───────────────────────────────────────────────────
step "4/6 下載 Microsoft ODBC Driver 18"

download_odbc() {
  local distro="$1"
  local dir="$2"
  local base="https://packages.microsoft.com/ubuntu/${distro}/prod/pool/main"
  local ok=0
  local pkg_name url_list

  for pkg_path in \
    "m/msodbcsql18" \
    "m/mssql-tools18" \
    "u/unixodbc" \
    "l/libodbc" ; do
    pkg_name=$(basename "$pkg_path")
    url_list=$(curl -sSL --max-time 20 "${base}/${pkg_path}/" 2>/dev/null | \
      grep -oE 'href="[^"]+_amd64\.deb"' | grep -oE '[^"]+_amd64\.deb' | sort -V | tail -5) || true
    for f in $url_list; do
      if curl -sSL --fail --max-time 120 -o "$dir/${pkg_name}_${f##*/}" "${base}/${pkg_path}/${f}" 2>/dev/null; then
        ok=$((ok+1))
        info "  ✓ $f"
        break
      fi
    done
  done
  if [[ $ok -eq 0 ]]; then
    warn "Ubuntu ${distro} ODBC Driver 下載失敗，請手動補充"
  fi
}

warn "下載 Ubuntu 20.04 ODBC Driver..."
download_odbc "20.04" "$BUNDLE_DIR/packages/odbc/ubuntu20"
warn "下載 Ubuntu 22.04 ODBC Driver..."
download_odbc "22.04" "$BUNDLE_DIR/packages/odbc/ubuntu22"

# ── Step 5: 複製程式碼與服務設定 ──────────────────────────────────────────────
step "5/6 複製 MCP Server 程式碼與服務設定"
cp -r src/mssql_mcp "$BUNDLE_DIR/src/"
cp requirements.txt "$BUNDLE_DIR/"

cat > "$BUNDLE_DIR/services/mssql-mcp.service" << 'EOF'
[Unit]
Description=MSSQL MCP Server (Claude Code / Claude Desktop)
After=network.target

[Service]
Type=simple
WorkingDirectory=INSTALL_DIR_PLACEHOLDER
Environment=PYTHONPATH=INSTALL_DIR_PLACEHOLDER
EnvironmentFile=INSTALL_DIR_PLACEHOLDER/.env
ExecStart=INSTALL_DIR_PLACEHOLDER/venv/bin/python -m mssql_mcp.server
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

cat > "$BUNDLE_DIR/services/mssql-mcpo.service" << 'EOF'
[Unit]
Description=MSSQL mcpo Bridge (Open WebUI Tool Server)
After=network.target mssql-mcp.service

[Service]
Type=simple
WorkingDirectory=INSTALL_DIR_PLACEHOLDER
Environment=PYTHONPATH=INSTALL_DIR_PLACEHOLDER
EnvironmentFile=INSTALL_DIR_PLACEHOLDER/.env
ExecStart=INSTALL_DIR_PLACEHOLDER/venv/bin/mcpo --port 8001 --host 0.0.0.0 -- INSTALL_DIR_PLACEHOLDER/venv/bin/python -m mssql_mcp.server_stdio
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

# ── Step 6: 建立安裝腳本與說明 ────────────────────────────────────────────────
step "6/6 建立安裝腳本"
cp install.sh "$BUNDLE_DIR/"
chmod +x "$BUNDLE_DIR/install.sh"

# 版本資訊
cat > "$BUNDLE_DIR/BUNDLE_INFO.txt" << EOF
MSSQL MCP Server — 離線安裝包
打包時間: $(date '+%Y-%m-%d %H:%M:%S')
打包機器: $(uname -n) ($(uname -r))
Python:   $($PYTHON_BIN --version)
uv:       $($UV --version)
套件數量: $(ls $BUNDLE_DIR/packages/pip | wc -l)
EOF

# ── 打包 ──────────────────────────────────────────────────────────────────────
ARCHIVE="${BUNDLE_NAME}.tar.gz"
tar -czf "$ARCHIVE" "$BUNDLE_DIR/"
SIZE=$(du -sh "$ARCHIVE" | cut -f1)
info "輸出: $ARCHIVE ($SIZE)"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   離線安裝包準備完成！                       ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  檔案: $(pwd)/$ARCHIVE ($SIZE)"
echo ""
echo "  複製到客戶機器後執行:"
echo "    tar -xzf $ARCHIVE"
echo "    cd $BUNDLE_DIR"
echo "    sudo bash install.sh"
echo ""
