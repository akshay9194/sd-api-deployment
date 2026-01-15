#!/usr/bin/env python3
"""
Batch generate persona images for XinMate.
Generates ~100 images per persona with varied scenarios, poses, outfits.
"""

import httpx
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

# Configuration
SD_API_URL = os.getenv("SD_API_URL", "http://localhost:8000")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./persona_images")
IMAGES_PER_PERSONA = int(os.getenv("IMAGES_PER_PERSONA", "100"))

# =============================================================================
# PERSONA DEFINITIONS WITH BASE PROMPTS
# =============================================================================

PERSONAS = {
    # =========================================================================
    # FEMALE PERSONAS (For Male Users)
    # =========================================================================
    
    "scarlett": {
        "name": "Scarlett",
        "gender": "female",
        "base_prompt": "beautiful woman, 25 years old, athletic fit body, long wavy red hair, striking green eyes, full lips, high cheekbones, beauty mark on cheek, confident expression, fair skin",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, masculine features, old age",
        "style_keywords": ["seductive", "confident", "fitness", "glamorous"],
        "fashion_style": "sexy",
        "seed_base": 100000,
    },
    
    "emma": {
        "name": "Emma", 
        "gender": "female",
        "base_prompt": "beautiful asian woman, 22 years old, petite body, long straight black hair, cute round face, big brown eyes, dimples, soft features, adorable smile, fair skin, youthful",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, mature, harsh features, old age",
        "style_keywords": ["cute", "innocent", "anime-inspired", "soft"],
        "fashion_style": "cute",
        "seed_base": 200000,
    },
    
    "victoria": {
        "name": "Victoria",
        "gender": "female", 
        "base_prompt": "beautiful woman, 32 years old, tall elegant body, black hair in sleek bob, piercing blue eyes, sharp jawline, high cheekbones, commanding presence, sophisticated, powerful CEO aesthetic, fair skin, intense gaze",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, submissive pose, casual clothes",
        "style_keywords": ["dominant", "powerful", "corporate", "elegant"],
        "fashion_style": "elegant",
        "seed_base": 300000,
    },
    
    "lily": {
        "name": "Lily",
        "gender": "female",
        "base_prompt": "beautiful woman, 24 years old, natural beauty, wavy brown hair, warm hazel eyes, freckles, dimples, warm genuine smile, girl next door, medium skin tone, approachable",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, heavy makeup, overly glamorous",
        "style_keywords": ["natural", "warm", "cozy", "genuine"],
        "fashion_style": "casual",
        "seed_base": 400000,
    },
    
    "isabella": {
        "name": "Isabella",
        "gender": "female",
        "base_prompt": "beautiful latina woman, 26 years old, curvy dancer body, long curly dark brown hair, warm brown eyes, full lips, tan skin, passionate expression, Colombian beauty, sensual pose",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, pale skin, reserved expression",
        "style_keywords": ["passionate", "dancer", "Latin", "fiery"],
        "fashion_style": "sexy",
        "seed_base": 500000,
    },
    
    "maya": {
        "name": "Maya",
        "gender": "female",
        "base_prompt": "beautiful african american woman, 24 years old, curvy body, long black braided hair, warm brown eyes, bright smile, trendy fashion, friendly expression, dark skin",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, serious expression",
        "style_keywords": ["trendy", "friendly", "vibrant", "stylish"],
        "fashion_style": "trendy",
        "seed_base": 600000,
    },
    
    "kira": {
        "name": "Kira",
        "gender": "female",
        "base_prompt": "beautiful succubus woman, supernatural beauty, curvy body, very long black wavy hair, glowing purple eyes, small demon horns, demon tail, pale skin, seductive expression, dark fantasy aesthetic",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, angel, innocent, modest clothing",
        "style_keywords": ["demon", "fantasy", "supernatural", "seductive"],
        "fashion_style": "fantasy",
        "seed_base": 700000,
    },
    
    # =========================================================================
    # MALE PERSONAS (For Female Users)
    # =========================================================================
    
    "marcus": {
        "name": "Marcus",
        "gender": "male",
        "base_prompt": "handsome man, 28 years old, athletic muscular body, short black hair with fade, warm brown eyes, strong jawline, tan skin, protective confident expression, firefighter physique, broad shoulders",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, feminine features, weak appearance",
        "style_keywords": ["protective", "muscular", "firefighter", "strong"],
        "fashion_style": "casual",
        "seed_base": 800000,
    },
    
    "ryan": {
        "name": "Ryan",
        "gender": "male",
        "base_prompt": "handsome man, 27 years old, lean athletic body, messy dark brown hair, intense blue eyes, stubble, tattoos on arms, bad boy aesthetic, leather jacket, smirk, dangerous charm",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, clean cut, innocent looking, soft features",
        "style_keywords": ["bad boy", "musician", "tattoos", "edgy"],
        "fashion_style": "edgy",
        "seed_base": 900000,
    },
    
    "alexander": {
        "name": "Alexander",
        "gender": "male",
        "base_prompt": "handsome man, 31 years old, tall slim build, styled brown hair, warm green eyes, chiseled features, distinguished gentleman aesthetic, tailored suit, warm sophisticated smile, fair skin",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, casual clothes, rough appearance",
        "style_keywords": ["gentleman", "sophisticated", "romantic", "elegant"],
        "fashion_style": "elegant",
        "seed_base": 1000000,
    },
    
    "ethan": {
        "name": "Ethan",
        "gender": "male",
        "base_prompt": "handsome man, 25 years old, average build, messy dirty blonde hair, warm brown eyes, boyish charm, friendly warm smile, casual hoodie style, approachable, light skin",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, formal wear, serious expression",
        "style_keywords": ["friendly", "casual", "gamer", "boy next door"],
        "fashion_style": "casual",
        "seed_base": 1100000,
    },
    
    "damien": {
        "name": "Damien",
        "gender": "male",
        "base_prompt": "handsome man, 30 years old, tall athletic build, short black hair slicked back, intense grey eyes, sharp jawline, CEO aesthetic, expensive suit, commanding presence, intimidating but attractive, fair skin",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, casual clothes, soft expression, friendly",
        "style_keywords": ["dominant", "CEO", "powerful", "intense"],
        "fashion_style": "elegant",
        "seed_base": 1200000,
    },
    
    "lucian": {
        "name": "Lucian",
        "gender": "male",
        "base_prompt": "handsome vampire man, ageless ethereal beauty, tall slim build, long silver hair, red eyes, pale skin, sharp features, fangs, gothic elegant clothing, dark romantic aesthetic, dangerous allure",
        "negative_prompt": "ugly, deformed, bad anatomy, blurry, low quality, modern clothes, warm skin tone, friendly expression",
        "style_keywords": ["vampire", "gothic", "dark romance", "immortal"],
        "fashion_style": "fantasy",
        "seed_base": 1300000,
    },
}

