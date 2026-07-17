"""
services/db.py
MySQL Connection Pool with SSL for Aiven Cloud Database

Responsibilities:
- Manage a thread-safe connection pool using mysql-connector-python
- Enforce SSL/TLS for all Aiven connections
- Provide a context manager for safe connection/cursor checkout
- Handle connection errors, retries, and graceful degradation
- Expose helper execute functions for SELECT, DML, and bulk operations
"""

import os
import time
import logging
import threading
from queue import Queue, Empty
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple, Union

import mysql.connector
from mysql.connector import Error as MySQLError
from mysql.connector.pooling import MySQLConnectionPool

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Configuration helpers (read from environment variables)
# ─────────────────────────────────────────────────────────────────────────────
def _build_db_config() -> Dict[str, Any]:
    """
    Build the MySQL connector config dict from environment variables.
    All secrets are read from env so nothing is hardcoded.

    Required env vars:
        DB_HOST         Aiven service hostname (e.g. mysql-xxx.aivencloud.com)
        DB_PORT         TCP port (Aiven default: 3306)
        DB_NAME         Database / schema name
        DB_USER         MySQL username
        DB_PASSWORD     MySQL password

    Optional env vars:
        DB_SSL_CA       Path to CA certificate file (required for Aiven SSL)
        DB_SSL_CERT     Path to client certificate (optional, mTLS)
        DB_SSL_KEY      Path to client private key  (optional, mTLS)
        DB_POOL_SIZE    Number of connections in the pool (default: 5)
        DB_POOL_TIMEOUT Seconds to wait for a free connection (default: 30)
        DB_CONNECT_TIMEOUT Seconds for initial TCP connect (default: 10)
    """
    host = os.environ.get("DB_HOST", "localhost")
    port = int(os.environ.get("DB_PORT", "3306"))
    database = os.environ.get("DB_NAME", "lost_and_found")
    user = os.environ.get("DB_USER", "root")
    password = os.environ.get("DB_PASSWORD", "")
    connect_timeout = int(os.environ.get("DB_CONNECT_TIMEOUT", "10"))

    config: Dict[str, Any] = {
        "host": host,
        "port": port,
        "database": database,
        "user": user,
        "password": password,
        "connect_timeout": connect_timeout,
        "connection_timeout": connect_timeout,
        # Charset / collation
        "charset": "utf8mb4",
        "collation": "utf8mb4_unicode_ci",
        # Raise exceptions on warnings that indicate data issues
        "raise_on_warnings": False,
        # Auto-reconnect at the pool level is handled manually
        "autocommit": False,
        # Use server-side prepared statements when possible
        "use_pure": True,
    }

    # ── SSL configuration (Aiven always requires SSL) ──────────────────────
    ssl_ca = os.environ.get("DB_SSL_CA", "")
    ssl_cert = os.environ.get("DB_SSL_CERT", "")
    ssl_key = os.environ.get("DB_SSL_KEY", "")

    if ssl_ca:
        # Verify server certificate against the given CA bundle
        config["ssl_ca"] = ssl_ca
        config["ssl_verify_cert"] = True
        config["ssl_verify_identity"] = True
        if ssl_cert and ssl_key:
            # mTLS — client presents its own certificate
            config["ssl_cert"] = ssl_cert
            config["ssl_key"] = ssl_key
        logger.info("SSL enabled: CA=%s, mTLS=%s", ssl_ca, bool(ssl_cert))
    else:
        # No CA provided — skip SSL verification.
        # Railway MySQL does not require SSL certificates.
        logger.warning(
            "DB_SSL_CA not set — running without SSL certificate verification. "
            "This is acceptable for Railway/internal MySQL connections."
        )

    return config


# ─────────────────────────────────────────────────────────────────────────────
# Pool singleton (created once per process)
# ─────────────────────────────────────────────────────────────────────────────
_pool: Optional[MySQLConnectionPool] = None
_pool_lock = threading.Lock()

# Pool / retry settings
POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "5"))
POOL_NAME = "lnf_pool"
MAX_INIT_RETRIES = 5
RETRY_BACKOFF_BASE = 2  # seconds


def _create_pool(config: Dict[str, Any]) -> MySQLConnectionPool:
    """
    Instantiate the MySQLConnectionPool with retry/back-off on failure.
    Aiven may take a moment to accept the connection immediately after deploy.
    """
    for attempt in range(1, MAX_INIT_RETRIES + 1):
        try:
            pool = MySQLConnectionPool(
                pool_name=POOL_NAME,
                pool_size=POOL_SIZE,
                pool_reset_session=True,
                **config,
            )
            logger.info(
                "MySQL connection pool '%s' created (size=%d, host=%s)",
                POOL_NAME,
                POOL_SIZE,
                config["host"],
            )
            return pool
        except MySQLError as exc:
            wait = RETRY_BACKOFF_BASE ** attempt
            logger.error(
                "Pool creation attempt %d/%d failed: %s — retrying in %ds",
                attempt,
                MAX_INIT_RETRIES,
                exc,
                wait,
            )
            if attempt == MAX_INIT_RETRIES:
                raise RuntimeError(
                    f"Could not create MySQL pool after {MAX_INIT_RETRIES} attempts. "
                    f"Last error: {exc}"
                ) from exc
            time.sleep(wait)


