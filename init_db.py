#!/usr/bin/env python3
"""
init_db.py
==========
One-shot database initialiser for the Lost & Found Portal.

Usage:
    python init_db.py            # create schema + seed data
    python init_db.py --drop     # DROP and recreate everything (CAUTION)
    python init_db.py --seed     # seed data only (schema must already exist)

Environment variables required (see services/db.py for full list):
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DB_SSL_CA (for Aiven)
"""

import argparse
import hashlib
import logging
import os
import sys
from datetime import datetime, timedelta

import mysql.connector
from mysql.connector import Error as MySQLError
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Direct connection (bypass pool — we need DDL privileges)
# ─────────────────────────────────────────────────────────────────────────────
def _connect() -> mysql.connector.MySQLConnection:
    config = {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "3306")),
        "database": os.environ.get("DB_NAME", "lost_and_found"),
        "user": os.environ.get("DB_USER", "root"),
        "password": os.environ.get("DB_PASSWORD", ""),
        "connect_timeout": 15,
        "charset": "utf8mb4",
        "collation": "utf8mb4_unicode_ci",
        "autocommit": False,
        "use_pure": True,
    }
    ssl_ca = os.environ.get("DB_SSL_CA", "")
    if ssl_ca:
        config["ssl_ca"] = ssl_ca
        config["ssl_verify_cert"] = True
        config["ssl_verify_identity"] = True
        ssl_cert = os.environ.get("DB_SSL_CERT", "")
        ssl_key = os.environ.get("DB_SSL_KEY", "")
        if ssl_cert and ssl_key:
            config["ssl_cert"] = ssl_cert
            config["ssl_key"] = ssl_key
    return mysql.connector.connect(**config)


