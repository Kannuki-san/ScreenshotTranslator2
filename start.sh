#!/usr/bin/env bash
set -euo pipefail

# Configurables (can be overridden via environment variables)
WEB_PORT=${WEB_PORT:-8012}
LLAMA_PORT=${LLAMA_PORT:-8009}
LLAMA_CTX=${LLAMA_CTX:-8192}
LLAMA_BIN=${LLAMA_BIN:-./llama.cpp/build/bin/llama-server}
SKIP_LLAMACPP=${SKIP_LLAMACPP:-0}

DEFAULT_MODEL_QWEN35="models/Qwen3.5-35B-A3B-UD-Q4_K_XL.gguf"
DEFAULT_MMPROJ_QWEN35="models/mmproj-F32.gguf"
DEFAULT_CHAT_TEMPLATE_QWEN35="app/chat_templates/qwen3.5-35b-a3b.chat_template.jinja"

LLAMA_MODEL="${LLAMA_MODEL:-$DEFAULT_MODEL_QWEN35}"
LLAMA_MMPROJ="${LLAMA_MMPROJ:-$DEFAULT_MMPROJ_QWEN35}"

LLAMA_CHAT_TEMPLATE_FILE="${LLAMA_CHAT_TEMPLATE_FILE:-}"
LLAMA_THINK_BUDGET="${LLAMA_THINK_BUDGET:-}"

if [ -z "$LLAMA_CHAT_TEMPLATE_FILE" ] && [ -n "${LLAMA_ARG_CHAT_TEMPLATE_FILE:-}" ]; then
  LLAMA_CHAT_TEMPLATE_FILE="$LLAMA_ARG_CHAT_TEMPLATE_FILE"
fi

if [ -z "$LLAMA_THINK_BUDGET" ] && [ -n "${LLAMA_ARG_THINK_BUDGET:-}" ]; then
  LLAMA_THINK_BUDGET="$LLAMA_ARG_THINK_BUDGET"
fi

if [ -z "$LLAMA_THINK_BUDGET" ] && [ -n "${LAMA_ARG_THINK_BUDGET:-}" ]; then
  LLAMA_THINK_BUDGET="$LAMA_ARG_THINK_BUDGET"
  echo "[WARN] LAMA_ARG_THINK_BUDGET is a typo; use LLAMA_THINK_BUDGET instead."
fi

if [ "$LLAMA_MODEL" = "$DEFAULT_MODEL_QWEN35" ]; then
  if [ -z "$LLAMA_CHAT_TEMPLATE_FILE" ] && [ -f "$DEFAULT_CHAT_TEMPLATE_QWEN35" ]; then
    LLAMA_CHAT_TEMPLATE_FILE="$DEFAULT_CHAT_TEMPLATE_QWEN35"
  fi
  if [ -z "$LLAMA_THINK_BUDGET" ]; then
    LLAMA_THINK_BUDGET=0
  fi
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "[ERROR] uv is required. Install via: pip install uv" >&2
  exit 1
fi

# Install Python deps inside .venv via uv (no global installs)
uv sync
# Initialize TTS models and dictionary
uv run app/scripts/setup_tts.py

if [ "$SKIP_LLAMACPP" != "1" ]; then
  if [ ! -x "$LLAMA_BIN" ]; then
    echo "[ERROR] llama-server binary not found at $LLAMA_BIN"
    echo "Run scripts/build_llama.sh to clone & build llama.cpp with CUDA."
    exit 1
  fi
  if [ ! -f "$LLAMA_MODEL" ]; then
    echo "[ERROR] model file not found at $LLAMA_MODEL"
    exit 1
  fi
  if [ ! -f "$LLAMA_MMPROJ" ]; then
    echo "[ERROR] mmproj file not found at $LLAMA_MMPROJ"
    exit 1
  fi

  LLAMA_ARGS=(
    --host 127.0.0.1
    --port "$LLAMA_PORT"
    -m "$LLAMA_MODEL"
    -c "$LLAMA_CTX"
    -ngl 999
    --jinja
    -ub 4096
    -b 4096
    --flash-attn on
    --mmproj "$LLAMA_MMPROJ"
  )
  if [ -n "$LLAMA_CHAT_TEMPLATE_FILE" ]; then
    LLAMA_ARGS+=(--chat-template-file "$LLAMA_CHAT_TEMPLATE_FILE")
  fi
  if [ -n "$LLAMA_THINK_BUDGET" ]; then
    LLAMA_ARGS+=(--reasoning-budget "$LLAMA_THINK_BUDGET")
  fi

  echo "[INFO] starting llama.cpp server on port $LLAMA_PORT"
  echo "[INFO] model: $LLAMA_MODEL"
  echo "[INFO] mmproj: $LLAMA_MMPROJ"
  if [ -n "$LLAMA_CHAT_TEMPLATE_FILE" ]; then
    echo "[INFO] chat template: $LLAMA_CHAT_TEMPLATE_FILE"
  fi
  if [ -n "$LLAMA_THINK_BUDGET" ]; then
    echo "[INFO] reasoning budget: $LLAMA_THINK_BUDGET"
  fi
  set +e
  "$LLAMA_BIN" "${LLAMA_ARGS[@]}" > llama-server.log 2>&1 &
  LLAMA_PID=$!
  set -e
  trap 'echo "[INFO] stopping llama.cpp"; kill $LLAMA_PID 2>/dev/null || true' EXIT
else
  echo "[INFO] SKIP_LLAMACPP=1 -> assuming llama-server already running on $LLAMA_PORT"
fi

export LLAMA_SERVER_URL=${LLAMA_SERVER_URL:-http://127.0.0.1:${LLAMA_PORT}}
export LLAMA_CTX

echo "[INFO] starting FastAPI on port $WEB_PORT"
uv run uvicorn app.main:app --host 127.0.0.1 --port "$WEB_PORT"
