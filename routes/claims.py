from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from services.db import query_all, query_one, execute, DatabaseError
from services.auth_service import login_required, get_session_user_id
from services.notification_service import notify_new_claim, notify_claim_status

claims_bp = Blueprint('claims', __name__)

@claims_bp.route('/my-claims')
@login_required
def my_claims():
    """
    Displays claims made BY the current user (Outgoing claims).
    """
    user_id = get_session_user_id()
    claims = query_all("""
        SELECT c.*, 
               i.title as item_title, i.type as item_type, 
               u.first_name as reporter_name
        FROM claim_requests c
        JOIN items i ON c.item_id = i.id
        JOIN users u ON c.reporter_id = u.id
        WHERE c.claimant_id = %s
        ORDER BY c.created_at DESC
    """, (user_id,))
    
    return render_template('my_claims.html', claims=claims)

@claims_bp.route('/claim-requests')
@login_required
def claim_requests():
    """
    Displays claims made ON the user's items (Incoming claims).
    """
    user_id = get_session_user_id()
    claims = query_all("""
        SELECT c.*, 
               i.title as item_title, i.type as item_type, 
               u.first_name as claimant_name
        FROM claim_requests c
        JOIN items i ON c.item_id = i.id
        JOIN users u ON c.claimant_id = u.id
        WHERE c.reporter_id = %s
        ORDER BY c.created_at DESC
    """, (user_id,))
    
    return render_template('claim_requests.html', claims=claims)

@claims_bp.route('/claim/<int:item_id>', methods=['POST'])
@login_required
def create_claim(item_id):
    """
    Submit a new claim request for a specific item.
    """
    user_id = get_session_user_id()
    description = request.form.get('description', '').strip()
    
    # Get the item to find the reporter
    item = query_one("SELECT user_id, title FROM items WHERE id = %s", (item_id,))
    if not item:
        flash("Item not found.", "error")
        return redirect(url_for('items.search'))
        
    reporter_id = item['user_id']
    
    if user_id == reporter_id:
        flash("You cannot claim your own item.", "warning")
        return redirect(url_for('items.item_detail', item_id=item_id))
        
    try:
        execute("""
            INSERT INTO claim_requests (item_id, claimant_id, reporter_id, description, status)
            VALUES (%s, %s, %s, %s, 'pending')
        """, (item_id, user_id, reporter_id, description))
        
        user = query_one("SELECT first_name FROM users WHERE id = %s", (user_id,))
        claimant_name = user['first_name'] if user else "Someone"
        notify_new_claim(reporter_id, claimant_name, item['title'], item_id)
        
        flash("Claim submitted successfully! The owner has been notified.", "success")
        
    except DatabaseError as e:
        # Check for duplicate claim via unique constraint
        if 'Duplicate entry' in str(e):
            flash("You have already submitted a claim for this item.", "warning")
        else:
            current_app.logger.error(f"Error creating claim: {e}")
            flash("An error occurred while submitting your claim.", "error")
            
    return redirect(url_for('items.item_detail', item_id=item_id))

@claims_bp.route('/claim/<int:claim_id>/update_status', methods=['POST'])
@login_required
def update_claim_status(claim_id):
    """
    Approve or reject a claim (must be the reporter of the item).
    """
    user_id = get_session_user_id()
    new_status = request.form.get('status') # 'approved' or 'rejected'
    reviewer_note = request.form.get('reviewer_note', '').strip()
    
    wants_json = request.headers.get('Accept') == 'application/json' or request.is_json
    
    if new_status not in ['approved', 'rejected']:
        if wants_json:
            return jsonify({'status': 'error', 'message': 'Invalid status update.'}), 400
        flash("Invalid status update.", "error")
        return redirect(url_for('claims.claim_requests'))
        
    claim = query_one("""
        SELECT c.reporter_id, c.item_id, c.claimant_id, i.title as item_title 
        FROM claim_requests c 
        JOIN items i ON c.item_id = i.id 
        WHERE c.id = %s
    """, (claim_id,))
    
    if not claim:
        if wants_json:
            return jsonify({'status': 'error', 'message': 'Claim not found.'}), 444
        flash("Claim not found.", "error")
        return redirect(url_for('claims.claim_requests'))
        
    if claim['reporter_id'] != user_id:
        if wants_json:
            return jsonify({'status': 'error', 'message': 'Unauthorized.'}), 403
        flash("You do not have permission to manage this claim.", "error")
        return redirect(url_for('claims.claim_requests'))
        
    try:
        execute("""
            UPDATE claim_requests 
            SET status = %s, reviewer_note = %s, reviewed_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (new_status, reviewer_note, claim_id))
        
        # If approved, we might also want to mark the item itself as resolved
        if new_status == 'approved':
            execute("UPDATE items SET status = 'resolved' WHERE id = %s", (claim['item_id'],))
            
            # Find counterpart matched item and resolve it too, marking match as verified
            claim_item = query_one("SELECT type FROM items WHERE id = %s", (claim['item_id'],))
            if claim_item:
                if claim_item['type'] == 'found':
                    matched_item = query_one("""
                        SELECT lost_item_id FROM item_matches m
                        JOIN items i ON m.lost_item_id = i.id
                        WHERE m.found_item_id = %s AND i.user_id = %s
                    """, (claim['item_id'], claim['claimant_id']))
                    if matched_item:
                        execute("UPDATE items SET status = 'resolved' WHERE id = %s", (matched_item['lost_item_id'],))
                else:
                    matched_item = query_one("""
                        SELECT found_item_id FROM item_matches m
                        JOIN items i ON m.found_item_id = i.id
                        WHERE m.lost_item_id = %s AND i.user_id = %s
                    """, (claim['item_id'], claim['claimant_id']))
                    if matched_item:
                        execute("UPDATE items SET status = 'resolved' WHERE id = %s", (matched_item['found_item_id'],))
            
        notify_claim_status(claim['claimant_id'], claim['item_title'], new_status, claim['item_id'])
            
        if wants_json:
            return jsonify({'status': 'success', 'message': f'Claim has been {new_status}.'})
            
        flash(f"Claim has been {new_status}.", "success")
        
    except DatabaseError as e:
        current_app.logger.error(f"Error updating claim {claim_id}: {e}")
        if wants_json:
            return jsonify({'status': 'error', 'message': 'Database error occurred.'}), 500
        flash("An error occurred while updating the claim.", "error")
        
    return redirect(url_for('claims.claim_requests'))
