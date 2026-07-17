"""
services/auth_service.py
========================
Security-critical authentication service for the Lost & Found Portal.

Responsibilities:
  - Password hashing and verification using bcrypt (cost factor configurable)
  - Secure Flask session creation, rotation, and destruction
  - Timing-safe login to prevent user enumeration via timing attacks
  - Role-based access control (RBAC) decorators: login_required, admin_required
  - Optional: current_user helper that loads the full user dict from session

Design decisions:
  - We use the `bcrypt` library directly (not Werkzeug) so we control the cost
    factor explicitly and can tune it as hardware improves.
  - Sessions store only the minimal user identity (id, role); the full user
    record is fetched lazily from the DB when needed.
  - Session IDs are regenerated on login to prevent session fixation attacks.
  - All functions that touch credentials use `hmac.compare_digest` or
    bcrypt's built-in constant-time comparison — never plain ==.
"""

from __future__ import annotations

import functools
import logging
import os
import re
import secrets
from typing import Any, Callable, Dict, Optional

import bcrypt
from flask import (
    abort,
    flash,
    g,
    redirect,
    request,
    session,
    url_for,
    current_app,
)

from services.db import DatabaseError, execute, query_one

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Configuration constants (override via environment variables)
# ─────────────────────────────────────────────────────────────────────────────

# bcrypt work factor — 12 is a safe default for 2024+ hardware.
# Each increment roughly doubles hashing time.
BCRYPT_LOG_ROUNDS: int = int(os.environ.get("BCRYPT_LOG_ROUNDS", "12"))

# Minimum password complexity requirements
MIN_PASSWORD_LENGTH: int = 8
PASSWORD_REGEX = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$",
    re.UNICODE,
)

# Session key names (centralised so templates / routes never hardcode strings)
SESSION_USER_ID   = "user_id"
SESSION_USER_NAME = "user_name"
SESSION_ROLE      = "role"
SESSION_EMAIL     = "email"

# ─────────────────────────────────────────────────────────────────────────────
# Custom exceptions
# ─────────────────────────────────────────────────────────────────────────────

class AuthError(Exception):
    """Base class for authentication/authorisation failures."""


class InvalidCredentialsError(AuthError):
    """Wrong email or password (deliberately vague for security)."""


class AccountInactiveError(AuthError):
    """Account exists but has been deactivated by an admin."""


class WeakPasswordError(AuthError):
    """Password does not meet complexity requirements."""


class EmailTakenError(AuthError):
    """Attempted registration with an already-registered email."""


# ─────────────────────────────────────────────────────────────────────────────
# Password utilities
# ─────────────────────────────────────────────────────────────────────────────

def hash_password(plain_text: str) -> str:
    """
    Hash a plain-text password with bcrypt.

    Args:
        plain_text: The raw password string supplied by the user.

    Returns:
        A bcrypt hash string (e.g. "$2b$12$...") suitable for database storage.

    Raises:
        WeakPasswordError: If the password does not meet complexity rules.
    """
    _validate_password_strength(plain_text)

    password_bytes = plain_text.encode("utf-8")
    salt = bcrypt.gensalt(rounds=BCRYPT_LOG_ROUNDS)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_text: str, hashed: str) -> bool:
    """
    Verify a plain-text password against a stored bcrypt hash.
    Uses bcrypt's built-in constant-time comparison to prevent timing attacks.

    Also handles the legacy '$sha256$...' placeholder that init_db.py creates
    for the seeded admin account — this lets the admin log in once so they can
    immediately change their password to a proper bcrypt hash.

    Args:
        plain_text: The password submitted by the user.
        hashed:     The stored hash from the database.

    Returns:
        True if the password matches, False otherwise.
    """
    if not plain_text or not hashed:
        return False

    # ── Legacy SHA-256 placeholder (init_db.py admin seed only) ─────────────
    if hashed.startswith("$sha256$"):
        import hashlib
        import hmac
        expected = "$sha256$" + hashlib.sha256(plain_text.encode("utf-8")).hexdigest()
        return hmac.compare_digest(expected, hashed)

    # ── Normal bcrypt path ────────────────────────────────────────────────────
    try:
        return bcrypt.checkpw(
            plain_text.encode("utf-8"),
            hashed.encode("utf-8"),
        )
    except Exception as exc:
        # Malformed hash or unexpected bcrypt error — fail closed
        logger.warning("bcrypt.checkpw raised an exception: %s", exc)
        return False


