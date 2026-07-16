/**
 * my-posts.js
 * handles tab filtering and delete warnings for the "My Posts" dashboard.
 */

document.addEventListener('DOMContentLoaded', () => {
    // ── Tab Filtering ───────────────────────────────────────────────────────
    const tabs = document.querySelectorAll('.tab-button');
    const postWrappers = document.querySelectorAll('.post-wrapper');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active class from all tabs
            tabs.forEach(t => t.classList.remove('active'));
            // Add active class to clicked tab
            tab.classList.add('active');

            const filterValue = tab.getAttribute('data-filter');

            postWrappers.forEach(post => {
                const status = post.getAttribute('data-status');

                if (filterValue === 'all') {
                    post.style.display = 'block';
                } else if (filterValue === 'open' && status === 'open') {
                    post.style.display = 'block';
                } else if (filterValue === 'resolved' && status === 'resolved') {
                    post.style.display = 'block';
                } else {
                    post.style.display = 'none';
                }
            });
        });
    });

    // ── Safe Delete Confirmations ──────────────────────────────────────────
    const deleteBtns = document.querySelectorAll('.delete-btn');

    deleteBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const form = btn.closest('.delete-form');
            if (form) {
                const confirmed = confirm('Are you sure you want to permanently delete this item? This action cannot be undone.');
                if (confirmed) {
                    form.submit();
                }
            }
        });
    });
});
