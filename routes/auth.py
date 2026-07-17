"""
routes/auth.py
==============
Flask Blueprint for authentication endpoints.

All security logic is delegated to services/auth_service.py.
This module only handles HTTP: form parsing, flashing, redirecting.
"""

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
    current_app,
)

from services.auth_service import (
    AuthError,
    AccountInactiveError,
    EmailTakenError,
    InvalidCredentialsError,
    WeakPasswordError,
    authenticate_user,
    change_password,
    create_session,
    destroy_session,
    is_authenticated,
    login_required,
    register_user,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# ─────────────────────────────────────────────────────────────────────────────
# Register
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Create a new user account."""
    if is_authenticated():
        return redirect(url_for("landing"))

    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name  = request.form.get("last_name", "").strip()
        email      = request.form.get("email", "").strip()
        password   = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        phone      = request.form.get("phone", "").strip() or None

        if not all([first_name, last_name, email, password, confirm_password]):
            flash("All fields are required.", "error")
            return render_template("auth/register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("auth/register.html")

        try:
            new_user_id = register_user(first_name, last_name, email, password, phone)
        except WeakPasswordError as exc:
            flash(str(exc), "error")
            return render_template("auth/register.html")
        except EmailTakenError:
            flash("That email address is already registered.", "error")
            return render_template("auth/register.html")
        except Exception:
            current_app.logger.exception("Unexpected error during registration")
            flash("Something went wrong. Please try again.", "error")
            return render_template("auth/register.html")

        flash("Your account has been created successfully. Please log in to continue.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


# ─────────────────────────────────────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Log in an existing user."""
    if is_authenticated():
        return redirect(url_for("landing"))

    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter your email and password.", "error")
            return render_template("auth/login.html")

        try:
            user = authenticate_user(email, password)
        except AccountInactiveError as exc:
            flash(str(exc), "error")
            return render_template("auth/login.html")
        except InvalidCredentialsError:
            # Deliberately vague — do not hint whether the email exists
            flash("Invalid email or password.", "error")
            return render_template("auth/login.html")
        except Exception:
            current_app.logger.exception("Unexpected error during login")
            flash("Something went wrong. Please try again.", "error")
            return render_template("auth/login.html")

        create_session(user)
        flash(f"Welcome back, {user['first_name']}!", "success")

        # Safe open-redirect: only follow relative paths
        next_page = request.args.get("next", "")
        if next_page and next_page.startswith("/") and not next_page.startswith("//"):
            return redirect(next_page)
        return redirect(url_for("dashboard"))

    return render_template("auth/login.html")


# ─────────────────────────────────────────────────────────────────────────────
# Logout
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route("/logout")
def logout():
    """Destroy the session and redirect to the login page."""
    destroy_session()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("auth.login"))


# ─────────────────────────────────────────────────────────────────────────────
# Change password (authenticated users only)
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password_view():
    """Allow an authenticated user to change their password."""
    if request.method == "POST":
        current_pw = request.form.get("current_password", "")
        new_pw     = request.form.get("new_password", "")
        confirm_pw = request.form.get("confirm_password", "")

        if not current_pw or not new_pw or not confirm_pw:
            flash("All fields are required.", "error")
            return render_template("auth/change_password.html")

        if new_pw != confirm_pw:
            flash("New passwords do not match.", "error")
            return render_template("auth/change_password.html")

        user_id = session.get("user_id")
        try:
            change_password(user_id, current_pw, new_pw)
        except InvalidCredentialsError:
            flash("Your current password is incorrect.", "error")
            return render_template("auth/change_password.html")
        except WeakPasswordError as exc:
            flash(str(exc), "error")
            return render_template("auth/change_password.html")
        except Exception:
            current_app.logger.exception("Unexpected error during password change")
            flash("Something went wrong. Please try again.", "error")
            return render_template("auth/change_password.html")

        flash("Password changed successfully. Please log in again.", "success")
        destroy_session()
        return redirect(url_for("auth.login"))

    return render_template("auth/change_password.html")


# ─────────────────────────────────────────────────────────────────────────────
# Email unverified placeholder (referenced by verified_email_required)
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route("/unverified")
@login_required
def unverified():
    """Page shown to users who have not verified their email yet."""
    return render_template("auth/unverified.html")


@auth_bp.route("/resend-verification", methods=["POST"])
@login_required
def resend_verification():
    """Resend verification email placeholder."""
    flash(f"Verification link successfully resent to {session.get('email')}.", "success")
    return redirect(url_for("auth.unverified"))
