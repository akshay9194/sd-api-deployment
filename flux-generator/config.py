"""
XinMate — Persona Image Generation Config
==========================================
10 personas (6F + 4M) × 500 images each = 5,000 total images
5 categories × 100 images per category per persona
Indian market-first character design.
"""

from dataclasses import dataclass, field
from typing import List, Dict

# ═══════════════════════════════════════════════════════════════
# MODEL CONFIG
# ═══════════════════════════════════════════════════════════════

BASE_MODEL = "black-forest-labs/FLUX.1-dev"
LORA_REPO = "Heartsync/Flux-NSFW-uncensored"
LORA_WEIGHT_NAME = "lora.safetensors"
LORA_ADAPTER_NAME = "uncensored"

INFERENCE_STEPS = 20
GUIDANCE_SCALE = 3.5
IMAGE_WIDTH = 1024
IMAGE_HEIGHT = 1024
TORCH_DTYPE = "bfloat16"  # FLUX was trained in bfloat16, produces sharper results

# ═══════════════════════════════════════════════════════════════
# AZURE BLOB CONFIG
# ═══════════════════════════════════════════════════════════════

AZURE_STORAGE_ACCOUNT = "sdxl"
AZURE_CONTAINER_NAME = "personas"
# AZURE_STORAGE_KEY loaded from env

# ═══════════════════════════════════════════════════════════════
# GENERATION CONFIG
# ═══════════════════════════════════════════════════════════════

IMAGES_PER_PERSONA = 500
IMAGES_PER_CATEGORY = 100
OUTPUT_DIR = "/workspace/generated_images"
MANIFEST_DIR = "/workspace/manifests"


# ═══════════════════════════════════════════════════════════════
# CATEGORIES — 5 categories × 100 images each = 500 per persona
# ═══════════════════════════════════════════════════════════════

CATEGORIES = {
    "selfie": {
        "count": 100,
        "db_category": "SELFIE",
        "prompt_suffix": "selfie, looking at camera, phone angle",
        "dimensions": (1024, 1024),
    },
    "portrait": {
        "count": 100,
        "db_category": "PORTRAIT",
        "prompt_suffix": "portrait, upper body, soft lighting",
        "dimensions": (1024, 1024),
    },
    "full_body": {
        "count": 100,
        "db_category": "FULL_BODY",
        "prompt_suffix": "full body shot, head to toe, standing",
        "dimensions": (832, 1216),
    },
    "lifestyle": {
        "count": 100,
        "db_category": "CANDID",
        "prompt_suffix": "candid, natural moment",
        "dimensions": (1024, 1024),
    },
    "fashion": {
        "count": 100,
        "db_category": "MOOD",
        "prompt_suffix": "fashion editorial, stylish",
        "dimensions": (1024, 1024),
    },
}


# ═══════════════════════════════════════════════════════════════
# GLOBAL NEGATIVE PROMPT
# ═══════════════════════════════════════════════════════════════

NEGATIVE_PROMPT = (
    "text, watermark, signature, logo, username, "
    "cartoon, anime, illustration, painting, drawing, cgi, 3d render, "
    "celebrity, famous person, real person, known face, "
    "distorted face, extra fingers, deformed eyes, bad anatomy, bad hands, "
    "blurry, low quality, jpeg artifacts, pixelated, grainy, "
    "cropped, out of frame, duplicate, clone"
)

# Extra negative for full-body to avoid crops
FULL_BODY_NEGATIVE_EXTRA = (
    "cropped, close up, portrait crop, face only, headshot, "
    "cut off legs, cut off feet, cut off arms"
)


# ═══════════════════════════════════════════════════════════════
# MOODS — cycled through for variation
# ═══════════════════════════════════════════════════════════════

MOODS = [
    "smiling warmly",
    "confident expression",
    "playful expression",
    "soft gentle expression",
    "laughing naturally",
    "thoughtful look",
    "relaxed happy expression",
    "cheerful bright smile",
    "calm serene expression",
    "excited joyful expression",
]

# ═══════════════════════════════════════════════════════════════
# SCENARIOS — per category, cycled for variation
# ═══════════════════════════════════════════════════════════════

SELFIE_SCENARIOS = [
    "mirror selfie, bedroom, ring light",
    "outdoor selfie, garden, golden hour",
    "car selfie, natural light",
    "getting ready, mirror selfie",
    "rooftop selfie, city evening",
    "cafe selfie, holding chai",
    "gym selfie, post-workout",
    "hotel room selfie, travel",
    "sunset selfie, balcony",
    "morning selfie, just woke up",
    "festival selfie, fairy lights",
    "poolside selfie, sunglasses",
]

