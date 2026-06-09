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

## Development

```bash
pip install -e ".[dev]"
pytest
```

`tests/` runs fully offline (citation parsing). Live calls require a valid key and
network access to the API hosts.
