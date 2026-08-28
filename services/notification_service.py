from services.db import execute, DatabaseError
from flask import current_app

def create_notification(user_id, notif_type, title, body=None, item_id=None, conversation_id=None):
    """
    Creates a new notification in the database.
    
    :param user_id: ID of the user receiving the notification
    :param notif_type: ENUM string matching DB allowed types (e.g., 'new_claim', 'claim_approved')
    :param title: Notification headline
    :param body: Detailed description
    :param item_id: Optional related item ID for deep-linking
    :param conversation_id: Optional related conversation ID for deep-linking
    """
    try:
        execute("""
            INSERT INTO notifications (user_id, type, title, body, item_id, conversation_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, notif_type, title, body, item_id, conversation_id))
        return True
    except DatabaseError as e:
        if current_app:
            current_app.logger.error(f"Error creating notification: {e}")
        return False

def notify_new_claim(reporter_id, claimant_name, item_title, item_id):
    title = f"New claim on '{item_title}'"
    body = f"{claimant_name} has submitted a claim on this item. Please review the claim details."
    return create_notification(reporter_id, 'new_claim', title, body, item_id=item_id)

def notify_claim_status(claimant_id, item_title, status, item_id):
    title = f"Claim {status.capitalize()}"
    body = f"Your claim for '{item_title}' has been {status} by the reporter."
    notif_type = 'claim_approved' if status == 'approved' else 'claim_rejected'
    return create_notification(claimant_id, notif_type, title, body, item_id=item_id)

def notify_match_found(user_id, item_title, matched_title, item_id):
    title = "Potential Match Found!"
    body = f"We found a potential match for your item '{item_title}'. Could it be '{matched_title}'?"
    return create_notification(user_id, 'match_found', title, body, item_id=item_id)

def notify_new_message(recipient_id, sender_name, conversation_id):
    title = f"New message from {sender_name}"
    body = "You have received a new chat message."
    return create_notification(recipient_id, 'new_message', title, body, conversation_id=conversation_id)