PORTRAIT_SCENARIOS = [
    "studio portrait, soft backdrop",
    "window light portrait, dreamy",
    "outdoor portrait, green garden",
    "golden hour portrait, warm tones",
    "urban portrait, city background",
    "indoor portrait, cozy room",
    "rain portrait, window drops",
    "terrace portrait, evening sky",
    "candlelit portrait, warm glow",
    "morning light portrait, sunrise",
    "festive portrait, diwali lights",
    "bookshelf background portrait",
]

FULL_BODY_SCENARIOS = [
    "city street, urban fashion",
    "Goa beach, casual boho",
    "studio, white background",
    "park, trees and sunlight",
    "vintage wall, old city",
    "ornate doorway, haveli",
    "marble steps, palace",
    "rooftop, city skyline",
    "garden walkway, flowers",
    "hotel lobby, elegant",
    "train platform, travel",
    "marketplace, colorful",
]

LIFESTYLE_SCENARIOS = [
    "cafe, holding chai cup",
    "cooking in kitchen, home",
    "reading book, cozy sofa",
    "working on laptop, office",
    "shopping, colorful bags",
    "restaurant, candle dinner",
    "yoga pose, morning terrace",
    "walking in park, morning",
    "balcony garden, plants",
    "painting, art corner",
    "temple, peaceful setting",
    "scooter ride, city",
]

FASHION_SCENARIOS = [
    "Indo-western fusion, urban",
    "lehenga, wedding reception",
    "athletic wear, gym",
    "oversized hoodie, rainy window",
    "summer dress, outdoor garden",
    "formal wear, glass office",
    "bohemian style, Goa beach",
    "denim jacket, rooftop party",
    "festive wear, Diwali",
    "designer outfit, luxury hotel",
    "casual streetwear, sneakers",
    "elegant saree, occasion",
]

CATEGORY_SCENARIOS = {
    "selfie": SELFIE_SCENARIOS,
    "portrait": PORTRAIT_SCENARIOS,
    "full_body": FULL_BODY_SCENARIOS,
    "lifestyle": LIFESTYLE_SCENARIOS,
    "fashion": FASHION_SCENARIOS,
}


# ═══════════════════════════════════════════════════════════════
# PERSONA DEFINITIONS — 10 characters (6F + 4M)
# Indian market-first. Names, looks, and archetypes chosen for
# maximum engagement & retention with 18-35 Indian users.
# ═══════════════════════════════════════════════════════════════

@dataclass
class PersonaConfig:
    name: str
    gender: str
    age: int
    archetype: str          # one-line hook for marketing
    base_prompt: str
    seed_base: int
    tags: List[str] = field(default_factory=list)


PHOTO_QUALITY = "raw photo, DSLR"

