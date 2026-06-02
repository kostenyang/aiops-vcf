"""Stdio transport entry point — used by mcpo to expose tools to Open WebUI."""

from .server import mcp


def main():
    mcp.run()


if __name__ == "__main__":
    main()
