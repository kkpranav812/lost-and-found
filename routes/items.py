"""
routes/items.py
===============
Flask Blueprint for Item operations (CRUD, Search, Filters).
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from datetime import datetime
import math

from services.db import get_db, query_one, query_all, execute, DatabaseError
from services.auth_service import login_required, get_session_user_id, verified_email_required
from services.cloudinary_service import validate_image, upload_image, delete_image

items_bp = Blueprint('items', __name__)

def get_categories():
    """Helper to fetch active categories"""
    return query_all("SELECT * FROM categories WHERE is_active = 1 ORDER BY sort_order, name")

# ─────────────────────────────────────────────────────────────────────────────
# Search & Filters
# ─────────────────────────────────────────────────────────────────────────────

@items_bp.route('/search')
def search():
    """
    Complex Search API & UI.
    Supports: q (text), category, type, status, page, sort.
    """
    categories = get_categories()
    
    # ── Parse Filters ──
    q = request.args.get('q', '').strip()
    category_id = request.args.get('category', type=int)
    item_type = request.args.get('type')  # 'lost' or 'found'
    status = request.args.get('status', 'open')  # Default to open items
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 12
    offset = (page - 1) * per_page
    
    # ── Build SQL Query dynamically ──
    # We use a base query and append conditions
    select_clause = """
        SELECT i.*, c.name as category_name, c.icon as category_icon, 
               u.first_name as user_name, u.avatar_url,
               (SELECT image_url FROM item_images img WHERE img.item_id = i.id ORDER BY is_primary DESC, sort_order ASC LIMIT 1) as primary_image
        FROM items i
        JOIN categories c ON i.category_id = c.id
        JOIN users u ON i.user_id = u.id
    """
    
    count_clause = """
        SELECT COUNT(i.id) as total
        FROM items i
        JOIN categories c ON i.category_id = c.id
        JOIN users u ON i.user_id = u.id
    """
    
    where_conditions = ["i.status = %s"]
    params = [status]
    
    if q:
        # Full-text search or simple LIKE fallback.
        # Since we have FULLTEXT KEY ft_items_search (title, description), we can use MATCH AGAINST
        # For simplicity and partial word matching in a small DB, we can use LIKE
        where_conditions.append("(i.title LIKE %s OR i.description LIKE %s)")
        wildcard_q = f"%{q}%"
        params.extend([wildcard_q, wildcard_q])
        
    if category_id:
        where_conditions.append("i.category_id = %s")
        params.append(category_id)
        
    if item_type in ['lost', 'found']:
        where_conditions.append("i.type = %s")
        params.append(item_type)
        
    # Combine conditions
    where_sql = " WHERE " + " AND ".join(where_conditions)
    
    # Count total for pagination
    try:
        total_result = query_one(count_clause + where_sql, tuple(params))
        total_items = total_result['total'] if total_result else 0
    except DatabaseError as e:
        current_app.logger.error(f"Search count error: {e}")
        total_items = 0
        
    total_pages = math.ceil(total_items / per_page)
    
    # Final data query
    order_sql = " ORDER BY i.created_at DESC LIMIT %s OFFSET %s"
    data_params = params + [per_page, offset]
    
    try:
        items = query_all(select_clause + where_sql + order_sql, tuple(data_params))
    except DatabaseError as e:
        current_app.logger.error(f"Search data error: {e}")
        items = []
        
    return render_template('search.html', 
                           items=items, 
                           categories=categories,
                           current_page=page,
                           total_pages=total_pages,
                           total_items=total_items,
                           q=q,
                           current_category=category_id,
                           current_type=item_type,
                           current_status=status)


# ─────────────────────────────────────────────────────────────────────────────
# View Item Details
# ─────────────────────────────────────────────────────────────────────────────

@items_bp.route('/item/<int:item_id>')
def item_detail(item_id):
    """View details for a specific item"""
    item = query_one("""
        SELECT i.*, c.name as category_name, c.icon as category_icon, 
               u.first_name, u.avatar_url, u.created_at as user_joined
        FROM items i
        JOIN categories c ON i.category_id = c.id
        JOIN users u ON i.user_id = u.id
        WHERE i.id = %s
    """, (item_id,))
    
    if not item:
        flash("Item not found.", "error")
        return redirect(url_for('items.search'))
        
    # Fetch images
    images = query_all("SELECT image_url, is_primary FROM item_images WHERE item_id = %s ORDER BY is_primary DESC, sort_order ASC", (item_id,))
    
    # Increment view count
    execute("UPDATE items SET view_count = view_count + 1 WHERE id = %s", (item_id,))
    
    return render_template('item_detail.html', item=item, images=images)


# ─────────────────────────────────────────────────────────────────────────────
# Report Lost / Found (Create)
# ─────────────────────────────────────────────────────────────────────────────

@items_bp.route('/report-lost', methods=['GET', 'POST'])
@login_required
def report_lost():
    return _handle_report(request, 'lost')

@items_bp.route('/report-found', methods=['GET', 'POST'])
@login_required
def report_found():
    return _handle_report(request, 'found')

def _handle_report(req, item_type):
    """Shared logic for creating lost and found items."""
    from services.notification_service import notify_match_found

    categories = get_categories()
    
    if req.method == 'POST':
        user_id = get_session_user_id()
        title = req.form.get('title', '').strip()
        category_id = req.form.get('category_id', type=int)
        description = req.form.get('description', '').strip()
        location = req.form.get('location', '').strip()
        incident_date = req.form.get('incident_date')
        lat = req.form.get('lat', type=float)
        lng = req.form.get('lng', type=float)
        
        # Validation
        if not title or not category_id or not location:
            flash("Please fill in all required fields.", "error")
            return render_template(f'report_{item_type}.html', categories=categories)
            
        try:
            # 1. Insert Item — use correct DB column names: latitude, longitude
            item_id = execute(
                """
                INSERT INTO items (user_id, category_id, title, description, type, status, location_text, latitude, longitude, incident_date)
                VALUES (%s, %s, %s, %s, %s, 'open', %s, %s, %s, %s)
                """,
                (user_id, category_id, title, description, item_type, location, lat, lng, incident_date or None),
                return_lastrowid=True
            )
            
            # 2. Handle Image Uploads (up to 5 images)
            if 'images' in req.files:
                files = req.files.getlist('images')
                uploaded_count = 0
                for i, file in enumerate(files):
                    if uploaded_count >= 5:
                        break
                    if file and file.filename:
                        is_valid, error = validate_image(file)
                        if is_valid:
                            upload_result = upload_image(file)
                            if upload_result:
                                is_primary = 1 if uploaded_count == 0 else 0
                                execute(
                                    "INSERT INTO item_images (item_id, image_url, public_id, is_primary, sort_order) VALUES (%s, %s, %s, %s, %s)",
                                    (item_id, upload_result['url'], upload_result['public_id'], is_primary, uploaded_count)
                                )
                                uploaded_count += 1
                        else:
                            current_app.logger.warning(f"Image upload skipped for {file.filename}: {error}")

            # 3. Match Notifications
            # Determine the opposite type to scan for potential matches
            opposite_type = 'lost' if item_type == 'found' else 'found'
            
            # Find open items in the same category of the opposite type
            potential_matches = query_all("""
                SELECT i.id, i.title, i.user_id
                FROM items i
                WHERE i.type = %s
                  AND i.status = 'open'
                  AND i.category_id = %s
                  AND i.user_id != %s
                LIMIT 10
            """, (opposite_type, category_id, user_id))

            if item_type == 'found':
                # Notify the owners of open LOST items that a potential match was found
                for match in potential_matches:
                    notify_match_found(
                        user_id=match['user_id'],
                        item_title=match['title'],
                        matched_title=title,
                        item_id=match['id']
                    )
                if potential_matches:
                    flash(
                        f"✅ Your found item was reported! We found {len(potential_matches)} potential "
                        f"match(es) — the owner(s) have been notified.",
                        "success"
                    )
                else:
                    flash("Your found item has been successfully reported! We'll alert you when a match is found.", "success")
            else:
                # For lost items: tell the reporter if existing found items match
                if potential_matches:
                    flash(
                        f"✅ Your lost item was reported! We found {len(potential_matches)} existing found "
                        f"item(s) in this category — check them out on the search page!",
                        "success"
                    )
                else:
                    flash("Your lost item has been successfully reported! We'll alert you when a match is found.", "success")

            return redirect(url_for('items.item_detail', item_id=item_id))
            
        except Exception as e:
            current_app.logger.error(f"Error reporting item: {e}")
            flash("An error occurred while saving your report. Please try again.", "error")
            
    return render_template(f'report_{item_type}.html', categories=categories)

# ─────────────────────────────────────────────────────────────────────────────
# Delete Item
# ─────────────────────────────────────────────────────────────────────────────

@items_bp.route('/item/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_item(item_id):
    user_id = get_session_user_id()
    
    # Verify ownership or admin
    item = query_one("SELECT user_id FROM items WHERE id = %s", (item_id,))
    if not item:
        flash("Item not found.", "error")
        return redirect(url_for('dashboard'))
        
    from services.auth_service import is_admin
    if item['user_id'] != user_id and not is_admin():
        flash("You don't have permission to delete this item.", "error")
        return redirect(url_for('dashboard'))
        
    try:
        # Delete images from Cloudinary first
        images = query_all("SELECT public_id FROM item_images WHERE item_id = %s", (item_id,))
        for img in images:
            if img.get('public_id'):
                delete_image(img['public_id'])
                
        # Delete from DB (foreign keys will handle cascades)
        execute("DELETE FROM items WHERE id = %s", (item_id,))
        flash("Item successfully deleted.", "success")
        
    except DatabaseError as e:
        current_app.logger.error(f"Error deleting item {item_id}: {e}")
        flash("Could not delete item.", "error")
        
    return redirect(url_for('my_posts'))

# ─────────────────────────────────────────────────────────────────────────────
# Resolve Item
# ─────────────────────────────────────────────────────────────────────────────

@items_bp.route('/item/<int:item_id>/resolve', methods=['POST'])
@login_required
def resolve_item(item_id):
    user_id = get_session_user_id()
    
    # Verify ownership or admin
    item = query_one("SELECT user_id FROM items WHERE id = %s", (item_id,))
    if not item:
        flash("Item not found.", "error")
        return redirect(url_for('my_posts'))
        
    from services.auth_service import is_admin
    if item['user_id'] != user_id and not is_admin():
        flash("You don't have permission to resolve this item.", "error")
        return redirect(url_for('my_posts'))
        
    try:
        execute("UPDATE items SET status = 'resolved' WHERE id = %s", (item_id,))
        flash("Item successfully marked as resolved!", "success")
    except DatabaseError as e:
        current_app.logger.error(f"Error resolving item {item_id}: {e}")
        flash("Could not resolve item.", "error")
        
    return redirect(url_for('my_posts'))
