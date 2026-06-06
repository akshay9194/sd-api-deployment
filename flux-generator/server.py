#!/usr/bin/env python3
"""
XinMate — Production Image Generation Server
==============================================
A crash-safe, always-on FastAPI server for batch image generation.

Features:
  - Background worker thread (server never blocks)
  - Auto-resume after crash/restart (manifest-based)
  - Per-image exception handling (one failure doesn't stop the batch)
  - GPU memory management (cache clearing between images)
  - Live web dashboard at /
  - REST API for control (start, stop, status)
  - Health endpoint for monitoring

Usage:
  python server.py                    # Start server on port 8080
  # Then POST /api/start to begin generation

Endpoints:
  GET  /                - Live dashboard
  GET  /health          - Health check
  GET  /api/status      - Full generation status
  POST /api/start       - Start generation (body: {"personas": [...], "limit": 20})
  POST /api/stop        - Stop generation gracefully
  GET  /api/preview/{persona}/{category}/{number} - View generated image
"""

import io
import json
import logging
import os
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Prevent CUDA OOM from memory fragmentation
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

from config import (
    BASE_MODEL, LORA_REPO, LORA_WEIGHT_NAME, LORA_ADAPTER_NAME,
    INFERENCE_STEPS, GUIDANCE_SCALE, TORCH_DTYPE,
    CATEGORIES, PERSONAS,
    OUTPUT_DIR, MANIFEST_DIR,
)
from prompts import build_prompt, get_seed, get_dimensions

# ═══════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/workspace/generator.log", mode="a"),
    ]
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# APP STATE
# ═══════════════════════════════════════════════════════════════

app = FastAPI(title="XinMate Image Generator")

class GeneratorState:
    def __init__(self):
        self.pipe = None
        self.is_running = False
        self.should_stop = False
        self.worker_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

        # Progress
        self.total_target = 0
        self.total_done = 0
        self.total_failed = 0
        self.current_persona = ""
        self.current_category = ""
        self.current_image = 0
        self.start_time = 0
        self.last_error = ""
        self.errors: List[dict] = []

        # Config
        self.limit_per_category = 0
        self.persona_filter: Optional[List[str]] = None

state = GeneratorState()

# ═══════════════════════════════════════════════════════════════
# MODEL LOADING
# ═══════════════════════════════════════════════════════════════

def load_pipeline():
    """Load Flux model + LoRA. Called once, reused for all images."""
    if state.pipe is not None:
        logger.info("Pipeline already loaded, reusing")
        return state.pipe

    from diffusers import AutoPipelineForText2Image

    dtype = torch.bfloat16 if TORCH_DTYPE == "bfloat16" else torch.float16

    logger.info(f"Loading base model: {BASE_MODEL}")
    pipe = AutoPipelineForText2Image.from_pretrained(
        BASE_MODEL,
        torch_dtype=dtype,
    )

    pipe.enable_sequential_cpu_offload()
    logger.info("Sequential CPU offload enabled")

    logger.info(f"Loading LoRA: {LORA_REPO}")
    pipe.load_lora_weights(
        LORA_REPO,
        weight_name=LORA_WEIGHT_NAME,
        adapter_name=LORA_ADAPTER_NAME,
    )

    try:
        pipe.enable_xformers_memory_efficient_attention()
        logger.info("xformers enabled")
    except Exception:
        pass

    state.pipe = pipe
    logger.info("Pipeline ready")
    return pipe


# ═══════════════════════════════════════════════════════════════
# IMAGE GENERATION (single image, fully exception-safe)
# ═══════════════════════════════════════════════════════════════

def generate_single(pipe, prompt: str, seed: int, width: int, height: int) -> bytes:
    """Generate one image. Returns PNG bytes. Raises on failure."""
    generator = torch.Generator(device="cpu").manual_seed(seed)

    result = pipe(
        prompt=prompt,
        guidance_scale=GUIDANCE_SCALE,
        num_inference_steps=INFERENCE_STEPS,
        width=width,
        height=height,
        generator=generator,
    )

    image = result.images[0]
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)

    # Free VRAM
    del result, image
    torch.cuda.empty_cache()

    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
# MANIFEST (crash-safe resume)
# ═══════════════════════════════════════════════════════════════

def load_manifest(persona_id: str) -> dict:
    path = Path(MANIFEST_DIR) / f"{persona_id}_manifest.json"
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return {"persona": persona_id, "images": []}
    return {"persona": persona_id, "images": []}