PERSONAS: Dict[str, PersonaConfig] = {

    # ── FEMALE PERSONAS (6) ──────────────────────────────────

    # 1. Ananya — The Desi Girl Next Door (biggest mass appeal)
    "ananya": PersonaConfig(
        name="Ananya",
        gender="female",
        age=22,
        archetype="Cute desi girl next door — your college crush who texts back",
        base_prompt=(
            "beautiful young Indian woman, 22, petite, "
            "long straight black hair, big brown eyes, dimples, "
            "warm brown skin, nose pin, "
            f"{PHOTO_QUALITY}"
        ),
        seed_base=100000,
        tags=["desi", "cute", "college", "girl-next-door"],
    ),

    # 2. Riya — The Bold City Girl (metro audience, high spend)
    "riya": PersonaConfig(
        name="Riya",
        gender="female",
        age=26,
        archetype="Bold Mumbai girl — confident, stylish, knows what she wants",
        base_prompt=(
            "stunning Indian woman, 26, tall slim, "
            "wavy dark brown hair, sharp brown eyes, "
            "fair skin, red lipstick, glamorous, "
            f"{PHOTO_QUALITY}"
        ),
        seed_base=200000,
        tags=["bold", "city", "glamorous", "confident"],
    ),

    # 3. Meera — The South Indian Beauty (huge underserved segment)
    "meera": PersonaConfig(
        name="Meera",
        gender="female",
        age=24,
        archetype="Traditional South Indian beauty — graceful, warm, classically gorgeous",
        base_prompt=(
            "beautiful South Indian woman, 24, curvy, "
            "long thick black hair, dark brown eyes with kajal, "
            "golden brown skin, gold jewelry, "
            f"{PHOTO_QUALITY}"
        ),
        seed_base=300000,
        tags=["south-indian", "traditional", "graceful", "curvy"],
    ),

    # 4. Zara — The Edgy Influencer (Gen-Z hook, Instagram aesthetic)
    "zara": PersonaConfig(
        name="Zara",
        gender="female",
        age=21,
        archetype="Instagram baddie — edgy, trendy, lives for the aesthetic",
        base_prompt=(
            "gorgeous young Indian woman, 21, slim toned, "
            "short black hair with streaks, intense dark eyes, "
            "light brown skin, ear piercings, bold eyeliner, "
            f"{PHOTO_QUALITY}"
        ),
        seed_base=400000,
        tags=["edgy", "genz", "influencer", "urban"],
    ),

    # 5. Priya — The Sophisticated Professional (premium segment)
    "priya": PersonaConfig(
        name="Priya",
        gender="female",
        age=29,
        archetype="Corporate queen — smart, sophisticated, intimidatingly attractive",
        base_prompt=(
            "beautiful Indian woman, 29, tall elegant, "
            "sleek black hair, sharp brown eyes, fair skin, "
            "pearl earrings, sophisticated, "
            f"{PHOTO_QUALITY}"
        ),
        seed_base=500000,
        tags=["professional", "sophisticated", "premium", "elegant"],
    ),

    # 6. Aisha — The Exotic Mixed Beauty (aspirational, unique look)
    "aisha": PersonaConfig(
        name="Aisha",
        gender="female",
        age=25,
        archetype="Indo-Middle Eastern beauty — mysterious, exotic, unforgettable face",
        base_prompt=(
            "stunning mixed heritage woman, 25, slim hourglass, "
            "long dark wavy hair, light brown-green eyes, "
            "olive tan skin, beauty mark, alluring, "
            f"{PHOTO_QUALITY}"
        ),
        seed_base=600000,
        tags=["exotic", "mixed", "mysterious", "alluring"],
    ),

    # ── MALE PERSONAS (4) ────────────────────────────────────

    # 7. Arjun — The Protective Alpha (biggest female draw in India)
    "arjun": PersonaConfig(
        name="Arjun",
        gender="male",
        age=28,
        archetype="The protective one — strong, reliable, makes you feel safe",
        base_prompt=(
            "handsome Indian man, 28, tall athletic muscular, "
            "short black hair fade, strong jawline, stubble, "
            "brown skin, broad shoulders, "
            f"{PHOTO_QUALITY}"
        ),
        seed_base=700000,
        tags=["protective", "athletic", "alpha", "reliable"],
    ),

    # 8. Kabir — The Brooding Artist (emotional hook, high retention)
    "kabir": PersonaConfig(
        name="Kabir",
        gender="male",
        age=26,
        archetype="Soulful musician — intense eyes, poetry in his voice, dangerous charm",
        base_prompt=(
            "handsome Indian man, 26, lean athletic, "
            "messy wavy black hair, intense brown eyes, "
            "stubble, medium brown skin, forearm tattoo, "
            f"{PHOTO_QUALITY}"
        ),
        seed_base=800000,
        tags=["artist", "brooding", "musician", "romantic"],
    ),

    # 9. Vivaan — The Rich Gentleman (aspirational, premium segment)
    "vivaan": PersonaConfig(
        name="Vivaan",
        gender="male",
        age=32,
        archetype="Old money charm — sophisticated, well-traveled, effortlessly elegant",
        base_prompt=(
            "handsome Indian man, 32, tall well-built, "
            "neat black hair, hazel brown eyes, clean shaven, "
            "fair skin, tailored suit, expensive watch, "
            f"{PHOTO_QUALITY}"
        ),
        seed_base=900000,
        tags=["gentleman", "rich", "sophisticated", "premium"],
    ),

    # 10. Rehan — The Charming Boy Next Door (relatable, safe choice)
    "rehan": PersonaConfig(
        name="Rehan",
        gender="male",
        age=24,
        archetype="Your best friend who's secretly in love — funny, sweet, always there",
        base_prompt=(
            "handsome young Indian man, 24, average fit, "
            "messy black hair, friendly brown eyes, dimples, "
            "warm brown skin, bright smile, "
            f"{PHOTO_QUALITY}"
        ),
        seed_base=1000000,
        tags=["friendly", "cute", "boy-next-door", "relatable"],
    ),
}
