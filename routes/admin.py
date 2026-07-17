from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from services.auth_service import admin_required
from services.db import query_all, query_one, execute

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    """Admin dashboard with aggregate metrics."""
    users_count = query_one("SELECT COUNT(*) AS count FROM users")["count"]
    items_count = query_one("SELECT COUNT(*) AS count FROM items")["count"]
    claims_count = query_one("SELECT COUNT(*) AS count FROM claim_requests")["count"]
    
    stats = {
        "users": users_count,
        "items": items_count,
        "claims": claims_count
    }
    return render_template("admin/dashboard.html", stats=stats)


@admin_bp.route("/users")
@admin_required
def users():
    """List all users."""
    search = request.args.get("search", "")
    
    sql = "SELECT id, first_name, last_name, email, role, is_active, created_at FROM users"
    params = []
    
    if search:
        sql += " WHERE email LIKE %s OR first_name LIKE %s OR last_name LIKE %s"
        like_search = f"%{search}%"
        params.extend([like_search, like_search, like_search])
        
    sql += " ORDER BY created_at DESC"
    
    users_list = query_all(sql, tuple(params))
    return render_template("admin/users.html", users=users_list, search=search)


@admin_bp.route("/users/<int:user_id>/ban", methods=["POST"])
@admin_required
def toggle_ban(user_id):
    """Toggle the is_active status of a user."""
    user = query_one("SELECT is_active, role FROM users WHERE id = %s", (user_id,))
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    if user["role"] == "admin":
        return jsonify({"error": "Cannot ban an admin user"}), 403
        
    new_status = 0 if user["is_active"] else 1
    execute("UPDATE users SET is_active = %s WHERE id = %s", (new_status, user_id))
    
    return jsonify({"success": True, "is_active": new_status})


@admin_bp.route("/items")
@admin_required
def items():
    """List all items."""
    sql = """
        SELECT i.id, i.title, i.status, i.type, i.created_at, u.email as reporter_email, c.name as category_name
        FROM items i
        LEFT JOIN users u ON i.user_id = u.id
        LEFT JOIN categories c ON i.category_id = c.id
        ORDER BY i.created_at DESC
    """
    items_list = query_all(sql)
    return render_template("admin/items.html", items=items_list)


@admin_bp.route("/items/<int:item_id>/delete", methods=["POST"])
@admin_required
def delete_item(item_id):
    """Delete an item."""
    execute("DELETE FROM items WHERE id = %s", (item_id,))
    return jsonify({"success": True})


@admin_bp.route("/categories", methods=["GET", "POST"])
@admin_required
def categories():
    """Manage categories."""
    if request.method == "POST":
        name = request.form.get("name")
        icon = request.form.get("icon", "fa-tag")
        color_hex = request.form.get("color_hex", "#6B7280")
        
        if name:
            execute(
                "INSERT INTO categories (name, icon, color_hex, sort_order) VALUES (%s, %s, %s, %s)",
                (name, icon, color_hex, 0)
            )
            flash("Category added successfully.", "success")
        return redirect(url_for("admin.categories"))
        
    categories_list = query_all("SELECT * FROM categories ORDER BY sort_order, name")
    return render_template("admin/categories.html", categories=categories_list)


@admin_bp.route("/categories/<int:cat_id>/delete", methods=["POST"])
@admin_required
def delete_category(cat_id):
    """Delete a category (soft delete or check references)."""
    try:
        execute("DELETE FROM categories WHERE id = %s", (cat_id,))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@admin_bp.route("/claims")
@admin_required
def claims():
    """List all claims."""
    sql = """
        SELECT cr.id, cr.status, cr.created_at, 
               i.title as item_title, i.id as item_id,
               u.email as claimant_email
        FROM claim_requests cr
        JOIN items i ON cr.item_id = i.id
        JOIN users u ON cr.claimant_id = u.id
        ORDER BY cr.created_at DESC
    """
    claims_list = query_all(sql)
    return render_template("admin/claims.html", claims=claims_list)


@admin_bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    """Manage system settings."""
    if request.method == "POST":
        for key, value in request.form.items():
            if key.startswith("setting_"):
                setting_key = key.replace("setting_", "", 1)
                execute(
                    "UPDATE system_settings SET setting_value = %s WHERE setting_key = %s",
                    (value, setting_key)
                )
        flash("Settings updated successfully.", "success")
        return redirect(url_for("admin.settings"))
        
    settings_list = query_all("SELECT * FROM system_settings ORDER BY setting_key")
    return render_template("admin/settings.html", settings=settings_list)
