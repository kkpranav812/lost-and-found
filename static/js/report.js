/**
 * report.js
 * Handles drag-and-drop file uploads, image previews, and geolocation tagging
 * for the Report Lost and Report Found forms.
 */

document.addEventListener('DOMContentLoaded', () => {
    // ── File Upload Drag & Drop & Previews ─────────────────────────────
    const uploadWrapper = document.querySelector('.image-upload-wrapper');
    const imageInput = document.getElementById('imageInput');
    const fileListContainer = document.getElementById('fileList');

    if (uploadWrapper && imageInput) {
        // Drag events
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadWrapper.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        ['dragenter', 'dragover'].forEach(eventName => {
            uploadWrapper.addEventListener(eventName, () => {
                uploadWrapper.style.borderColor = 'var(--primary)';
                uploadWrapper.style.backgroundColor = 'var(--primary-light)';
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            uploadWrapper.addEventListener(eventName, () => {
                uploadWrapper.style.borderColor = '#cbd5e1';
                uploadWrapper.style.backgroundColor = '#f8fafc';
            }, false);
        });

        uploadWrapper.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            
            // Assign dropped files to the input (using DataTransfer to modify FileList)
            if (files.length > 0) {
                const dataTransfer = new DataTransfer();
                for(let i = 0; i < files.length; i++) {
                    dataTransfer.items.add(files[i]);
                }
                imageInput.files = dataTransfer.files;
                
                // Trigger change event for preview logic
                const event = new Event('change', { bubbles: true });
                imageInput.dispatchEvent(event);
            }
        }, false);

        // Preview rendering
        imageInput.addEventListener('change', function() {
            fileListContainer.innerHTML = '';
            
            if (this.files && this.files.length > 0) {
                const grid = document.createElement('div');
                grid.style.display = 'grid';
                grid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(100px, 1fr))';
                grid.style.gap = '10px';
                grid.style.marginTop = '15px';
                
                Array.from(this.files).forEach(file => {
                    // Check file size (5MB)
                    if (file.size > 5 * 1024 * 1024) {
                        alert(`File ${file.name} is too large. Max size is 5MB.`);
                        return;
                    }
                    
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        const wrapper = document.createElement('div');
                        wrapper.style.position = 'relative';
                        wrapper.style.paddingTop = '100%';
                        wrapper.style.borderRadius = 'var(--radius-sm)';
                        wrapper.style.overflow = 'hidden';
                        wrapper.style.border = '1px solid var(--border-color)';
                        
                        const img = document.createElement('img');
                        img.src = e.target.result;
                        img.style.position = 'absolute';
                        img.style.top = '0';
                        img.style.left = '0';
                        img.style.width = '100%';
                        img.style.height = '100%';
                        img.style.objectFit = 'cover';
                        
                        wrapper.appendChild(img);
                        grid.appendChild(wrapper);
                    };
                    reader.readAsDataURL(file);
                });
                
                fileListContainer.appendChild(grid);
            }
        });
    }

    // ── Geolocation (Mock Map Tagging) ──────────────────────────────────
    const mapPlaceholder = document.querySelector('.map-placeholder');
    const locationInput = document.getElementById('location');

    if (mapPlaceholder && locationInput) {
        mapPlaceholder.style.cursor = 'pointer';
        
        mapPlaceholder.addEventListener('click', () => {
            if ("geolocation" in navigator) {
                // Show loading state
                mapPlaceholder.innerHTML = `
                    <div class="text-center">
                        <i class="fas fa-spinner fa-spin map-placeholder-icon"></i>
                        <p class="mb-0 font-weight-600">Locating...</p>
                    </div>
                `;
                
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        const lat = position.coords.latitude.toFixed(6);
                        const lng = position.coords.longitude.toFixed(6);
                        
                        // Set input value
                        locationInput.value = `Lat: ${lat}, Lng: ${lng} (Pinned)`;
                        
                        // Update visuals
                        mapPlaceholder.innerHTML = `
                            <div class="text-center">
                                <i class="fas fa-map-marker-alt map-placeholder-icon text-success"></i>
                                <p class="mb-0 font-weight-600">Location Tagged</p>
                                <p class="text-small mb-0 text-muted">${lat}, ${lng}</p>
                            </div>
                            <div class="map-overlay-text bg-success">Coordinates Acquired</div>
                        `;
                        mapPlaceholder.style.border = '2px solid var(--success)';
                        mapPlaceholder.style.backgroundColor = 'var(--success-light)';
                    },
                    (error) => {
                        let msg = "Failed to get location.";
                        if (error.code === 1) msg = "Location permission denied.";
                        
                        mapPlaceholder.innerHTML = `
                            <div class="text-center">
                                <i class="fas fa-exclamation-triangle map-placeholder-icon text-warning"></i>
                                <p class="mb-0 font-weight-600">Geolocation Failed</p>
                                <p class="text-small mb-0 text-muted">${msg}</p>
                            </div>
                        `;
                        alert("Could not access your location. Please type it manually.");
                    },
                    { enableHighAccuracy: true, timeout: 5000, maximumAge: 0 }
                );
            } else {
                alert("Geolocation is not supported by your browser.");
            }
        });
    }
});
