#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# XinMate — Production Startup Script for RunPod
# ═══════════════════════════════════════════════════════════════
#
# This script:
#   1. Installs pip packages (cached on network volume)
#   2. Sets up environment
#   3. Starts the generation server
#
# The server stays alive. Use the web UI to start/stop generation.
# If the pod restarts, just run this script again.
#
# Usage:
#   bash start.sh
#
# ═══════════════════════════════════════════════════════════════

set -e

echo "═══════════════════════════════════════════"
echo "  XinMate Image Generation Server"
echo "  $(date)"
echo "═══════════════════════════════════════════"

# ── 1. Environment ──────────────────────────────────────────
export HF_HOME=/workspace/hf_cache
export TRANSFORMERS_CACHE=/workspace/hf_cache
export HUGGINGFACE_HUB_CACHE=/workspace/hf_cache
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# ── 2. Install packages (use cache on network volume) ───────
PIP_CACHE="/workspace/pip_cache"
mkdir -p "$PIP_CACHE"

echo "📦 Installing packages..."
pip install --cache-dir "$PIP_CACHE" \
    torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124 \
    2>/dev/null || true

pip install --cache-dir "$PIP_CACHE" \
    transformers==4.44.2 \
    diffusers==0.30.3 \
    peft==0.12.0 \
    accelerate==0.34.2 \
    safetensors \
    sentencepiece \
    Pillow \
    tqdm \
    protobuf \
    fastapi \
    uvicorn

# Verify critical packages
python -c "import fastapi, diffusers, torch; print(f'✅ torch={torch.__version__} diffusers={diffusers.__version__}')" || {
    echo "❌ Package install failed. Check pip output above."
    exit 1
}

echo "✅ Packages ready"

# ── 3. Ensure code is up to date ────────────────────────────
cd /workspace/sd-api-deployment/flux-generator

if [ -d "/workspace/sd-api-deployment/.git" ]; then
    echo "📥 Pulling latest code..."
    cd /workspace/sd-api-deployment
    git pull origin main 2>/dev/null || true
    cd flux-generator
fi

# ── 4. Create directories ───────────────────────────────────
mkdir -p /workspace/generated_images
mkdir -p /workspace/manifests

# ── 5. GPU check ─────────────────────────────────────────────
echo ""
echo "🖥️  GPU:"
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null || echo "No GPU detected"
echo ""

# ── 6. Start server (detached — survives terminal disconnect) ─
echo "🚀 Starting server on port 8080 (background)..."
echo "   Dashboard: https://YOUR-POD-ID-8080.proxy.runpod.net"
echo "   Log file:  /workspace/generator.log"
echo ""

# Kill old server if running
if [ -f /workspace/server.pid ]; then
    OLD_PID=$(cat /workspace/server.pid)
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "   Stopping old server (PID $OLD_PID)..."
        kill "$OLD_PID" 2>/dev/null
        sleep 2
    fi
fi

# Start detached
nohup python server.py > /workspace/generator.log 2>&1 &
echo $! > /workspace/server.pid

echo "   ✅ Server running in background (PID: $(cat /workspace/server.pid))"
echo ""
echo "   Use the web UI to start/stop generation."
echo "   You can close this terminal — server keeps running."
echo ""
echo "   Commands:"
echo "     tail -f /workspace/generator.log    # View logs"
echo "     kill \$(cat /workspace/server.pid)    # Stop server"
echo "     bash start.sh                        # Restart server"
