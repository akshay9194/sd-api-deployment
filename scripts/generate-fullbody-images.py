#!/usr/bin/env python3
"""
Generate FULL BODY persona images for XinMate.
Uses tall aspect ratio (832x1216) with full-body-specific prompts and scenarios.

Usage:
  export SD_API_URL="https://YOUR-POD-ID-8000.proxy.runpod.net"
  export IMAGES_PER_PERSONA=10   # default 50
  python scripts/generate-fullbody-images.py

  # Single persona only:
  export PERSONA=scarlett
  python scripts/generate-fullbody-images.py
"""

import httpx
import asyncio
import json
import os
import random
from datetime import datetime
from pathlib import Path

# Configuration
SD_API_URL = os.getenv("SD_API_URL", "http://localhost:8000")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./persona_images/fullbody")
IMAGES_PER_PERSONA = int(os.getenv("IMAGES_PER_PERSONA", "50"))
SINGLE_PERSONA = os.getenv("PERSONA", "")  # empty = all personas

# Full body image dimensions (SDXL-native tall aspect ratio)
IMG_WIDTH = 832
IMG_HEIGHT = 1216

# =============================================================================
# FULL BODY FRAMING — appended to EVERY prompt
# =============================================================================
FULLBODY_CORE = (
    "full body shot, head to toe, full length photo, "
    "showing feet, standing pose, wide framing, "
    "professional photography, studio quality"
)

FULLBODY_NEGATIVE_EXTRA = (
    "cropped, close up, portrait crop, face only, headshot, "
    "cut off legs, cut off feet, missing legs, missing feet, "
    "floating body, bad proportions, short body"
)

# =============================================================================
# PERSONA DEFINITIONS (same faces, full body base prompts)
# =============================================================================

