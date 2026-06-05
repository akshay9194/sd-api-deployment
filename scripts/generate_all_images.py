#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  XinMate — Standalone Image Generator for ComfyUI Template  ║
║                                                              ║
║  ZERO SETUP: Upload this one file, run it, download images.  ║
║  Works directly with ComfyUI on localhost:8188.              ║
║  No pip installs, no git clone, no FastAPI needed.           ║
╚══════════════════════════════════════════════════════════════╝

INSTRUCTIONS:
  1. Deploy "ComfyUI" template on RunPod
  2. Wait for logs to say "All startup tasks have been completed"
  3. Open JupyterLab (port 8888) or SSH in
  4. Upload this file to /workspace/
  5. Run:
       cd /workspace
       python generate_all_images.py

  6. Download images from FileBrowser (port 8080):
       /workspace/xinmate_images/portraits/scarlett/
       /workspace/xinmate_images/fullbody/scarlett/
       ...

  OR download the zip:
       /workspace/xinmate_images.zip

OPTIONS (env vars):
  IMAGES_PER_PERSONA=10      (default 20, set lower to test)
  PERSONA=scarlett            (default: all 13 personas)
  MODE=fullbody               (default: both portrait + fullbody)
  MODEL_NAME=juggernautXL_v9.safetensors
"""

import os
import sys
import json
import time
import shutil
import hashlib
import subprocess
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from datetime import datetime

# ═════════════════════════════════════════════════════════════════
# CONFIG
# ═════════════════════════════════════════════════════════════════
COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")
MODEL_NAME = os.getenv("MODEL_NAME", "juggernautXL_v9.safetensors")
OUTPUT_BASE = Path(os.getenv("OUTPUT_DIR", "/workspace/xinmate_images"))
IMAGES_PER_PERSONA = int(os.getenv("IMAGES_PER_PERSONA", "20"))
SINGLE_PERSONA = os.getenv("PERSONA", "")
MODE = os.getenv("MODE", "both")  # "portrait", "fullbody", or "both"
CREATE_ZIP = os.getenv("CREATE_ZIP", "true").lower() == "true"

# Model download config
MODEL_URL = os.getenv(
    "MODEL_URL",
    "https://huggingface.co/RunDiffusion/Juggernaut-XL-v9/resolve/main/Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors"
)
# ComfyUI checkpoints dir — try template path first, fallback to common paths
CHECKPOINTS_DIRS = [
    Path("/workspace/runpod-slim/ComfyUI/models/checkpoints"),
    Path("/workspace/ComfyUI/models/checkpoints"),
    Path("/root/ComfyUI/models/checkpoints"),
]

# ═════════════════════════════════════════════════════════════════
# COMFYUI CLIENT (stdlib only — no httpx/requests needed)
# ═════════════════════════════════════════════════════════════════

def comfyui_post(endpoint: str, data: dict) -> dict:
    """POST JSON to ComfyUI."""
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        f"{COMFYUI_URL}{endpoint}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def comfyui_get(endpoint: str, params: dict = None) -> bytes:
    """GET from ComfyUI, return raw bytes."""
    url = f"{COMFYUI_URL}{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read()


def comfyui_get_json(endpoint: str) -> dict:
    """GET JSON from ComfyUI."""
    return json.loads(comfyui_get(endpoint))


def check_health() -> bool:
    """Check if ComfyUI is ready."""
    try:
        data = comfyui_get_json("/system_stats")
        return True
    except Exception as e:
        return False


def queue_prompt(workflow: dict) -> str:
    """Send workflow to ComfyUI, return prompt_id."""
    result = comfyui_post("/prompt", {"prompt": workflow})
    return result["prompt_id"]


def wait_for_image(prompt_id: str, timeout: int = 300) -> tuple:
    """Wait for generation to complete, return (filename, subfolder)."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            raw = comfyui_get(f"/history/{prompt_id}")
            history = json.loads(raw)
            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                for node_id, node_out in outputs.items():
                    if "images" in node_out:
                        img = node_out["images"][0]
                        return img["filename"], img.get("subfolder", "")
        except Exception:
            pass
        time.sleep(1.5)
    raise TimeoutError(f"Generation timed out after {timeout}s")


