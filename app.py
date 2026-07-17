# pyrefly: ignore [missing-import]
import eventlet
eventlet.monkey_patch()
import os
from datetime import datetime

from flask import Flask, render_template, request, session, redirect, url_for, flash
from dotenv import load_dotenv

load_dotenv()

is_dev = os.environ.get('FLASK_ENV', 'development') == 'development'

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0 if is_dev else 31536000
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key_change_me_later')

# Create bundled static assets to reduce HTTP requests for common CSS/JS.
def _create_bundle_file(bundle_path, source_paths):
    os.makedirs(os.path.dirname(bundle_path), exist_ok=True)
    try:
        with open(bundle_path, 'w', encoding='utf-8') as bundle_file:
            for source in source_paths:
                source_path = os.path.join(app.static_folder, source)
                if os.path.exists(source_path):
                    bundle_file.write(f"/* {source} */\n")
                    with open(source_path, 'r', encoding='utf-8') as src_file:
                        bundle_file.write(src_file.read())
                        bundle_file.write("\n\n")
    except OSError as exc:
        app.logger.warning('Could not write static bundle %s: %s', bundle_path, exc)

css_bundle_path = os.path.join(app.static_folder, 'css', 'bundle.css')
js_bundle_path = os.path.join(app.static_folder, 'js', 'bundle.js')
landing_css_bundle_path = os.path.join(app.static_folder, 'css', 'landing.bundle.css')


if is_dev or not os.path.exists(css_bundle_path):
    _create_bundle_file(css_bundle_path, ['css/style.css', 'css/sidebar.css', 'css/responsive.css'])
if is_dev or not os.path.exists(js_bundle_path):
    _create_bundle_file(js_bundle_path, ['js/app.js', 'js/notifications.js'])
if is_dev or not os.path.exists(landing_css_bundle_path):
    _create_bundle_file(landing_css_bundle_path, ['css/style.css', 'css/landing.css'])

# Initialize extensions
from extensions import socketio
socketio.init_app(app)

# ── Blueprints ────────────────────────────────────────────────────────────────
from routes.auth import auth_bp
app.register_blueprint(auth_bp)

from routes.chat import chat_bp
app.register_blueprint(chat_bp)

from routes.items import items_bp
app.register_blueprint(items_bp)

from routes.claims import claims_bp
app.register_blueprint(claims_bp)

from routes.notifications import notifications_bp
app.register_blueprint(notifications_bp)

from routes.admin import admin_bp
app.register_blueprint(admin_bp)

# ── Template context: inject current_user into every Jinja2 template ─────────
from services.auth_service import inject_current_user, login_required, get_session_user_id
app.context_processor(inject_current_user)


@app.route('/')
def landing():
    return render_template('landing.html')

# Auth is handled by routes/auth.py Blueprint

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = get_session_user_id()
    
    from services.db import query_one, query_all
    
    # ── Fetch Real Stats ──
    stats_query = query_one("""
        SELECT 
            (SELECT COUNT(*) FROM items WHERE type = 'lost') as reported_items,
            (SELECT COUNT(*) FROM items WHERE type = 'found') as found_items,
            (SELECT COUNT(*) FROM claim_requests) as total_matches,
            (SELECT COUNT(*) FROM claim_requests WHERE status = 'pending') as claim_requests,
            (SELECT COUNT(*) FROM items WHERE user_id = %s) as my_posts,
            0 as chats,
            0 as notifications,
            (SELECT COUNT(*) FROM items WHERE status = 'resolved') as items_returned
    """, (user_id,))
    
    stats = stats_query if stats_query else {
        'reported_items': 0, 'found_items': 0, 'total_matches': 0, 'claim_requests': 0, 
        'my_posts': 0, 'chats': 0, 'notifications': 0, 'items_returned': 0
    }
    
    # ── Fetch Recent Activity ──
    recent_activities = query_all("""
        SELECT id, type, title as item_name, location_text as location, created_at
        FROM items
        WHERE status = 'open'
        ORDER BY created_at DESC LIMIT 10
    """)
    
    # Format time_ago
    for activity in recent_activities:
        activity['time_ago'] = activity['created_at'].strftime("%Y-%m-%d %H:%M")
        
    # ── Fetch Recently Resolved Matches ──
    resolved_stories = query_all("""
        SELECT m.id, m.score,
               lost.title as lost_title, found.title as found_title,
               m.created_at
        FROM item_matches m
        JOIN items lost ON m.lost_item_id = lost.id
        JOIN items found ON m.found_item_id = found.id
        WHERE lost.status = 'resolved' AND found.status = 'resolved'
        ORDER BY m.created_at DESC LIMIT 5
    """)
    for story in resolved_stories:
        story['time_ago'] = story['created_at'].strftime("%Y-%m-%d %H:%M")
        story['percentage'] = int(float(story['score']) * 100) if story['score'] else 0
    
    return render_template('dashboard.html', stats=stats, recent_activities=recent_activities, resolved_stories=resolved_stories)