PERSONAS = {
    # ─── FEMALE ──────────────────────────────────────────────────
    "scarlett": {
        "name": "Scarlett",
        "gender": "female",
        "base_prompt": "beautiful woman, 25 years old, athletic fit body, long legs, long wavy red hair, striking green eyes, full lips, high cheekbones, beauty mark on cheek, confident expression, fair skin",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, masculine features, old age",
        "fashion_style": "sexy",
        "seed_base": 100000,
    },
    "emma": {
        "name": "Emma",
        "gender": "female",
        "base_prompt": "beautiful asian woman, 22 years old, petite slim body, long straight black hair, cute round face, big brown eyes, dimples, soft features, adorable smile, fair skin, youthful",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, mature, harsh features, old age",
        "fashion_style": "cute",
        "seed_base": 200000,
    },
    "victoria": {
        "name": "Victoria",
        "gender": "female",
        "base_prompt": "beautiful woman, 32 years old, tall elegant body, long legs, black hair in sleek bob, piercing blue eyes, sharp jawline, high cheekbones, commanding presence, sophisticated, powerful CEO aesthetic, fair skin, intense gaze",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, submissive pose, casual clothes",
        "fashion_style": "elegant",
        "seed_base": 300000,
    },
    "lily": {
        "name": "Lily",
        "gender": "female",
        "base_prompt": "beautiful woman, 24 years old, natural beauty, slim body, wavy brown hair, warm hazel eyes, freckles, dimples, warm genuine smile, girl next door, medium skin tone, approachable",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, heavy makeup, overly glamorous",
        "fashion_style": "casual",
        "seed_base": 400000,
    },
    "isabella": {
        "name": "Isabella",
        "gender": "female",
        "base_prompt": "beautiful latina woman, 26 years old, curvy dancer body, long legs, long curly dark brown hair, warm brown eyes, full lips, tan skin, passionate expression, Colombian beauty",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, pale skin, reserved expression",
        "fashion_style": "sexy",
        "seed_base": 500000,
    },
    "maya": {
        "name": "Maya",
        "gender": "female",
        "base_prompt": "beautiful african american woman, 24 years old, curvy body, long legs, long black braided hair, warm brown eyes, bright smile, trendy fashion, friendly expression, dark skin",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, serious expression",
        "fashion_style": "trendy",
        "seed_base": 600000,
    },
    "kira": {
        "name": "Kira",
        "gender": "female",
        "base_prompt": "beautiful succubus woman, supernatural beauty, curvy body, long legs, very long black wavy hair, glowing purple eyes, small demon horns, demon tail, pale skin, seductive expression, dark fantasy aesthetic",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, angel, innocent, modest clothing",
        "fashion_style": "fantasy",
        "seed_base": 700000,
    },

    # ─── MALE ────────────────────────────────────────────────────
    "marcus": {
        "name": "Marcus",
        "gender": "male",
        "base_prompt": "handsome man, 28 years old, athletic muscular body, tall, short black hair with fade, warm brown eyes, strong jawline, tan skin, protective confident expression, firefighter physique, broad shoulders",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, feminine features, weak appearance",
        "fashion_style": "casual",
        "seed_base": 800000,
    },
    "ryan": {
        "name": "Ryan",
        "gender": "male",
        "base_prompt": "handsome man, 27 years old, lean athletic body, tall, messy dark brown hair, intense blue eyes, stubble, tattoos on arms, bad boy aesthetic, smirk, dangerous charm",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, clean cut, innocent looking, soft features",
        "fashion_style": "edgy",
        "seed_base": 900000,
    },
    "alexander": {
        "name": "Alexander",
        "gender": "male",
        "base_prompt": "handsome man, 31 years old, tall slim build, styled brown hair, warm green eyes, chiseled features, distinguished gentleman aesthetic, warm sophisticated smile, fair skin",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, casual clothes, rough appearance",
        "fashion_style": "elegant",
        "seed_base": 1000000,
    },
    "ethan": {
        "name": "Ethan",
        "gender": "male",
        "base_prompt": "handsome man, 25 years old, average build, messy dirty blonde hair, warm brown eyes, boyish charm, friendly warm smile, approachable, light skin",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, formal wear, serious expression",
        "fashion_style": "casual",
        "seed_base": 1100000,
    },
    "damien": {
        "name": "Damien",
        "gender": "male",
        "base_prompt": "handsome man, 30 years old, tall athletic build, short black hair slicked back, intense grey eyes, sharp jawline, CEO aesthetic, commanding presence, intimidating but attractive, fair skin",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, casual clothes, soft expression, friendly",
        "fashion_style": "elegant",
        "seed_base": 1200000,
    },
    "lucian": {
        "name": "Lucian",
        "gender": "male",
        "base_prompt": "handsome vampire man, ageless ethereal beauty, tall slim build, long silver hair, red eyes, pale skin, sharp features, fangs, dark romantic aesthetic, dangerous allure",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, modern clothes, warm skin tone, friendly expression",
        "fashion_style": "fantasy",
        "seed_base": 1300000,
    },
}

# =============================================================================
# FULL BODY SCENARIOS (different from the portrait selfie ones)
# =============================================================================

