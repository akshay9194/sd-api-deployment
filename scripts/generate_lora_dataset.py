#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  Phase 1: Generate LoRA Training Dataset                     ║
║  One consistent face — Indo-Asian fashion model              ║
║                                                              ║
║  Generates 30 images optimized for Kohya LoRA training:      ║
║  - Same seed = same face across all images                   ║
║  - Varied angles, lighting, expressions                      ║
║  - Simple outfits (LoRA learns the FACE, not clothes)        ║
║  - Plain backgrounds (no distractions)                       ║
║  - 768x768 (optimal for SDXL LoRA training)                  ║
╚══════════════════════════════════════════════════════════════╝

USAGE:
  cd /workspace
  python generate_lora_dataset.py

  # Then train LoRA with Kohya on the output folder

OUTPUT:
  /workspace/lora_dataset/anya/        ← 30 training images
  /workspace/lora_dataset/anya.txt     ← auto-caption file
  /workspace/lora_dataset/manifest.json
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
from pathlib import Path
from datetime import datetime

# ═════════════════════════════════════════════════════════════════
# CONFIG
# ═════════════════════════════════════════════════════════════════
COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")
MODEL_NAME = os.getenv("MODEL_NAME", "juggernautXL_v9.safetensors")
OUTPUT_BASE = Path(os.getenv("OUTPUT_DIR", "/workspace/lora_dataset"))

# The trigger word you'll use when generating with your trained LoRA
TRIGGER_WORD = "anya"

# ═══ THE FACE — locked seed for consistency ═══
FACE_SEED = 424242  # Change this if you don't like the face generated

# ═════════════════════════════════════════════════════════════════
# MODEL FACE DEFINITION
# ═════════════════════════════════════════════════════════════════
# This is your fashion model. Every image uses this EXACT face description.
# The seed keeps the face consistent. Only angles/lighting/expression change.

FACE_BASE = (
    "beautiful young Indian woman, 23 years old, "
    "thin delicate facial features, sharp nose, defined jawline, "
    "long flowing dark brown hair with soft waves, silky hair, "
    "large expressive brown eyes, thick eyelashes, "
    "clear glowing skin, warm golden-brown complexion, "
    "high cheekbones, naturally full lips, "
    "elegant face shape, photogenic, fashion model"
)

NEGATIVE_PROMPT = (
    "ugly, deformed, bad anatomy, blurry, low quality, "
    "distorted face, extra fingers, deformed eyes, "
    "cartoon, anime, illustration, painting, cgi, 3d render, "
    "celebrity, famous person, known face, "
    "pale skin, very dark skin, "
    "round face, chubby face, wide nose, "
    "bad hair, messy unkempt hair, short hair, "
    "old, wrinkles, blemishes, acne, scars"
)

# ═════════════════════════════════════════════════════════════════
# TRAINING VARIATIONS
# For LoRA: we vary ANGLE + LIGHTING + EXPRESSION + SIMPLE OUTFIT
# We keep backgrounds plain so model learns the FACE, not scenery
# ═════════════════════════════════════════════════════════════════