def download_image(filename: str, subfolder: str = "") -> bytes:
    """Download generated image from ComfyUI."""
    params = {"filename": filename, "subfolder": subfolder, "type": "output"}
    return comfyui_get("/view", params)


def find_checkpoints_dir() -> Path:
    """Find the ComfyUI checkpoints directory."""
    for d in CHECKPOINTS_DIRS:
        if d.exists():
            return d
    # If none exist, create the template one
    CHECKPOINTS_DIRS[0].mkdir(parents=True, exist_ok=True)
    return CHECKPOINTS_DIRS[0]


def download_model_if_needed():
    """Download Juggernaut-XL model if not already present."""
    ckpt_dir = find_checkpoints_dir()
    model_path = ckpt_dir / MODEL_NAME

    if model_path.exists():
        size_gb = model_path.stat().st_size / (1024**3)
        print(f"✅ Model already exists: {model_path} ({size_gb:.1f} GB)")
        return

    print(f"📥 Model '{MODEL_NAME}' not found in {ckpt_dir}")
    print(f"   Downloading from HuggingFace (~6.5 GB)...")
    print(f"   This may take 5-10 minutes on first run.\n")

    tmp_path = model_path.with_suffix(".downloading")

    # Method 1: Try wget (most reliable on RunPod — handles DNS, retries, redirects)
    wget_path = shutil.which("wget")
    curl_path = shutil.which("curl")

    if wget_path:
        print("   Using wget for download...")
        result = subprocess.run(
            ["wget", "-O", str(tmp_path), "--progress=bar:force:noscroll", MODEL_URL],
            capture_output=False,
        )
        if result.returncode == 0 and tmp_path.exists() and tmp_path.stat().st_size > 1_000_000_000:
            tmp_path.rename(model_path)
            print(f"\n   ✅ Download complete: {model_path}")
            return
        else:
            if tmp_path.exists():
                tmp_path.unlink()
            print("   ⚠️  wget failed, trying curl...")

    if curl_path:
        print("   Using curl for download...")
        result = subprocess.run(
            ["curl", "-L", "-o", str(tmp_path), "--progress-bar", MODEL_URL],
            capture_output=False,
        )
        if result.returncode == 0 and tmp_path.exists() and tmp_path.stat().st_size > 1_000_000_000:
            tmp_path.rename(model_path)
            print(f"\n   ✅ Download complete: {model_path}")
            return
        else:
            if tmp_path.exists():
                tmp_path.unlink()
            print("   ⚠️  curl failed, trying Python urllib...")

    # Method 3: Python urllib fallback
    try:
        req = urllib.request.Request(MODEL_URL, headers={"User-Agent": "XinMate-Generator/1.0"})
        with urllib.request.urlopen(req, timeout=600) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 8 * 1024 * 1024  # 8MB chunks

            with open(tmp_path, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = downloaded / total * 100
                        gb_done = downloaded / (1024**3)
                        gb_total = total / (1024**3)
                        print(f"\r   ⏳ {gb_done:.1f} / {gb_total:.1f} GB ({pct:.0f}%)", end="", flush=True)

        tmp_path.rename(model_path)
        print(f"\n   ✅ Download complete: {model_path}")

    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink()
        print(f"\n   ❌ All download methods failed: {e}")
        print(f"\n   MANUAL FIX — run this in the terminal:")
        print(f"   wget -O {ckpt_dir}/{MODEL_NAME} {MODEL_URL}")
        sys.exit(1)


# ═════════════════════════════════════════════════════════════════
# WORKFLOW BUILDER
# ═════════════════════════════════════════════════════════════════

def build_workflow(
    prompt: str,
    negative_prompt: str,
    seed: int,
    width: int,
    height: int,
    steps: int = 32,
    cfg: float = 6.0,
    filename_prefix: str = "xinmate",
) -> dict:
    return {
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
                "latent_image": ["5", 0],
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": MODEL_NAME},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["4", 1]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_prompt, "clip": ["4", 1]},
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": filename_prefix, "images": ["8", 0]},
        },
    }


