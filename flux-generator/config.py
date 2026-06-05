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

INFERENCE_STEPS = 28
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
    "mirror selfie in bedroom, casual, ring light",
    "outdoor selfie in garden, golden hour sunlight",
    "car selfie, natural light through window",
    "getting ready selfie, mirror, doing makeup",
    "rooftop selfie, city skyline evening",
    "cafe selfie, holding chai or coffee, cozy",
    "gym selfie, post-workout glow, athletic wear",
    "hotel room selfie, luxury bed behind, travel vibes",
    "sunset selfie on balcony, golden warm lighting",
    "morning selfie, just woke up, messy hair, natural beauty",
    "festival selfie, fairy lights background, festive",
    "poolside selfie, sunglasses, summer vibes",
]

PORTRAIT_SCENARIOS = [
    "studio portrait, soft warm backdrop, Bollywood style",
    "window light portrait, sheer curtains, dreamy indoor",
    "outdoor portrait, lush green garden background",
    "golden hour portrait, warm golden tones, magic hour",
    "urban portrait, modern Indian city background",
    "indoor portrait, cozy decorated room, warm lights",
    "rain portrait, glass window with water drops, moody",
    "terrace portrait, evening sky, dramatic lighting",
    "candlelit portrait, intimate warm glow, romantic",
    "morning light portrait, soft sunrise tones, fresh",
    "festive portrait, diwali lights or lanterns background",
    "bookshelf background portrait, intellectual aesthetic",
]

FULL_BODY_SCENARIOS = [
    "standing on city street, modern Indian urban fashion",
    "walking on Goa beach, casual boho style",
    "posing in studio, clean white background, fashion shoot",
    "standing in lush park, trees and sunlight",
    "leaning against vintage wall, old city aesthetic",
    "standing in ornate doorway, haveli architecture",
    "outdoor marble steps, palace or temple backdrop",
    "rooftop with city skyline, evening golden hour",
    "garden walkway, flowers and greenery",
    "luxury hotel lobby, chandelier, elegant interior",
    "railway platform or vintage train, travel aesthetic",
    "marketplace street, colorful background, vibrant India",
]

LIFESTYLE_SCENARIOS = [
    "sitting at cafe, holding chai cup, cozy Indian cafe",
    "cooking in kitchen, making chai or food, home setting",
    "reading a book on cozy sofa, warm indoor lighting",
    "working on laptop, modern workspace, focused",
    "shopping in market, colorful bags, city vibes",
    "eating at restaurant, candle dinner, romantic setting",
    "yoga pose, morning light, terrace or garden, peaceful",
    "walking in park, morning jog, earphones, active",
    "balcony garden, watering plants, golden hour",
    "painting or sketching, art corner, creative mood",
    "temple or spiritual setting, peaceful prayerful",
    "bike ride or scooter, helmet, city adventure",
]

FASHION_SCENARIOS = [
    "wearing trendy Indo-western fusion outfit, urban backdrop",
    "elegant lehenga or sherwani, wedding reception setting",
    "sporty athletic wear, modern gym setting",
    "cozy oversized hoodie, rainy day window, warm vibes",
    "floral summer dress or linen kurta, outdoor garden",
    "sharp formal wear, glass office building, corporate",
    "bohemian style, Goa beach vibes, festival aesthetic",
    "denim jacket, rooftop party, fairy lights, evening",
    "traditional festive wear, Diwali or Eid celebration",
    "luxury designer outfit, five star hotel, premium feel",
    "casual streetwear, sneakers, mall or city walk",
    "elegant saree or kurta pajama, classical Indian occasion",
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


PHOTO_QUALITY = "photograph, real person, raw photo, natural skin pores, DSLR"

PERSONAS: Dict[str, PersonaConfig] = {

    # ── FEMALE PERSONAS (6) ──────────────────────────────────

    # 1. Ananya — The Desi Girl Next Door (biggest mass appeal)
    "ananya": PersonaConfig(
        name="Ananya",
        gender="female",
        age=22,
        archetype="Cute desi girl next door — your college crush who texts back",
        base_prompt=(
            "beautiful young Indian woman, 22 years old, petite slim body, "
            "long straight silky black hair, big expressive brown eyes, "
            "cute dimples, soft round face, warm brown skin, "
            "natural minimal makeup, nose pin, genuine bright smile, "
            "wearing simple kurta or casual Indian fashion, "
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
            "stunning Indian woman, 26 years old, tall slim fit body, "
            "long wavy dark brown hair with highlights, sharp brown eyes, "
            "defined jawline, medium fair skin, bold confident expression, "
            "trendy western fashion, red lipstick, glamorous, "
            "Bollywood actress level beauty, "
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
            "beautiful South Indian woman, 24 years old, curvy feminine body, "
            "very long thick black hair, large dark brown eyes with kajal, "
            "full lips, warm golden brown skin, traditional gold jewelry, "
            "jasmine flowers in hair, warm inviting smile, "
            "elegant saree or half-saree, classical Indian beauty, "
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
            "gorgeous young Indian woman, 21 years old, slim toned body, "
            "shoulder-length black hair with streaks, intense dark eyes, "
            "sharp features, light brown skin, edgy street style fashion, "
            "multiple ear piercings, bold eyeliner, attitude in expression, "
            "urban Indian aesthetic, influencer vibes, "
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
            "beautiful Indian woman, 29 years old, tall elegant body, "
            "sleek black hair in low bun or straight blow-dry, "
            "intelligent sharp brown eyes, high cheekbones, fair skin, "
            "subtle sophisticated makeup, pearl earrings, "
            "wearing blazer or elegant formal wear, powerful presence, "
            "executive aesthetic, "
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
            "stunningly beautiful mixed heritage woman, 25 years old, "
            "slim hourglass body, long flowing dark wavy hair, "
            "striking light brown eyes with green flecks, full lips, "
            "olive tan skin, sharp nose, beauty mark near lips, "
            "mysterious alluring expression, exotic elegant fashion, "
            "Middle Eastern Indian fusion beauty, "
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
            "handsome Indian man, 28 years old, tall athletic muscular body, "
            "short black hair with clean fade, strong jawline with stubble, "
            "warm dark brown eyes, brown skin, broad shoulders, "
            "confident protective expression, wearing fitted henley or kurta, "
            "Bollywood hero physique, "
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
            "handsome Indian man, 26 years old, lean athletic body, "
            "messy wavy black hair slightly long, intense deep brown eyes, "
            "sharp features, light stubble, medium brown skin, "
            "soulful brooding expression, wearing denim jacket or kurta, "
            "tattoo on forearm, musician artist aesthetic, "
            "rugged romantic charm, "
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
            "handsome Indian man, 32 years old, tall well-built body, "
            "neatly styled black hair, warm hazel brown eyes, "
            "clean shaven, chiseled features, fair skin, "
            "warm sophisticated smile, wearing tailored suit or blazer, "
            "expensive watch, old money aesthetic, "
            "distinguished gentleman presence, "
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
            "handsome young Indian man, 24 years old, average fit body, "
            "slightly messy black hair, warm friendly brown eyes, "
            "boyish face, light stubble, warm brown skin, "
            "genuine bright smile showing teeth, dimples, "
            "wearing casual t-shirt or hoodie, approachable, "
            "boy next door charm, "
            f"{PHOTO_QUALITY}"
        ),
        seed_base=1000000,
        tags=["friendly", "cute", "boy-next-door", "relatable"],
    ),
}
