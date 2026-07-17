from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from flask_socketio import emit, join_room, leave_room
from extensions import socketio
from services.db import query_all, query_one, execute
from services.auth_service import login_required, get_session_user_id
from datetime import datetime

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/chat')
@login_required
def index():
    user_id = get_session_user_id()
    
    # Fetch all conversations for the user
    query = """
        SELECT c.*, i.title as item_title, i.status as item_status, (SELECT image_url FROM item_images img WHERE img.item_id = i.id ORDER BY is_primary DESC, sort_order ASC LIMIT 1) as primary_image,
               u1.first_name as u1_first, u1.last_name as u1_last, u1.id as u1_id,
               u2.first_name as u2_first, u2.last_name as u2_last, u2.id as u2_id,
               (SELECT content FROM messages m WHERE m.conversation_id = c.id ORDER BY created_at DESC LIMIT 1) as last_message,
               (SELECT created_at FROM messages m WHERE m.conversation_id = c.id ORDER BY created_at DESC LIMIT 1) as last_message_time
        FROM conversations c
        JOIN items i ON c.item_id = i.id
        JOIN users u1 ON c.user_one_id = u1.id
        JOIN users u2 ON c.user_two_id = u2.id
        WHERE c.user_one_id = %s OR c.user_two_id = %s
        ORDER BY c.last_message_at DESC
    """
    conversations_raw = query_all(query, (user_id, user_id))
    
    # Process for the template
    conversations = []
    for c in conversations_raw:
        other_user_id = c['u2_id'] if c['u1_id'] == user_id else c['u1_id']
        other_user_name = f"{c['u2_first']} {c['u2_last']}" if c['u1_id'] == user_id else f"{c['u1_first']} {c['u1_last']}"
        
        conversations.append({
            'id': c['id'],
            'item_id': c['item_id'],
            'item_title': c['item_title'],
            'item_status': c['item_status'],
            'primary_image': c['primary_image'],
            'other_user_id': other_user_id,
            'other_user_name': other_user_name,
            'last_message': c['last_message'],
            'last_message_time': c['last_message_time'] or c['created_at'],
            'is_active': False
        })
        
    return render_template('chat.html', conversations=conversations, active_conversation=None)

@chat_bp.route('/chat/<int:conversation_id>')
@login_required
def view_chat(conversation_id):
    user_id = get_session_user_id()
    
    # Same query to fetch conversations
    query = """
        SELECT c.*, i.title as item_title, i.status as item_status,
               (SELECT image_url FROM item_images img WHERE img.item_id = i.id ORDER BY is_primary DESC, sort_order ASC LIMIT 1) as primary_image,
               u1.first_name as u1_first, u1.last_name as u1_last, u1.id as u1_id,
               u2.first_name as u2_first, u2.last_name as u2_last, u2.id as u2_id,
               (SELECT content FROM messages m WHERE m.conversation_id = c.id ORDER BY created_at DESC LIMIT 1) as last_message,
               (SELECT created_at FROM messages m WHERE m.conversation_id = c.id ORDER BY created_at DESC LIMIT 1) as last_message_time
        FROM conversations c
        JOIN items i ON c.item_id = i.id
        JOIN users u1 ON c.user_one_id = u1.id
        JOIN users u2 ON c.user_two_id = u2.id
        WHERE c.user_one_id = %s OR c.user_two_id = %s
        ORDER BY c.last_message_at DESC
    """
    conversations_raw = query_all(query, (user_id, user_id))
    
    conversations = []
    active_conversation = None
    
    for c in conversations_raw:
        other_user_id = c['u2_id'] if c['u1_id'] == user_id else c['u1_id']
        other_user_name = f"{c['u2_first']} {c['u2_last']}" if c['u1_id'] == user_id else f"{c['u1_first']} {c['u1_last']}"
        
        conv = {
            'id': c['id'],
            'item_id': c['item_id'],
            'item_title': c['item_title'],
            'item_status': c['item_status'],
            'primary_image': c['primary_image'],
            'other_user_id': other_user_id,
            'other_user_name': other_user_name,
            'last_message': c['last_message'],
            'last_message_time': c['last_message_time'] or c['created_at'],
            'is_active': (c['id'] == conversation_id)
        }
        conversations.append(conv)
        if conv['is_active']:
            active_conversation = conv

    if not active_conversation:
        flash("Conversation not found or you don't have access.", "danger")
        return redirect(url_for('chat.index'))

    # Fetch messages
    messages = query_all("""
        SELECT m.*, u.first_name, u.last_name
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        WHERE m.conversation_id = %s
        ORDER BY m.created_at ASC
    """, (conversation_id,))
    
    # Mark messages as read
    execute("""
        UPDATE messages 
        SET is_read = 1 
        WHERE conversation_id = %s AND sender_id != %s AND is_read = 0
    """, (conversation_id, user_id))

    return render_template('chat.html', conversations=conversations, active_conversation=active_conversation, messages=messages, current_user_id=user_id)