# ═════════════════════════════════════════════════════════════════
# GLOBAL NEGATIVE (realism guard)
# ═════════════════════════════════════════════════════════════════

GLOBAL_NEGATIVE = (
    "celebrity, famous person, actor, actress, influencer, model, "
    "real person, known face, beauty filter, airbrushed skin, plastic skin, "
    "anime, illustration, painting, cgi, 3d render, "
    "teen, teenage, young-looking, childlike, youthful face, "
    "school uniform, student, cosplay, "
    "distorted face, extra fingers, deformed eyes"
)

FULLBODY_NEGATIVE_EXTRA = (
    "cropped, close up, portrait crop, face only, headshot, "
    "cut off legs, cut off feet, missing legs, missing feet, "
    "floating body, bad proportions, short body"
)

FULLBODY_CORE = (
    "full body shot, head to toe, full length photo, "
    "showing feet, standing pose, wide framing, "
    "professional photography, studio quality"
)

# ═════════════════════════════════════════════════════════════════
# PERSONA DEFINITIONS
# ═════════════════════════════════════════════════════════════════

PERSONAS = {
    # ── FEMALE ───────────────────────────────────────────────
    "scarlett": {
        "name": "Scarlett",
        "gender": "female",
        "base": "beautiful woman, 25 years old, athletic fit body, long wavy red hair, striking green eyes, full lips, high cheekbones, beauty mark on cheek, confident expression, fair skin",
        "neg": "ugly, deformed, bad anatomy, blurry, low quality, masculine features, old age",
        "style": "sexy",
        "seed": 100000,
    },
    "emma": {
        "name": "Emma",
        "gender": "female",
        "base": "beautiful asian woman, 22 years old, petite slim body, long straight black hair, cute round face, big brown eyes, dimples, soft features, adorable smile, fair skin, youthful",
        "neg": "ugly, deformed, bad anatomy, blurry, low quality, mature, harsh features, old age",
        "style": "cute",
        "seed": 200000,
    },
    "victoria": {
        "name": "Victoria",
        "gender": "female",
        "base": "beautiful woman, 32 years old, tall elegant body, black hair in sleek bob, piercing blue eyes, sharp jawline, high cheekbones, commanding presence, sophisticated, powerful CEO aesthetic, fair skin, intense gaze",
        "neg": "ugly, deformed, bad anatomy, blurry, low quality, submissive pose, casual clothes",
        "style": "elegant",
        "seed": 300000,
    },
    "lily": {
        "name": "Lily",
        "gender": "female",
        "base": "beautiful woman, 24 years old, natural beauty, slim body, wavy brown hair, warm hazel eyes, freckles, dimples, warm genuine smile, girl next door, medium skin tone, approachable",
        "neg": "ugly, deformed, bad anatomy, blurry, low quality, heavy makeup, overly glamorous",
        "style": "casual",
        "seed": 400000,
    },
    "isabella": {
        "name": "Isabella",
        "gender": "female",
        "base": "beautiful latina woman, 26 years old, curvy dancer body, long curly dark brown hair, warm brown eyes, full lips, tan skin, passionate expression, Colombian beauty, sensual pose",
        "neg": "ugly, deformed, bad anatomy, blurry, low quality, pale skin, reserved expression",
        "style": "sexy",
        "seed": 500000,
    },
    "maya": {
        "name": "Maya",
        "gender": "female",
        "base": "beautiful african american woman, 24 years old, curvy body, long black braided hair, warm brown eyes, bright smile, trendy fashion, friendly expression, dark skin",
        "neg": "ugly, deformed, bad anatomy, blurry, low quality, serious expression",
        "style": "trendy",
        "seed": 600000,
    },
    "kira": {
        "name": "Kira",
        "gender": "female",
        "base": "beautiful succubus woman, supernatural beauty, curvy body, very long black wavy hair, glowing purple eyes, small demon horns, demon tail, pale skin, seductive expression, dark fantasy aesthetic",
        "neg": "ugly, deformed, bad anatomy, blurry, low quality, angel, innocent, modest clothing",
        "style": "fantasy",
        "seed": 700000,
    },
    # ── MALE ─────────────────────────────────────────────────
    "marcus": {
        "name": "Marcus",
        "gender": "male",
        "base": "handsome man, 28 years old, athletic muscular body, short black hair with fade, warm brown eyes, strong jawline, tan skin, protective confident expression, firefighter physique, broad shoulders",
        "neg": "ugly, deformed, bad anatomy, blurry, low quality, feminine features, weak appearance",
        "style": "casual",
        "seed": 800000,
    },
    "ryan": {
        "name": "Ryan",
        "gender": "male",
        "base": "handsome man, 27 years old, lean athletic body, messy dark brown hair, intense blue eyes, stubble, tattoos on arms, bad boy aesthetic, leather jacket, smirk, dangerous charm",
        "neg": "ugly, deformed, bad anatomy, blurry, low quality, clean cut, innocent looking, soft features",
        "style": "edgy",
        "seed": 900000,
    },
    "alexander": {
        "name": "Alexander",
        "gender": "male",
        "base": "handsome man, 31 years old, tall slim build, styled brown hair, warm green eyes, chiseled features, distinguished gentleman aesthetic, tailored suit, warm sophisticated smile, fair skin",
        "neg": "ugly, deformed, bad anatomy, blurry, low quality, casual clothes, rough appearance",
        "style": "elegant",
        "seed": 1000000,
    },
    "ethan": {
        "name": "Ethan",
        "gender": "male",
        "base": "handsome man, 25 years old, average build, messy dirty blonde hair, warm brown eyes, boyish charm, friendly warm smile, approachable, light skin",
        "neg": "ugly, deformed, bad anatomy, blurry, low quality, formal wear, serious expression",
        "style": "casual",
        "seed": 1100000,
    },
    "damien": {
        "name": "Damien",
        "gender": "male",
        "base": "handsome man, 30 years old, tall athletic build, short black hair slicked back, intense grey eyes, sharp jawline, CEO aesthetic, expensive suit, commanding presence, intimidating but attractive, fair skin",
        "neg": "ugly, deformed, bad anatomy, blurry, low quality, casual clothes, soft expression, friendly",
        "style": "elegant",
        "seed": 1200000,
    },
    "lucian": {
        "name": "Lucian",
        "gender": "male",
        "base": "handsome vampire man, ageless ethereal beauty, tall slim build, long silver hair, red eyes, pale skin, sharp features, fangs, gothic elegant clothing, dark romantic aesthetic, dangerous allure",
        "neg": "ugly, deformed, bad anatomy, blurry, low quality, modern clothes, warm skin tone, friendly expression",
        "style": "fantasy",
        "seed": 1300000,
    },
}

