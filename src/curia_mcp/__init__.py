"""curia-mcp — an MCP bridge to EU case-law (InfoCuria / EUR-Lex / Cellar).

The Court of Justice's InfoCuria site (https://infocuria.curia.europa.eu) has no
public API, so this server uses the EU Publications Office **Cellar** repository as
its data backbone (a public, no-registration SPARQL endpoint plus REST content
negotiation by CELEX number) and keeps **InfoCuria** for human-facing deep links
by case number. See :mod:`curia_mcp.eurlex` and :mod:`curia_mcp.infocuria`.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
