"""
services/cloudinary_service.py
==============================
Handles secure image uploads, transformations, and deletion via Cloudinary.
"""

import os
import logging
from typing import Optional, Dict, Any, Tuple
import cloudinary
import cloudinary.uploader
from werkzeug.datastructures import FileStorage

logger = logging.getLogger(__name__)

# Cloudinary is configured via the environment variables:
# CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
# The `cloudinary` python package automatically picks these up if they are in the environment,
# or we can explicitly configure them here.
def init_cloudinary():
    """Explicitly configure Cloudinary from env variables just to be safe."""
    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME")
    api_key = os.environ.get("CLOUDINARY_API_KEY")
    api_secret = os.environ.get("CLOUDINARY_API_SECRET")
    
    if cloud_name and api_key and api_secret:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True
        )
    else:
        logger.warning("Cloudinary environment variables missing. Image upload will fail.")

# Initialise on module load
init_cloudinary()

# Valid image extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'heic'}
MAX_FILE_SIZE_MB = int(os.environ.get("MAX_IMAGE_SIZE_MB", "5"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_image(file: FileStorage) -> Tuple[bool, Optional[str]]:
    """
    Validate the file extension and size.
    Returns (is_valid, error_message).
    """
    if not file or not file.filename:
        return False, "No file selected."
    
    if not allowed_file(file.filename):
        return False, f"Allowed file types are: {', '.join(ALLOWED_EXTENSIONS)}"
        
    # Check file size by seeking to end
    file.seek(0, os.SEEK_END)
    file_length = file.tell()
    file.seek(0) # reset cursor for upload
    
    if file_length > MAX_FILE_SIZE_BYTES:
        return False, f"File exceeds maximum size of {MAX_FILE_SIZE_MB}MB."
        
    return True, None

def upload_image(file: FileStorage, folder: str = "lnf") -> Optional[Dict[str, Any]]:
    """
    Upload an image file to Cloudinary.
    
    Args:
        file: The file object from request.files
        folder: Cloudinary subfolder name
        
    Returns:
        Dict with 'url' and 'public_id' on success, None on failure.
    """
    try:
        # Uploads to cloudinary and applies a sensible crop/transformation limit
        result = cloudinary.uploader.upload(
            file,
            folder=folder,
            resource_type="image",
            transformation=[
                {"width": 1200, "height": 1200, "crop": "limit"}, # Downscale huge images
                {"quality": "auto", "fetch_format": "auto"}       # Optimise delivery
            ]
        )
        return {
            "url": result.get("secure_url"),
            "public_id": result.get("public_id")
        }
    except Exception as exc:
        logger.error("Cloudinary upload failed: %s", exc)
        return None

def delete_image(public_id: str) -> bool:
    """
    Delete an image from Cloudinary by its public_id.
    """
    if not public_id:
        return False
        
    try:
        result = cloudinary.uploader.destroy(public_id)
        return result.get("result") == "ok"
    except Exception as exc:
        logger.error("Cloudinary delete failed for %s: %s", public_id, exc)
        return False