# ═════════════════════════════════════════════════════════════════
# SCENARIOS
# ═════════════════════════════════════════════════════════════════

PORTRAIT_SCENARIOS = [
    ("selfie", "selfie angle, looking at camera, smartphone photo style, close up", 15),
    ("morning", "morning sunlight, cozy bedroom, just woke up, natural lighting", 10),
    ("coffee", "holding coffee cup, cafe setting, warm ambiance, relaxed", 8),
    ("casual_home", "at home, comfortable setting, relaxed pose, cozy", 10),
    ("bedroom_romantic", "bedroom setting, romantic lighting, intimate atmosphere, soft lighting", 10),
    ("evening_dress", "elegant evening wear, dressed up, romantic dinner setting, candlelight", 8),
    ("flirty", "flirty expression, playful pose, suggestive but tasteful", 10),
    ("workout", "gym clothes, fitness setting, active pose, athletic", 5),
    ("beach", "beach setting, summer vibes, swimwear, sunny day", 5),
    ("night_out", "night club lighting, party outfit, vibrant atmosphere", 5),
    ("relaxed_evening", "evening at home, comfortable clothes, soft lighting, relaxed", 8),
    ("professional", "professional setting, office background, business attire", 3),
    ("date_night", "restaurant setting, date night outfit, romantic ambiance", 5),
]