def save_manifest(persona_id: str, manifest: dict):
    path = Path(MANIFEST_DIR) / f"{persona_id}_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    # Write to temp file first, then rename (atomic on Linux)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(manifest, f, indent=2)
    tmp.rename(path)


def get_completed_keys(manifest: dict) -> set:
    return {img["key"] for img in manifest.get("images", [])}


# ═══════════════════════════════════════════════════════════════
# AZURE UPLOAD (with retry)
# ═══════════════════════════════════════════════════════════════

def try_upload(png_bytes: bytes, persona_name: str, category: str, image_number: int) -> str:
    """Upload to Azure with 2 retries. Returns URL or empty string."""
    try:
        from upload import upload_image
    except Exception:
        return ""

    for attempt in range(3):
        try:
            return upload_image(png_bytes, persona_name, category, image_number)
        except Exception as e:
            logger.warning(f"Upload attempt {attempt+1} failed: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)
    return ""


# ═══════════════════════════════════════════════════════════════
# BACKGROUND WORKER
# ═══════════════════════════════════════════════════════════════

def worker_loop():
    """Main generation loop. Runs in background thread."""
    try:
        logger.info("=" * 60)
        logger.info("  WORKER STARTED")
        logger.info("=" * 60)

        # Load model
        try:
            pipe = load_pipeline()
        except Exception as e:
            state.last_error = f"Model load failed: {e}"
            logger.error(f"FATAL: {state.last_error}")
            logger.error(traceback.format_exc())
            state.is_running = False
            return

        # Determine personas
        if state.persona_filter:
            personas = {k: v for k, v in PERSONAS.items() if k in state.persona_filter}
        else:
            personas = PERSONAS

        categories = CATEGORIES
        limit = state.limit_per_category

        # Count total
        state.total_target = 0
        for cat in categories.values():
            effective = min(cat["count"], limit) if limit > 0 else cat["count"]
            state.total_target += effective * len(personas)

        state.total_done = 0
        state.total_failed = 0
        state.start_time = time.time()
        state.errors = []

        logger.info(f"Personas: {len(personas)} | Categories: {len(categories)} | Total: {state.total_target}")

        for persona_id, persona in personas.items():
            if state.should_stop:
                logger.info("Stop requested, exiting gracefully")
                break

            state.current_persona = persona.name
            logger.info(f"\n{'='*50}")
            logger.info(f"  PERSONA: {persona.name}")
            logger.info(f"{'='*50}")

            manifest = load_manifest(persona_id)
            completed = get_completed_keys(manifest)

            for cat_name, cat_cfg in categories.items():
                if state.should_stop:
                    break

                count = cat_cfg["count"]
                if limit > 0:
                    count = min(count, limit)
                width, height = get_dimensions(cat_name)

                state.current_category = cat_name
                logger.info(f"  Category: {cat_name} ({count} images, {width}×{height})")

                for i in range(count):
                    if state.should_stop:
                        break

                    key = f"{persona_id}/{cat_name}/{i:04d}"
                    state.current_image = i

                    # Skip completed (resume)
                    if key in completed:
                        state.total_done += 1
                        continue

                    # Build prompt
                    positive, negative, meta = build_prompt(persona, cat_name, i)
                    seed = get_seed(persona, cat_name, i)

                    # Generate with full error handling
                    t0 = time.time()
                    png_bytes = None

                    for attempt in range(3):
                        try:
                            png_bytes = generate_single(pipe, positive, seed, width, height)
                            break
                        except torch.cuda.OutOfMemoryError:
                            logger.warning(f"  OOM on {key} (attempt {attempt+1}), clearing cache...")
                            torch.cuda.empty_cache()
                            time.sleep(2)
                        except Exception as e:
                            logger.error(f"  Generation error on {key} (attempt {attempt+1}): {e}")
                            if attempt < 2:
                                time.sleep(1)

                    if png_bytes is None:
                        state.total_failed += 1
                        err = {"key": key, "error": "Failed after 3 attempts", "time": datetime.now(timezone.utc).isoformat()}
                        state.errors.append(err)
                        logger.error(f"  FAILED {key} after 3 attempts")
                        continue

                    gen_time = time.time() - t0

                    # Save locally
                    try:
                        local_path = Path(OUTPUT_DIR) / f"{key}.png"
                        local_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(local_path, "wb") as f:
                            f.write(png_bytes)
                    except Exception as e:
                        logger.error(f"  Local save failed {key}: {e}")

                    # Upload to Azure
                    blob_url = try_upload(png_bytes, persona.name, cat_name, i)

                    # Update manifest (crash-safe)
                    manifest["images"].append({
                        "key": key,
                        "url": blob_url or str(local_path),
                        "category": meta["category"],
                        "mood": meta["mood"],
                        "scenario": meta["scenario"],
                        "tags": meta["tags"],
                        "isNsfw": meta["isNsfw"],
                        "seed": seed,
                        "prompt": positive,
                        "width": width,
                        "height": height,
                        "generatedAt": datetime.now(timezone.utc).isoformat(),
                    })
                    save_manifest(persona_id, manifest)

                    state.total_done += 1
                    remaining = state.total_target - state.total_done
                    elapsed = time.time() - state.start_time
                    avg = elapsed / state.total_done if state.total_done > 0 else 0
                    eta = remaining * avg

                    logger.info(
                        f"  [{state.total_done}/{state.total_target}] {key} "
                        f"seed={seed} {gen_time:.1f}s "
                        f"ETA: {_fmt_time(eta)} | "
                        f"Failed: {state.total_failed}"
                    )

        elapsed_total = time.time() - state.start_time
        logger.info(f"\n{'='*60}")
        logger.info(f"  WORKER COMPLETE")
        logger.info(f"  Done:   {state.total_done}/{state.total_target}")
        logger.info(f"  Failed: {state.total_failed}")
        logger.info(f"  Time:   {_fmt_time(elapsed_total)}")
        logger.info(f"{'='*60}")

    except Exception as e:
        state.last_error = f"Worker crashed: {e}"
        logger.error(f"WORKER CRASH: {e}")
        logger.error(traceback.format_exc())
    finally:
        state.is_running = False
        state.should_stop = False


def _fmt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}h {m}m {s}s"


