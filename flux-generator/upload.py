"""
XinMate — Azure Blob Uploader
===============================
Uploads generated images to Azure Blob Storage.
Container: personas/{persona_name}/{category}/{nnnn}.png
"""

import os
import hashlib
import hmac
import base64
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote

logger = logging.getLogger(__name__)

STORAGE_ACCOUNT = os.getenv("AZURE_STORAGE_ACCOUNT", "sdxl")
STORAGE_KEY = os.getenv("AZURE_STORAGE_KEY", "")
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "personas")


def _sign_request(verb: str, blob_path: str, headers: dict) -> str:
    """Generate Azure Blob Storage Shared Key auth signature."""
    content_length = headers.get("Content-Length", "")
    content_type = headers.get("Content-Type", "")
    x_ms_date = headers.get("x-ms-date", "")
    x_ms_version = headers.get("x-ms-version", "")
    x_ms_blob_type = headers.get("x-ms-blob-type", "")

    canonicalized_headers = ""
    if x_ms_blob_type:
        canonicalized_headers += f"x-ms-blob-type:{x_ms_blob_type}\n"
    canonicalized_headers += f"x-ms-date:{x_ms_date}\n"
    canonicalized_headers += f"x-ms-version:{x_ms_version}"

    canonicalized_resource = f"/{STORAGE_ACCOUNT}/{CONTAINER_NAME}/{blob_path}"

    string_to_sign = (
        f"{verb}\n"       # HTTP verb
        f"\n"             # Content-Encoding
        f"\n"             # Content-Language
        f"{content_length}\n"  # Content-Length
        f"\n"             # Content-MD5
        f"{content_type}\n"    # Content-Type
        f"\n"             # Date
        f"\n"             # If-Modified-Since
        f"\n"             # If-Match
        f"\n"             # If-None-Match
        f"\n"             # If-Unmodified-Since
        f"\n"             # Range
        f"{canonicalized_headers}\n"
        f"{canonicalized_resource}"
    )

    key_bytes = base64.b64decode(STORAGE_KEY)
    sig = base64.b64encode(
        hmac.new(key_bytes, string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")

    return f"SharedKey {STORAGE_ACCOUNT}:{sig}"


def upload_image(
    image_bytes: bytes,
    persona_name: str,
    category: str,
    image_number: int,
    extension: str = "png",
) -> str:
    """
    Upload image to Azure Blob Storage.

    Returns:
        Full blob URL (without SAS token).
    """
    if not STORAGE_KEY:
        raise RuntimeError("AZURE_STORAGE_KEY not set")

    blob_name = f"{persona_name.lower()}/{category}/{image_number:04d}.{extension}"
    url = f"https://{STORAGE_ACCOUNT}.blob.core.windows.net/{CONTAINER_NAME}/{quote(blob_name)}"

    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

    headers = {
        "Content-Type": f"image/{extension}",
        "Content-Length": str(len(image_bytes)),
        "x-ms-date": now,
        "x-ms-version": "2021-06-08",
        "x-ms-blob-type": "BlockBlob",
    }

    auth = _sign_request("PUT", blob_name, headers)
    headers["Authorization"] = auth

    req = Request(url, data=image_bytes, method="PUT", headers=headers)

    try:
        with urlopen(req) as resp:
            if resp.status in (200, 201):
                logger.debug(f"Uploaded: {blob_name}")
                return url
            else:
                raise RuntimeError(f"Upload failed: HTTP {resp.status}")
    except Exception as e:
        logger.error(f"Upload failed for {blob_name}: {e}")
        raise


def build_blob_url(persona_name: str, category: str, image_number: int) -> str:
    """Build the expected blob URL without uploading."""
    blob_name = f"{persona_name.lower()}/{category}/{image_number:04d}.png"
    return f"https://{STORAGE_ACCOUNT}.blob.core.windows.net/{CONTAINER_NAME}/{quote(blob_name)}"