SCENARIOS = {
    "standing_casual": {
        "prompt_add": "standing naturally, relaxed pose, urban street background, natural daylight",
        "weight": 12,
    },
    "fashion_pose": {
        "prompt_add": "fashion model pose, editorial photography, clean background, studio lighting",
        "weight": 10,
    },
    "walking": {
        "prompt_add": "walking towards camera, city sidewalk, confident stride, outdoor",
        "weight": 8,
    },
    "leaning_wall": {
        "prompt_add": "leaning against wall, relaxed cool pose, urban background, natural lighting",
        "weight": 8,
    },
    "mirror_selfie": {
        "prompt_add": "full body mirror selfie, bedroom mirror, smartphone in hand, casual pose",
        "weight": 10,
    },
    "doorway": {
        "prompt_add": "standing in doorway, leaning on door frame, home setting, warm lighting",
        "weight": 6,
    },
    "outdoor_nature": {
        "prompt_add": "standing outdoors, park or garden, natural greenery, golden hour lighting",
        "weight": 6,
    },
    "beach_full": {
        "prompt_add": "standing on beach, ocean background, sunny day, sand under feet",
        "weight": 5,
    },
    "gym_full": {
        "prompt_add": "standing in gym, fitness setting, athletic pose, gym equipment background",
        "weight": 5,
    },
    "date_arrival": {
        "prompt_add": "standing at restaurant entrance, evening lighting, dressed up, ready for date",
        "weight": 6,
    },
    "staircase": {
        "prompt_add": "standing on stairs, elegant staircase, looking at camera, dramatic angle",
        "weight": 4,
    },
    "balcony": {
        "prompt_add": "standing on balcony, city skyline background, evening light, railing visible",
        "weight": 5,
    },
    "bedroom_standing": {
        "prompt_add": "standing in bedroom, morning light through window, intimate setting, soft lighting",
        "weight": 8,
    },
    "red_carpet": {
        "prompt_add": "red carpet pose, elegant background, paparazzi lighting, glamorous",
        "weight": 3,
    },
    "cafe_standing": {
        "prompt_add": "standing outside cafe, holding coffee, street scene, casual vibe",
        "weight": 4,
    },
}

# =============================================================================
# FULL BODY OUTFITS (head-to-toe visible)
# =============================================================================

OUTFITS = {
    "sexy": [
        "wearing tight mini dress and high heels",
        "wearing crop top, mini skirt, and strappy heels",
        "wearing bodycon dress and stilettos",
        "wearing lingerie and silk robe, bare feet",
        "wearing bikini and sarong wrap",
        "wearing off-shoulder dress and heels",
        "wearing tight jeans, heels, and corset top",
        "wearing cocktail dress and pumps",
    ],
    "cute": [
        "wearing oversized sweater, knee socks, and sneakers",
        "wearing sundress and white sneakers",
        "wearing pleated skirt, cardigan, and loafers",
        "wearing cute pajamas and fuzzy slippers",
        "wearing pastel dress and ankle boots",
        "wearing denim overalls and t-shirt",
        "wearing hoodie dress and sneakers",
        "wearing floral dress and sandals",
    ],
    "elegant": [
        "wearing tailored suit and oxford shoes",
        "wearing floor-length gown and heels",
        "wearing business dress and pumps",
        "wearing silk blouse, tailored trousers, and loafers",
        "wearing designer dress and stilettos",
        "wearing tuxedo and dress shoes",
        "wearing pencil skirt, blazer, and heels",
        "wearing three-piece suit and polished shoes",
    ],
    "casual": [
        "wearing jeans, t-shirt, and sneakers",
        "wearing casual dress and sandals",
        "wearing joggers, hoodie, and running shoes",
        "wearing shorts, tank top, and flip flops",
        "wearing chinos, polo shirt, and loafers",
        "wearing sweater, jeans, and boots",
        "wearing cargo pants, graphic tee, and sneakers",
        "wearing denim jacket, jeans, and boots",
    ],
    "trendy": [
        "wearing streetwear outfit and chunky sneakers",
        "wearing designer tracksuit and trainers",
        "wearing high-waisted pants, crop top, and platform shoes",
        "wearing oversized jacket, bike shorts, and sneakers",
        "wearing trendy co-ord set and boots",
        "wearing wide-leg pants, fitted top, and sneakers",
        "wearing leather pants, designer top, and boots",
        "wearing modern jumpsuit and heels",
    ],
    "edgy": [
        "wearing leather jacket, ripped jeans, and combat boots",
        "wearing all black outfit and heavy boots",
        "wearing band tee, leather pants, and boots",
        "wearing biker jacket, dark jeans, and chunky boots",
        "wearing punk style outfit and platform boots",
        "wearing distressed denim and motorcycle boots",
        "wearing dark hoodie, cargo pants, and combat boots",
        "wearing chain accessories, black jeans, and boots",
    ],
    "fantasy": [
        "wearing dark elegant robes and gothic boots",
        "wearing fantasy armor and leather boots",
        "wearing gothic gown and platform boots",
        "wearing dark corset dress and thigh-high boots",
        "wearing mystical cloak and ornate boots",
        "wearing dark leather outfit and combat boots",
        "wearing supernatural elegant suit and dress shoes",
        "wearing dark romantic outfit with cape",
    ],
}

