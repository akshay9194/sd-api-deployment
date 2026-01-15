"""
Stable Diffusion Image Generation API
Configurable wrapper for ComfyUI with safety features.

All settings configurable via environment variables.
Designed for RunPod GPU deployment.

Environment Variables:
  COMFYUI_URL        - ComfyUI server URL (default: http://127.0.0.1:8188)
  API_KEY            - Bearer token for auth (optional, empty = no auth)
  OUTPUT_DIR         - Directory for generated images (default: /workspace/outputs)
  DEFAULT_STEPS      - Default generation steps (default: 25)
  DEFAULT_CFG        - Default CFG scale (default: 7.0)
  DEFAULT_WIDTH      - Default image width (default: 1024)
  DEFAULT_HEIGHT     - Default image height (default: 1024)
  MODEL_NAME         - SD model checkpoint name (default: juggernautXL_v9.safetensors)
  ENABLE_SAFETY      - Enable prompt safety filter (default: true)
"""

import os
import re
import uuid
import json
import asyncio
import logging
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import httpx
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="SD Image Generation API", version="1.0.0")
security = HTTPBearer(auto_error=False)

# ═══════════════════════════════════════════════════════════════
# Configuration from Environment Variables
# ═══════════════════════════════════════════════════════════════
COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")
API_KEY = os.getenv("API_KEY", "")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/workspace/ComfyUI/output"))
DEFAULT_STEPS = int(os.getenv("DEFAULT_STEPS", "32"))
DEFAULT_CFG = float(os.getenv("DEFAULT_CFG", "6.0"))
DEFAULT_WIDTH = int(os.getenv("DEFAULT_WIDTH", "1024"))
DEFAULT_HEIGHT = int(os.getenv("DEFAULT_HEIGHT", "1024"))
MODEL_NAME = os.getenv("MODEL_NAME", "juggernautXL_v9.safetensors")
ENABLE_SAFETY = os.getenv("ENABLE_SAFETY", "true").lower() == "true"

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════
# Global Negative Prompt (Mandatory for Realism)
# ═══════════════════════════════════════════════════════════════
GLOBAL_NEGATIVE_PROMPT = """
celebrity, famous person, actor, actress, influencer, model,
real person, known face, instagram face, tiktok face,
beauty filter, airbrushed skin, plastic skin,
anime, illustration, painting, cgi, 3d render,
teen, teenage, young-looking, childlike, youthful face,
school uniform, student, cosplay,
distorted face, extra fingers, deformed eyes
"""

# ═══════════════════════════════════════════════════════════════
# Blocked Patterns (Prompt Firewall)
# ═══════════════════════════════════════════════════════════════
BLOCKED_PATTERNS = {
    "celebrities": r"\b(taylor swift|scarlett johansson|emma watson|jennifer lawrence|megan fox|kim kardashian|ariana grande|selena gomez|beyonce|rihanna|angelina jolie|margot robbie|gal gadot|zendaya|billie eilish)\b",
    "professions": r"\b(actress|actor|famous model|influencer|celebrity|famous person)\b",
    "references": r"\b(looks? like|resembles?|similar to|based on|inspired by)\b",
    "age_down": r"\b(younger|teen|teenage|underage|school|student|childlike|loli|shota)\b",
    "uniforms": r"\b(school uniform|cheerleader uniform|schoolgirl|college girl uniform)\b",
    "face_swap": r"\b(face swap|deepfake|my face|her face|his face|real photo of)\b",
    "illegal": r"\b(child|minor|kid|forced|non-?consensual|rape)\b",
}

# ═══════════════════════════════════════════════════════════════
# Request/Response Models
# ═══════════════════════════════════════════════════════════════

