# SD Image Generation API

Configurable Stable Diffusion SDXL API with ComfyUI backend. Optimized for RunPod GPU deployment.

Features:
- SDXL support (Juggernaut-XL, RealVisXL, etc.)
- Prompt safety filtering (age, celebrity, illegal content)
- Adult content reinforcement
- Async generation with callbacks
- Audit logging for compliance

## Quick Deploy (RunPod)

### Start Command (One-liner)

Copy this entire command into RunPod Pod "Start Command":

```bash
bash -c "apt-get update && apt-get install -y wget git && pip install fastapi uvicorn httpx aiofiles Pillow python-multipart && if [ ! -d '/workspace/ComfyUI' ]; then cd /workspace && git clone https://github.com/comfyanonymous/ComfyUI.git; fi && cd /workspace/ComfyUI && pip install -r requirements.txt && if [ ! -f '/workspace/ComfyUI/models/checkpoints/juggernautXL_v9.safetensors' ]; then mkdir -p /workspace/ComfyUI/models/checkpoints && cd /workspace/ComfyUI/models/checkpoints && wget -q 'https://civitai.com/api/download/models/357609?type=Model&format=SafeTensor&size=pruned&fp=fp16' -O juggernautXL_v9.safetensors; fi && cd /workspace/ComfyUI && python main.py --listen 0.0.0.0 --port 8188 & sleep 30 && rm -rf /workspace/sd-api && git clone https://github.com/akshay9194/sd-api-deployment.git /workspace/sd-api && cd /workspace/sd-api/app && uvicorn server:app --host 0.0.0.0 --port 8000"
```

### What the Start Command Does

1. Installs system dependencies (wget, git)
2. Installs Python packages (fastapi, uvicorn, etc.)
3. Clones ComfyUI (if not in network volume)
4. Downloads Juggernaut-XL model (if not exists) - ~6.5GB
5. Starts ComfyUI in background (port 8188)
6. Clones this SD API repo
7. Starts FastAPI server (port 8000)

### Prerequisites

1. **Network Volume** (50GB+) attached to `/workspace`
2. **GPU Pod**: RTX 4090 recommended (or RTX 3090)
3. **Template**: PyTorch or RunPod Pytorch
4. **Expose Port**: 8000

### First Run vs Subsequent

| Scenario | Time | Notes |
|----------|------|-------|
| First time | 5-10 min | Downloads ComfyUI + model |
| Spot restart | 30-60 sec | Everything cached in volume |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COMFYUI_URL` | `http://127.0.0.1:8188` | ComfyUI server URL |
| `API_KEY` | `` | Bearer token (empty = no auth) |
| `OUTPUT_DIR` | `/workspace/outputs` | Generated images directory |
| `MODEL_NAME` | `juggernautXL_v9.safetensors` | Checkpoint to use |
| `DEFAULT_STEPS` | `25` | Default generation steps |
| `DEFAULT_CFG` | `7.0` | Default CFG scale |
| `DEFAULT_WIDTH` | `1024` | Default image width |
| `DEFAULT_HEIGHT` | `1024` | Default image height |
| `ENABLE_SAFETY` | `true` | Enable prompt safety filter |

## API Endpoints

### Health Check
```bash
GET /health
```

### List Available Models
```bash
GET /models
```

### Generate Image (Sync)
```bash
POST /generate
{
  "prompt": "beautiful woman, elegant dress, city background",
  "negative_prompt": "ugly, blurry",
  "seed": 12345,
  "steps": 25,
  "cfg_scale": 7.0,
  "width": 1024,
  "height": 1024,
  "persona_id": "scarlett",
  "user_id": "user123"
}
```

Response:
```json
{
  "success": true,
  "image_url": "/images/abc123_def456.png",
  "image_hash": "abc123def456",
  "seed_used": 12345
}
```

### Generate Image (Async with Callback)
```bash
POST /generate-async
{
  "prompt": "beautiful woman, elegant dress",
  "request_id": "req_123",
  "callback_url": "https://your-api.com/image-callback",
  "user_id": "user123"
}
```

Response:
```json
{
  "status": "queued",
  "request_id": "req_123",
  "message": "Image generation started in background"
}
```

Callback payload (POST to callback_url):
```json
{
  "request_id": "req_123",
  "status": "completed",
  "image_url": "/images/abc123.png",
  "image_hash": "abc123",
  "seed_used": 12345,
  "user_id": "user123"
}
```

### Get Image
```bash
GET /images/{filename}
```

## Safety Features

### Blocked Content (Auto-Rejected)
- Celebrity names and references
- Age regression keywords
- School/underage uniforms
- Face swap / deepfake requests
- Illegal content

### Auto-Added Prompts
Every generation automatically includes:
- **Positive**: Adult age reinforcement (25+ years)
- **Negative**: Celebrity/real person blockers

## Recommended Models

Download to `/workspace/ComfyUI/models/checkpoints/`:

| Model | Quality | Size | Download |
|-------|---------|------|----------|
| Juggernaut XL v9 | Best | 6.5GB | [CivitAI](https://civitai.com/models/133005) |
| RealVisXL V4.0 | Excellent | 6.5GB | [CivitAI](https://civitai.com/models/139562) |
| DreamShaper XL | Good | 6.5GB | [CivitAI](https://civitai.com/models/112902) |

## Cost Estimates (RunPod)

| GPU | $/hour | SDXL Speed | Notes |
|-----|--------|------------|-------|
| RTX 4090 | $0.44 | ~6s/image | Best performance |
| RTX 4090 Spot | $0.29 | ~6s/image | Can be interrupted |
| RTX 3090 | $0.22 | ~12s/image | Budget option |
| A100 40GB | $1.29 | ~4s/image | Overkill for single images |

## Local Development

```bash
# Requires ComfyUI running on localhost:8188
pip install -r app/requirements.txt
cd app && uvicorn server:app --reload --port 8000
```

## Architecture

```
Client Request → SD API (port 8000) → ComfyUI (port 8188) → GPU
                     ↓
              Prompt Validation
              Safety Filtering
              Adult Reinforcement
                     ↓
              ComfyUI Workflow
                     ↓
              Image + Audit Log
```
