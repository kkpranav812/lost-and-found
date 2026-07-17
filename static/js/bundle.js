/* js/app.js */
/**
 * app.js
 * Core application interactions (sidebar toggle, dropdowns, generic UI logic)
 */

document.addEventListener('DOMContentLoaded', () => {
    // ── Sidebar Toggle Logic ────────────────────────────────────────────────
    const sidebarToggleBtn = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');

    if (sidebarToggleBtn && sidebar) {
        sidebarToggleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            if (window.innerWidth > 992) {
                // Desktop toggle
                document.body.classList.toggle('sidebar-collapsed');
            } else {
                // Mobile toggle
                sidebar.classList.toggle('show');
            }
        });

        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 992 && sidebar.classList.contains('show')) {
                if (!sidebar.contains(e.target) && !sidebarToggleBtn.contains(e.target)) {
                    sidebar.classList.remove('show');
                }
            }
        });
    }

    // ── Flash Messages Auto-dismiss ─────────────────────────────────────────
    const flashAlerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    flashAlerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(() => {
                if(alert.parentNode) alert.parentNode.removeChild(alert);
            }, 500);
        }, 4000);
    });

    // ── User Dropdown Toggle ────────────────────────────────────────────────
    const userDropdownBtn = document.getElementById('userDropdownBtn');
    const userDropdownMenu = document.getElementById('userDropdownMenu');

    if (userDropdownBtn && userDropdownMenu) {
        userDropdownBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isVisible = userDropdownMenu.style.display === 'block';
            userDropdownMenu.style.display = isVisible ? 'none' : 'block';
        });

        document.addEventListener('click', () => {
            userDropdownMenu.style.display = 'none';
        });
    }

    // ── Tooltips initialization (Optional) ──────────────────────────────────
    // If you plan to add tooltips manually later, place init logic here.
});


/* js/notifications.js */
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