TRAINING_SHOTS = [
    # ── CLOSE-UP FACE (10 shots) — LoRA needs lots of face detail ──
    {
        "name": "face_front_neutral",
        "prompt": f"{FACE_BASE}, close up face portrait, looking straight at camera, neutral expression, studio lighting, plain grey background, sharp focus on face",
        "caption": f"{TRIGGER_WORD}, close up portrait, neutral expression, studio lighting",
    },
    {
        "name": "face_front_smile",
        "prompt": f"{FACE_BASE}, close up face portrait, looking at camera, gentle confident smile, soft studio lighting, plain white background",
        "caption": f"{TRIGGER_WORD}, close up portrait, gentle smile, soft lighting",
    },
    {
        "name": "face_front_serious",
        "prompt": f"{FACE_BASE}, close up face portrait, looking at camera, serious intense expression, dramatic side lighting, dark background",
        "caption": f"{TRIGGER_WORD}, close up portrait, serious expression, dramatic lighting",
    },
    {
        "name": "face_threequarter_left",
        "prompt": f"{FACE_BASE}, close up face portrait, three quarter view facing left, slight smile, natural window light, plain background",
        "caption": f"{TRIGGER_WORD}, three quarter view, slight smile, natural light",
    },
    {
        "name": "face_threequarter_right",
        "prompt": f"{FACE_BASE}, close up face portrait, three quarter view facing right, confident expression, golden hour lighting, plain background",
        "caption": f"{TRIGGER_WORD}, three quarter view right, confident, golden hour",
    },
    {
        "name": "face_slight_tilt",
        "prompt": f"{FACE_BASE}, close up face portrait, head slightly tilted, playful knowing smile, soft diffused lighting, plain background",
        "caption": f"{TRIGGER_WORD}, close up, head tilted, playful smile, soft light",
    },
    {
        "name": "face_looking_down",
        "prompt": f"{FACE_BASE}, close up face portrait, looking slightly downward, peaceful serene expression, soft overhead lighting, plain background",
        "caption": f"{TRIGGER_WORD}, looking down, serene expression, overhead light",
    },
    {
        "name": "face_looking_up",
        "prompt": f"{FACE_BASE}, close up face portrait, looking slightly upward, hopeful inspired expression, natural sunlight, plain background",
        "caption": f"{TRIGGER_WORD}, looking up, hopeful expression, sunlight",
    },
    {
        "name": "face_profile_left",
        "prompt": f"{FACE_BASE}, side profile view facing left, elegant pose, showing jawline and nose, rim lighting, dark background",
        "caption": f"{TRIGGER_WORD}, side profile, elegant, rim lighting",
    },
    {
        "name": "face_profile_right",
        "prompt": f"{FACE_BASE}, side profile view facing right, hair flowing, beauty shot, studio lighting, plain background",
        "caption": f"{TRIGGER_WORD}, side profile right, hair flowing, beauty shot",
    },

    # ── UPPER BODY (10 shots) — face + shoulders/torso ──
    {
        "name": "upper_white_tshirt",
        "prompt": f"{FACE_BASE}, upper body portrait, wearing plain white t-shirt, arms relaxed, confident pose, studio lighting, plain grey background",
        "caption": f"{TRIGGER_WORD}, upper body, white t-shirt, confident, studio light",
    },
    {
        "name": "upper_black_top",
        "prompt": f"{FACE_BASE}, upper body portrait, wearing simple black top, hands on hips, strong pose, dramatic lighting, dark background",
        "caption": f"{TRIGGER_WORD}, upper body, black top, strong pose, dramatic light",
    },
    {
        "name": "upper_casual_denim",
        "prompt": f"{FACE_BASE}, upper body portrait, wearing casual denim jacket over white top, relaxed smile, natural daylight, plain background",
        "caption": f"{TRIGGER_WORD}, upper body, denim jacket, relaxed smile, daylight",
    },
    {
        "name": "upper_elegant_blouse",
        "prompt": f"{FACE_BASE}, upper body portrait, wearing elegant cream silk blouse, poised expression, soft warm lighting, plain background",
        "caption": f"{TRIGGER_WORD}, upper body, silk blouse, poised, warm light",
    },
    {
        "name": "upper_tank_top",
        "prompt": f"{FACE_BASE}, upper body portrait, wearing simple tank top, showing collarbones and shoulders, natural beauty, studio lighting, plain white background",
        "caption": f"{TRIGGER_WORD}, upper body, tank top, natural beauty, studio",
    },
    {
        "name": "upper_arms_crossed",
        "prompt": f"{FACE_BASE}, upper body portrait, wearing simple sweater, arms crossed, confident business-like expression, even lighting, plain background",
        "caption": f"{TRIGGER_WORD}, upper body, sweater, arms crossed, confident",
    },
    {
        "name": "upper_hair_touch",
        "prompt": f"{FACE_BASE}, upper body portrait, wearing off-shoulder top, hand touching hair, looking at camera, natural light, plain background",
        "caption": f"{TRIGGER_WORD}, upper body, off-shoulder, touching hair, natural light",
    },
    {
        "name": "upper_side_angle",
        "prompt": f"{FACE_BASE}, upper body portrait from side angle, wearing fitted top, looking over shoulder at camera, dramatic lighting, plain background",
        "caption": f"{TRIGGER_WORD}, upper body side angle, looking over shoulder",
    },
    {
        "name": "upper_warm_light",
        "prompt": f"{FACE_BASE}, upper body portrait, wearing simple linen top, warm golden light on face, peaceful expression, soft background",
        "caption": f"{TRIGGER_WORD}, upper body, linen top, golden light, peaceful",
    },
    {
        "name": "upper_cool_light",
        "prompt": f"{FACE_BASE}, upper body portrait, wearing dark turtleneck, cool blue-toned lighting, intense gaze, minimalist background",
        "caption": f"{TRIGGER_WORD}, upper body, turtleneck, cool light, intense gaze",
    },

    # ── FULL BODY (10 shots) — LoRA also needs body proportions ──
    {
        "name": "full_standing_neutral",
        "prompt": f"{FACE_BASE}, slim toned body, full body shot head to toe, wearing simple white dress, standing straight, neutral pose, studio lighting, plain grey background",
        "caption": f"{TRIGGER_WORD}, full body, white dress, standing, studio",
    },
    {
        "name": "full_casual_jeans",
        "prompt": f"{FACE_BASE}, slim toned body, full body shot head to toe, wearing jeans and fitted top and sneakers, casual confident stance, natural lighting, plain background",
        "caption": f"{TRIGGER_WORD}, full body, jeans and top, casual stance",
    },
    {
        "name": "full_elegant_dress",
        "prompt": f"{FACE_BASE}, slim toned body, full body shot head to toe, wearing elegant knee-length dress and heels, poised model stance, studio lighting, plain white background",
        "caption": f"{TRIGGER_WORD}, full body, elegant dress, model stance",
    },
    {
        "name": "full_active_wear",
        "prompt": f"{FACE_BASE}, slim toned body, full body shot head to toe, wearing athletic wear sports bra and leggings, confident athletic pose, studio lighting, plain background",
        "caption": f"{TRIGGER_WORD}, full body, athletic wear, confident pose",
    },
    {
        "name": "full_formal_suit",
        "prompt": f"{FACE_BASE}, slim toned body, full body shot head to toe, wearing tailored pantsuit and heels, power pose hands on hips, dramatic lighting, plain dark background",
        "caption": f"{TRIGGER_WORD}, full body, pantsuit, power pose, dramatic",
    },
    {
        "name": "full_summer_dress",
        "prompt": f"{FACE_BASE}, slim toned body, full body shot head to toe, wearing flowy summer dress and sandals, walking pose, warm sunlight, plain background",
        "caption": f"{TRIGGER_WORD}, full body, summer dress, walking, warm light",
    },
    {
        "name": "full_side_walk",
        "prompt": f"{FACE_BASE}, slim toned body, full body shot head to toe, wearing simple outfit, side walking pose, looking at camera, studio lighting, plain background",
        "caption": f"{TRIGGER_WORD}, full body, side walking, looking at camera",
    },
    {
        "name": "full_back_angle",
        "prompt": f"{FACE_BASE}, slim toned body, full body shot from slight back angle, wearing backless top and skirt, looking over shoulder, studio lighting, plain background",
        "caption": f"{TRIGGER_WORD}, full body, back angle, looking over shoulder",
    },
    {
        "name": "full_seated",
        "prompt": f"{FACE_BASE}, slim toned body, seated pose on simple stool, wearing casual clothes, relaxed elegant posture, studio lighting, plain background",
        "caption": f"{TRIGGER_WORD}, seated, casual clothes, relaxed posture",
    },
    {
        "name": "full_fashion_pose",
        "prompt": f"{FACE_BASE}, slim toned body, full body shot head to toe, wearing simple black dress, editorial fashion pose, dramatic studio lighting, clean white background",
        "caption": f"{TRIGGER_WORD}, full body, black dress, fashion pose, editorial",
    },
]


