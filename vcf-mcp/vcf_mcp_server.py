#!/usr/bin/env python3
"""
VCF MCP Server — Customer Edition
Runs on Ubuntu / RHEL Linux, exposes tools for Claude to interact with
VMware Cloud Foundation environments.

All IPs and credentials are configured via /opt/vcf-mcp/.env — no hardcoded
lab addresses. Suitable for customer on-site deployment.

Tools:
  ssh_exec              - SSH into any host and run a command
  get_ssl_thumbprint    - Get SHA-256 SSL cert thumbprint
  vcenter_api           - vCenter REST API calls
  vcf_installer_api     - VCF Installer REST API calls
  sddc_manager_api      - SDDC Manager REST API calls
  vrops_api             - Aria Operations (vROps) REST API calls (optional)
  check_dns             - DNS resolution check
  ping_host             - Network reachability check
  vcf_version           - Detect VCF component version
  list_environments     - List configured VCF environments

Start:  python3 vcf_mcp_server.py
Port:   https://0.0.0.0:7000/sse  (override with MCP_PORT in .env)

Config:   /opt/vcf-mcp/.env
API keys: /opt/vcf-mcp/keys.json
SSL cert: /opt/vcf-mcp/cert.pem  /opt/vcf-mcp/key.pem
"""

import hashlib
import json
import os
import pathlib
import socket
import ssl
import subprocess

import paramiko
import requests
import urllib3
import uvicorn
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

load_dotenv("/opt/vcf-mcp/.env")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Configuration (all from .env) ────────────────────────────────────────────
VCENTER_IP   = os.getenv("VCENTER_IP", "")
VCENTER_FQDN = os.getenv("VCENTER_FQDN", "")
VCENTER_USER = os.getenv("VCENTER_USER", "administrator@vsphere.local")
VCENTER_PASS = os.getenv("VCENTER_PASS", "")

VCF_INSTALLER_IP   = os.getenv("VCF_INSTALLER_IP", "")
VCF_INSTALLER_USER = os.getenv("VCF_INSTALLER_USER", "admin@local")
VCF_INSTALLER_PASS = os.getenv("VCF_INSTALLER_PASS", "")

SDDC_MANAGER_IP   = os.getenv("SDDC_MANAGER_IP", "")
SDDC_MANAGER_USER = os.getenv("SDDC_MANAGER_USER", "administrator@vsphere.local")
SDDC_MANAGER_PASS = os.getenv("SDDC_MANAGER_PASS", "")

VROPS_IP   = os.getenv("VROPS_IP", "")
VROPS_USER = os.getenv("VROPS_USER", "admin")
VROPS_PASS = os.getenv("VROPS_PASS", "")

DEFAULT_SSH_USER = os.getenv("DEFAULT_SSH_USER", "root")
DEFAULT_SSH_PASS = os.getenv("DEFAULT_SSH_PASS", "")

DNS_SERVER = os.getenv("DNS_SERVER", "")

MCP_PORT = int(os.getenv("MCP_PORT", "7000"))

SSL_CERTFILE      = "/opt/vcf-mcp/cert.pem"
SSL_KEYFILE       = "/opt/vcf-mcp/key.pem"
API_KEYS_FILE     = pathlib.Path("/opt/vcf-mcp/keys.json")
ENVIRONMENTS_FILE = pathlib.Path("/opt/vcf-mcp/environments.json")


# ── Environments ──────────────────────────────────────────────────────────────
def _load_environments() -> dict:
    """Load from environments.json; fall back to single-env from .env vars."""
    if ENVIRONMENTS_FILE.exists():
        try:
            with ENVIRONMENTS_FILE.open() as f:
                return json.load(f)
        except Exception:
            pass

    env_name  = os.getenv("ENVIRONMENT_NAME", "Management")
    esxi_list = [h.strip() for h in os.getenv("ESXI_HOSTS", "").split(",") if h.strip()]
    entry: dict = {"purpose": os.getenv("ENVIRONMENT_PURPOSE", "VCF Management Domain")}
    for k, v in [
        ("vcenter_ip",       VCENTER_IP),
        ("vcenter_fqdn",     VCENTER_FQDN),
        ("sddc_manager_ip",  SDDC_MANAGER_IP),
        ("vcf_installer_ip", VCF_INSTALLER_IP),
    ]:
        if v:
            entry[k] = v
    if esxi_list:
        entry["esxi_hosts"] = esxi_list
    return {env_name: entry}


