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