# ═════════════════════════════════════════════════════════════════
# COMFYUI CLIENT (same as generate_all_images.py)
# ═════════════════════════════════════════════════════════════════

def comfyui_post(endpoint, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        f"{COMFYUI_URL}{endpoint}", data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

def comfyui_get(endpoint, params=None):
    url = f"{COMFYUI_URL}{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read()

def comfyui_get_json(endpoint):
    return json.loads(comfyui_get(endpoint))

def check_health():
    try:
        comfyui_get_json("/system_stats")
        return True
    except:
        return False

def clear_queue():
    """Clear any stuck/pending prompts from ComfyUI queue"""
    try:
        comfyui_post("/queue", {"clear": True})
        print("  🧹 Queue cleared")
    except:
        pass

def queue_prompt(workflow):
    result = comfyui_post("/prompt", {"prompt": workflow})
    return result["prompt_id"]

def wait_for_image(prompt_id, timeout=600):
    """Wait for image with progress dots — 600s for dynamic VRAM loading GPUs"""
    start = time.time()
    dots = 0
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
                # Check for errors
                status = history[prompt_id].get("status", {})
                if status.get("status_str") == "error":
                    raise RuntimeError(f"ComfyUI error: {status.get('messages', 'unknown')}")
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        # Print progress dot every 15s so user knows it's alive
        dots += 1
        if dots % 10 == 0:
            elapsed = int(time.time() - start)
            print(f" ({elapsed}s)", end="", flush=True)
        time.sleep(1.5)
    raise TimeoutError(f"Generation timed out after {timeout}s")

def download_image(filename, subfolder=""):
    params = {"filename": filename, "subfolder": subfolder, "type": "output"}
    return comfyui_get("/view", params)


# ═════════════════════════════════════════════════════════════════
# WORKFLOW BUILDER (768x768 for LoRA training)
# ═════════════════════════════════════════════════════════════════

def build_workflow(prompt, negative, seed, width=512, height=512):
    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": 20,       # fast generation, still good for LoRA training
                "cfg": 7.0,        # higher cfg = sharper features at lower res
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
            "inputs": {"text": negative, "clip": ["4", 1]},
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": f"lora_{TRIGGER_WORD}", "images": ["8", 0]},
        },
    }