LAB_ENVIRONMENTS = _load_environments()


# ── API Keys ──────────────────────────────────────────────────────────────────
def _load_api_keys() -> dict[str, str]:
    if not API_KEYS_FILE.exists():
        raise RuntimeError(f"API keys file not found: {API_KEYS_FILE}")
    with API_KEYS_FILE.open() as f:
        keys = json.load(f)
    if not isinstance(keys, dict) or not keys:
        raise RuntimeError("Invalid keys file: must be non-empty JSON object")
    return keys


API_KEYS: dict[str, str] = _load_api_keys()

mcp = FastMCP(
    "vcf-mcp",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)


# ── API Key Middleware (pure ASGI, SSE-safe) ──────────────────────────────────
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
                        [b"www-authenticate", b'Bearer realm="vcf-mcp"'],
                    ],
                })
                await send({"type": "http.response.body",
                            "body": b'{"error":"Unauthorized"}'})
                return
        await self.app(scope, receive, send)


# ── Token helpers ─────────────────────────────────────────────────────────────
def _vcenter_token(ip: str = "", user: str = "", pwd: str = "") -> str:
    ip   = ip   or VCENTER_IP
    user = user or VCENTER_USER
    pwd  = pwd  or VCENTER_PASS
    resp = requests.post(f"https://{ip}/api/session", auth=(user, pwd),
                         verify=False, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _vcf_token(ip: str = "", user: str = "", pwd: str = "") -> str:
    ip   = ip   or VCF_INSTALLER_IP
    user = user or VCF_INSTALLER_USER
    pwd  = pwd  or VCF_INSTALLER_PASS
    resp = requests.post(
        f"https://{ip}/v1/tokens",
        json={"username": user, "password": pwd},
        verify=False, timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("accessToken", "")


def _sddc_token(ip: str = "", user: str = "", pwd: str = "") -> str:
    ip   = ip   or SDDC_MANAGER_IP
    user = user or SDDC_MANAGER_USER
    pwd  = pwd  or SDDC_MANAGER_PASS
    resp = requests.post(
        f"https://{ip}/v1/tokens",
        json={"username": user, "password": pwd},
        verify=False, timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("accessToken", "")


def _vrops_token(ip: str = "", user: str = "", pwd: str = "") -> str:
    ip   = ip   or VROPS_IP
    user = user or VROPS_USER
    pwd  = pwd  or VROPS_PASS
    resp = requests.post(
        f"https://{ip}/suite-api/api/auth/token/acquire",
        json={"username": user, "password": pwd, "authSource": "Local"},
        headers={"Accept": "application/json"},
        verify=False, timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("token", "")


# ── Tools ─────────────────────────────────────────────────────────────────────
@mcp.tool()
def ssh_exec(host: str, command: str, username: str = "", password: str = "") -> str:
    """
    Execute a shell command on any host via SSH and return stdout+stderr.
    Works for ESXi hosts, SDDC Manager, VCF Installer, etc.

    username defaults to DEFAULT_SSH_USER (.env), password to DEFAULT_SSH_PASS.
    Example: ssh_exec("192.168.1.11", "esxcli system version get")
    """
    username = username or DEFAULT_SSH_USER
    password = password or DEFAULT_SSH_PASS
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(host, username=username, password=password, timeout=30,
                       look_for_keys=False, allow_agent=False)
        _, stdout, stderr = client.exec_command(command, timeout=60)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        return (out + err).strip() or "(no output)"
    except Exception as exc:
        return f"SSH error connecting to {host}: {exc}"
    finally:
        client.close()


@mcp.tool()
def get_ssl_thumbprint(host: str, port: int = 443) -> str:
    """
    Return the SHA-256 SSL certificate thumbprint (colon-separated) for any host.
    Useful for getting ESXi thumbprints before VCF bringup.
    Example: get_ssl_thumbprint("192.168.1.11")
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                der = tls.getpeercert(binary_form=True)
                digest = hashlib.sha256(der).hexdigest().upper()
                return ":".join(digest[i:i+2] for i in range(0, len(digest), 2))
    except Exception as exc:
        return f"Error getting thumbprint from {host}:{port}: {exc}"


@mcp.tool()
def vcenter_api(
    method: str,
    path: str,
    body: str = "",
    vcenter_ip: str = "",
    username: str = "",
    password: str = "",
) -> str:
    """
    Make a vCenter REST API call.
    method    : GET | POST | PUT | PATCH | DELETE
    path      : e.g. /api/vcenter/cluster, /api/vcenter/host
    body      : JSON string for POST/PUT/PATCH (leave empty for GET/DELETE)
    vcenter_ip: defaults to VCENTER_IP in .env

    Examples:
      vcenter_api("GET", "/api/vcenter/cluster")
      vcenter_api("GET", "/api/vcenter/host")
      vcenter_api("GET", "/api/vcenter/datastore")
    """
    try:
        ip    = vcenter_ip or VCENTER_IP
        token = _vcenter_token(ip, username, password)
        headers = {"vmware-api-session-id": token, "Content-Type": "application/json"}
        resp = requests.request(
            method.upper(), f"https://{ip}{path}",
            headers=headers, data=body or None, verify=False, timeout=30,
        )
        return f"HTTP {resp.status_code}\n{resp.text[:6000]}"
    except Exception as exc:
        return f"vCenter API error: {exc}"


@mcp.tool()
def vcf_installer_api(
    method: str,
    path: str,
    body: str = "",
    installer_ip: str = "",
    username: str = "",
    password: str = "",
) -> str:
    """
    Make a VCF Installer (Cloud Builder) REST API call.
    method      : GET | POST | PUT | PATCH | DELETE
    path        : e.g. /v1/system/appliance-info, /v1/sddcs, /v1/bundles/download-status
    installer_ip: defaults to VCF_INSTALLER_IP in .env

    Common paths:
      vcf_installer_api("GET", "/v1/system/appliance-info")   # readiness check
      vcf_installer_api("GET", "/v1/sddcs")                   # deployment status
      vcf_installer_api("GET", "/v1/system/settings/depot")   # depot config
    """
    try:
        ip    = installer_ip or VCF_INSTALLER_IP
        if not ip:
            return "VCF_INSTALLER_IP not configured in .env"
        token = _vcf_token(ip, username, password)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        resp = requests.request(
            method.upper(), f"https://{ip}{path}",
            headers=headers, data=body or None, verify=False, timeout=30,
        )
        return f"HTTP {resp.status_code}\n{resp.text[:6000]}"
    except Exception as exc:
        return f"VCF Installer API error: {exc}"


@mcp.tool()
def sddc_manager_api(
    method: str,
    path: str,
    body: str = "",
    sddc_ip: str = "",
    username: str = "",
    password: str = "",
) -> str:
    """
    Make an SDDC Manager REST API call.
    method  : GET | POST | PUT | PATCH | DELETE
    path    : e.g. /v1/domains, /v1/hosts, /v1/clusters, /v1/tasks
    sddc_ip : defaults to SDDC_MANAGER_IP in .env

    Examples:
      sddc_manager_api("GET", "/v1/domains")
      sddc_manager_api("GET", "/v1/hosts?status=UNASSIGNED_USEABLE")
      sddc_manager_api("GET", "/v1/tasks?status=Failed")
    """
    try:
        ip    = sddc_ip or SDDC_MANAGER_IP
        token = _sddc_token(ip, username, password)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        resp = requests.request(
            method.upper(), f"https://{ip}{path}",
            headers=headers, data=body or None, verify=False, timeout=30,
        )
        return f"HTTP {resp.status_code}\n{resp.text[:6000]}"
    except Exception as exc:
        return f"SDDC Manager API error: {exc}"


@mcp.tool()
def vrops_api(
    method: str,
    path: str,
    body: str = "",
    vrops_ip: str = "",
    username: str = "",
    password: str = "",
) -> str:
    """
    Make a vRealize Operations / Aria Operations REST API call.
    method  : GET | POST | PUT | PATCH | DELETE
    path    : e.g. /suite-api/api/resources, /suite-api/api/alerts
    vrops_ip: defaults to VROPS_IP in .env (returns error if not configured)

    Examples:
      vrops_api("GET", "/suite-api/api/versions/current")
      vrops_api("GET", "/suite-api/api/resources?resourceKind=VirtualMachine")
      vrops_api("GET", "/suite-api/api/alerts?activeOnly=true")
    """
    ip = vrops_ip or VROPS_IP
    if not ip:
        return "Aria Operations (vROps) not configured. Set VROPS_IP in .env"
    try:
        token = _vrops_token(ip, username, password)
        headers = {
            "Authorization": f"vRealizeOpsToken {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        resp = requests.request(
            method.upper(), f"https://{ip}{path}",
            headers=headers, data=body or None, verify=False, timeout=30,
        )
        return f"HTTP {resp.status_code}\n{resp.text[:6000]}"
    except Exception as exc:
        return f"vROps API error: {exc}"


@mcp.tool()
def check_dns(fqdn: str, dns_server: str = "") -> str:
    """
    Resolve an FQDN using the configured DNS server.
    Useful for verifying DNS records before VCF bringup.
    dns_server defaults to DNS_SERVER in .env.
    Example: check_dns("vcenter.domain.com")
    """
    server = dns_server or DNS_SERVER
    if not server:
        return "DNS_SERVER not configured in .env"
    try:
        result = subprocess.run(
            ["nslookup", fqdn, server],
            capture_output=True, text=True, timeout=10,
        )
        return (result.stdout + result.stderr).strip()
    except Exception as exc:
        return f"DNS check error: {exc}"


@mcp.tool()
def ping_host(host: str, count: int = 3) -> str:
    """
    Ping a host to check network reachability.
    Example: ping_host("192.168.1.11")
    """
    try:
        result = subprocess.run(
            ["ping", "-c", str(count), host],
            capture_output=True, text=True, timeout=20,
        )
        return (result.stdout + result.stderr).strip()
    except Exception as exc:
        return f"Ping error: {exc}"


@mcp.tool()
def vcf_version(
    host: str,
    host_type: str = "auto",
    username: str = "",
    password: str = "",
) -> str:
    """
    Detect VCF component version at the given host IP.

    host_type : "auto" / "sddc" / "installer" / "vcenter"
      auto: tries SDDC Manager → VCF Installer → vCenter in sequence

    username/password: if empty, uses .env defaults for each component type.

    Examples:
      vcf_version("192.168.1.5")                  # auto-detect SDDC version
      vcf_version("192.168.1.4", "installer")     # VCF Installer version
      vcf_version("192.168.1.10", "vcenter")      # vCenter version
    """
    errors: list[str] = []

    def _try_sddc() -> str | None:
        u = username or SDDC_MANAGER_USER
        p = password or SDDC_MANAGER_PASS
        try:
            t = _sddc_token(host, u, p)
            r = requests.get(f"https://{host}/v1/manifest",
                             headers={"Authorization": f"Bearer {t}"},
                             verify=False, timeout=10)
            if r.ok:
                d = r.json()
                v = d.get("vcfVersion") or d.get("releaseVersion") or "unknown"
                return f"SDDC Manager: VCF {v}"
        except Exception as e:
            errors.append(f"  sddc: {type(e).__name__}: {str(e)[:80]}")
        return None

    def _try_installer() -> str | None:
        try:
            r = requests.get(f"https://{host}/v1/system/appliance-info",
                             verify=False, timeout=10)
            if r.ok:
                d = r.json()
                v = d.get("version") or d.get("buildNumber") or str(d)
                return f"VCF Installer: {v}"
        except Exception as e:
            errors.append(f"  installer: {type(e).__name__}: {str(e)[:80]}")
        return None

    def _try_vcenter() -> str | None:
        u = username or VCENTER_USER
        p = password or VCENTER_PASS
        try:
            r = requests.get(f"https://{host}/api/appliance/system/version",
                             auth=(u, p), verify=False, timeout=10)
            if r.ok:
                d = r.json()
                v     = d.get("version", "unknown")
                build = d.get("build", "")
                return f"vCenter {v} (build {build})"
        except Exception as e:
            errors.append(f"  vcenter: {type(e).__name__}: {str(e)[:80]}")
        return None

    probes = {"sddc": _try_sddc, "installer": _try_installer, "vcenter": _try_vcenter}

    if host_type == "auto":
        for fn in probes.values():
            out = fn()
            if out:
                return out
        return f"Could not detect version at {host}\nProbes:\n" + "\n".join(errors)

    if host_type not in probes:
        return f"Invalid host_type '{host_type}'. Use: auto / sddc / installer / vcenter"
    out = probes[host_type]()
    return out or f"Could not detect {host_type} version at {host}\n" + "\n".join(errors)


@mcp.tool()
def list_environments(probe: bool = False, discover: bool = False) -> str:
    """
    List all known VCF environments configured on this server.

    probe   : TCP-probe each host (port 443) and attempt version detection (slower).
    discover: Query SDDC Manager /v1/domains to auto-discover workload domains.

    Config sources (in priority order):
      1. /opt/vcf-mcp/environments.json  (multi-environment JSON)
      2. .env single-environment variables (VCENTER_IP, SDDC_MANAGER_IP, etc.)

    Returns JSON string with environment details.
    """
    env = json.loads(json.dumps(LAB_ENVIRONMENTS))

    if discover and SDDC_MANAGER_IP and SDDC_MANAGER_PASS:
        try:
            token = _sddc_token()
            resp  = requests.get(
                f"https://{SDDC_MANAGER_IP}/v1/domains",
                headers={"Authorization": f"Bearer {token}"},
                verify=False, timeout=15,
            )
            if resp.ok:
                for d in resp.json().get("elements", []):
                    name = d.get("name") or d.get("id", "unknown")
                    if name not in env:
                        env[name] = {
                            "purpose":   f"VCF {d.get('type', 'WORKLOAD')} domain",
                            "domain_id": d.get("id"),
                            "status":    d.get("status"),
                            "_source":   "sddc_discovery",
                        }
        except Exception as e:
            env["_discovery_error"] = str(e)

    if not probe:
        return json.dumps(env, indent=2, ensure_ascii=False)

    for name, cfg in env.items():
        if name.startswith("_"):
            continue
        cfg["_live"] = {}
        for key in ("sddc_manager_ip", "vcf_installer_ip", "vcenter_ip"):
            ip = cfg.get(key)
            if not ip:
                continue
            try:
                with socket.create_connection((ip, 443), timeout=2):
                    pass
                kind = ("sddc"      if "sddc_manager" in key
                        else "installer" if "installer"    in key
                        else "vcenter")
                cfg["_live"][key] = {"reachable": True}
                try:
                    cfg["_live"][key]["version"] = vcf_version(ip, kind)
                except Exception:
                    pass
            except OSError:
                cfg["_live"][key] = {"reachable": False}

    return json.dumps(env, indent=2, ensure_ascii=False)


# ── Entry points ──────────────────────────────────────────────────────────────
def main():
    print(f"Starting VCF MCP Server on https://0.0.0.0:{MCP_PORT}/sse")
    print(f"API keys loaded: {list(API_KEYS.keys())}")
    uvicorn.run(
        APIKeyMiddleware(mcp.sse_app()),
        host="0.0.0.0",
        port=MCP_PORT,
        ssl_keyfile=SSL_KEYFILE,
        ssl_certfile=SSL_CERTFILE,
    )


def stdio_main():
    """Entry point for mcpo stdio bridge (Open WebUI)."""
    mcp.run()


if __name__ == "__main__":
    main()
