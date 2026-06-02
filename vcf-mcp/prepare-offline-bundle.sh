#!/usr/bin/env bash
# prepare-offline-bundle.sh
# 在有網路的 Linux x86_64 機器上執行，產生 VCF MCP Server 完整離線安裝包。
#
# 需求: curl, tar, Python 3.11+
# 用法: bash prepare-offline-bundle.sh
#
# 輸出: vcf-mcp-offline.tar.gz  (~200-400 MB)
#       解壓後執行: sudo bash vcf-mcp-offline/install.sh
set -euo pipefail

BUNDLE_NAME="vcf-mcp-offline"
BUNDLE_DIR="$BUNDLE_NAME"
PYTHON_VERSION="3.11"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }
step()  { echo -e "\n${GREEN}━━ $* ${NC}"; }

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   VCF MCP Server — 離線安裝包準備工具               ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

command -v curl &>/dev/null || error "需要 curl"
command -v tar  &>/dev/null || error "需要 tar"

# ── 確認在正確目錄 ────────────────────────────────────────────────────────────
[[ -f "vcf_mcp_server.py" ]] || error "請在 vcf-mcp/ 目錄內執行此腳本"

# ── 清除舊 bundle ─────────────────────────────────────────────────────────────
rm -rf "$BUNDLE_DIR"
mkdir -p "$BUNDLE_DIR"/{packages/pip,uv,services}

# ── Step 1: 下載 uv ────────────────────────────────────────────────────────────
step "1/5 下載 uv（Python 版本管理器）"
UV_URL="https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz"
curl -sSL "$UV_URL" -o /tmp/uv-vcf.tar.gz
tar -xzf /tmp/uv-vcf.tar.gz -C /tmp/
cp /tmp/uv-x86_64-unknown-linux-gnu/uv "$BUNDLE_DIR/uv/"
chmod +x "$BUNDLE_DIR/uv/uv"
UV="$BUNDLE_DIR/uv/uv"
info "uv $($UV --version)"

# ── Step 2: 下載 Python 3.11 standalone ───────────────────────────────────────
step "2/5 下載 Python ${PYTHON_VERSION} standalone"
export UV_PYTHON_INSTALL_DIR="$BUNDLE_DIR/python-install"
"$UV" python install "$PYTHON_VERSION" 2>&1 | tail -3
PYTHON_BIN=$(find "$BUNDLE_DIR/python-install" -name "python3.11" -type f | head -1)
[[ -z "$PYTHON_BIN" ]] && error "Python 3.11 下載失敗"
info "Python: $($PYTHON_BIN --version)  →  $PYTHON_BIN"

# ── Step 3: 下載 Python 套件 (wheels) ─────────────────────────────────────────
step "3/5 下載 Python 套件 (manylinux wheels)"
"$PYTHON_BIN" -m pip download --quiet \
  "mcp[cli]>=1.0.0" \
  "fastmcp>=0.1.0" \
  "uvicorn[standard]>=0.30.0" \
  "paramiko>=3.0.0" \
  "requests>=2.31.0" \
  "urllib3>=2.0.0" \
  "python-dotenv>=1.0.0" \
  "cryptography>=41.0.0" \
  "mcpo>=0.0.1" \
  -d "$BUNDLE_DIR/packages/pip" \
  --python-version 3.11 \
  --platform manylinux_2_17_x86_64 \
  --only-binary=:all: 2>/dev/null || {
  warn "manylinux 下載失敗，改用本機平台下載（請在 Linux x86_64 上執行）"
  "$PYTHON_BIN" -m pip download --quiet \
    "mcp[cli]>=1.0.0" \
    "fastmcp>=0.1.0" \
    "uvicorn[standard]>=0.30.0" \
    "paramiko>=3.0.0" \
    "requests>=2.31.0" \
    "urllib3>=2.0.0" \
    "python-dotenv>=1.0.0" \
    "cryptography>=41.0.0" \
    "mcpo>=0.0.1" \
    -d "$BUNDLE_DIR/packages/pip"
}
info "$(ls "$BUNDLE_DIR/packages/pip" | wc -l) 個套件"

# ── Step 4: 複製程式碼與 Service 設定 ─────────────────────────────────────────
step "4/5 複製程式碼與服務設定"
cp vcf_mcp_server.py  "$BUNDLE_DIR/"
cp requirements.txt   "$BUNDLE_DIR/"
cp .env.example       "$BUNDLE_DIR/"

cat > "$BUNDLE_DIR/services/vcf-mcp.service" << 'SVCEOF'
[Unit]
Description=VCF MCP Server (Claude Code / Claude Desktop)
After=network.target

[Service]
Type=simple
WorkingDirectory=INSTALL_DIR_PLACEHOLDER
EnvironmentFile=INSTALL_DIR_PLACEHOLDER/.env
ExecStart=INSTALL_DIR_PLACEHOLDER/venv/bin/python INSTALL_DIR_PLACEHOLDER/vcf_mcp_server.py
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF

cat > "$BUNDLE_DIR/services/vcf-mcpo.service" << 'SVCEOF'
[Unit]
Description=VCF mcpo Bridge (Open WebUI Tool Server)
After=network.target vcf-mcp.service

[Service]
Type=simple
WorkingDirectory=INSTALL_DIR_PLACEHOLDER
EnvironmentFile=INSTALL_DIR_PLACEHOLDER/.env
ExecStart=INSTALL_DIR_PLACEHOLDER/venv/bin/mcpo --port 8000 --host 0.0.0.0 -- \
  INSTALL_DIR_PLACEHOLDER/venv/bin/python -c \
  "import sys; sys.path.insert(0,'INSTALL_DIR_PLACEHOLDER'); from vcf_mcp_server import stdio_main; stdio_main()"
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF

# ── Step 5: 安裝腳本 ──────────────────────────────────────────────────────────
step "5/5 複製安裝腳本"
cp install.sh "$BUNDLE_DIR/"
chmod +x "$BUNDLE_DIR/install.sh"

# Bundle 資訊
cat > "$BUNDLE_DIR/BUNDLE_INFO.txt" << EOF
VCF MCP Server — 離線安裝包
打包時間: $(date '+%Y-%m-%d %H:%M:%S')
打包機器: $(uname -n) ($(uname -r))
Python:   $($PYTHON_BIN --version)
uv:       $($UV --version)
套件數量: $(ls "$BUNDLE_DIR/packages/pip" | wc -l)
EOF

# ── 打包 ──────────────────────────────────────────────────────────────────────
ARCHIVE="${BUNDLE_NAME}.tar.gz"
tar -czf "$ARCHIVE" "$BUNDLE_DIR/"
SIZE=$(du -sh "$ARCHIVE" | cut -f1)

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   離線安裝包準備完成！                               ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  檔案: $(pwd)/$ARCHIVE  ($SIZE)"
echo ""
echo "  複製到目標機器後執行："
echo "    tar -xzf $ARCHIVE"
echo "    cd $BUNDLE_DIR"
echo "    sudo bash install.sh"
echo ""
