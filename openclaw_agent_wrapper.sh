#!/usr/bin/env bash
set -euo pipefail

OPENCLAW_BIN="${OPENCLAW_BIN:-openclaw}"
OPENCLAW_AGENT_ID="${OPENCLAW_AGENT_ID:-main}"

message="$(cat)"
if [[ -z "${message//[[:space:]]/}" ]]; then
  echo "Empty prompt. Provide text after /ask or send a non-slash message in free-text mode."
  exit 0
fi

exec "$OPENCLAW_BIN" agent --local --agent "$OPENCLAW_AGENT_ID" --message "$message"