class GenerateRequest(BaseModel):
    """Image generation request"""
    prompt: str = Field(..., description="Main prompt for image generation")
    negative_prompt: Optional[str] = Field("", description="Negative prompt")
    seed: Optional[int] = Field(None, description="Seed for reproducibility (-1 for random)")
    steps: Optional[int] = Field(None, description="Generation steps")
    cfg_scale: Optional[float] = Field(None, description="CFG scale")
    width: Optional[int] = Field(None, description="Image width")
    height: Optional[int] = Field(None, description="Image height")
    # Face consistency
    face_reference: Optional[str] = Field(None, description="Base64 face reference image")
    face_weight: Optional[float] = Field(0.7, description="Face similarity strength (0-1)")
    # Metadata
    persona_id: Optional[str] = Field(None, description="Persona identifier for logging")
    user_id: Optional[str] = Field(None, description="User identifier for logging")

class GenerateAsyncRequest(GenerateRequest):
    """Async generation with callback"""
    request_id: str = Field(..., description="Unique request ID")
    callback_url: str = Field(..., description="URL to POST result")

class GenerateResponse(BaseModel):
    """Generation response"""
    success: bool
    image_url: Optional[str] = None
    image_hash: Optional[str] = None
    seed_used: Optional[int] = None
    error: Optional[str] = None

class AsyncQueuedResponse(BaseModel):
    """Async queued response"""
    status: str = "queued"
    request_id: str
    message: str = "Image generation started"

# ═══════════════════════════════════════════════════════════════
# Authentication
# ═══════════════════════════════════════════════════════════════

async def verify_api_key(creds: HTTPAuthorizationCredentials = Depends(security)):
    """Verify Bearer token if API_KEY is configured"""
    if not API_KEY:
        return True
    if not creds or creds.credentials != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True

# ═══════════════════════════════════════════════════════════════
# Prompt Safety Validation
# ═══════════════════════════════════════════════════════════════

def validate_prompt(prompt: str) -> tuple[bool, str]:
    """Validate prompt against blocked patterns"""
    if not ENABLE_SAFETY:
        return True, ""
    
    prompt_lower = prompt.lower()
    
    for category, pattern in BLOCKED_PATTERNS.items():
        if re.search(pattern, prompt_lower, re.IGNORECASE):
            return False, f"Prompt rejected: {category} content not allowed"
    
    return True, ""

def build_safe_prompt(prompt: str, negative_prompt: str = "") -> tuple[str, str]:
    """Build prompt with global negative prompt for realism"""
    # Use prompt directly - no automatic modifications
    safe_prompt = prompt.strip()
    
    # Combine user negative with global mandatory negative
    combined_negative = GLOBAL_NEGATIVE_PROMPT.strip()
    if negative_prompt:
        combined_negative = f"{negative_prompt}, {combined_negative}"
    
    return safe_prompt, combined_negative.strip()

# ═══════════════════════════════════════════════════════════════
# ComfyUI Workflow Builder
# ═══════════════════════════════════════════════════════════════

def build_comfyui_workflow(
    prompt: str,
    negative_prompt: str,
    seed: int,
    steps: int,
    cfg: float,
    width: int,
    height: int,
    model_name: str = MODEL_NAME,
) -> dict:
    """Build ComfyUI workflow JSON for SDXL"""
    
    # Basic SDXL txt2img workflow (Production-tuned for Juggernaut-XL)
    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0]
            }
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": model_name
            }
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1
            }
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt,
                "clip": ["4", 1]
            }
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt,
                "clip": ["4", 1]
            }
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["3", 0],
                "vae": ["4", 2]
            }
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "xinmate",
                "images": ["8", 0]
            }
        }
    }
    
    return workflow

# ═══════════════════════════════════════════════════════════════
# ComfyUI API Client
# ═══════════════════════════════════════════════════════════════

