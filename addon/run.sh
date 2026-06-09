#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
set -e

# The API access key comes from the add-on option 'access_key' and is handed to
# the server via the environment variable it expects.
export ESEL_API_ACCESS_KEY="$(bashio::config 'access_key')"

# Run as a network service so Home Assistant (MCP Client integration) can reach it.
export MCP_TRANSPORT="sse"
export MCP_HOST="0.0.0.0"
export MCP_PORT="8099"
export MCP_LOG_LEVEL="$(bashio::config 'log_level')"  # uppercased by the server

if bashio::config.is_empty 'access_key'; then
    bashio::log.warning \
        "No 'access_key' configured — API calls will fail until you set it in the add-on Configuration tab."
fi

bashio::log.info "Starting sbirka-mcp (SSE) on port 8099, endpoint http://<host>:8099/sse"
exec sbirka-mcp