def get_pool() -> MySQLConnectionPool:
    """
    Return the process-wide connection pool, initialising it on first call.
    Thread-safe via a module-level lock.
    """
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:  # double-checked locking
                config = _build_db_config()
                _pool = _create_pool(config)
    return _pool


# ─────────────────────────────────────────────────────────────────────────────
# Context manager — the primary public API
# ─────────────────────────────────────────────────────────────────────────────
@contextmanager
def get_db(auto_commit: bool = False):
    """
    Context manager that yields (connection, cursor) from the pool.

    Usage:
        with get_db() as (conn, cur):
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()

        # or for write operations:
        with get_db() as (conn, cur):
            cur.execute("INSERT INTO items ...")
            conn.commit()

    The cursor uses dictionary=True so rows come back as dicts.
    The connection is returned to the pool on exit (committed or rolled back).
    """
    pool = get_pool()
    conn = None
    cursor = None
    try:
        conn = pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        yield conn, cursor

        if auto_commit:
            conn.commit()

    except MySQLError as exc:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.exception("Database error — rolled back: %s", exc)
        raise DatabaseError(str(exc)) from exc

    except Exception:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise

    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()  # returns connection to pool
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Custom exception
# ─────────────────────────────────────────────────────────────────────────────
class DatabaseError(Exception):
    """Raised when a MySQL operation fails after any applicable retries."""


# ─────────────────────────────────────────────────────────────────────────────
# Convenience helpers
# ─────────────────────────────────────────────────────────────────────────────

def query_one(
    sql: str,
    params: Optional[Tuple] = None,
) -> Optional[Dict[str, Any]]:
    """
    Execute a SELECT and return the first matching row as a dict, or None.

    Example:
        user = query_one("SELECT * FROM users WHERE id = %s", (user_id,))
    """
    with get_db() as (conn, cur):
        cur.execute(sql, params or ())
        return cur.fetchone()


def query_all(
    sql: str,
    params: Optional[Tuple] = None,
) -> List[Dict[str, Any]]:
    """
    Execute a SELECT and return all matching rows as a list of dicts.

    Example:
        items = query_all("SELECT * FROM items WHERE status = %s", ("open",))
    """
    with get_db() as (conn, cur):
        cur.execute(sql, params or ())
        return cur.fetchall()


def execute(
    sql: str,
    params: Optional[Tuple] = None,
    *,
    return_lastrowid: bool = False,
) -> Union[int, None]:
    """
    Execute a DML statement (INSERT / UPDATE / DELETE) and commit.

    Args:
        sql:              Parameterised SQL string.
        params:           Tuple of bind values.
        return_lastrowid: If True, return the auto-increment ID of the inserted row.

    Returns:
        Last insert ID (if requested), else None.

    Example:
        new_id = execute(
            "INSERT INTO items (title, type, user_id) VALUES (%s, %s, %s)",
            (title, item_type, user_id),
            return_lastrowid=True
        )
    """
    with get_db() as (conn, cur):
        cur.execute(sql, params or ())
        conn.commit()
        if return_lastrowid:
            return cur.lastrowid
        return cur.rowcount


def execute_many(
    sql: str,
    params_list: List[Tuple],
) -> int:
    """
    Execute a DML statement in bulk (executemany) within a single transaction.

    Returns:
        Number of rows affected.

    Example:
        execute_many(
            "INSERT INTO item_images (item_id, image_url) VALUES (%s, %s)",
            [(item_id, url) for url in urls]
        )
    """
    if not params_list:
        return 0

    with get_db() as (conn, cur):
        cur.executemany(sql, params_list)
        conn.commit()
        return cur.rowcount


def call_proc(
    proc_name: str,
    args: Optional[Tuple] = None,
) -> List[Dict[str, Any]]:
    """
    Call a stored procedure and return all result rows.

    Example:
        rows = call_proc("get_matching_items", (item_id,))
    """
    with get_db() as (conn, cur):
        cur.callproc(proc_name, args or ())
        results = []
        for result in cur.stored_results():
            results.extend(result.fetchall())
        return results


# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────
def ping() -> bool:
    """
    Return True if the database is reachable, False otherwise.
    Safe to call from a health-check endpoint without raising exceptions.
    """
    try:
        with get_db() as (conn, cur):
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception as exc:
        logger.warning("DB health check failed: %s", exc)
        return False


def get_pool_status() -> Dict[str, Any]:
    """
    Return diagnostic information about the connection pool.
    Useful for /admin/health endpoints.
    """
    try:
        pool = get_pool()
        return {
            "pool_name": pool.pool_name,
            "pool_size": pool.pool_size,
            "healthy": ping(),
        }
    except Exception as exc:
        return {"healthy": False, "error": str(exc)}