def generate_one(prompt, negative, seed, width=512, height=512):
    workflow = build_workflow(prompt, negative, seed, width, height)
    prompt_id = queue_prompt(workflow)
    filename, subfolder = wait_for_image(prompt_id, timeout=600)
    image_data = download_image(filename, subfolder)
    return image_data


# ═════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════

def main():
    print("=" * 64)
    print("🎯 LoRA Training Dataset Generator")
    print("   Indo-Asian Fashion Model — Phase 1")
    print("=" * 64)
    print(f"  Trigger word:  {TRIGGER_WORD}")
    print(f"  Face seed:     {FACE_SEED}")
    print(f"  Total images:  {len(TRAINING_SHOTS)}")
    print(f"  Resolution:    512x512 / 512x768 (fast + LoRA-friendly)")
    print(f"  Output:        {OUTPUT_BASE}/{TRIGGER_WORD}/")
    print(f"  Steps/CFG:     20 / 7.0 (fast generation)")
    print("=" * 64)
    print()
    print("  📋 Image breakdown:")
    print(f"     10 × close-up face (angles + lighting)")
    print(f"     10 × upper body (simple outfits)")
    print(f"     10 × full body (basic clothes, plain BG)")
    print()
    print("  After generation, review images and remove any bad ones.")
    print("  Then train LoRA with Kohya SS using the output folder.")
    print("=" * 64)

    # Health check
    print("\n⏳ Checking ComfyUI...", end=" ", flush=True)
    retries = 0
    while not check_health():
        retries += 1
        if retries > 30:
            print("\n❌ ComfyUI not responding.")
            sys.exit(1)
        print(".", end="", flush=True)
        time.sleep(5)
    print("✅ Ready!")

    # Clear any stuck queue from previous runs
    clear_queue()
    time.sleep(2)

    # Verify model
    print("🔍 Checking model...", end=" ", flush=True)
    try:
        obj_info = comfyui_get_json("/object_info/CheckpointLoaderSimple")
        available = obj_info.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
        if MODEL_NAME not in available:
            print(f"\n❌ Model '{MODEL_NAME}' not found!")
            print(f"   Available: {available}")
            sys.exit(1)
    except Exception as e:
        print(f"⚠️  Could not verify: {e}")
    print(f"✅ {MODEL_NAME}")

    # Create output folder
    out_dir = OUTPUT_BASE / TRIGGER_WORD
    out_dir.mkdir(parents=True, exist_ok=True)

    start_time = datetime.now()
    stats = {"success": 0, "fail": 0}
    manifest = {
        "type": "lora_training_dataset",
        "trigger_word": TRIGGER_WORD,
        "face_seed": FACE_SEED,
        "model": MODEL_NAME,
        "generated_at": start_time.isoformat(),
        "images": [],
    }

    print(f"\n🎨 Generating {len(TRAINING_SHOTS)} training images...\n")
    print("   ⚠️  First image may take 2-5 min (dynamic VRAM model loading)")
    print("   Subsequent images: ~10-20s each")
    print("   Total estimated: ~10-15 minutes\n")

    for i, shot in enumerate(TRAINING_SHOTS):
        name = shot["name"]
        prompt = shot["prompt"]
        caption = shot["caption"]

        # Full body shots use taller resolution
        if name.startswith("full_"):
            w, h = 512, 768
        else:
            w, h = 512, 512

        # Skip if already generated (allows restart)
        img_name = f"{i:02d}_{name}.png"
        img_path = out_dir / img_name
        if img_path.exists() and img_path.stat().st_size > 10000:
            print(f"  ⏭️  {i+1:2d}/{len(TRAINING_SHOTS)} {name:30s} — already exists, skipping")
            stats["success"] += 1
            # Still add to manifest
            caption_path = img_path.with_suffix(".txt")
            manifest["images"].append({
                "file": img_name,
                "caption": caption,
                "resolution": f"{w}x{h}",
                "shot_type": name.split("_")[0],
                "hash": "skipped",
            })
            continue

        try:
            img_data = generate_one(prompt, NEGATIVE_PROMPT, FACE_SEED, w, h)
            img_hash = hashlib.sha256(img_data).hexdigest()[:8]

            # Save image (numbered for Kohya)
            img_path.write_bytes(img_data)

            # Save caption file (Kohya reads .txt next to .png)
            caption_path = img_path.with_suffix(".txt")
            caption_path.write_text(caption)

            stats["success"] += 1
            manifest["images"].append({
                "file": img_name,
                "caption": caption,
                "resolution": f"{w}x{h}",
                "shot_type": name.split("_")[0],
                "hash": img_hash,
            })

            elapsed = (datetime.now() - start_time).total_seconds()
            eta_per = elapsed / (i + 1)
            eta_remain = eta_per * (len(TRAINING_SHOTS) - i - 1)
            print(f"  ✅ {i+1:2d}/{len(TRAINING_SHOTS)} {name:30s} ({w}x{h}) [ETA: {eta_remain:.0f}s]")

        except Exception as e:
            stats["fail"] += 1
            print(f"  ❌ {i+1:2d}/{len(TRAINING_SHOTS)} {name:30s} — {e}")

        time.sleep(0.3)

    # Save manifest
    manifest["completed_at"] = datetime.now().isoformat()
    manifest["stats"] = stats
    (OUTPUT_BASE / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # Summary
    duration = datetime.now() - start_time
    print("\n" + "=" * 64)
    print("📊 DATASET GENERATION COMPLETE")
    print("=" * 64)
    print(f"  Time:        {duration}")
    print(f"  Success:     {stats['success']}/{len(TRAINING_SHOTS)}")
    print(f"  Failed:      {stats['fail']}")
    print(f"  Images at:   {out_dir}/")
    print(f"  Captions:    .txt files next to each .png")
    print()
    print("=" * 64)
    print("📋 NEXT STEPS — LoRA Training with Kohya SS")
    print("=" * 64)
    print()
    print("  1. REVIEW: Open FileBrowser (port 8080)")
    print(f"     Browse {out_dir}/")
    print("     DELETE any images with bad faces/artifacts")
    print("     Keep 20-25 clean images minimum")
    print()
    print("  2. INSTALL KOHYA (in SSH terminal):")
    print("     cd /workspace")
    print("     git clone https://github.com/bmaltais/kohya_ss.git")
    print("     cd kohya_ss && python3 -m venv venv")
    print("     source venv/bin/activate")
    print("     pip install -r requirements.txt")
    print("     python kohya_gui.py --listen 0.0.0.0 --server_port 7860")
    print()
    print("  3. TRAIN LORA (in Kohya GUI at port 7860):")
    print(f"     • Training folder: {out_dir}")
    print(f"     • Trigger word: {TRIGGER_WORD}")
    print("     • Base model: juggernautXL_v9.safetensors")
    print("     • Network rank: 32")
    print("     • Network alpha: 16")
    print("     • Learning rate: 1e-4")
    print("     • Epochs: 10-15")
    print("     • Resolution: 768")
    print()
    print("  4. USE YOUR LORA:")
    print(f'     Prompt: "{TRIGGER_WORD}, wearing designer saree, fashion photoshoot, studio lighting"')
    print(f'     → Generates YOUR model in any outfit, any pose!')
    print("=" * 64)


if __name__ == "__main__":
    main()