async def queue_prompt(workflow: dict) -> str:
    """Queue a prompt in ComfyUI and return prompt_id"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{COMFYUI_URL}/prompt",
            json={"prompt": workflow},
            timeout=30.0
        )
        if response.status_code != 200:
            raise HTTPException(500, f"ComfyUI error: {response.text}")
        return response.json()["prompt_id"]

async def wait_for_completion(prompt_id: str, timeout: int = 300) -> dict:
    """Wait for ComfyUI to complete generation (5 min timeout for first-run model loading)"""
    async with httpx.AsyncClient() as client:
        start_time = asyncio.get_event_loop().time()
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                raise HTTPException(504, f"Generation timeout after {timeout}s")
            
            response = await client.get(f"{COMFYUI_URL}/history/{prompt_id}")
            if response.status_code == 200:
                history = response.json()
                if prompt_id in history:
                    return history[prompt_id]
            
            await asyncio.sleep(1)

async def get_generated_image(history: dict) -> tuple[str, bytes]:
    """Get the generated image from ComfyUI history"""
    outputs = history.get("outputs", {})
    
    for node_id, node_output in outputs.items():
        if "images" in node_output:
            for image_info in node_output["images"]:
                filename = image_info["filename"]
                subfolder = image_info.get("subfolder", "")
                
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{COMFYUI_URL}/view",
                        params={"filename": filename, "subfolder": subfolder, "type": "output"}
                    )
                    if response.status_code == 200:
                        return filename, response.content
    
    raise HTTPException(500, "No image found in output")

# ═══════════════════════════════════════════════════════════════
# Image Post-Processing
# ═══════════════════════════════════════════════════════════════

def save_and_hash_image(image_data: bytes, metadata: dict) -> tuple[str, str]:
    """Save image and generate hash for audit trail"""
    # Generate unique filename
    image_hash = hashlib.sha256(image_data).hexdigest()[:16]
    filename = f"{image_hash}_{uuid.uuid4().hex[:8]}.png"
    filepath = OUTPUT_DIR / filename
    
    # Save image
    with open(filepath, "wb") as f:
        f.write(image_data)
    
    # Log audit entry
    audit_entry = {
        "image_hash": image_hash,
        "filename": filename,
        "timestamp": datetime.utcnow().isoformat(),
        "persona_id": metadata.get("persona_id"),
        "user_id": metadata.get("user_id"),
        "seed": metadata.get("seed"),
        "prompt_hash": hashlib.sha256(metadata.get("prompt", "").encode()).hexdigest()[:16],
    }
    logger.info(f"Generated: {json.dumps(audit_entry)}")
    
    return filename, image_hash

# ═══════════════════════════════════════════════════════════════
# API Endpoints
# ═══════════════════════════════════════════════════════════════

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # Check ComfyUI connectivity
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{COMFYUI_URL}/system_stats", timeout=5.0)
            comfyui_status = "ok" if response.status_code == 200 else "error"
    except:
        comfyui_status = "unreachable"
    
    return {
        "status": "healthy",
        "comfyui": comfyui_status,
        "model": MODEL_NAME,
        "safety_enabled": ENABLE_SAFETY,
    }

@app.get("/models")
async def list_models(auth: bool = Depends(verify_api_key)):
    """List available models"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{COMFYUI_URL}/object_info/CheckpointLoaderSimple")
            if response.status_code == 200:
                data = response.json()
                models = data.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
                return {"models": models, "current": MODEL_NAME}
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
    
    return {"models": [], "current": MODEL_NAME}

