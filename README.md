# sbirka-mcp

MCP server for the Czech **e-Sbírka** and **e-Legislativa** public REST API
(Ministerstvo vnitra ČR). It lets an MCP client (Claude Code / Claude Desktop)
do legal research: search legal acts and intents in the legislative process, read
draft detail, browse code lists, and fetch published regulations from the Sbírka
zákonů by citation.

## Prerequisites

You need an **access key** issued by the Ministry of the Interior after registering
for the public REST API (a single key works for both e-Sbírka and e-Legislativa).
See the official docs: <https://e-sbirka.gov.cz/restful-api>.

> The data is informational only. Respect the agreed call quota (the API enforces
> it with HTTP 429) and do **not** share your access key — these are conditions of
> the registration.

## Where it runs

`sbirka-mcp` runs **locally on your machine** as a stdio subprocess that your MCP
client launches on demand. It is not a hosted service; your machine makes the HTTPS
calls to `api.e-sbirka.gov.cz` / `api.e-legislativa.gov.cz`.

## Install

With [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv tool install .        # or: uvx --from . sbirka-mcp
```

Or with pip:

```bash
pip install .
```

## Configure the access key

The server reads the key from the `ESEL_API_ACCESS_KEY` environment variable. Either
set it in your MCP client config (recommended) or copy `.env.example` to `.env` and
fill it in. `.env` is gitignored — never commit your key.

### MCP client config

```json
{
  "mcpServers": {
    "sbirka": {
      "command": "uvx",
      "args": ["--from", "/path/to/sbirka-mcp", "sbirka-mcp"],
      "env": { "ESEL_API_ACCESS_KEY": "<your-access-key>" }
    }
  }
}
```

(If installed on your PATH, `"command": "sbirka-mcp"` with `"args": []` also works.)

Optional environment overrides: `ESBIRKA_API_BASE_URL`,
`ELEGISLATIVA_API_BASE_URL`, `ESEL_API_TIMEOUT` (seconds).

## Transports

By default the server speaks **stdio** (for desktop clients that launch it as a
subprocess). For a network service set `MCP_TRANSPORT`:

* `streamable-http` — modern transport used by Claude connectors. Endpoint path is
  `MCP_HTTP_PATH` (default `/mcp`); set it to `/` to serve at the root. Use
  `MCP_STATELESS_HTTP=true` for connectors that don't keep a session. This is the
  mode used by the Home Assistant add-on (mounted at `/`).
* `sse` — older transport, endpoint at `/sse` (+ `/messages/`).

Host/port come from `MCP_HOST`/`MCP_PORT` (default `127.0.0.1:8099`).

### Optional OAuth

Set `MCP_OAUTH_ENABLED=true` together with `MCP_OAUTH_PASSWORD=<secret>` and
`MCP_PUBLIC_URL=<https://your-host>` to put a password-gated OAuth 2.0 login in front
of the HTTP endpoint. This is what lets the **claude.ai web connector** attach (it
requires OAuth) and stops an exposed URL from being wide open. Tokens are kept
in memory, so they reset on restart.

```bash
# Streamable HTTP at the root path (what the HA add-on runs):
MCP_TRANSPORT=streamable-http MCP_HTTP_PATH=/ MCP_STATELESS_HTTP=true \
  MCP_HOST=0.0.0.0 MCP_PORT=8099 ESEL_API_ACCESS_KEY=<key> sbirka-mcp
```

## Home Assistant add-on

This repository is also a Home Assistant add-on repository. In Home Assistant:
**Settings → Add-ons → Add-on Store → ⋮ → Repositories**, add
`https://github.com/davzavada/sbirka-mcp`, then install **e-Sbírka MCP Server**.
The API key is an add-on option (`access_key`), and the server is reachable over
Streamable HTTP at `http://<ha-host>:8099/` — add it as a custom connector in Claude
Desktop, or `claude mcp add --transport http sbirka http://<ha-host>:8099/`. See
[`addon/DOCS.md`](addon/DOCS.md) for details.

## Tools

| Tool | What it does | API |
| --- | --- | --- |
| `vyhledat_predpisy` | Full-text search of legal acts (zákony, vyhlášky, …) | e-Legislativa `POST /vyhledavani/pravni-akt-rozsirene` |
| `vyhledat_vecny_zamer` | Search věcné záměry | e-Legislativa `POST /vyhledavani/vecny-zamer-rozsirene` |
| `vyhledat_legislativni_zamer` | Search legislativní záměry | e-Legislativa `POST /vyhledavani/legislativni-zamer-rozsirene` |
| `ziskat_navrh` | Detail of a draft by id | e-Legislativa `GET /navrhy/{id}` |
| `vypis_ciselnik` | List a code list (allowed filter values) | e-Legislativa `GET /ciselniky/{kod}` |
| `ziskat_dokument_sbirky` | Published regulation metadata by citation / ELI | e-Sbírka `GET /dokumenty-sbirky/{stálé-url}` |

Search results carry an `identifikator`; pass it to `ziskat_navrh` for detail.
Use `vypis_ciselnik("DruhAktu")` to discover values for the `typ_aktu` filter.

---

# curia-mcp (EU case-law bridge)

A second MCP server in this repo, **`curia-mcp`**, bridges EU case-law. The Court of
Justice's [InfoCuria](https://infocuria.curia.europa.eu/tabs/tout) site has **no API**
(and its January 2026 single-page UI blocks scraping), so this server uses the EU
Publications Office **Cellar** repository as its data backbone — a public,
no-registration SPARQL endpoint plus REST content negotiation by **CELEX** number —
and keeps InfoCuria for stable, human-facing deep links by case number.

No API key is required.

## Tools

| Tool | What it does | Source |
| --- | --- | --- |
| `search_case_law` | Search case-law metadata/titles by text, court, year range | Cellar SPARQL |
| `fetch_case_metadata` | Title / ECLI / date for a case by CELEX number | Cellar SPARQL |
| `fetch_case_text` | Full document text by CELEX number, in a chosen language | Cellar REST |
| `lookup_case_number` | Resolve a case number (e.g. `C-159/18`) to an InfoCuria link | InfoCuria |
| `identify_reference` | Detect whether a string is a CELEX, ECLI, or case number | offline |

Identifier formats: **CELEX** `62018CJ0159` (sector 6 = case-law), **ECLI**
`ECLI:EU:C:2019:933`, **case number** `C-159/18` (Court of Justice), `T-79/16`
(General Court), `F-1/05` (Civil Service Tribunal). A case number alone can't be
turned into a CELEX (its year is when the case was *brought*, not the judgment year),
so it routes to an InfoCuria deep link.

## Run

```bash
curia-mcp                       # stdio (default)
MCP_TRANSPORT=streamable-http MCP_PORT=8098 curia-mcp   # network service
```

MCP client config:

```json
{
  "mcpServers": {
    "curia": { "command": "uvx", "args": ["--from", "/path/to/sbirka-mcp", "curia-mcp"] }
  }
}
```

Optional environment overrides: `CELLAR_SPARQL_URL`, `CELLAR_RESOURCE_BASE`,
`CURIA_HTTP_TIMEOUT`, `CURIA_USER_AGENT`.

## Status / what still needs live validation

The CELEX/ECLI/case-number parsing and InfoCuria link building are fully tested
offline. The **Cellar SPARQL queries** in `eurlex.py` follow the documented `cdm`
ontology but should be tuned against the live endpoint — if a field comes back empty,
capture a working query and adjust the predicates. Full-text search over judgment
*bodies* is not available via Cellar SPARQL (it indexes metadata/titles); for that,
open the `infocuria_search` link the tool returns, or we can add EUR-Lex Expert
Search (which needs registered web-service credentials).

---

## Development

```bash
pip install -e ".[dev]"
pytest
```

`tests/` runs fully offline (citation parsing, CELEX/ECLI/case-number parsing, link
building). Live calls require a valid key and network access to the API / Cellar hosts.