@app.route('/my-posts')
@login_required
def my_posts():
    user_id = get_session_user_id()
    from services.db import query_all, query_one
    
    items = query_all("""
        (SELECT i.*, c.name as category_name, c.icon as category_icon, 
               u.first_name as user_name,
               (SELECT image_url FROM item_images img WHERE img.item_id = i.id ORDER BY is_primary DESC, sort_order ASC LIMIT 1) as primary_image
        FROM items i
        JOIN categories c ON i.category_id = c.id
        JOIN users u ON i.user_id = u.id
        WHERE i.user_id = %s AND i.status = 'open')
        UNION ALL
        (SELECT i.*, c.name as category_name, c.icon as category_icon, 
               u.first_name as user_name,
               (SELECT image_url FROM item_images img WHERE img.item_id = i.id ORDER BY is_primary DESC, sort_order ASC LIMIT 1) as primary_image
        FROM items i
        JOIN categories c ON i.category_id = c.id
        JOIN users u ON i.user_id = u.id
        WHERE i.user_id = %s AND i.status = 'resolved'
        ORDER BY i.created_at DESC LIMIT 3)
        ORDER BY created_at DESC
    """, (user_id, user_id))
    
    # Format time / dates and query matches
    for item in items:
        item['created_at'] = item['created_at'].strftime("%b %d, %Y")
        if item.get('incident_date'):
            item['incident_date'] = item['incident_date'].strftime("%Y-%m-%d")
            
        # Query matches for this post
        if item['type'] == 'lost':
            matches = query_all("""
                SELECT m.score, i.id as match_item_id, i.title as match_title, i.type as match_type, i.status as match_status
                FROM item_matches m
                JOIN items i ON m.found_item_id = i.id
                WHERE m.lost_item_id = %s
                ORDER BY m.score DESC
            """, (item['id'],))
        else:
            matches = query_all("""
                SELECT m.score, i.id as match_item_id, i.title as match_title, i.type as match_type, i.status as match_status
                FROM item_matches m
                JOIN items i ON m.lost_item_id = i.id
                WHERE m.found_item_id = %s
                ORDER BY m.score DESC
            """, (item['id'],))
            
        # Format match scores as percentage
        for match in matches:
            match['percentage'] = int(float(match['score']) * 100) if match['score'] else 0
            
        item['matches'] = matches
            
    return render_template('my_posts.html', items=items)





@app.route('/admin/users')
def admin_users():
    return render_template('admin/users.html')

@app.route('/admin/items')
def admin_items():
    return render_template('admin/items.html')

@app.route('/admin/claims')
def admin_claims():
    return render_template('admin/claims.html')

@app.route('/admin/settings')
def admin_settings():
    return render_template('admin/settings.html')

@app.route('/admin/categories')
def admin_categories():
    return render_template('admin/categories.html')

# (Mock routes removed, handled by items_bp)

# Dummy template filter
@app.template_filter('date_format')
def date_format(value): return value.strftime('%Y-%m-%d') if isinstance(value, datetime) else value

@app.after_request
def add_static_cache_headers(response):
    if request.path.startswith('/static/') and response.status_code == 200:
        if os.environ.get('FLASK_ENV', 'development') == 'development':
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        else:
            response.headers.setdefault('Cache-Control', 'public, max-age=86400')
    return response

if __name__ == '__main__':
    # Make static and template folders if they don't exist
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    os.makedirs('static/images', exist_ok=True)
    os.makedirs('templates/auth', exist_ok=True)
    os.makedirs('templates/admin', exist_ok=True)
    os.makedirs('templates/components', exist_ok=True)
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)