# ─────────────────────────────────────────────────────────────────────────────
# DDL — Full MySQL schema
# ─────────────────────────────────────────────────────────────────────────────
SCHEMA_SQL = """
-- ══════════════════════════════════════════════════════════════════════════════
-- Lost & Found Portal — Full MySQL 8.x Schema
-- ══════════════════════════════════════════════════════════════════════════════

-- ----------------------------------------------------------------------------
-- 1. USERS
-- Stores registered users. Supports Google OAuth (oauth_provider / oauth_uid).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    first_name      VARCHAR(64)     NOT NULL,
    last_name       VARCHAR(64)     NOT NULL,
    email           VARCHAR(255)    NOT NULL,
    password_hash   VARCHAR(255)        NULL COMMENT 'NULL for OAuth-only accounts',
    phone           VARCHAR(20)         NULL,
    avatar_url      VARCHAR(500)        NULL,

    -- OAuth support
    oauth_provider  ENUM('google', 'github')  NULL,
    oauth_uid       VARCHAR(128)              NULL,

    -- Roles & status
    role            ENUM('user', 'admin')    NOT NULL DEFAULT 'user',
    is_active       TINYINT(1)               NOT NULL DEFAULT 1,
    email_verified  TINYINT(1)               NOT NULL DEFAULT 0,
    verify_token    VARCHAR(128)                  NULL COMMENT 'Email verification token',

    -- Password reset
    reset_token         VARCHAR(128)   NULL,
    reset_token_expiry  DATETIME       NULL,

    -- Audit
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login_at   DATETIME             NULL,

    PRIMARY KEY (id),
    UNIQUE KEY uq_users_email             (email),
    UNIQUE KEY uq_users_oauth             (oauth_provider, oauth_uid),
    KEY idx_users_role                    (role),
    KEY idx_users_is_active               (is_active),
    KEY idx_users_created_at              (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ----------------------------------------------------------------------------
-- 2. CATEGORIES
-- Admin-managed item categories (Electronics, Keys, Wallets, etc.)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS categories (
    id          SMALLINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    name        VARCHAR(80)        NOT NULL,
    icon        VARCHAR(60)        NOT NULL DEFAULT 'fa-box' COMMENT 'FontAwesome class',
    color_hex   CHAR(7)            NOT NULL DEFAULT '#4F46E5',
    is_active   TINYINT(1)         NOT NULL DEFAULT 1,
    sort_order  SMALLINT UNSIGNED  NOT NULL DEFAULT 0,
    created_at  DATETIME           NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_categories_name (name),
    KEY idx_categories_is_active  (is_active),
    KEY idx_categories_sort       (sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ----------------------------------------------------------------------------
-- 3. ITEMS
-- Core table for all reported lost / found items.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS items (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    user_id         INT UNSIGNED    NOT NULL,
    category_id     SMALLINT UNSIGNED NOT NULL,

    -- Basic details
    title           VARCHAR(200)    NOT NULL,
    description     TEXT                NULL,
    type            ENUM('lost','found') NOT NULL,
    status          ENUM('open','claimed','resolved','deleted')
                                   NOT NULL DEFAULT 'open',

    -- Location
    location_text   VARCHAR(300)        NULL COMMENT 'Human-readable address',
    latitude        DECIMAL(10,7)       NULL,
    longitude       DECIMAL(10,7)       NULL,

    -- When was it lost/found?
    incident_date   DATE                NULL,

    -- Moderation
    is_verified     TINYINT(1)     NOT NULL DEFAULT 0,
    is_flagged      TINYINT(1)     NOT NULL DEFAULT 0,
    flag_reason     VARCHAR(300)        NULL,

    -- View counter (for analytics / relevance sorting)
    view_count      INT UNSIGNED   NOT NULL DEFAULT 0,

    -- Audit
    created_at      DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    CONSTRAINT fk_items_user     FOREIGN KEY (user_id)     REFERENCES users(id)      ON DELETE CASCADE,
    CONSTRAINT fk_items_category FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT,

    KEY idx_items_user_id        (user_id),
    KEY idx_items_category_id    (category_id),
    KEY idx_items_type           (type),
    KEY idx_items_status         (status),
    KEY idx_items_is_verified    (is_verified),
    KEY idx_items_location       (latitude, longitude),
    KEY idx_items_incident_date  (incident_date),
    KEY idx_items_created_at     (created_at),

    -- Full-text search index for title + description
    FULLTEXT KEY ft_items_search (title, description)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ----------------------------------------------------------------------------
-- 4. ITEM_IMAGES
-- Multiple images per item, stored as URLs (Cloudinary CDN).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS item_images (
    id          INT UNSIGNED   NOT NULL AUTO_INCREMENT,
    item_id     INT UNSIGNED   NOT NULL,
    image_url   VARCHAR(500)   NOT NULL,
    public_id   VARCHAR(200)       NULL COMMENT 'Cloudinary public_id for deletion',
    is_primary  TINYINT(1)     NOT NULL DEFAULT 0,
    sort_order  TINYINT UNSIGNED NOT NULL DEFAULT 0,
    created_at  DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    CONSTRAINT fk_images_item FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,

    KEY idx_images_item_id   (item_id),
    KEY idx_images_is_primary (is_primary)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ----------------------------------------------------------------------------
-- 5. CLAIM_REQUESTS
-- A user claims that a "found" item belongs to them, or that they found a
-- "lost" item. The reporter reviews and approves/rejects.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS claim_requests (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    item_id         INT UNSIGNED    NOT NULL,
    claimant_id     INT UNSIGNED    NOT NULL COMMENT 'User making the claim',
    reporter_id     INT UNSIGNED    NOT NULL COMMENT 'User who posted the item',

    status          ENUM('pending','approved','rejected','cancelled')
                                   NOT NULL DEFAULT 'pending',

    -- Proof provided by the claimant
    description     TEXT                NULL COMMENT 'Why they believe it is theirs',
    proof_url       VARCHAR(500)        NULL COMMENT 'Optional supporting image',

    -- Admin / reporter notes
    reviewer_note   VARCHAR(500)        NULL,
    reviewed_at     DATETIME            NULL,

    -- Audit
    created_at  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    CONSTRAINT fk_claims_item       FOREIGN KEY (item_id)     REFERENCES items(id)  ON DELETE CASCADE,
    CONSTRAINT fk_claims_claimant   FOREIGN KEY (claimant_id) REFERENCES users(id)  ON DELETE CASCADE,
    CONSTRAINT fk_claims_reporter   FOREIGN KEY (reporter_id) REFERENCES users(id)  ON DELETE CASCADE,

    -- One pending claim per user per item
    UNIQUE KEY uq_claim_user_item   (item_id, claimant_id),

    KEY idx_claims_item_id          (item_id),
    KEY idx_claims_claimant_id      (claimant_id),
    KEY idx_claims_reporter_id      (reporter_id),
    KEY idx_claims_status           (status),
    KEY idx_claims_created_at       (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ----------------------------------------------------------------------------
-- 6. CONVERSATIONS
-- One conversation ties one item to two users (reporter ↔ claimant).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversations (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    item_id         INT UNSIGNED    NOT NULL,
    user_one_id     INT UNSIGNED    NOT NULL,
    user_two_id     INT UNSIGNED    NOT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_message_at DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    CONSTRAINT fk_conv_item     FOREIGN KEY (item_id)     REFERENCES items(id) ON DELETE CASCADE,
    CONSTRAINT fk_conv_user_one FOREIGN KEY (user_one_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_conv_user_two FOREIGN KEY (user_two_id) REFERENCES users(id) ON DELETE CASCADE,

    -- Prevent duplicate conversations for the same item between the same two users
    UNIQUE KEY uq_conv_item_users     (item_id, user_one_id, user_two_id),

    KEY idx_conv_item_id              (item_id),
    KEY idx_conv_user_one             (user_one_id),
    KEY idx_conv_user_two             (user_two_id),
    KEY idx_conv_last_message_at      (last_message_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ----------------------------------------------------------------------------
-- 7. MESSAGES
-- Individual chat messages within a conversation.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS messages (
    id                  INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    conversation_id     INT UNSIGNED    NOT NULL,
    sender_id           INT UNSIGNED    NOT NULL,
    content             TEXT            NOT NULL,
    is_read             TINYINT(1)      NOT NULL DEFAULT 0,
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    CONSTRAINT fk_msg_conversation FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    CONSTRAINT fk_msg_sender       FOREIGN KEY (sender_id)       REFERENCES users(id)         ON DELETE CASCADE,

    KEY idx_msg_conversation_id (conversation_id),
    KEY idx_msg_sender_id       (sender_id),
    KEY idx_msg_is_read         (is_read),
    KEY idx_msg_created_at      (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ----------------------------------------------------------------------------
-- 8. NOTIFICATIONS
-- Per-user notification feed (match found, claim approved, new message, etc.)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    user_id         INT UNSIGNED    NOT NULL,

    type            ENUM(
                        'new_claim',
                        'claim_approved',
                        'claim_rejected',
                        'match_found',
                        'new_message',
                        'item_returned',
                        'item_viewed',
                        'system'
                    )               NOT NULL,

    title           VARCHAR(200)    NOT NULL,
    body            TEXT                NULL,

    -- Optional deep-link targets
    item_id         INT UNSIGNED        NULL,
    conversation_id INT UNSIGNED        NULL,

    is_read         TINYINT(1)      NOT NULL DEFAULT 0,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    CONSTRAINT fk_notif_user         FOREIGN KEY (user_id)         REFERENCES users(id)         ON DELETE CASCADE,
    CONSTRAINT fk_notif_item         FOREIGN KEY (item_id)         REFERENCES items(id)          ON DELETE SET NULL,
    CONSTRAINT fk_notif_conversation FOREIGN KEY (conversation_id) REFERENCES conversations(id)  ON DELETE SET NULL,

    KEY idx_notif_user_id   (user_id),
    KEY idx_notif_is_read   (is_read),
    KEY idx_notif_type      (type),
    KEY idx_notif_created   (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ----------------------------------------------------------------------------
-- 9. ITEM_MATCHES
-- Stores automatically detected matches between lost and found items.
-- Populated by a background matching job.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS item_matches (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    lost_item_id    INT UNSIGNED    NOT NULL,
    found_item_id   INT UNSIGNED    NOT NULL,
    score           DECIMAL(5,4)    NOT NULL DEFAULT 0.0000
                    COMMENT 'Match confidence 0.0–1.0',
    notified        TINYINT(1)      NOT NULL DEFAULT 0,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    CONSTRAINT fk_match_lost  FOREIGN KEY (lost_item_id)  REFERENCES items(id) ON DELETE CASCADE,
    CONSTRAINT fk_match_found FOREIGN KEY (found_item_id) REFERENCES items(id) ON DELETE CASCADE,

    UNIQUE KEY uq_match_pair        (lost_item_id, found_item_id),
    KEY idx_match_score             (score),
    KEY idx_match_notified          (notified)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ----------------------------------------------------------------------------
-- 10. SYSTEM_SETTINGS
-- Key-value store for admin-configurable portal settings.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS system_settings (
    setting_key     VARCHAR(100)    NOT NULL,
    setting_value   TEXT                NULL,
    value_type      ENUM('string','integer','boolean','json')
                                    NOT NULL DEFAULT 'string',
    description     VARCHAR(500)        NULL,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_by      INT UNSIGNED        NULL,

    PRIMARY KEY (setting_key),
    CONSTRAINT fk_settings_updater FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ----------------------------------------------------------------------------
-- 11. AUDIT_LOG
-- Immutable record of admin actions for accountability.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    actor_id    INT UNSIGNED        NULL COMMENT 'User performing action - NULL = system',
    action      VARCHAR(100)    NOT NULL COMMENT 'e.g. DELETE_ITEM, BAN_USER',
    target_type VARCHAR(50)         NULL COMMENT 'e.g. item, user, claim',
    target_id   INT UNSIGNED        NULL,
    detail      JSON                NULL COMMENT 'Before/after snapshot or extra context',
    ip_address  VARCHAR(45)         NULL COMMENT 'IPv4 or IPv6',
    created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    CONSTRAINT fk_audit_actor FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL,

    KEY idx_audit_actor     (actor_id),
    KEY idx_audit_action    (action),
    KEY idx_audit_target    (target_type, target_id),
    KEY idx_audit_created   (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ----------------------------------------------------------------------------
-- 12. USER_SESSIONS
-- Server-side session store (used when not relying on Flask-Session + Redis).
-- Allows forced logout / session revocation by admin.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_sessions (
    session_id      CHAR(64)        NOT NULL COMMENT 'SHA-256 of the cookie value',
    user_id         INT UNSIGNED    NOT NULL,
    ip_address      VARCHAR(45)         NULL,
    user_agent      VARCHAR(300)        NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at      DATETIME        NOT NULL,
    last_seen_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (session_id),
    CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,

    KEY idx_sessions_user_id    (user_id),
    KEY idx_sessions_expires    (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

# ─────────────────────────────────────────────────────────────────────────────
# Seed data
# ─────────────────────────────────────────────────────────────────────────────
CATEGORY_SEED = [
    # (name,                icon,                   color_hex, sort_order)
    ("Electronics",         "fa-mobile-alt",         "#2563EB", 1),
    ("Keys",                "fa-key",                "#F59E0B", 2),
    ("Wallets & Purses",    "fa-wallet",             "#8B5CF6", 3),
    ("Bags & Backpacks",    "fa-shopping-bag",       "#10B981", 4),
    ("Clothing",            "fa-tshirt",             "#F43F5E", 5),
    ("Jewellery",           "fa-gem",                "#EC4899", 6),
    ("Documents & Cards",   "fa-id-card",            "#6366F1", 7),
    ("Books & Stationery",  "fa-book",               "#0EA5E9", 8),
    ("Sports Equipment",    "fa-football-ball",      "#F97316", 9),
    ("Toys & Games",        "fa-gamepad",            "#84CC16", 10),
    ("Musical Instruments", "fa-guitar",             "#A78BFA", 11),
    ("Pets & Animals",      "fa-paw",                "#FB923C", 12),
    ("Glasses & Eyewear",   "fa-glasses",            "#38BDF8", 13),
    ("Vehicles & Parts",    "fa-car",                "#6B7280", 14),
    ("Other",               "fa-box-open",           "#9CA3AF", 15),
]

SYSTEM_SETTINGS_SEED = [
    # (key,                  value,    type,      description)
    ("site_name",            "Lost & Found Portal",  "string",  "Display name of the portal"),
    ("items_per_page",       "12",     "integer", "Number of items per search results page"),
    ("max_images_per_item",  "5",      "integer", "Maximum images a user may attach per item"),
    ("max_image_size_mb",    "5",      "integer", "Maximum upload size per image in megabytes"),
    ("require_email_verify", "1",      "boolean", "Require email verification before posting"),
    ("allow_google_oauth",   "1",      "boolean", "Enable Sign in with Google"),
    ("maintenance_mode",     "0",      "boolean", "When 1, show maintenance page to non-admins"),
    ("auto_match_enabled",   "1",      "boolean", "Run automatic lost/found matching on new items"),
    ("match_score_threshold","0.60",   "string",  "Minimum match score to trigger notification"),
    ("cloudinary_folder",    "lnf",    "string",  "Cloudinary top-level folder for uploads"),
]


def _hash_password(plain: str) -> str:
    """Deterministic bcrypt-style hash for seeding (uses SHA-256 as placeholder)."""
    import hashlib
    # In production, use bcrypt via auth_service.hash_password()
    # This is only for the seed admin account
    return "$sha256$" + hashlib.sha256(plain.encode()).hexdigest()


ADMIN_SEED = {
    "first_name":     "Admin",
    "last_name":      "Portal",
    "email":          "admin@lostandfound.com",
    "password_hash":  _hash_password("Admin@123"),
    "role":           "admin",
    "is_active":      1,
    "email_verified": 1,
}

# Demo items (inserted after seeding admin so we know the admin user_id)
DEMO_ITEMS = [
    {
        "title": "Blue Samsung Galaxy S21",
        "description": "Blue Samsung phone found near the main library entrance. Screen has a small crack at the top-left corner.",
        "type": "found",
        "category_name": "Electronics",
        "location_text": "Main Library, Ground Floor",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "incident_date": (datetime.today() - timedelta(days=2)).date().isoformat(),
        "status": "open",
    },
    {
        "title": "Car Keys — Honda Civic, red keychain",
        "description": "Found in the parking lot near Gate B. Has a small red ball keychain and two keys.",
        "type": "found",
        "category_name": "Keys",
        "location_text": "Parking Lot B, Gate Entrance",
        "latitude": 19.0750,
        "longitude": 72.8800,
        "incident_date": (datetime.today() - timedelta(days=1)).date().isoformat(),
        "status": "open",
    },
    {
        "title": "Black Leather Wallet",
        "description": "Lost my black leather wallet near the cafeteria. Contains ID card and some cash. Please return.",
        "type": "lost",
        "category_name": "Wallets & Purses",
        "location_text": "Campus Cafeteria",
        "latitude": 19.0765,
        "longitude": 72.8789,
        "incident_date": (datetime.today() - timedelta(days=3)).date().isoformat(),
        "status": "open",
    },
    {
        "title": "Blue HP Laptop Bag",
        "description": "I lost my HP branded blue laptop bag near the seminar hall. Contains charger and some notes inside.",
        "type": "lost",
        "category_name": "Bags & Backpacks",
        "location_text": "Seminar Hall, Block C",
        "latitude": 19.0755,
        "longitude": 72.8810,
        "incident_date": (datetime.today() - timedelta(days=5)).date().isoformat(),
        "status": "open",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _run_statements(cursor, sql_block: str) -> None:
    """Split a multi-statement SQL block and execute each statement."""
    # mysql-connector-python does not support multi=True with cursor.execute
    # on all platforms — split manually
    statements = [s.strip() for s in sql_block.split(";") if s.strip()]
    for stmt in statements:
        try:
            cursor.execute(stmt)
        except MySQLError as exc:
            logger.error("Failed to execute statement:\n%s\nError: %s", stmt[:200], exc)
            raise


# ─────────────────────────────────────────────────────────────────────────────
# Main operations
# ─────────────────────────────────────────────────────────────────────────────
def drop_schema(conn, cursor) -> None:
    """Drop all tables in dependency order (DANGEROUS — irreversible)."""
    logger.warning("Dropping all tables — this cannot be undone!")
    drop_order = [
        "audit_log",
        "user_sessions",
        "item_matches",
        "notifications",
        "messages",
        "conversations",
        "claim_requests",
        "item_images",
        "items",
        "system_settings",
        "categories",
        "users",
    ]
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    for table in drop_order:
        cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
        logger.info("  Dropped table: %s", table)
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()
    logger.info("All tables dropped.")


def create_schema(cursor) -> None:
    """Execute the full DDL schema."""
    logger.info("Creating schema tables…")
    _run_statements(cursor, SCHEMA_SQL)
    logger.info("Schema creation complete.")


def seed_categories(conn, cursor) -> None:
    """Insert categories, skip if already present (INSERT IGNORE)."""
    sql = """
        INSERT IGNORE INTO categories (name, icon, color_hex, sort_order, is_active)
        VALUES (%s, %s, %s, %s, 1)
    """
    cursor.executemany(sql, [
        (name, icon, color, order_)
        for name, icon, color, order_ in CATEGORY_SEED
    ])
    conn.commit()
    logger.info("  Seeded %d categories.", cursor.rowcount)


def seed_settings(conn, cursor) -> None:
    """Insert system settings, skip if already present."""
    sql = """
        INSERT IGNORE INTO system_settings (setting_key, setting_value, value_type, description)
        VALUES (%s, %s, %s, %s)
    """
    cursor.executemany(sql, [
        (key, value, vtype, desc)
        for key, value, vtype, desc in SYSTEM_SETTINGS_SEED
    ])
    conn.commit()
    logger.info("  Seeded %d system settings.", cursor.rowcount)


def seed_admin(conn, cursor) -> int:
    """
    Insert the default admin account if the email does not already exist.
    Returns the admin's user_id.
    """
    cursor.execute(
        "SELECT id FROM users WHERE email = %s",
        (ADMIN_SEED["email"],),
    )
    row = cursor.fetchone()
    if row:
        admin_id = row["id"] if isinstance(row, dict) else row[0]
        logger.info("  Admin already exists (id=%d) — skipping.", admin_id)
        return admin_id

    sql = """
        INSERT INTO users
            (first_name, last_name, email, password_hash, role, is_active, email_verified)
        VALUES
            (%(first_name)s, %(last_name)s, %(email)s, %(password_hash)s,
             %(role)s, %(is_active)s, %(email_verified)s)
    """
    cursor.execute(sql, ADMIN_SEED)
    conn.commit()
    admin_id = cursor.lastrowid
    logger.info("  Admin account created (id=%d, email=%s).", admin_id, ADMIN_SEED["email"])
    return admin_id


def seed_demo_items(conn, cursor, admin_id: int) -> None:
    """Insert a small set of demo items so the portal looks populated."""
    # Build category name → id mapping
    cursor.execute("SELECT id, name FROM categories")
    cat_rows = cursor.fetchall()
    cat_map = {}
    for row in cat_rows:
        if isinstance(row, dict):
            cat_map[row["name"]] = row["id"]
        else:
            cat_map[row[1]] = row[0]

    item_sql = """
        INSERT IGNORE INTO items
            (user_id, category_id, title, description, type, status,
             location_text, latitude, longitude, incident_date, is_verified)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
    """
    inserted = 0
    for item in DEMO_ITEMS:
        cat_id = cat_map.get(item["category_name"])
        if not cat_id:
            logger.warning("  Category '%s' not found, skipping item.", item["category_name"])
            continue
        cursor.execute(item_sql, (
            admin_id,
            cat_id,
            item["title"],
            item["description"],
            item["type"],
            item["status"],
            item["location_text"],
            item["latitude"],
            item["longitude"],
            item["incident_date"],
        ))
        inserted += 1

    conn.commit()
    logger.info("  Seeded %d demo items.", inserted)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Lost & Found Portal — DB Initialiser")
    parser.add_argument(
        "--drop",
        action="store_true",
        help="DROP all existing tables before recreating (DESTRUCTIVE)",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Run seed data only (schema must already exist)",
    )
    args = parser.parse_args()

    logger.info("Connecting to MySQL at %s:%s …",
                os.environ.get("DB_HOST", "localhost"),
                os.environ.get("DB_PORT", "3306"))

    try:
        conn = _connect()
    except MySQLError as exc:
        logger.error("Connection failed: %s", exc)
        sys.exit(1)

    try:
        cursor = conn.cursor(dictionary=True)

        if args.drop:
            confirm = input(
                f"⚠  This will DROP all tables in '{os.environ.get('DB_NAME', 'lost_and_found')}'. "
                "Type 'yes' to confirm: "
            )
            if confirm.strip().lower() != "yes":
                logger.info("Aborted.")
                return
            drop_schema(conn, cursor)

        if not args.seed:
            create_schema(cursor)

        logger.info("Seeding reference data…")
        seed_categories(conn, cursor)
        seed_settings(conn, cursor)
        admin_id = seed_admin(conn, cursor)
        seed_demo_items(conn, cursor, admin_id)

        logger.info("✅  Database initialisation complete.")
        logger.info("")
        logger.info("  Admin login:  admin@lostandfound.com  /  Admin@123")
        logger.info("  ⚠  Change the admin password immediately after first login!")

    except Exception as exc:
        logger.exception("Initialisation failed: %s", exc)
        conn.rollback()
        sys.exit(1)
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
