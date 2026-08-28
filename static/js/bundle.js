/* js/app.js */
/**
 * app.js
 * Core application interactions (sidebar toggle, dropdowns, generic UI logic)
 */

document.addEventListener('DOMContentLoaded', () => {
    // ── Sidebar Toggle Logic ────────────────────────────────────────────────
    const sidebarToggleBtn = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    const sidebarBackdrop = document.getElementById('sidebarBackdrop');

    if (sidebarToggleBtn && sidebar) {
        sidebarToggleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            if (window.innerWidth > 992) {
                // Desktop toggle
                document.body.classList.toggle('sidebar-collapsed');
            } else {
                // Mobile toggle
                sidebar.classList.toggle('show');
                if (sidebarBackdrop) {
                    sidebarBackdrop.classList.toggle('show');
                }
            }
        });

        // Close sidebar when clicking backdrop on mobile
        if (sidebarBackdrop) {
            sidebarBackdrop.addEventListener('click', () => {
                sidebar.classList.remove('show');
                sidebarBackdrop.classList.remove('show');
            });
        }

        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 992 && sidebar.classList.contains('show')) {
                if (!sidebar.contains(e.target) && !sidebarToggleBtn.contains(e.target) && (!sidebarBackdrop || !sidebarBackdrop.contains(e.target))) {
                    sidebar.classList.remove('show');
                    if (sidebarBackdrop) {
                        sidebarBackdrop.classList.remove('show');
                    }
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

let lastUnreadCount = parseInt(localStorage.getItem('lastUnreadCount') || '0', 10);

document.addEventListener('DOMContentLoaded', () => {
    // Perform initial count fetch and register polling
    updateUnreadCount();
    
    // Poll every 15 seconds
    setInterval(updateUnreadCount, 15000);
});

/**
 * Show a styled toast alert when a new notification is received.
 */
function showNotificationToast() {
    let toast = document.getElementById('notifToast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'notifToast';
        toast.style.cssText = `
            position: fixed;
            bottom: 24px;
            right: 24px;
            background-color: var(--primary, #1251e6);
            color: white;
            padding: 14px 24px;
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(18, 81, 230, 0.25);
            display: flex;
            align-items: center;
            gap: 14px;
            z-index: 9999;
            transform: translateY(120px);
            opacity: 0;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            cursor: pointer;
            font-family: 'Poppins', sans-serif;
        `;
        toast.innerHTML = `
            <div style="font-size: 1.5rem; display: flex; align-items: center;">
                <i class="fas fa-bell fa-shake" style="animation: fa-shake 1.5s infinite linear;"></i>
            </div>
            <div>
                <strong style="display: block; font-size: 0.9rem; font-weight: 600;">New Notification</strong>
                <span style="font-size: 0.8rem; opacity: 0.9; white-space: nowrap;">You have new matching items/claims!</span>
            </div>
        `;
        toast.addEventListener('click', () => {
            window.location.href = '/notifications';
        });
        document.body.appendChild(toast);
    }
    
    // Show toast
    setTimeout(() => {
        toast.style.transform = 'translateY(0)';
        toast.style.opacity = '1';
    }, 100);
    
    // Auto-hide after 6 seconds
    setTimeout(() => {
        toast.style.transform = 'translateY(120px)';
        toast.style.opacity = '0';
    }, 6000);
}

/**
 * Fetch latest unread count and update navbar badge.
 */
async function updateUnreadCount() {
    const badge = document.getElementById('notificationBadge');
    if (!badge) return;
    
    try {
        const response = await fetch('/notifications/unread-count', {
            cache: 'no-store'
        });
        if (response.ok) {
            const data = await response.json();
            const count = data.unread_count || 0;
            
            if (count > 0) {
                badge.textContent = count;
                badge.style.display = 'inline-flex';
                
                // If unread notifications increased, trigger toast
                if (count > lastUnreadCount) {
                    showNotificationToast();
                }
            } else {
                badge.style.display = 'none';
            }
            
            lastUnreadCount = count;
            localStorage.setItem('lastUnreadCount', count);
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