# =============================================================================
# STANDING POSES (vary body language)
# =============================================================================

POSES = [
    "standing straight, hands at sides",
    "standing with hand on hip",
    "standing with arms crossed",
    "standing with hands in pockets",
    "standing leaning slightly forward",
    "standing with one leg bent",
    "standing confident power pose",
    "standing relaxed natural pose",
    "standing with hand touching hair",
    "standing looking over shoulder",
]

# =============================================================================
# IMAGE GENERATION
# =============================================================================

async def generate_image(
    client: httpx.AsyncClient,
    persona_id: str,
    persona: dict,
    scenario_name: str,
    scenario_data: dict,
    outfit: str,
    pose: str,
    image_number: int,
) -> dict:
    """Generate a single full body image."""

    # Build prompt: base face + full body core + outfit + pose + scenario
    full_prompt = (
        f"{persona['base_prompt']}, "
        f"{FULLBODY_CORE}, "
        f"{outfit}, "
        f"{pose}, "
        f"{scenario_data['prompt_add']}, "
        f"high quality, professional photo, detailed, sharp focus"
    )

    # Combine negatives
    negative = f"{persona['negative_prompt']}, {FULLBODY_NEGATIVE_EXTRA}"

    # Deterministic seed per persona + image number
    seed = persona["seed_base"] + 5000 + image_number  # offset from portrait seeds

    payload = {
        "prompt": full_prompt,
        "negative_prompt": negative,
        "seed": seed,
        "steps": 32,
        "cfg_scale": 6.0,
        "width": IMG_WIDTH,
        "height": IMG_HEIGHT,
        "persona_id": persona_id,
        "user_id": "fullbody_generator",
    }

    try:
        response = await client.post(
            f"{SD_API_URL}/generate", json=payload, timeout=180.0
        )
        result = response.json()

        if result.get("success"):
            return {
                "success": True,
                "persona_id": persona_id,
                "image_number": image_number,
                "scenario": scenario_name,
                "seed": seed,
                "image_url": result.get("image_url"),
                "image_hash": result.get("image_hash"),
                "prompt": full_prompt,
            }
        else:
            return {
                "success": False,
                "persona_id": persona_id,
                "image_number": image_number,
                "error": result.get("error", "Unknown error"),
            }
    except Exception as e:
        return {
            "success": False,
            "persona_id": persona_id,
            "image_number": image_number,
            "error": str(e),
        }


def build_variations(persona_id: str, persona: dict, count: int) -> list:
    """Build list of full body image variations."""
    variations = []
    fashion_style = persona["fashion_style"]
    outfits = OUTFITS.get(fashion_style, OUTFITS["casual"])

    # Weighted scenario distribution
    total_weight = sum(s["weight"] for s in SCENARIOS.values())

    image_num = 0
    for scenario_name, scenario_data in SCENARIOS.items():
        scenario_count = max(1, int((scenario_data["weight"] / total_weight) * count))

        for i in range(scenario_count):
            if image_num >= count:
                break

            outfit = outfits[image_num % len(outfits)]
            pose = POSES[image_num % len(POSES)]

            variations.append({
                "persona_id": persona_id,
                "persona": persona,
                "scenario": scenario_name,
                "scenario_data": scenario_data,
                "outfit": outfit,
                "pose": pose,
                "image_number": image_num,
            })
            image_num += 1

    # Fill remaining with mirror_selfie + fashion_pose mix
    fill_scenarios = ["mirror_selfie", "fashion_pose", "standing_casual"]
    while image_num < count:
        sc = fill_scenarios[image_num % len(fill_scenarios)]
        variations.append({
            "persona_id": persona_id,
            "persona": persona,
            "scenario": sc,
            "scenario_data": SCENARIOS[sc],
            "outfit": outfits[image_num % len(outfits)],
            "pose": POSES[image_num % len(POSES)],
            "image_number": image_num,
        })
        image_num += 1

    return variations


