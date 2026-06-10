# e-Sbírka MCP Server — Home Assistant add-on

Runs [`sbirka-mcp`](https://github.com/davzavada/sbirka-mcp) as a network service
inside Home Assistant. It exposes a **Streamable HTTP MCP endpoint** that remote MCP
clients (Claude connectors, Claude Code, …) connect to, giving your assistant tools
to search Czech legislation (e-Legislativa) and look up published regulations
(e-Sbírka).

## Installation

1. In Home Assistant go to **Settings → Add-ons → Add-on Store**.
2. Open the **⋮** menu (top right) → **Repositories**, and add:
   `https://github.com/davzavada/sbirka-mcp`
3. The **e-Sbírka MCP Server** add-on appears in the store — click it and **Install**.

## Configuration

| Option | Description |
| --- | --- |
| `access_key` | Your e-Sbírka / e-Legislativa REST API access key from the Ministry of the Interior. Stored as a secret. |
| `oauth_enabled` | Turn on OAuth login in front of the MCP endpoint. Required to attach the **claude.ai web** connector, and recommended before any public exposure. |
| `oauth_password` | The shared password users must enter to authorise a client (only used when `oauth_enabled`). Stored as a secret. |
| `public_url` | The external base URL the server is reached on, e.g. `https://sbirka.example.eu`. Required when `oauth_enabled` so OAuth metadata advertises the right URLs. |
| `log_level` | `debug`, `info` (default), `warning`, or `error`. |

Set `access_key`, then **Start** the add-on. Without it the server starts but every
API call returns an authentication error.

> The data is informational only. Respect the agreed call quota (the API enforces it
> with HTTP 429) and do not share your access key.

## Connecting a client to it

The add-on serves **Streamable HTTP** on port **8099** at the **root path** (`/`):

```
http://<your-ha-host>:8099/
```

* **Claude Code** — `claude mcp add --transport http sbirka http://<ha-host>:8099/`
* **Claude Desktop** — use the `mcp-remote` bridge in the config pointing at the URL.
* **claude.ai (web/mobile)** — needs a **public HTTPS URL** (e.g. your Cloudflare
  Tunnel, like `https://sbirka.example.eu/`) **and OAuth enabled** (see below).

### Enabling OAuth for the claude.ai web connector

The web connector only attaches to servers that implement OAuth. Turn it on:

1. Set `oauth_enabled: true`, choose an `oauth_password`, and set `public_url` to your
   public HTTPS address (e.g. `https://sbirka.example.eu`). Restart the add-on.
2. In claude.ai → **Settings → Connectors → Add custom connector** → paste the public
   URL. Claude redirects you to a `§` login page; enter the password to authorise.

Without OAuth the endpoint is unauthenticated — only expose it on a trusted network.
With OAuth, anyone who knows the password can connect, so pick a strong one.

## Tools provided

- `vyhledat_predpisy` — full-text search of legal acts (e-Legislativa)
- `vyhledat_vecny_zamer`, `vyhledat_legislativni_zamer` — search intents
- `ziskat_navrh` — draft detail by id
- `vypis_ciselnik` — code lists (allowed filter values)
- `ziskat_dokument_sbirky` — published regulation metadata by citation / ELI (e-Sbírka)

## Updating

The image installs `sbirka-mcp` from the repository's `main` branch at build time.
To pull a newer version, **Rebuild** the add-on (⋮ menu) after the repo updates.