def _validate_password_strength(password: str) -> None:
    """
    Raise WeakPasswordError if the password does not meet complexity rules.

    Rules:
        - At least MIN_PASSWORD_LENGTH characters
        - At least one lowercase letter
        - At least one uppercase letter
        - At least one digit
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )
    if not PASSWORD_REGEX.match(password):
        raise WeakPasswordError(
            "Password must contain at least one uppercase letter, "
            "one lowercase letter, and one digit."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Session management
# ─────────────────────────────────────────────────────────────────────────────

def create_session(user: Dict[str, Any]) -> None:
    """
    Populate the Flask session after a successful login.

    We call session.clear() first and then regenerate the session ID to
    prevent session fixation attacks. Only the minimum required fields are
    stored in the cookie — the full user record is not serialised there.

    Args:
        user: A dict containing at least 'id', 'first_name', 'role', 'email'.
    """
    # Regenerate session ID to prevent fixation — Flask/Werkzeug handles this
    # automatically when we call session.clear() + re-populate.
    session.clear()

    session[SESSION_USER_ID]   = user["id"]
    session[SESSION_USER_NAME] = user.get("first_name", "")
    session[SESSION_ROLE]      = user.get("role", "user")
    session[SESSION_EMAIL]     = user.get("email", "")
    session.permanent          = True   # respect PERMANENT_SESSION_LIFETIME


def destroy_session() -> None:
    """
    Securely destroy the current session on logout.
    Clears all session data and invalidates the cookie.
    """
    session.clear()


def get_session_user_id() -> Optional[int]:
    """Return the currently authenticated user's ID, or None."""
    return session.get(SESSION_USER_ID)


def get_session_role() -> Optional[str]:
    """Return the currently authenticated user's role, or None."""
    return session.get(SESSION_ROLE)


def is_authenticated() -> bool:
    """Return True if a user is currently logged in."""
    return SESSION_USER_ID in session


def is_admin() -> bool:
    """Return True if the current session belongs to an admin user."""
    return session.get(SESSION_ROLE) == "admin"


# ─────────────────────────────────────────────────────────────────────────────
# Current user loader (lazy, cached per request via flask.g)
# ─────────────────────────────────────────────────────────────────────────────

def get_current_user() -> Optional[Dict[str, Any]]:
    """
    Return the full user record for the currently authenticated session.

    The result is cached on Flask's `g` object for the duration of the request
    so that multiple callers within the same request context do not hit the DB
    multiple times.

    Returns:
        A dict with user fields, or None if not authenticated.
    """
    if not is_authenticated():
        return None

    # Use g to cache the user record within the current request
    if not hasattr(g, "_current_user"):
        user_id = get_session_user_id()
        g._current_user = query_one(
            """
            SELECT id, first_name, last_name, email, role,
                   is_active, email_verified, avatar_url, phone,
                   created_at, last_login_at
            FROM   users
            WHERE  id = %s AND is_active = 1
            """,
            (user_id,),
        )
    return g._current_user


# ─────────────────────────────────────────────────────────────────────────────
# Registration
# ─────────────────────────────────────────────────────────────────────────────

def register_user(
    first_name: str,
    last_name: str,
    email: str,
    password: str,
    phone: Optional[str] = None,
) -> int:
    """
    Register a new user account and return the new user's ID.

    This function:
        1. Validates password strength (raises WeakPasswordError on failure).
        2. Checks for duplicate email (raises EmailTakenError on collision).
        3. Hashes the password with bcrypt.
        4. Inserts the user row.

    Args:
        first_name: Given name.
        last_name:  Family name.
        email:      Email address (will be lowercased and stripped).
        password:   Plain-text password (not stored).
        phone:      Optional phone number.

    Returns:
        The auto-increment ID of the newly created user.

    Raises:
        WeakPasswordError:  Password does not meet complexity requirements.
        EmailTakenError:    Email is already registered.
        DatabaseError:      Unexpected database error.
    """
    email = email.strip().lower()

    # Check duplicate before hashing (hashing is expensive — skip if possible)
    existing = query_one("SELECT id FROM users WHERE email = %s", (email,))
    if existing:
        raise EmailTakenError(f"Email '{email}' is already registered.")

    password_hash = hash_password(password)  # may raise WeakPasswordError

    try:
        new_id = execute(
            """
            INSERT INTO users
                (first_name, last_name, email, password_hash, phone,
                 role, is_active, email_verified)
            VALUES
                (%s, %s, %s, %s, %s, 'user', 1, 0)
            """,
            (first_name.strip(), last_name.strip(), email, password_hash, phone),
            return_lastrowid=True,
        )
    except DatabaseError:
        logger.exception("Database error during user registration for %s", email)
        raise

    logger.info("New user registered: id=%s email=%s", new_id, email)
    return new_id


# ─────────────────────────────────────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────────────────────────────────────

