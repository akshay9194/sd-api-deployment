#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# XinMate — RunPod Flux Generator Start Command
# ═══════════════════════════════════════════════════════════════
#
# Copy this entire script into RunPod Pod "Start Command"
# or save to network volume and run manually.
#
# Prerequisites:
#   - GPU Pod: A100 40GB (recommended) or RTX 4090
#   - Network Volume: 100GB+ attached at /workspace
#   - Template: RunPod PyTorch 2.x
#
# Environment Variables (set in RunPod Pod settings):
#   AZURE_STORAGE_ACCOUNT=sdxl
#   AZURE_STORAGE_KEY=<your-key>
#   AZURE_CONTAINER_NAME=personas
#   HF_TOKEN=<huggingface-token>  (if model is gated)
#
# ═══════════════════════════════════════════════════════════════

set -e

echo "═══════════════════════════════════════════"
echo "  XinMate Flux Batch Generator"
echo "  $(date)"
echo "═══════════════════════════════════════════"

# ── 1. Install dependencies ──────────────────────────────────
echo "📦 Installing dependencies..."
pip install -q diffusers transformers accelerate peft safetensors sentencepiece Pillow tqdm psycopg2-binary

# ── 2. Clone/update generator code ──────────────────────────
GENERATOR_DIR="/workspace/flux-generator"

if [ -d "$GENERATOR_DIR" ]; then
    echo "📂 Generator code exists, pulling updates..."
    cd "$GENERATOR_DIR"
    git pull 2>/dev/null || true
else
    echo "📥 Cloning generator code..."
    # Clone just the flux-generator subfolder
    git clone --depth 1 https://github.com/akshay9194/sd-api-deployment.git /tmp/sd-api
    mkdir -p "$GENERATOR_DIR"
    cp -r /tmp/sd-api/flux-generator/* "$GENERATOR_DIR/"
    rm -rf /tmp/sd-api
fi

cd "$GENERATOR_DIR"

# ── 3. Create output directories ────────────────────────────
mkdir -p /workspace/generated_images
mkdir -p /workspace/manifests

# ── 4. Verify GPU ────────────────────────────────────────────
echo ""
echo "🖥️  GPU Info:"
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader
echo ""

# ── 5. Start monitor dashboard ───────────────────────────────
echo "📊 Starting monitor dashboard on port 8080..."
python monitor.py &
MONITOR_PID=$!
sleep 2
echo "   Dashboard: http://localhost:8080"
echo "   On RunPod: https://YOUR-POD-ID-8080.proxy.runpod.net"
echo ""

# ── 6. Run generator ────────────────────────────────────────
echo "🚀 Starting batch generation..."
echo "   Output:    /workspace/generated_images/"
echo "   Manifests: /workspace/manifests/"
echo ""

# Generate all personas, all categories
# Add --persona scarlett to generate single persona
# Add --skip-upload to skip Azure upload
# Add --dry-run to preview prompts
python generate.py "$@"

echo ""
echo "✅ Generation complete!"
echo "   Images:    /workspace/generated_images/"
echo "   Manifests: /workspace/manifests/"
echo ""
echo "To import to PostgreSQL:"
echo "   DATABASE_URL='postgresql://...' python import_to_db.py"
