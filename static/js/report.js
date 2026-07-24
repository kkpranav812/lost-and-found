/**
 * report.js
 * Handles drag-and-drop file uploads, image previews with removal,
 * and geolocation tagging for the Report Lost and Report Found forms.
 */

document.addEventListener('DOMContentLoaded', () => {
    // ── File Upload Drag & Drop & Previews with Removal ──────────────────
    const uploadWrapper = document.querySelector('.image-upload-wrapper');
    const imageInput = document.getElementById('imageInput');
    const fileListContainer = document.getElementById('fileList');
    const reportForm = document.querySelector('form[enctype="multipart/form-data"]');
    const submitBtn = reportForm ? reportForm.querySelector('button[type="submit"]') : null;

    // Track selected files in an array so we can remove individual items
    let selectedFiles = [];

    function syncInputFiles() {
        const dt = new DataTransfer();
        selectedFiles.forEach(f => dt.items.add(f));
        imageInput.files = dt.files;
    }

    function renderPreviews() {
        fileListContainer.innerHTML = '';
        if (selectedFiles.length === 0) return;

        const grid = document.createElement('div');
        grid.style.cssText = `
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
            gap: 10px;
            margin-top: 15px;
        `;

        selectedFiles.forEach((file, index) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                // Outer wrapper — relative position for ×-button
                const wrapper = document.createElement('div');
                wrapper.style.cssText = `
                    position: relative;
                    padding-top: 100%;
                    border-radius: var(--radius-sm, 6px);
                    overflow: hidden;
                    border: 1px solid var(--border-color, #e2e8f0);
                    background: #f8fafc;
                `;

                // Thumbnail image
                const img = document.createElement('img');
                img.src = e.target.result;
                img.alt = file.name;
                img.style.cssText = `
                    position: absolute;
                    top: 0; left: 0;
                    width: 100%; height: 100%;
                    object-fit: cover;
                `;

                // Remove button (×)
                const removeBtn = document.createElement('button');
                removeBtn.type = 'button';
                removeBtn.title = 'Remove image';
                removeBtn.textContent = '×';
                removeBtn.style.cssText = `
                    position: absolute;
                    top: 4px; right: 4px;
                    width: 22px; height: 22px;
                    border-radius: 50%;
                    border: none;
                    background: rgba(15,23,42,0.75);
                    color: #fff;
                    font-size: 14px;
                    line-height: 1;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 10;
                    transition: background 0.15s;
                `;
                removeBtn.onmouseenter = () => removeBtn.style.background = 'rgba(220,38,38,0.9)';
                removeBtn.onmouseleave = () => removeBtn.style.background = 'rgba(15,23,42,0.75)';
                removeBtn.addEventListener('click', () => {
                    selectedFiles.splice(index, 1);
                    syncInputFiles();
                    renderPreviews();
                });

                // File name label
                const label = document.createElement('div');
                label.style.cssText = `
                    position: absolute;
                    bottom: 0; left: 0; right: 0;
                    background: rgba(15,23,42,0.55);
                    color: #fff;
                    font-size: 0.65rem;
                    padding: 2px 4px;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                `;
                label.textContent = file.name;

                wrapper.appendChild(img);
                wrapper.appendChild(removeBtn);
                wrapper.appendChild(label);
                grid.appendChild(wrapper);
            };
            reader.readAsDataURL(file);
        });

        // Upload count badge
        const badge = document.createElement('div');
        badge.style.cssText = 'margin-top: 8px; font-size: 0.8rem; color: var(--text-muted, #64748b);';
        badge.textContent = `${selectedFiles.length} / 5 image${selectedFiles.length !== 1 ? 's' : ''} selected`;

        fileListContainer.appendChild(grid);
        fileListContainer.appendChild(badge);
    }

    if (uploadWrapper && imageInput) {
        // Drag events
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(ev => {
            uploadWrapper.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); }, false);
        });

        ['dragenter', 'dragover'].forEach(ev => {
            uploadWrapper.addEventListener(ev, () => {
                uploadWrapper.style.borderColor = 'var(--primary, #4F46E5)';
                uploadWrapper.style.backgroundColor = 'var(--primary-light, #ede9fe)';
            });
        });
        ['dragleave', 'drop'].forEach(ev => {
            uploadWrapper.addEventListener(ev, () => {
                uploadWrapper.style.borderColor = '#cbd5e1';
                uploadWrapper.style.backgroundColor = '#f8fafc';
            });
        });

        uploadWrapper.addEventListener('drop', (e) => {
            const dropped = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
            addFiles(dropped);
        }, false);

        imageInput.addEventListener('change', function () {
            addFiles(Array.from(this.files));
            // Reset so the same file can be re-selected after removal
            this.value = '';
        });
    }

    function addFiles(newFiles) {
        newFiles.forEach(file => {
            if (selectedFiles.length >= 5) {
                alert('Maximum 5 images allowed. Extra files were ignored.');
                return;
            }
            if (file.size > 5 * 1024 * 1024) {
                alert(`"${file.name}" is larger than 5 MB and was skipped.`);
                return;
            }
            selectedFiles.push(file);
        });
        syncInputFiles();
        renderPreviews();
    }

    // ── Loading Overlay on Submit ────────────────────────────────────────
    if (reportForm) {
        reportForm.addEventListener('submit', (e) => {
            // Basic client-side validation before showing spinner
            const title = reportForm.querySelector('#title');
            const category = reportForm.querySelector('#category_id');
            const location = reportForm.querySelector('#location');

            if (!title?.value.trim() || !category?.value || !location?.value.trim()) {
                // Let browser handle the required-field validation
                return;
            }

            // Show upload overlay
            const overlay = document.getElementById('uploadOverlay');
            if (overlay) {
                overlay.style.display = 'flex';
            }

            // Disable submit to prevent double-submit
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Uploading…';
            }
        });
    }
});