# ═══════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════════

class StartRequest(BaseModel):
    personas: Optional[List[str]] = None   # None = all
    limit: int = 0                         # 0 = all (100 per category)
    skip_upload: bool = False


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "gpu": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "worker_running": state.is_running,
        "model_loaded": state.pipe is not None,
    }


@app.post("/api/start")
async def start_generation(req: StartRequest):
    with state.lock:
        if state.is_running:
            raise HTTPException(409, "Generation already running. POST /api/stop first.")

        state.is_running = True
        state.should_stop = False
        state.persona_filter = req.personas
        state.limit_per_category = req.limit
        state.last_error = ""

        state.worker_thread = threading.Thread(target=worker_loop, daemon=True)
        state.worker_thread.start()

    return {"status": "started", "personas": req.personas or "all", "limit": req.limit}


@app.post("/api/stop")
async def stop_generation():
    if not state.is_running:
        return {"status": "not running"}
    state.should_stop = True
    return {"status": "stopping", "note": "Will stop after current image completes"}


@app.get("/api/status")
async def get_status():
    elapsed = time.time() - state.start_time if state.start_time > 0 else 0
    avg = elapsed / state.total_done if state.total_done > 0 else 0
    remaining = (state.total_target - state.total_done) * avg

    # Read manifests for per-persona breakdown
    persona_stats = {}
    for pid, pinfo in PERSONAS.items():
        manifest = load_manifest(pid)
        images = manifest.get("images", [])
        cat_counts = {}
        for cat in CATEGORIES:
            cat_counts[cat] = sum(1 for img in images if f"/{cat}/" in img.get("key", ""))
        persona_stats[pid] = {
            "name": pinfo.name,
            "done": len(images),
            "categories": cat_counts,
        }

    return {
        "running": state.is_running,
        "stopping": state.should_stop,
        "current": {
            "persona": state.current_persona,
            "category": state.current_category,
            "image": state.current_image,
        },
        "progress": {
            "done": state.total_done,
            "failed": state.total_failed,
            "target": state.total_target,
            "pct": round(state.total_done / state.total_target * 100, 1) if state.total_target > 0 else 0,
        },
        "timing": {
            "elapsed": _fmt_time(elapsed),
            "avg_per_image": f"{avg:.1f}s",
            "eta": _fmt_time(remaining),
        },
        "last_error": state.last_error,
        "recent_errors": state.errors[-5:],
        "personas": persona_stats,
    }


@app.get("/api/preview/{persona}/{category}/{number}")
async def get_preview(persona: str, category: str, number: int):
    path = Path(OUTPUT_DIR) / persona / category / f"{number:04d}.png"
    if path.exists():
        return FileResponse(path, media_type="image/png")
    raise HTTPException(404, "Image not found")