# =============================================================================
# SCENARIO VARIATIONS (Apply to all personas)
# =============================================================================

SCENARIOS = {
    # Casual/Everyday
    "morning": {
        "prompt_add": "morning sunlight, cozy bedroom, just woke up, natural lighting",
        "weight": 10,
    },
    "coffee": {
        "prompt_add": "holding coffee cup, cafe setting, warm ambiance, relaxed",
        "weight": 8,
    },
    "casual_home": {
        "prompt_add": "at home, comfortable setting, relaxed pose, cozy",
        "weight": 10,
    },
    "selfie": {
        "prompt_add": "selfie angle, looking at camera, smartphone photo style, close up",
        "weight": 15,
    },
    
    # Romantic/Intimate
    "bedroom_romantic": {
        "prompt_add": "bedroom setting, romantic lighting, intimate atmosphere, soft lighting",
        "weight": 10,
    },
    "evening_dress": {
        "prompt_add": "elegant evening wear, dressed up, romantic dinner setting, candlelight",
        "weight": 8,
    },
    "flirty": {
        "prompt_add": "flirty expression, playful pose, suggestive but tasteful",
        "weight": 10,
    },
    
    # Lifestyle
    "workout": {
        "prompt_add": "gym clothes, fitness setting, active pose, athletic",
        "weight": 5,
    },
    "beach": {
        "prompt_add": "beach setting, summer vibes, swimwear, sunny day",
        "weight": 5,
    },
    "night_out": {
        "prompt_add": "night club lighting, party outfit, vibrant atmosphere",
        "weight": 5,
    },
    "relaxed_evening": {
        "prompt_add": "evening at home, comfortable clothes, soft lighting, relaxed",
        "weight": 8,
    },
    
    # Special/Themed
    "professional": {
        "prompt_add": "professional setting, office background, business attire",
        "weight": 3,
    },
    "date_night": {
        "prompt_add": "restaurant setting, date night outfit, romantic ambiance",
        "weight": 5,
    },
}