FULLBODY_SCENARIOS = [
    ("standing_casual", "standing naturally, relaxed pose, urban street background, natural daylight", 12),
    ("fashion_pose", "fashion model pose, editorial photography, clean background, studio lighting", 10),
    ("walking", "walking towards camera, city sidewalk, confident stride, outdoor", 8),
    ("leaning_wall", "leaning against wall, relaxed cool pose, urban background, natural lighting", 8),
    ("mirror_selfie", "full body mirror selfie, bedroom mirror, smartphone in hand, casual pose", 10),
    ("doorway", "standing in doorway, leaning on door frame, home setting, warm lighting", 6),
    ("outdoor_nature", "standing outdoors, park or garden, natural greenery, golden hour lighting", 6),
    ("beach_full", "standing on beach, ocean background, sunny day, sand under feet", 5),
    ("gym_full", "standing in gym, fitness setting, athletic pose, gym equipment background", 5),
    ("date_arrival", "standing at restaurant entrance, evening lighting, dressed up, ready for date", 6),
    ("staircase", "standing on stairs, elegant staircase, looking at camera, dramatic angle", 4),
    ("balcony", "standing on balcony, city skyline background, evening light, railing visible", 5),
    ("bedroom_standing", "standing in bedroom, morning light through window, intimate setting, soft lighting", 8),
    ("cafe_standing", "standing outside cafe, holding coffee, street scene, casual vibe", 4),
]

# ═════════════════════════════════════════════════════════════════
# OUTFITS
# ═════════════════════════════════════════════════════════════════

PORTRAIT_OUTFITS = {
    "sexy": ["wearing tight dress", "wearing lingerie", "wearing crop top and shorts", "wearing bodycon dress", "wearing silk robe", "wearing off-shoulder top", "wearing mini skirt", "wearing form-fitting dress"],
    "cute": ["wearing oversized sweater", "wearing cute pajamas", "wearing sundress", "wearing casual dress", "wearing hoodie", "wearing pastel colors", "wearing cute loungewear"],
    "elegant": ["wearing tailored suit", "wearing elegant blouse", "wearing business dress", "wearing designer clothes", "wearing silk shirt", "wearing formal attire", "wearing sophisticated outfit"],
    "casual": ["wearing jeans and t-shirt", "wearing casual dress", "wearing comfortable clothes", "wearing hoodie and jeans", "wearing sweater", "wearing casual summer outfit", "wearing weekend casual"],
    "trendy": ["wearing streetwear", "wearing trendy outfit", "wearing fashionable clothes", "wearing designer streetwear", "wearing modern fashion", "wearing stylish outfit"],
    "edgy": ["wearing leather jacket", "wearing band t-shirt", "wearing ripped jeans", "wearing all black outfit", "wearing punk style", "wearing dark clothes"],
    "fantasy": ["wearing dark elegant robes", "wearing gothic outfit", "wearing fantasy costume", "wearing dark lingerie", "wearing mystical clothing", "wearing dark romantic outfit"],
}

