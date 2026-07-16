/**
 * dashboard.js
 * Interactive scripts for user dashboard (Stat animations, auto-refresh options)
 */

document.addEventListener('DOMContentLoaded', () => {
    // ── Stat Counter Animation ──────────────────────────────────────────────
    const animateStats = () => {
        const values = document.querySelectorAll('.stat-value');
        values.forEach(val => {
            const target = parseInt(val.textContent, 10);
            if (isNaN(target) || target === 0) return;
            
            let count = 0;
            const duration = 1000; // 1 second
            const speed = Math.ceil(target / (duration / 16)); // ~60fps
            
            const counter = setInterval(() => {
                count += speed;
                if (count >= target) {
                    val.textContent = target;
                    clearInterval(counter);
                } else {
                    val.textContent = count;
                }
            }, 16);
        });
    };

    animateStats();

    // ── Quick Guide Button Action ───────────────────────────────────────────
    const guideBtn = document.querySelector('.card.bg-primary button');
    if (guideBtn) {
        guideBtn.addEventListener('click', () => {
            alert('Opening Safety Handover Guide... (Feature under development)');
        });
    }
});