# =============================================================================
# OUTFIT VARIATIONS BY FASHION STYLE
# =============================================================================

OUTFITS = {
    "sexy": [
        "wearing tight dress",
        "wearing lingerie",
        "wearing crop top and shorts", 
        "wearing bodycon dress",
        "wearing silk robe",
        "wearing off-shoulder top",
        "wearing mini skirt",
        "wearing form-fitting dress",
    ],
    "cute": [
        "wearing oversized sweater",
        "wearing cute pajamas",
        "wearing sundress",
        "wearing casual dress",
        "wearing hoodie",
        "wearing school-style outfit",
        "wearing pastel colors",
        "wearing cute loungewear",
    ],
    "elegant": [
        "wearing tailored suit",
        "wearing elegant blouse",
        "wearing business dress",
        "wearing designer clothes",
        "wearing silk shirt",
        "wearing formal attire",
        "wearing high fashion",
        "wearing sophisticated outfit",
    ],
    "casual": [
        "wearing jeans and t-shirt",
        "wearing casual dress",
        "wearing comfortable clothes",
        "wearing hoodie and jeans",
        "wearing sweater",
        "wearing casual summer outfit",
        "wearing relaxed fit clothes",
        "wearing weekend casual",
    ],
    "trendy": [
        "wearing streetwear",
        "wearing trendy outfit",
        "wearing fashionable clothes",
        "wearing designer streetwear",
        "wearing modern fashion",
        "wearing stylish outfit",
        "wearing Instagram fashion",
        "wearing influencer style",
    ],
    "edgy": [
        "wearing leather jacket",
        "wearing band t-shirt",
        "wearing ripped jeans",
        "wearing all black outfit",
        "wearing punk style",
        "wearing rock aesthetic",
        "wearing dark clothes",
        "wearing biker style",
    ],
    "fantasy": [
        "wearing dark elegant robes",
        "wearing gothic outfit",
        "wearing fantasy costume",
        "wearing dark lingerie",
        "wearing mystical clothing",
        "wearing supernatural attire",
        "wearing dark romantic outfit",
        "wearing otherworldly fashion",
    ],
}

# =============================================================================
# EXPRESSION/MOOD VARIATIONS
# =============================================================================

EXPRESSIONS = [
    "smiling warmly",
    "seductive look",
    "playful expression",
    "confident smile",
    "soft gentle expression",
    "intense gaze",
    "laughing naturally",
    "flirty smile",
    "mysterious look",
    "loving expression",
]

# =============================================================================
# IMAGE GENERATION
# =============================================================================