FULLBODY_OUTFITS = {
    "sexy": ["wearing tight mini dress and high heels", "wearing crop top, mini skirt, and strappy heels", "wearing bodycon dress and stilettos", "wearing lingerie and silk robe, bare feet", "wearing bikini and sarong wrap", "wearing off-shoulder dress and heels", "wearing tight jeans, heels, and corset top", "wearing cocktail dress and pumps"],
    "cute": ["wearing oversized sweater, knee socks, and sneakers", "wearing sundress and white sneakers", "wearing pleated skirt, cardigan, and loafers", "wearing cute pajamas and fuzzy slippers", "wearing pastel dress and ankle boots", "wearing denim overalls and t-shirt", "wearing hoodie dress and sneakers", "wearing floral dress and sandals"],
    "elegant": ["wearing tailored suit and oxford shoes", "wearing floor-length gown and heels", "wearing business dress and pumps", "wearing silk blouse, tailored trousers, and loafers", "wearing designer dress and stilettos", "wearing tuxedo and dress shoes", "wearing pencil skirt, blazer, and heels", "wearing three-piece suit and polished shoes"],
    "casual": ["wearing jeans, t-shirt, and sneakers", "wearing casual dress and sandals", "wearing joggers, hoodie, and running shoes", "wearing shorts, tank top, and flip flops", "wearing chinos, polo shirt, and loafers", "wearing sweater, jeans, and boots", "wearing cargo pants, graphic tee, and sneakers", "wearing denim jacket, jeans, and boots"],
    "trendy": ["wearing streetwear outfit and chunky sneakers", "wearing designer tracksuit and trainers", "wearing high-waisted pants, crop top, and platform shoes", "wearing oversized jacket, bike shorts, and sneakers", "wearing trendy co-ord set and boots", "wearing wide-leg pants, fitted top, and sneakers", "wearing leather pants, designer top, and boots"],
    "edgy": ["wearing leather jacket, ripped jeans, and combat boots", "wearing all black outfit and heavy boots", "wearing band tee, leather pants, and boots", "wearing biker jacket, dark jeans, and chunky boots", "wearing punk style outfit and platform boots", "wearing distressed denim and motorcycle boots", "wearing dark hoodie, cargo pants, and combat boots"],
    "fantasy": ["wearing dark elegant robes and gothic boots", "wearing fantasy armor and leather boots", "wearing gothic gown and platform boots", "wearing dark corset dress and thigh-high boots", "wearing mystical cloak and ornate boots", "wearing dark leather outfit and combat boots", "wearing supernatural elegant suit and dress shoes"],
}

EXPRESSIONS = [
    "smiling warmly", "seductive look", "playful expression", "confident smile",
    "soft gentle expression", "intense gaze", "laughing naturally", "flirty smile",
    "mysterious look", "loving expression",
]

POSES = [
    "standing straight, hands at sides", "standing with hand on hip",
    "standing with arms crossed", "standing with hands in pockets",
    "standing leaning slightly forward", "standing with one leg bent",
    "standing confident power pose", "standing relaxed natural pose",
    "standing with hand touching hair", "standing looking over shoulder",
]

# ═════════════════════════════════════════════════════════════════
# VARIATION BUILDER
# ═════════════════════════════════════════════════════════════════