@chat_bp.route('/chat/start/<int:item_id>')
@login_required
def start_chat(item_id):
    user_id = get_session_user_id()
    
    # Get item
    item = query_one("SELECT * FROM items WHERE id = %s", (item_id,))
    if not item:
        flash("Item not found.", "danger")
        return redirect(url_for('items.index'))
        
    if item['user_id'] == user_id:
        flash("You cannot start a chat with yourself about your own item.", "warning")
        return redirect(url_for('items.item_detail', id=item_id))
        
    # Check if conversation already exists
    # Make sure we check both permutations of user1, user2
    user_one_id = min(user_id, item['user_id'])
    user_two_id = max(user_id, item['user_id'])
    
    conv = query_one("""
        SELECT id FROM conversations 
        WHERE item_id = %s AND user_one_id = %s AND user_two_id = %s
    """, (item_id, user_one_id, user_two_id))
    
    if conv:
        return redirect(url_for('chat.view_chat', conversation_id=conv['id']))
        
    # Create new conversation
    conv_id = execute("""
        INSERT INTO conversations (item_id, user_one_id, user_two_id)
        VALUES (%s, %s, %s)
    """, (item_id, user_one_id, user_two_id), return_lastrowid=True)
    
    return redirect(url_for('chat.view_chat', conversation_id=conv_id))

# --- Socket.IO Events ---

@socketio.on('join')
def on_join(data):
    if 'user_id' not in session:
        return False # Unauthorized
        
    conversation_id = data.get('conversation_id')
    if not conversation_id:
        return False
        
    # Verify user has access to this conversation
    user_id = session['user_id']
    conv = query_one("""
        SELECT id FROM conversations 
        WHERE id = %s AND (user_one_id = %s OR user_two_id = %s)
    """, (conversation_id, user_id, user_id))
    
    if conv:
        room = f"conversation_{conversation_id}"
        join_room(room)
        emit('status', {'msg': 'User joined the room.'}, room=room)

@socketio.on('send_message')
def handle_message(data):
    if 'user_id' not in session:
        return False
        
    user_id = session['user_id']
    conversation_id = data.get('conversation_id')
    content = data.get('content', '').strip()
    
    if not conversation_id or not content:
        return False
        
    # Verify access
    conv = query_one("""
        SELECT * FROM conversations 
        WHERE id = %s AND (user_one_id = %s OR user_two_id = %s)
    """, (conversation_id, user_id, user_id))
    
    if not conv:
        return False
        
    # Insert message
    msg_id = execute("""
        INSERT INTO messages (conversation_id, sender_id, content)
        VALUES (%s, %s, %s)
    """, (conversation_id, user_id, content))
    
    # Update conversation last_message_at
    execute("""
        UPDATE conversations 
        SET last_message_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """, (conversation_id,))
    
    # Fetch sender info for frontend
    sender = query_one("SELECT first_name, last_name FROM users WHERE id = %s", (user_id,))
    
    # Broadcast to room
    room = f"conversation_{conversation_id}"
    emit('receive_message', {
        'id': msg_id,
        'conversation_id': conversation_id,
        'sender_id': user_id,
        'sender_name': f"{sender['first_name']} {sender['last_name']}",
        'content': content,
        'created_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    }, room=room)
    
    # Optional notification
    recipient_id = conv['user_two_id'] if conv['user_one_id'] == user_id else conv['user_one_id']
    
    try:
        from services.notification_service import create_notification
        create_notification(
            user_id=recipient_id,
            notif_type='new_message',
            title=f"New message from {sender['first_name']}",
            body="You have received a new chat message.",
            conversation_id=conversation_id
        )
    except Exception as e:
        print("Failed to send notification:", e)

@socketio.on('typing')
def handle_typing(data):
    if 'user_id' not in session:
        return False
        
    conversation_id = data.get('conversation_id')
    is_typing = data.get('is_typing', False)
    
    if conversation_id:
        room = f"conversation_{conversation_id}"
        emit('typing_status', {
            'user_id': session['user_id'],
            'is_typing': is_typing
        }, room=room, include_self=False)
