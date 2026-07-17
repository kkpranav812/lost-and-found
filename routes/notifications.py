from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app
from services.db import query_all, query_one, execute, DatabaseError
from services.auth_service import login_required, get_session_user_id

notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('/notifications')
@login_required
def list_notifications():
    """
    Renders notifications page for the logged-in user.
    """
    user_id = get_session_user_id()
    notifications = query_all("""
        SELECT * FROM notifications
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (user_id,))
    
    return render_template('notifications.html', notifications=notifications)

@notifications_bp.route('/notifications/unread-count')
@login_required
def unread_count():
    """
    Returns unread count as JSON for navbar updates.
    """
    user_id = get_session_user_id()
    res = query_one("""
        SELECT COUNT(*) as cnt FROM notifications
        WHERE user_id = %s AND is_read = 0
    """, (user_id,))
    return jsonify({'unread_count': res['cnt'] if res else 0})

@notifications_bp.route('/notifications/mark-read/<int:notif_id>', methods=['POST'])
@login_required
def mark_read(notif_id):
    """
    Marks a single notification as read.
    """
    user_id = get_session_user_id()
    try:
        execute("""
            UPDATE notifications 
            SET is_read = 1 
            WHERE id = %s AND user_id = %s
        """, (notif_id, user_id))
        return jsonify({'status': 'success'})
    except DatabaseError as e:
        current_app.logger.error(f"Error marking notification {notif_id} as read: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@notifications_bp.route('/notifications/clear-all', methods=['POST'])
@login_required
def clear_all():
    """
    Deletes all notifications for the user.
    """
    user_id = get_session_user_id()
    try:
        execute("""
            DELETE FROM notifications 
            WHERE user_id = %s
        """, (user_id,))
        flash("All notifications cleared.", "success")
        return redirect(url_for('notifications.list_notifications'))
    except DatabaseError as e:
        current_app.logger.error(f"Error clearing all notifications: {e}")
        flash("Could not clear notifications.", "error")
        return redirect(url_for('notifications.list_notifications'))

@notifications_bp.route('/notifications/delete/<int:notif_id>', methods=['POST'])
@login_required
def delete_notification(notif_id):
    """
    Deletes a notification.
    """
    user_id = get_session_user_id()
    try:
        execute("""
            DELETE FROM notifications 
            WHERE id = %s AND user_id = %s
        """, (notif_id, user_id))
        flash("Notification deleted.", "success")
    except DatabaseError as e:
        current_app.logger.error(f"Error deleting notification {notif_id}: {e}")
        flash("Could not delete notification.", "error")
        
    return redirect(url_for('notifications.list_notifications'))
