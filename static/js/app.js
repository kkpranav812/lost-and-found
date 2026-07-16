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
            // On mobile, this toggles the 'show' class
            sidebar.classList.toggle('show');
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

    // ── Tooltips initialization (Optional) ──────────────────────────────────
    // If you plan to add tooltips manually later, place init logic here.
});
