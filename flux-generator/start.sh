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
pip install --cache-dir "$PIP_CACHE" -q \
    torch==2.4.1 \
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
    uvicorn \
    2>/dev/null

echo "✅ Packages installed"

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

# ── 6. Start server ─────────────────────────────────────────
echo "🚀 Starting server on port 8080..."
echo "   Dashboard: https://YOUR-POD-ID-8080.proxy.runpod.net"
echo "   Log file:  /workspace/generator.log"
echo ""
echo "   Use the web UI to start/stop generation."
echo "   Server stays alive even if generation stops."
echo ""

exec python server.py