@app.get("/api/latest")
async def get_latest_images():
    """Get the most recently generated images across all personas."""
    all_images = []
    for pid in PERSONAS:
        manifest = load_manifest(pid)
        for img in manifest.get("images", [])[-5:]:
            all_images.append(img)
    all_images.sort(key=lambda x: x.get("generatedAt", ""), reverse=True)
    return all_images[:20]


# ═══════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>XinMate Generator</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f0f0f;color:#e0e0e0}
.header{background:linear-gradient(135deg,#1a1a2e,#16213e);padding:20px 30px;border-bottom:1px solid #333}
.header h1{font-size:22px;color:#fff}
.header .sub{font-size:13px;color:#888;margin-top:4px}
.controls{padding:15px 30px;background:#161616;border-bottom:1px solid #222;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.btn{padding:8px 20px;border:none;border-radius:6px;font-size:13px;font-weight:600;cursor:pointer;transition:all .2s}
.btn-start{background:#22c55e;color:#000}.btn-start:hover{background:#16a34a}
.btn-stop{background:#ef4444;color:#fff}.btn-stop:hover{background:#dc2626}
.btn:disabled{opacity:.4;cursor:not-allowed}
.input{background:#2a2a2a;border:1px solid #444;color:#fff;padding:6px 12px;border-radius:6px;font-size:13px}
.stats{display:flex;gap:20px;padding:20px 30px;flex-wrap:wrap}
.stat{background:#1e1e1e;border-radius:10px;padding:16px 24px;min-width:150px}
.stat .label{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px}
.stat .val{font-size:28px;font-weight:700;color:#fff;margin-top:4px}
.stat .val.g{color:#4ade80}.stat .val.b{color:#60a5fa}.stat .val.r{color:#ef4444}.stat .val.y{color:#fbbf24}
.pbar{width:100%;height:8px;background:#333;border-radius:4px;margin-top:8px}
.pfill{height:100%;border-radius:4px;background:linear-gradient(90deg,#4ade80,#22d3ee);transition:width .5s}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;padding:20px 30px}
.card{background:#1a1a1a;border-radius:10px;padding:14px;border:1px solid #2a2a2a}
.card .name{font-size:15px;font-weight:600;color:#fff}
.card .cnt{font-size:12px;color:#aaa;margin-top:4px}
.card .cats{display:flex;gap:4px;margin-top:8px;flex-wrap:wrap}
.tag{font-size:10px;padding:2px 7px;border-radius:5px;background:#2a2a2a;color:#ccc}
.tag.ok{background:#166534;color:#4ade80}
.stitle{padding:16px 30px 8px;font-size:15px;color:#888}
.errors{padding:0 30px 20px}
.err{font-size:12px;color:#f87171;padding:4px 0;border-bottom:1px solid #222}
.preview-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;padding:0 30px 30px}
.preview-card{background:#1a1a1a;border-radius:8px;overflow:hidden;border:1px solid #2a2a2a}
.preview-card img{width:100%;aspect-ratio:1;object-fit:cover}
.preview-card .info{padding:6px 8px;font-size:11px;color:#888}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.dot.run{background:#4ade80;animation:pulse 1.5s infinite}
.dot.stop{background:#fbbf24;animation:pulse .8s infinite}
.dot.idle{background:#555}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.foot{text-align:center;padding:10px;font-size:11px;color:#444}
</style>
</head>
<body>
<div class="header">
  <h1>🎨 XinMate Image Generator</h1>
  <div class="sub" id="ts">Loading...</div>
</div>

<div class="controls">
  <button class="btn btn-start" id="btn-start" onclick="startGen()">▶ Start</button>
  <button class="btn btn-stop" id="btn-stop" onclick="stopGen()" disabled>⏹ Stop</button>
  <label style="font-size:12px;color:#888;margin-left:10px">Limit/cat:</label>
  <input class="input" id="limit" type="number" value="20" min="0" max="100" style="width:60px">
  <label style="font-size:12px;color:#888;margin-left:10px">Personas (blank=all):</label>
  <input class="input" id="personas" type="text" placeholder="ananya,riya" style="width:180px">
</div>

<div class="stats">
  <div class="stat"><div class="label">Status</div><div class="val" id="status"><span class="dot idle"></span>Idle</div></div>
  <div class="stat"><div class="label">Progress</div><div class="val g" id="progress">0 / 0</div><div class="pbar"><div class="pfill" id="pbar" style="width:0%"></div></div></div>
  <div class="stat"><div class="label">Done %</div><div class="val b" id="pct">0%</div></div>
  <div class="stat"><div class="label">Failed</div><div class="val r" id="failed">0</div></div>
  <div class="stat"><div class="label">Speed</div><div class="val y" id="speed">-</div></div>
  <div class="stat"><div class="label">ETA</div><div class="val" id="eta">-</div></div>
</div>

<div class="stitle">Personas</div>
<div class="grid" id="pgrid"></div>

<div class="stitle">Latest Images</div>
<div class="preview-grid" id="previews"></div>

<div class="stitle" id="err-title" style="display:none">Recent Errors</div>
<div class="errors" id="errs"></div>

<div class="foot">Auto-refreshes every 5s · Server log: /workspace/generator.log</div>

<script>
async function refresh(){
  try{
    const r=await fetch('/api/status');
    const d=await r.json();
    document.getElementById('ts').textContent='Updated: '+new Date().toLocaleTimeString();

    const s=document.getElementById('status');
    if(d.stopping) s.innerHTML='<span class="dot stop"></span>Stopping...';
    else if(d.running) s.innerHTML='<span class="dot run"></span>Generating';
    else s.innerHTML='<span class="dot idle"></span>Idle';

    document.getElementById('btn-start').disabled=d.running;
    document.getElementById('btn-stop').disabled=!d.running;

    const p=d.progress;
    document.getElementById('progress').textContent=p.done+' / '+p.target;
    document.getElementById('pct').textContent=p.pct+'%';
    document.getElementById('pbar').style.width=p.pct+'%';
    document.getElementById('failed').textContent=p.failed;
    document.getElementById('speed').textContent=d.timing.avg_per_image;
    document.getElementById('eta').textContent=d.timing.eta;

    let g='';
    for(const[pid,ps] of Object.entries(d.personas)){
      let cats='';
      for(const[c,n] of Object.entries(ps.categories)){
        const lim=parseInt(document.getElementById('limit').value)||100;
        cats+='<span class="tag '+(n>=lim?'ok':'')+'">'+c+':'+n+'</span>';
      }
      const pct=d.progress.target>0?Math.round(ps.done/(d.progress.target/Object.keys(d.personas).length)*100):0;
      g+='<div class="card"><span class="name">'+ps.name+'</span><div class="cnt">'+ps.done+' images ('+pct+'%)</div><div class="pbar"><div class="pfill" style="width:'+pct+'%"></div></div><div class="cats">'+cats+'</div></div>';
    }
    document.getElementById('pgrid').innerHTML=g;

    if(d.recent_errors&&d.recent_errors.length>0){
      document.getElementById('err-title').style.display='block';
      document.getElementById('errs').innerHTML=d.recent_errors.map(e=>'<div class="err">'+e.key+': '+e.error+'</div>').join('');
    }else{
      document.getElementById('err-title').style.display='none';
      document.getElementById('errs').innerHTML='';
    }

    // Load previews
    const lr=await fetch('/api/latest');
    const imgs=await lr.json();
    let pv='';
    for(const img of imgs.slice(0,12)){
      const parts=img.key.split('/');
      pv+='<div class="preview-card"><img src="/api/preview/'+parts[0]+'/'+parts[1]+'/'+parseInt(parts[2])+'" loading="lazy" onerror="this.style.display=\'none\'"><div class="info">'+img.key+' · '+img.mood+'</div></div>';
    }
    document.getElementById('previews').innerHTML=pv;
  }catch(e){console.error(e)}
}

async function startGen(){
  const limit=parseInt(document.getElementById('limit').value)||0;
  const pStr=document.getElementById('personas').value.trim();
  const personas=pStr?pStr.split(',').map(s=>s.trim()):null;
  const r=await fetch('/api/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({limit,personas})});
  const d=await r.json();
  if(r.ok) refresh();
  else alert(d.detail||'Error');
}

async function stopGen(){
  await fetch('/api/stop',{method:'POST'});
  refresh();
}

refresh();
setInterval(refresh,5000);
</script>
</body>
</html>
"""


# ═══════════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  XinMate Image Generation Server")
    print("  Dashboard:  http://localhost:8080")
    print("  Health:     http://localhost:8080/health")
    print("  On RunPod:  https://YOUR-POD-ID-8080.proxy.runpod.net")
    print()
    print("  POST /api/start  to begin generation")
    print("  POST /api/stop   to stop gracefully")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