async def generate_persona_images(persona_id: str, persona: dict, count: int):
    """Generate all full body images for one persona."""
    print(f"\n🧍 Generating {count} full body images for {persona['name']}...")

    variations = build_variations(persona_id, persona, count)
    results = []

    async with httpx.AsyncClient() as client:
        for i, v in enumerate(variations):
            result = await generate_image(
                client,
                v["persona_id"],
                v["persona"],
                v["scenario"],
                v["scenario_data"],
                v["outfit"],
                v["pose"],
                v["image_number"],
            )
            results.append(result)

            status = "✅" if result["success"] else "❌"
            print(f"  {status} {persona['name']} #{i+1}/{count} - {v['scenario']} ({v['outfit'][:30]}...)")

            await asyncio.sleep(0.5)

    success_count = sum(1 for r in results if r["success"])
    print(f"  📊 {persona['name']}: {success_count}/{count} successful")
    return results


async def main():
    """Main entry point."""
    print("=" * 60)
    print("🧍 XinMate FULL BODY Image Generator")
    print("=" * 60)
    print(f"API URL:    {SD_API_URL}")
    print(f"Output:     {OUTPUT_DIR}")
    print(f"Resolution: {IMG_WIDTH}x{IMG_HEIGHT} (tall portrait)")
    print(f"Per persona: {IMAGES_PER_PERSONA}")

    # Filter personas
    if SINGLE_PERSONA:
        if SINGLE_PERSONA not in PERSONAS:
            print(f"❌ Unknown persona: {SINGLE_PERSONA}")
            print(f"   Available: {', '.join(PERSONAS.keys())}")
            return
        personas_to_run = {SINGLE_PERSONA: PERSONAS[SINGLE_PERSONA]}
    else:
        personas_to_run = PERSONAS

    total_images = len(personas_to_run) * IMAGES_PER_PERSONA
    print(f"Personas:   {len(personas_to_run)} ({', '.join(personas_to_run.keys())})")
    print(f"Total:      {total_images} images")
    print("=" * 60)

    # Health check
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{SD_API_URL}/health")
            health = response.json()
            if health.get("comfyui") != "ok":
                print("❌ ComfyUI not ready. Wait and retry.")
                return
            print(f"✅ API healthy: {health}")
        except Exception as e:
            print(f"❌ Cannot connect to API: {e}")
            return

    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    all_results = {}
    start_time = datetime.now()

    for persona_id, persona in personas_to_run.items():
        results = await generate_persona_images(persona_id, persona, IMAGES_PER_PERSONA)
        all_results[persona_id] = results

    # Save manifest
    manifest = {
        "type": "fullbody",
        "generated_at": datetime.now().isoformat(),
        "api_url": SD_API_URL,
        "resolution": f"{IMG_WIDTH}x{IMG_HEIGHT}",
        "images_per_persona": IMAGES_PER_PERSONA,
        "results": all_results,
    }

    manifest_path = Path(OUTPUT_DIR) / "fullbody-manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # Summary
    duration = datetime.now() - start_time
    total_success = sum(
        sum(1 for r in results if r["success"])
        for results in all_results.values()
    )

    print("\n" + "=" * 60)
    print("📊 FULL BODY GENERATION COMPLETE")
    print("=" * 60)
    print(f"Time:         {duration}")
    print(f"Success rate: {total_success}/{total_images} ({100*total_success/total_images:.1f}%)")
    print(f"Manifest:     {manifest_path}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
