document.addEventListener('DOMContentLoaded', () => {
    // Handle toggle ban user
    const toggleBanBtns = document.querySelectorAll('.toggle-ban-btn');
    
    toggleBanBtns.forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const userId = btn.getAttribute('data-user-id');
            if (confirm('Are you sure you want to toggle the ban status for this user?')) {
                try {
                    const response = await fetch(`/admin/users/${userId}/ban`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        const statusBadge = document.getElementById(`status-${userId}`);
                        if (data.is_active) {
                            statusBadge.className = 'badge badge-success';
                            statusBadge.textContent = 'Active';
                        } else {
                            statusBadge.className = 'badge badge-danger';
                            statusBadge.textContent = 'Banned';
                        }
                    } else {
                        alert(data.error || 'Failed to toggle ban status.');
                    }
                } catch (error) {
                    console.error('Error toggling ban:', error);
                    alert('An error occurred.');
                }
            }
        });
    });

    // Handle delete item
    const deleteItemBtns = document.querySelectorAll('.delete-item-btn');
    
    deleteItemBtns.forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const itemId = btn.getAttribute('data-item-id');
            if (confirm('Are you sure you want to delete this item? This action cannot be undone.')) {
                try {
                    const response = await fetch(`/admin/items/${itemId}/delete`, {
                        method: 'POST'
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        const row = document.getElementById(`item-row-${itemId}`);
                        row.remove();
                    } else {
                        alert(data.error || 'Failed to delete item.');
                    }
                } catch (error) {
                    console.error('Error deleting item:', error);
                    alert('An error occurred.');
                }
            }
        });
    });

    // Handle delete category
    const deleteCatBtns = document.querySelectorAll('.delete-cat-btn');
    
    deleteCatBtns.forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const catId = btn.getAttribute('data-cat-id');
            if (confirm('Are you sure you want to delete this category? Make sure no items are associated with it.')) {
                try {
                    const response = await fetch(`/admin/categories/${catId}/delete`, {
                        method: 'POST'
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        const row = document.getElementById(`cat-row-${catId}`);
                        row.remove();
                    } else {
                        alert(data.error || 'Failed to delete category.');
                    }
                } catch (error) {
                    console.error('Error deleting category:', error);
                    alert('An error occurred.');
                }
            }
        });
    });
});
