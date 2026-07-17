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

def check_and_notify_matches(new_item_id) -> int:
    """
    Scans the database for potential matches for the newly created item.
    If high-confidence matches are found, it stores them in the item_matches table
    and notifies both owners. Returns the number of matches found.
    """
    from services.db import query_one, query_all
    
    # 1. Fetch the details of the new item
    new_item = query_one("""
        SELECT id, user_id, title, description, type, category_id
        FROM items WHERE id = %s
    """, (new_item_id,))
    if not new_item:
        return 0

    # 2. Query open candidate items of the opposite type in the same category
    opposite_type = 'found' if new_item['type'] == 'lost' else 'lost'
    candidates = query_all("""
        SELECT id, user_id, title, description
        FROM items
        WHERE type = %s AND category_id = %s AND status = 'open' AND user_id != %s
    """, (opposite_type, new_item['category_id'], new_item['user_id']))

    # Helper function to compute word overlap
    def calculate_score(text1, text2):
        words1 = set(w for w in text1.lower().split() if len(w) >= 3)
        words2 = set(w for w in text2.lower().split() if len(w) >= 3)
        if not words1 or not words2:
            return 0.0
        intersection = words1.intersection(words2)
        return len(intersection) / max(len(words1), len(words2))

    matches_count = 0
    for candidate in candidates:
        title_score = calculate_score(new_item['title'], candidate['title'])
        desc_score = calculate_score(new_item['description'], candidate['description'])
        score = (title_score * 0.6) + (desc_score * 0.4)
        
        # 0.15 is a reasonable word overlap threshold
        if score >= 0.15:
            lost_item_id = new_item['id'] if new_item['type'] == 'lost' else candidate['id']
            found_item_id = new_item['id'] if new_item['type'] == 'found' else candidate['id']
            
            lost_owner_id = new_item['user_id'] if new_item['type'] == 'lost' else candidate['user_id']
            found_owner_id = new_item['user_id'] if new_item['type'] == 'found' else candidate['user_id']
            
            lost_title = new_item['title'] if new_item['type'] == 'lost' else candidate['title']
            found_title = new_item['title'] if new_item['type'] == 'found' else candidate['title']
            
            try:
                execute("""
                    INSERT INTO item_matches (lost_item_id, found_item_id, score, notified)
                    VALUES (%s, %s, %s, 1)
                    ON DUPLICATE KEY UPDATE score = VALUES(score)
                """, (lost_item_id, found_item_id, score))
                
                # Notify both sides
                notify_match_found(lost_owner_id, lost_title, found_title, lost_item_id)
                notify_match_found(found_owner_id, found_title, lost_title, found_item_id)
                matches_count += 1
            except DatabaseError as e:
                if current_app:
                    current_app.logger.error(f"Error saving match: {e}")
                    
    return matches_count