def build_variations(persona_id, persona, count, mode="portrait"):
    """Build list of (prompt, negative, seed, width, height, scenario_name) tuples."""
    is_fullbody = mode == "fullbody"
    scenarios = FULLBODY_SCENARIOS if is_fullbody else PORTRAIT_SCENARIOS
    outfits = (FULLBODY_OUTFITS if is_fullbody else PORTRAIT_OUTFITS).get(persona["style"], PORTRAIT_OUTFITS["casual"])
    seed_offset = 5000 if is_fullbody else 0

    total_weight = sum(w for _, _, w in scenarios)
    variations = []
    idx = 0

    for sc_name, sc_prompt, weight in scenarios:
        sc_count = max(1, int((weight / total_weight) * count))
        for _ in range(sc_count):
            if idx >= count:
                break

            outfit = outfits[idx % len(outfits)]
            if is_fullbody:
                pose = POSES[idx % len(POSES)]
                prompt = f"{persona['base']}, {FULLBODY_CORE}, {outfit}, {pose}, {sc_prompt}, high quality, professional photo, detailed, sharp focus"
                neg = f"{persona['neg']}, {GLOBAL_NEGATIVE}, {FULLBODY_NEGATIVE_EXTRA}"
                w, h = 832, 1216
            else:
                expr = EXPRESSIONS[idx % len(EXPRESSIONS)]
                prompt = f"{persona['base']}, {outfit}, {expr}, {sc_prompt}, high quality, professional photo, detailed"
                neg = f"{persona['neg']}, {GLOBAL_NEGATIVE}"
                w, h = 1024, 1024

            seed = persona["seed"] + seed_offset + idx
            variations.append((prompt, neg, seed, w, h, sc_name))
            idx += 1

    # fill remaining
    fill_sc = scenarios[0]  # most weighted
    while idx < count:
        outfit = outfits[idx % len(outfits)]
        if is_fullbody:
            pose = POSES[idx % len(POSES)]
            prompt = f"{persona['base']}, {FULLBODY_CORE}, {outfit}, {pose}, {fill_sc[1]}, high quality, professional photo, detailed, sharp focus"
            neg = f"{persona['neg']}, {GLOBAL_NEGATIVE}, {FULLBODY_NEGATIVE_EXTRA}"
            w, h = 832, 1216
        else:
            expr = EXPRESSIONS[idx % len(EXPRESSIONS)]
            prompt = f"{persona['base']}, {outfit}, {expr}, {fill_sc[1]}, high quality, professional photo, detailed"
            neg = f"{persona['neg']}, {GLOBAL_NEGATIVE}"
            w, h = 1024, 1024

        seed = persona["seed"] + seed_offset + idx
        variations.append((prompt, neg, seed, w, h, fill_sc[0]))
        idx += 1

    return variations


# ═════════════════════════════════════════════════════════════════
# GENERATE ONE IMAGE
# ═════════════════════════════════════════════════════════════════

def generate_one(prompt, negative, seed, width, height, prefix="xinmate") -> tuple:
    """Generate a single image. Returns (image_bytes, seed) or raises."""
    workflow = build_workflow(prompt, negative, seed, width, height, filename_prefix=prefix)
    prompt_id = queue_prompt(workflow)
    filename, subfolder = wait_for_image(prompt_id, timeout=300)
    image_data = download_image(filename, subfolder)
    return image_data, seed


# ═════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════