def authenticate_user(email: str, password: str) -> Dict[str, Any]:
    """
    Authenticate a user by email and password.

    This function is deliberately structured to be timing-safe:
        - The bcrypt check always runs even for unknown emails (using a dummy
          hash) so that an attacker cannot determine whether an email is
          registered by measuring response time.

    Args:
        email:    The submitted email address.
        password: The submitted plain-text password.

    Returns:
        The user's full record dict on success.

    Raises:
        InvalidCredentialsError: Email not found or wrong password.
        AccountInactiveError:    Account has been deactivated.
    """
    email = email.strip().lower()

    user = query_one(
        """
        SELECT id, first_name, last_name, email,
               password_hash, role, is_active, avatar_url
        FROM   users
        WHERE  email = %s
        """,
        (email,),
    )

    # ── Timing-safe path: always run verify_password, even for unknown emails
    # This prevents enumeration via timing differences.
    _DUMMY_HASH = (
        "$2b$12$eVf6xNjZf6I4I/CxX3.8Y.k8VHgTJpY4Y3nXpK0JxGFn4a3ZSW7Uy"
    )
    candidate_hash = user["password_hash"] if user else _DUMMY_HASH

    password_ok = verify_password(password, candidate_hash)

    if not user or not password_ok:
        # Deliberate vague message — do not distinguish "no user" from "wrong password"
        raise InvalidCredentialsError("Invalid email or password.")

    if not user["is_active"]:
        raise AccountInactiveError(
            "Your account has been deactivated. Please contact support."
        )

    # ── Stamp last login time (non-critical; fail silently if it errors) ──────
    try:
        execute(
            "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = %s",
            (user["id"],),
        )
    except Exception:
        logger.warning("Failed to update last_login_at for user id=%s", user["id"])

    logger.info("User authenticated: id=%s email=%s", user["id"], email)
    return user


# ─────────────────────────────────────────────────────────────────────────────
# Password change
# ─────────────────────────────────────────────────────────────────────────────

def change_password(user_id: int, current_password: str, new_password: str) -> None:
    """
    Change a user's password after verifying the current one.

    Args:
        user_id:          The user whose password to change.
        current_password: Their current plain-text password for verification.
        new_password:     The new plain-text password.

    Raises:
        InvalidCredentialsError: Current password is wrong.
        WeakPasswordError:       New password fails complexity check.
        DatabaseError:           Unexpected DB error.
    """
    user = query_one(
        "SELECT password_hash FROM users WHERE id = %s",
        (user_id,),
    )
    if not user or not verify_password(current_password, user["password_hash"]):
        raise InvalidCredentialsError("Current password is incorrect.")

    new_hash = hash_password(new_password)  # validates strength, raises WeakPasswordError

    execute(
        "UPDATE users SET password_hash = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (new_hash, user_id),
    )
    logger.info("Password changed for user id=%s", user_id)


# ─────────────────────────────────────────────────────────────────────────────
# RBAC decorators
# ─────────────────────────────────────────────────────────────────────────────

def login_required(f: Callable) -> Callable:
    """
    Route decorator: redirect unauthenticated users to the login page.

    Usage::

        @app.route('/dashboard')
        @login_required
        def dashboard():
            ...

    The original destination URL is preserved in the ``next`` query parameter
    so that the login view can redirect the user back after authentication.
    """
    @functools.wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if not is_authenticated():
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.full_path))
        return f(*args, **kwargs)
    return decorated


def admin_required(f: Callable) -> Callable:
    """
    Route decorator: restrict access to admin users only.

    Unauthenticated users are redirected to login.
    Authenticated non-admins receive a 403 Forbidden response.

    Usage::

        @app.route('/admin/users')
        @admin_required
        def admin_users():
            ...
    """
    @functools.wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if not is_authenticated():
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.full_path))
        if not is_admin():
            logger.warning(
                "Forbidden access attempt: user_id=%s path=%s",
                get_session_user_id(),
                request.path,
            )
            abort(403)
        return f(*args, **kwargs)
    return decorated


def verified_email_required(f: Callable) -> Callable:
    """
    Route decorator: require the user's email to be verified.

    Useful for gating item posting behind email verification.
    Redirects to a 'verify your email' page if not verified.
    """
    @functools.wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if not is_authenticated():
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.full_path))

        user = get_current_user()
        if not user or not user.get("email_verified"):
            flash("Please verify your email address before continuing.", "warning")
            return redirect(url_for("auth.unverified"))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────────────────────────────────────
# Template context helper (inject current_user into every Jinja2 template)
# ─────────────────────────────────────────────────────────────────────────────

def inject_current_user() -> Dict[str, Any]:
    """
    Flask context processor — makes ``current_user`` and ``is_admin``
    available in every template without explicitly passing them.

    Register with::

        app.context_processor(inject_current_user)

    Template usage::

        {% if current_user %}
            Hello, {{ current_user.first_name }}!
        {% endif %}
        {% if is_admin_user %}
            <a href="/admin">Admin Panel</a>
        {% endif %}
    """
    current_user = get_current_user()
    my_posts_count = 0
    if current_user:
        try:
            res = query_one("SELECT COUNT(*) as count FROM items WHERE user_id = %s", (current_user["id"],))
            if res:
                my_posts_count = res.get("count", 0)
        except Exception as e:
            logger.error(f"Error getting my posts count: {e}")
            
    return {
        "current_user": current_user,
        "is_admin_user": is_admin(),
        "is_authenticated": is_authenticated(),
        "my_posts_count": my_posts_count,
    }