async def generate_image(
    client: httpx.AsyncClient,
    persona_id: str,
    persona: dict,
    scenario: str,
    scenario_data: dict,
    outfit: str,
    expression: str,
    image_number: int,
) -> dict:
    """Generate a single image for a persona."""
    
    # Build the full prompt
    full_prompt = f"{persona['base_prompt']}, {outfit}, {expression}, {scenario_data['prompt_add']}"
    
    # Add style keywords
    style_str = ", ".join(persona["style_keywords"])
    full_prompt = f"{full_prompt}, {style_str}, high quality, professional photo, detailed"
    
    # Calculate seed for reproducibility (same seed = same face)
    seed = persona["seed_base"] + image_number
    
    payload = {
        "prompt": full_prompt,
        "negative_prompt": persona["negative_prompt"],
        "seed": seed,
        "steps": 25,
        "cfg_scale": 7.0,
        "width": 1024,
        "height": 1024,
        "persona_id": persona_id,
        "user_id": "batch_generator",
    }
    
    try:
        response = await client.post(f"{SD_API_URL}/generate", json=payload, timeout=120.0)
        result = response.json()
        
        if result.get("success"):
            return {
                "success": True,
                "persona_id": persona_id,
                "image_number": image_number,
                "scenario": scenario,
                "seed": seed,
                "image_url": result.get("image_url"),
                "image_hash": result.get("image_hash"),
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


def build_image_variations(persona_id: str, persona: dict, count: int) -> list:
    """Build list of image variations to generate."""
    variations = []
    
    fashion_style = persona["fashion_style"]
    outfits = OUTFITS.get(fashion_style, OUTFITS["casual"])
    
    # Calculate weighted scenario distribution
    total_weight = sum(s["weight"] for s in SCENARIOS.values())
    
    image_num = 0
    for scenario_name, scenario_data in SCENARIOS.items():
        # How many images for this scenario based on weight
        scenario_count = int((scenario_data["weight"] / total_weight) * count)
        
        for i in range(scenario_count):
            if image_num >= count:
                break
                
            outfit = outfits[image_num % len(outfits)]
            expression = EXPRESSIONS[image_num % len(EXPRESSIONS)]
            
            variations.append({
                "persona_id": persona_id,
                "persona": persona,
                "scenario": scenario_name,
                "scenario_data": scenario_data,
                "outfit": outfit,
                "expression": expression,
                "image_number": image_num,
            })
            image_num += 1
    
    # Fill remaining with selfies (most common)
    while image_num < count:
        variations.append({
            "persona_id": persona_id,
            "persona": persona,
            "scenario": "selfie",
            "scenario_data": SCENARIOS["selfie"],
            "outfit": outfits[image_num % len(outfits)],
            "expression": EXPRESSIONS[image_num % len(EXPRESSIONS)],
            "image_number": image_num,
        })
        image_num += 1
    
    return variations


async def generate_persona_images(persona_id: str, persona: dict, count: int):
    """Generate all images for a single persona."""
    print(f"\n🎨 Generating {count} images for {persona['name']}...")
    
    variations = build_image_variations(persona_id, persona, count)
    
    results = []
    async with httpx.AsyncClient() as client:
        for i, variation in enumerate(variations):
            result = await generate_image(
                client,
                variation["persona_id"],
                variation["persona"],
                variation["scenario"],
                variation["scenario_data"],
                variation["outfit"],
                variation["expression"],
                variation["image_number"],
            )
            results.append(result)
            
            status = "✅" if result["success"] else "❌"
            print(f"  {status} {persona['name']} #{i+1}/{count} - {variation['scenario']}")
            
            # Small delay to avoid overwhelming the server
            await asyncio.sleep(0.5)
    
    success_count = sum(1 for r in results if r["success"])
    print(f"  📊 {persona['name']}: {success_count}/{count} successful")
    
    return results


async def main():
    """Main entry point."""
    print("=" * 60)
    print("🖼️  XinMate Persona Image Generator")
    print("=" * 60)
    print(f"API URL: {SD_API_URL}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Images per persona: {IMAGES_PER_PERSONA}")
    print(f"Total personas: {len(PERSONAS)}")
    print(f"Total images to generate: {len(PERSONAS) * IMAGES_PER_PERSONA}")
    print("=" * 60)
    
    # Check API health
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{SD_API_URL}/health")
            health = response.json()
            if health.get("comfyui") != "ok":
                print("❌ ComfyUI not ready. Please wait and try again.")
                return
            print(f"✅ API healthy: {health}")
        except Exception as e:
            print(f"❌ Cannot connect to API: {e}")
            return
    
    # Create output directory
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    
    # Generate images for each persona
    all_results = {}
    start_time = datetime.now()
    
    for persona_id, persona in PERSONAS.items():
        results = await generate_persona_images(persona_id, persona, IMAGES_PER_PERSONA)
        all_results[persona_id] = results
    
    # Save manifest
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "api_url": SD_API_URL,
        "images_per_persona": IMAGES_PER_PERSONA,
        "results": all_results,
    }
    
    manifest_path = Path(OUTPUT_DIR) / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    # Summary
    end_time = datetime.now()
    duration = end_time - start_time
    
    total_success = sum(
        sum(1 for r in results if r["success"]) 
        for results in all_results.values()
    )
    total_images = len(PERSONAS) * IMAGES_PER_PERSONA
    
    print("\n" + "=" * 60)
    print("📊 GENERATION COMPLETE")
    print("=" * 60)
    print(f"Total time: {duration}")
    print(f"Success rate: {total_success}/{total_images} ({100*total_success/total_images:.1f}%)")
    print(f"Manifest saved: {manifest_path}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
