// Notifications Management & Live Polling

document.addEventListener('DOMContentLoaded', () => {
    // Perform initial count fetch and register polling
    updateUnreadCount();
    
    // Poll every 30 seconds
    setInterval(updateUnreadCount, 30000);
});

/**
 * Fetch latest unread count and update navbar badge.
 */
async function updateUnreadCount() {
    const badge = document.getElementById('notificationBadge');
    if (!badge) return;
    
    try {
        const response = await fetch('/notifications/unread-count');
        if (response.ok) {
            const data = await response.json();
            const count = data.unread_count || 0;
            
            if (count > 0) {
                badge.textContent = count;
                badge.style.display = 'inline-flex';
            } else {
                badge.style.display = 'none';
            }
        }
    } catch (err) {
        console.error('Failed to poll unread notifications count:', err);
    }
}

/**
 * Mark a single notification as read via AJAX POST.
 * @param {number} notifId - The ID of the notification.
 */
async function markAsRead(notifId) {
    const notifItem = document.getElementById(`notif-${notifId}`);
    if (!notifItem) return;
    
    try {
        const response = await fetch(`/notifications/mark-read/${notifId}`, {
            method: 'POST',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.status === 'success') {
                // Smoothly remove 'unread' styling class
                notifItem.classList.remove('unread');
                
                // Hide mark-as-read action button inside the item
                const readBtn = notifItem.querySelector('.notif-actions button[title="Mark as Read"]');
                if (readBtn) readBtn.remove();
                
                // Decrease unread count locally
                updateUnreadCount();
            } else {
                console.error('Error marking read:', data.message);
            }
        }
    } catch (err) {
        console.error('Network error marking read:', err);
    }
}
