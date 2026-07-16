import os
from datetime import datetime

from flask import Flask, render_template, request, session, redirect, url_for, flash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key_change_me_later')

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

# Mock Data
MOCK_USER = {
    'id': 1,
    'first_name': 'Prof',
    'last_name': 'Smith',
    'email': 'prof@university.edu'
}

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
        SELECT type, title as item_name, location_text as location, created_at
        FROM items
        ORDER BY created_at DESC LIMIT 5
    """)
    
    # Format time_ago in python or jinja. We will pass raw dates and use a simple filter.
    for activity in recent_activities:
        # Simple string formatting, a real app would use a proper humanize library
        activity['time_ago'] = activity['created_at'].strftime("%Y-%m-%d %H:%M")
    
    recent_notifications = [
        {'type': 'system', 'message': 'Welcome to Lost & Found Portal!', 'time_ago': 'Just now'}
    ]
    
    return render_template('dashboard.html', stats=stats, recent_activities=recent_activities, recent_notifications=recent_notifications)

@app.route('/chat')
def chat():
    contacts = [
        {'conversation_id': 1, 'other_user_name': 'Alice Smith', 'unread_count': 2, 'last_message': 'Is this your phone?', 'last_message_time': '10:30 AM'},
        {'conversation_id': 2, 'other_user_name': 'Bob Jones', 'unread_count': 0, 'last_message': 'Thanks for returning my keys.', 'last_message_time': 'Yesterday'}
    ]
    current_conv = {'id': 1, 'other_user_name': 'Alice Smith', 'item_id': 1, 'item_title': 'iPhone 13 Pro'}
    messages = [
        {'sender_id': 2, 'content': 'Hi, I saw your post about the iPhone.', 'created_at': '10:25 AM'},
        {'sender_id': session.get('user_id', 1), 'content': 'Yes! Did you find it?', 'created_at': '10:28 AM'},
        {'sender_id': 2, 'content': 'Is this your phone?', 'created_at': '10:30 AM'}
    ]
    return render_template('chat.html', contacts=contacts, current_conversation=current_conv, messages=messages)

@app.route('/my-posts')
@login_required
def my_posts():
    user_id = get_session_user_id()
    from services.db import query_all
    
    items = query_all("""
        SELECT i.*, c.name as category_name, c.icon as category_icon, 
               u.first_name as user_name,
               (SELECT image_url FROM item_images img WHERE img.item_id = i.id ORDER BY is_primary DESC, sort_order ASC LIMIT 1) as primary_image
        FROM items i
        JOIN categories c ON i.category_id = c.id
        JOIN users u ON i.user_id = u.id
        WHERE i.user_id = %s
        ORDER BY i.created_at DESC
    """, (user_id,))
    
    # Format time / dates
    for item in items:
        item['created_at'] = item['created_at'].strftime("%b %d, %Y")
        if item.get('incident_date'):
            item['incident_date'] = item['incident_date'].strftime("%Y-%m-%d")
            
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

if __name__ == '__main__':
    # Make static and template folders if they don't exist
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    os.makedirs('static/images', exist_ok=True)
    os.makedirs('templates/auth', exist_ok=True)
    os.makedirs('templates/admin', exist_ok=True)
    os.makedirs('templates/components', exist_ok=True)
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)
