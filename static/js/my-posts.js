/**
 * my-posts.js
 * handles tab & button filtering and delete warnings for the "My Posts" dashboard.
 */

document.addEventListener('DOMContentLoaded', () => {
    // ── Tab & Button Filtering ─────────────────────────────────────────────
    const typeTabs = document.querySelectorAll('.type-tab');
    const statusBtns = document.querySelectorAll('.status-filter-btn');
    const postWrappers = document.querySelectorAll('.post-wrapper');

    let currentType = 'all';
    let currentStatus = 'all';

    function filterPosts() {
        postWrappers.forEach(post => {
            const postType = post.getAttribute('data-type');
            const postStatus = post.getAttribute('data-status');

            const typeMatch = (currentType === 'all' || postType === currentType);
            const statusMatch = (currentStatus === 'all' || postStatus === currentStatus);

            if (typeMatch && statusMatch) {
                post.style.display = 'block';
            } else {
                post.style.display = 'none';
            }
        });
    }

    typeTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            typeTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            currentType = tab.getAttribute('data-type-filter');
            filterPosts();
        });
    });

    statusBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            statusBtns.forEach(b => {
                b.classList.remove('btn-primary');
                b.classList.add('btn-outline-primary');
            });
            btn.classList.remove('btn-outline-primary');
            btn.classList.add('btn-primary');

            currentStatus = btn.getAttribute('data-status-filter');
            filterPosts();
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
