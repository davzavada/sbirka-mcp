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

bashio::log.info "Starting sbirka-mcp (Streamable HTTP) on port 8099 at path /"
exec sbirka-mcp
