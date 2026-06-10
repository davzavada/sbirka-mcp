#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
set -e

# The API access key comes from the add-on option 'access_key' and is handed to
# the server via the environment variable it expects.
export ESEL_API_ACCESS_KEY="$(bashio::config 'access_key')"

# Run as a network service so remote MCP clients can reach it. Claude's connectors
# use the Streamable HTTP transport and POST to the root path, so mount it at "/".
export MCP_TRANSPORT="streamable-http"
export MCP_HOST="0.0.0.0"
export MCP_PORT="8099"
export MCP_HTTP_PATH="/"
export MCP_STATELESS_HTTP="true"
export MCP_LOG_LEVEL="$(bashio::config 'log_level')"  # uppercased by the server

if bashio::config.is_empty 'access_key'; then
    bashio::log.warning \
        "No 'access_key' configured — API calls will fail until you set it in the add-on Configuration tab."
fi

# Optional OAuth: required by clients like the claude.ai web connector. Needs both a
# password and the public URL the server is reached on (e.g. https://sbirka.example.eu).
if bashio::config.true 'oauth_enabled'; then
    if bashio::config.is_empty 'oauth_password' || bashio::config.is_empty 'public_url'; then
        bashio::log.warning \
            "oauth_enabled is on but 'oauth_password' or 'public_url' is empty — OAuth stays OFF (endpoint is unauthenticated)."
    else
        export MCP_OAUTH_ENABLED="true"
        export MCP_OAUTH_PASSWORD="$(bashio::config 'oauth_password')"
        export MCP_PUBLIC_URL="$(bashio::config 'public_url')"
        bashio::log.info "OAuth enabled; issuer ${MCP_PUBLIC_URL}"
    fi
fi

bashio::log.info "Starting sbirka-mcp (Streamable HTTP) on port 8099 at path /"
exec sbirka-mcp
