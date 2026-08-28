#!/usr/bin/env python3
"""
import_cloudinary_images.py
===========================
Fetches all uploaded images from your Cloudinary account and automatically
creates item cards in the Lost & Found database with matching categories and images.
"""

import os
import sys
import logging
from datetime import datetime
import cloudinary
import cloudinary.api
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def main():
    # 1. Configure Cloudinary
    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME")
    api_key = os.environ.get("CLOUDINARY_API_KEY")
    api_secret = os.environ.get("CLOUDINARY_API_SECRET")

    if not (cloud_name and api_key and api_secret):
        logger.error("Missing CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, or CLOUDINARY_API_SECRET in environment!")
        sys.exit(1)

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True
    )

    logger.info("Fetching uploaded resources from Cloudinary account '%s'...", cloud_name)
    try:
        # Fetch up to 100 images
        res = cloudinary.api.resources(type="upload", max_results=100)
        resources = res.get("resources", [])
    except Exception as exc:
        logger.exception("Failed to query Cloudinary API: %s", exc)
        sys.exit(1)

    if not resources:
        logger.info("No images found in your Cloudinary account.")
        return

    logger.info("Found %d images in Cloudinary!", len(resources))

    # 2. Connect to MySQL Database
    from init_db import _connect
    try:
        conn = _connect()
        cursor = conn.cursor(dictionary=True)
    except Exception as exc:
        logger.exception("Failed to connect to MySQL database: %s", exc)
        sys.exit(1)

    # Get admin user ID
    cursor.execute("SELECT id FROM users WHERE role='admin' OR email='admin@lostandfound.com' LIMIT 1")
    admin_row = cursor.fetchone()
    if admin_row:
        user_id = admin_row["id"]
    else:
        cursor.execute("SELECT id FROM users LIMIT 1")
        first_user = cursor.fetchone()
        user_id = first_user["id"] if first_user else 1

    # Get default category
    cursor.execute("SELECT id, name FROM categories")
    categories = cursor.fetchall()
    cat_map = {c["name"].lower(): c["id"] for c in categories}
    default_cat_id = categories[0]["id"] if categories else 1

    imported_count = 0

    for idx, r in enumerate(resources, 1):
        image_url = r.get("secure_url")
        public_id = r.get("public_id", "")
        
        # Check if already imported
        cursor.execute("SELECT id FROM item_images WHERE image_url = %s OR public_id = %s", (image_url, public_id))
        if cursor.fetchone():
            logger.info("  [%d/%d] Skipping already imported: %s", idx, len(resources), public_id)
            continue

        # Format title from folder/filename
        raw_name = public_id.split("/")[-1].replace("_", " ").replace("-", " ")
        if public_id.startswith("lnf/"):
            title = f"Reported Item ({raw_name[:12]})"
            desc = "Original uploaded item photo recovered from Cloudinary library."
        elif "sample" in public_id:
            title = raw_name.title()
            desc = f"Item matching photo: {raw_name}."
        else:
            title = raw_name.title()
            desc = "Item photo from Cloudinary storage."

        item_type = "found" if idx % 2 == 0 else "lost"

        # Guess category from public_id
        selected_cat = default_cat_id
        for cat_name, cat_id in cat_map.items():
            if cat_name in public_id.lower():
                selected_cat = cat_id
                break

        # Insert item
        cursor.execute("""
            INSERT INTO items (user_id, category_id, title, description, type, status, is_verified, location_text)
            VALUES (%s, %s, %s, %s, %s, 'open', 1, 'Campus / Main Hall')
        """, (user_id, selected_cat, title, desc, item_type))
        
        item_id = cursor.lastrowid

        # Insert image
        cursor.execute("""
            INSERT INTO item_images (item_id, image_url, public_id, is_primary, sort_order)
            VALUES (%s, %s, %s, 1, 0)
        """, (item_id, image_url, public_id))

        imported_count += 1
        logger.info("  [%d/%d] Imported item '%s' (Image: %s)", idx, len(resources), title, image_url)

    conn.commit()
    cursor.close()
    conn.close()

    logger.info("Successfully imported %d items from Cloudinary into your database!", imported_count)

if __name__ == "__main__":
    main()
