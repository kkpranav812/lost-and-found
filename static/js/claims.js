document.addEventListener('DOMContentLoaded', () => {
    const forms = document.querySelectorAll('.claim-card form');
    
    forms.forEach(form => {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const claimId = form.querySelector('input[type="hidden"]').id.split('-')[1];
            const status = document.getElementById('status-' + claimId).value;
            const reviewerNote = form.querySelector('textarea').value;
            
            const submitBtn = form.querySelector('button[type="submit"]');
            const originalBtnText = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Submitting...';
            
            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    headers: {
                        'Accept': 'application/json',
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    body: new URLSearchParams({
                        'status': status,
                        'reviewer_note': reviewerNote
                    })
                });
                
                const data = await response.json();
                
                if (response.ok && data.status === 'success') {
                    // Find the card container
                    const card = document.querySelector(`.claim-card[data-claim-id="${claimId}"]`);
                    
                    // Update the status badge in the header
                    const headerBadge = card.querySelector('.claim-card-header .badge');
                    headerBadge.className = 'badge ' + (status === 'approved' ? 'badge-success' : 'badge-danger');
                    headerBadge.textContent = status.charAt(0).toUpperCase() + status.slice(1);
                    
                    // Remove actions footer
                    const actions = document.getElementById('actions-' + claimId);
                    if (actions) actions.remove();
                    
                    // Replace decision panel content with the finalized note view
                    const decisionPanel = document.getElementById('decision-panel-' + claimId);
                    if (decisionPanel) {
                        decisionPanel.className = 'mt-2 p-2 rounded bg-light';
                        decisionPanel.style.border = '1px solid var(--border-color)';
                        decisionPanel.style.fontSize = '0.9rem';
                        decisionPanel.style.display = 'block';
                        decisionPanel.innerHTML = `
                            <strong class="d-block mb-1 text-muted" style="font-size: 0.8rem;">Your Note:</strong>
                            <p class="m-0 text-muted" style="font-style: italic;">"${reviewerNote || 'No message provided.'}"</p>
                        `;
                    }
                    
                    // Show a transient premium-feeling message instead of standard alert
                    showToast(data.message || `Claim successfully ${status}!`, 'success');
                } else {
                    showToast(data.message || 'An error occurred while updating the claim.', 'error');
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalBtnText;
                }
            } catch (err) {
                console.error('API Error:', err);
                showToast('A connection error occurred. Please try again.', 'error');
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnText;
            }
        });
    });
});

// Helper for UI feedback
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} fade-in`;
    toast.style.position = 'fixed';
    toast.style.bottom = '20px';
    toast.style.right = '20px';
    toast.style.zIndex = '9999';
    toast.style.boxShadow = 'var(--shadow-lg)';
    toast.style.minWidth = '250px';
    toast.innerHTML = message;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.5s ease';
        setTimeout(() => toast.remove(), 500);
    }, 4000);
}
