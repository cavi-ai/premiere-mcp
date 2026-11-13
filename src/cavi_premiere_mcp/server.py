"""MCP server for Adobe Premiere Pro. A tool module registers its tools on app.mcp when imported."""

from . import tools  # noqa: F401
from .app import mcp


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