def main():
    print("=" * 64)
    print("🖼️  XinMate Standalone Image Generator")
    print("   Works directly with ComfyUI — no extra servers needed")
    print("=" * 64)

    # Determine which personas
    if SINGLE_PERSONA:
        if SINGLE_PERSONA not in PERSONAS:
            print(f"❌ Unknown persona '{SINGLE_PERSONA}'")
            print(f"   Available: {', '.join(PERSONAS.keys())}")
            sys.exit(1)
        personas = {SINGLE_PERSONA: PERSONAS[SINGLE_PERSONA]}
    else:
        personas = PERSONAS

    # Determine modes
    modes = []
    if MODE in ("portrait", "both"):
        modes.append("portrait")
    if MODE in ("fullbody", "both"):
        modes.append("fullbody")

    total = len(personas) * len(modes) * IMAGES_PER_PERSONA
    print(f"  ComfyUI:    {COMFYUI_URL}")
    print(f"  Model:      {MODEL_NAME}")
    print(f"  Output:     {OUTPUT_BASE}")
    print(f"  Personas:   {len(personas)} ({', '.join(personas.keys())})")
    print(f"  Modes:      {', '.join(modes)}")
    print(f"  Per combo:  {IMAGES_PER_PERSONA}")
    print(f"  Total:      {total} images")
    print("=" * 64)

    # Health check
    print("\n⏳ Checking ComfyUI...", end=" ", flush=True)
    retries = 0
    while not check_health():
        retries += 1
        if retries > 30:
            print("\n❌ ComfyUI not responding after 30 attempts. Is it running?")
            sys.exit(1)
        print(".", end="", flush=True)
        time.sleep(5)
    print("✅ Ready!")

    # Download model if not present
    download_model_if_needed()

    # Check model is visible to ComfyUI (may need a moment after download)
    print("🔍 Verifying model in ComfyUI...", end=" ", flush=True)
    model_found = False
    for attempt in range(12):  # wait up to 60s for ComfyUI to detect new model
        try:
            obj_info = comfyui_get_json("/object_info/CheckpointLoaderSimple")
            available = obj_info.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
            if MODEL_NAME in available:
                model_found = True
                break
        except Exception:
            pass
        time.sleep(5)
        print(".", end="", flush=True)

    if not model_found:
        print(f"\n⚠️  Model '{MODEL_NAME}' not detected by ComfyUI.")
        print(f"   Available: {available if 'available' in dir() else '(unknown)'}")
        print(f"   Try restarting ComfyUI or check the checkpoints folder.")
        sys.exit(1)

    print(f"✅ {MODEL_NAME}")

    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
    start_time = datetime.now()
    stats = {"success": 0, "fail": 0}
    manifest = {"generated_at": start_time.isoformat(), "model": MODEL_NAME, "images": []}

    for mode in modes:
        for pid, persona in personas.items():
            folder = OUTPUT_BASE / mode / pid
            folder.mkdir(parents=True, exist_ok=True)

            label = "🧍" if mode == "fullbody" else "📸"
            print(f"\n{label} {persona['name']} — {mode} ({IMAGES_PER_PERSONA} images)")

            variations = build_variations(pid, persona, IMAGES_PER_PERSONA, mode)

            for i, (prompt, neg, seed, w, h, sc_name) in enumerate(variations):
                try:
                    img_data, used_seed = generate_one(prompt, neg, seed, w, h, prefix=f"xm_{pid}")
                    img_hash = hashlib.sha256(img_data).hexdigest()[:12]
                    fname = f"{pid}_{mode}_{i:03d}_s{used_seed}_{img_hash}.png"
                    fpath = folder / fname
                    fpath.write_bytes(img_data)

                    stats["success"] += 1
                    manifest["images"].append({
                        "persona": pid, "mode": mode, "scenario": sc_name,
                        "seed": used_seed, "file": str(fpath.relative_to(OUTPUT_BASE)),
                        "hash": img_hash, "resolution": f"{w}x{h}",
                    })
                    print(f"  ✅ {i+1}/{IMAGES_PER_PERSONA} {sc_name} (seed {used_seed})")
                except Exception as e:
                    stats["fail"] += 1
                    print(f"  ❌ {i+1}/{IMAGES_PER_PERSONA} {sc_name} — {e}")

                time.sleep(0.3)

    # Save manifest
    manifest["completed_at"] = datetime.now().isoformat()
    manifest["stats"] = stats
    (OUTPUT_BASE / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # Create zip for easy download
    if CREATE_ZIP:
        print("\n📦 Creating zip for download...")
        zip_path = OUTPUT_BASE.parent / "xinmate_images"
        shutil.make_archive(str(zip_path), "zip", str(OUTPUT_BASE))
        zip_file = f"{zip_path}.zip"
        size_mb = os.path.getsize(zip_file) / (1024 * 1024)
        print(f"   {zip_file} ({size_mb:.1f} MB)")

    # Summary
    duration = datetime.now() - start_time
    print("\n" + "=" * 64)
    print("📊 COMPLETE")
    print("=" * 64)
    print(f"  Time:       {duration}")
    print(f"  Success:    {stats['success']}")
    print(f"  Failed:     {stats['fail']}")
    print(f"  Images at:  {OUTPUT_BASE}/")
    if CREATE_ZIP:
        print(f"  Zip at:     /workspace/xinmate_images.zip")
    print()
    print("📥 DOWNLOAD OPTIONS:")
    print("   1. FileBrowser → http://<pod-ip>:8080 → /workspace/xinmate_images/")
    print("   2. FileBrowser → download /workspace/xinmate_images.zip")
    print("   3. JupyterLab → http://<pod-ip>:8888 → browse & download")
    print("   4. scp root@<pod-ip>:/workspace/xinmate_images.zip ./")
    print("=" * 64)


if __name__ == "__main__":
    main()
