#!/bin/bash
export PATH="$HOME/.local/bin:$PATH"
export ANTHROPIC_BASE_URL="http://127.0.0.1:11434"
export ANTHROPIC_AUTH_TOKEN="ollama"
export ANTHROPIC_API_KEY=""
export ANTHROPIC_MODEL="gpt-oss:20b"
export ANTHROPIC_SMALL_FAST_MODEL="gpt-oss:20b"
export CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT="1"
cd /content/gpt_oss_proxy_test
exec bash
