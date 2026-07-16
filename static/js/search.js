/**
 * search.js
 * Handles client-side micro-interactions and instant filter submit for browse list.
 */

document.addEventListener('DOMContentLoaded', () => {
    const filterForm = document.getElementById('filterForm');
    const mainSearchForm = document.getElementById('mainSearchForm');

    // Automatically submit filter form when radio buttons are changed
    if (filterForm) {
        const radios = filterForm.querySelectorAll('input[type="radio"]');
        radios.forEach(radio => {
            radio.addEventListener('change', () => {
                filterForm.submit();
            });
        });
    }

    // Capture category selects in search bar to dynamically set filters
    const categorySelect = document.querySelector('.main-search-form select');
    if (categorySelect && filterForm) {
        categorySelect.addEventListener('change', () => {
            // Find corresponding input inside main filter form to mirror the search select
            const categoryInput = filterForm.querySelector('input[name="category"]');
            if (categoryInput) {
                categoryInput.value = categorySelect.value;
            }
            mainSearchForm.submit();
        });
    }
});