@app.post("/generate", response_model=GenerateResponse)
async def generate_image(req: GenerateRequest, auth: bool = Depends(verify_api_key)):
    """Generate image synchronously"""
    
    # Validate prompt
    is_valid, error = validate_prompt(req.prompt)
    if not is_valid:
        raise HTTPException(400, error)
    
    # Build safe prompt
    safe_prompt, safe_negative = build_safe_prompt(req.prompt, req.negative_prompt or "")
    
    # Get parameters
    seed = req.seed if req.seed and req.seed > 0 else int(uuid.uuid4().int % (2**32))
    steps = req.steps or DEFAULT_STEPS
    cfg = req.cfg_scale or DEFAULT_CFG
    width = req.width or DEFAULT_WIDTH
    height = req.height or DEFAULT_HEIGHT
    
    try:
        # Build workflow
        workflow = build_comfyui_workflow(
            prompt=safe_prompt,
            negative_prompt=safe_negative,
            seed=seed,
            steps=steps,
            cfg=cfg,
            width=width,
            height=height,
        )
        
        # Queue and wait
        prompt_id = await queue_prompt(workflow)
        history = await wait_for_completion(prompt_id)
        
        # Get image
        _, image_data = await get_generated_image(history)
        
        # Save and hash
        filename, image_hash = save_and_hash_image(image_data, {
            "prompt": req.prompt,
            "seed": seed,
            "persona_id": req.persona_id,
            "user_id": req.user_id,
        })
        
        return GenerateResponse(
            success=True,
            image_url=f"/images/{filename}",
            image_hash=image_hash,
            seed_used=seed,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        return GenerateResponse(success=False, error=str(e))

@app.post("/generate-async", response_model=AsyncQueuedResponse)
async def generate_image_async(
    req: GenerateAsyncRequest,
    background_tasks: BackgroundTasks,
    auth: bool = Depends(verify_api_key)
):
    """Generate image asynchronously with callback"""
    
    # Validate prompt
    is_valid, error = validate_prompt(req.prompt)
    if not is_valid:
        raise HTTPException(400, error)
    
    # Add to background tasks
    background_tasks.add_task(process_async_generation, req)
    
    return AsyncQueuedResponse(
        request_id=req.request_id,
        message="Image generation started in background"
    )

async def process_async_generation(req: GenerateAsyncRequest):
    """Background task for async generation"""
    try:
        # Build safe prompt
        safe_prompt, safe_negative = build_safe_prompt(req.prompt, req.negative_prompt or "")
        
        seed = req.seed if req.seed and req.seed > 0 else int(uuid.uuid4().int % (2**32))
        steps = req.steps or DEFAULT_STEPS
        cfg = req.cfg_scale or DEFAULT_CFG
        width = req.width or DEFAULT_WIDTH
        height = req.height or DEFAULT_HEIGHT
        
        # Build and execute workflow
        workflow = build_comfyui_workflow(
            prompt=safe_prompt,
            negative_prompt=safe_negative,
            seed=seed,
            steps=steps,
            cfg=cfg,
            width=width,
            height=height,
        )
        
        prompt_id = await queue_prompt(workflow)
        history = await wait_for_completion(prompt_id)
        _, image_data = await get_generated_image(history)
        
        filename, image_hash = save_and_hash_image(image_data, {
            "prompt": req.prompt,
            "seed": seed,
            "persona_id": req.persona_id,
            "user_id": req.user_id,
        })
        
        # Send success callback
        callback_data = {
            "request_id": req.request_id,
            "status": "completed",
            "image_url": f"/images/{filename}",
            "image_hash": image_hash,
            "seed_used": seed,
            "user_id": req.user_id,
            "persona_id": req.persona_id,
        }
        
        async with httpx.AsyncClient() as client:
            await client.post(req.callback_url, json=callback_data, timeout=10.0)
            logger.info(f"Callback sent for {req.request_id}")
            
    except Exception as e:
        logger.error(f"Async generation failed for {req.request_id}: {e}")
        
        # Send error callback
        error_data = {
            "request_id": req.request_id,
            "status": "failed",
            "error": str(e),
            "user_id": req.user_id,
        }
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post(req.callback_url, json=error_data, timeout=10.0)
        except:
            pass

@app.get("/images/{filename}")
async def get_image(filename: str, auth: bool = Depends(verify_api_key)):
    """Serve generated image"""
    filepath = OUTPUT_DIR / filename
    if not filepath.exists():
        raise HTTPException(404, "Image not found")
    return FileResponse(filepath, media_type="image/png")

# Mount static files (optional, for direct access)
if OUTPUT_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(OUTPUT_DIR)), name="static")
