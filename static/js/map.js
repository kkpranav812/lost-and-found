/**
 * map.js
 * ======
 * Leaflet.js map integration for the Report Lost / Report Found forms.
 *
 * Features:
 *  - Interactive Leaflet map pinned to the user's locale or a default campus center
 *  - Draggable marker for precise geo-tagging
 *  - Nominatim reverse-geocoding on marker drop (human-readable address)
 *  - Forward geocoding via the search bar inside the map control
 *  - Hidden lat/lng inputs synced to the marker position
 *  - "Use My Location" button using the HTML5 Geolocation API
 *  - Graceful fallback when geolocation or network is unavailable
 */

(function () {
    'use strict';

    // ── Config ─────────────────────────────────────────────────────────────
    const DEFAULT_LAT  = 12.9716;   // Bengaluru, India — swap to your campus
    const DEFAULT_LNG  = 77.5946;
    const DEFAULT_ZOOM = 15;
    const TILE_URL     = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
    const TILE_ATTR    = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
    const NOMINATIM    = 'https://nominatim.openstreetmap.org';

    // ── DOM Targets ────────────────────────────────────────────────────────
    const mapEl        = document.getElementById('leaflet-map');
    const locationInput = document.getElementById('location');
    const latInput     = document.getElementById('lat');
    const lngInput     = document.getElementById('lng');
    const locateBtn    = document.getElementById('locateMeBtn');
    const geocodeInput = document.getElementById('geocodeSearch');
    const geocodeBtn   = document.getElementById('geocodeBtn');

    if (!mapEl || !locationInput) return;  // Not on a report page — skip.

    // ── Custom Marker Icon ──────────────────────────────────────────────────
    const pinIcon = L.divIcon({
        className: '',
        html: `
            <div style="
                width: 36px; height: 36px;
                background: #1251e6;
                border: 3px solid white;
                border-radius: 50% 50% 50% 0;
                transform: rotate(-45deg);
                box-shadow: 0 4px 12px rgba(18,81,230,0.4);
            "></div>`,
        iconSize: [36, 36],
        iconAnchor: [18, 36],
        popupAnchor: [0, -36]
    });

    // ── Map Init ───────────────────────────────────────────────────────────
    const map = L.map('leaflet-map', {
        center: [DEFAULT_LAT, DEFAULT_LNG],
        zoom: DEFAULT_ZOOM,
        zoomControl: true,
        scrollWheelZoom: true
    });

    L.tileLayer(TILE_URL, {
        attribution: TILE_ATTR,
        maxZoom: 19
    }).addTo(map);

    // ── Marker ─────────────────────────────────────────────────────────────
    let marker = L.marker([DEFAULT_LAT, DEFAULT_LNG], {
        icon: pinIcon,
        draggable: true
    }).addTo(map);

    marker.bindPopup('<b>Drag me</b> to your exact location.').openPopup();

    // ── Reverse Geocoding ──────────────────────────────────────────────────
    async function reverseGeocode(lat, lng) {
        try {
            const url  = `${NOMINATIM}/reverse?format=jsonv2&lat=${lat}&lon=${lng}`;
            const resp = await fetch(url, {
                headers: { 'Accept-Language': 'en' }
            });
            if (!resp.ok) return null;
            const data = await resp.json();
            return data.display_name || null;
        } catch {
            return null;
        }
    }

    function syncInputs(lat, lng, address) {
        if (latInput)  latInput.value  = lat.toFixed(7);
        if (lngInput)  lngInput.value  = lng.toFixed(7);
        if (address) {
            locationInput.value = address;
        } else {
            locationInput.value = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
        }
        // Visual feedback on the text field
        locationInput.style.borderColor = 'var(--success)';
        setTimeout(() => { locationInput.style.borderColor = ''; }, 2000);
    }

    // Called whenever the marker is moved
    async function onMarkerMove(e) {
        const { lat, lng } = e.latlng;
        const address = await reverseGeocode(lat, lng);
        syncInputs(lat, lng, address);
        marker.setPopupContent(address || `${lat.toFixed(5)}, ${lng.toFixed(5)}`).openPopup();
    }

    marker.on('dragend', onMarkerMove);

    // Also allow clicking the map to place / move the marker
    map.on('click', async (e) => {
        marker.setLatLng(e.latlng);
        await onMarkerMove({ latlng: e.latlng });
    });

    // ── "Use My Location" Button ────────────────────────────────────────────
    if (locateBtn) {
        locateBtn.addEventListener('click', async () => {
            if (!('geolocation' in navigator)) {
                alert('Geolocation is not supported by your browser.');
                return;
            }

            locateBtn.disabled = true;
            locateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Locating…';

            navigator.geolocation.getCurrentPosition(
                async (pos) => {
                    const lat = pos.coords.latitude;
                    const lng = pos.coords.longitude;
                    map.setView([lat, lng], 17);
                    marker.setLatLng([lat, lng]);
                    const address = await reverseGeocode(lat, lng);
                    syncInputs(lat, lng, address);
                    marker.setPopupContent(address || `${lat.toFixed(5)}, ${lng.toFixed(5)}`).openPopup();

                    locateBtn.disabled = false;
                    locateBtn.innerHTML = '<i class="fas fa-crosshairs"></i> My Location';
                },
                (err) => {
                    locateBtn.disabled = false;
                    locateBtn.innerHTML = '<i class="fas fa-crosshairs"></i> My Location';
                    const msgs = {
                        1: 'Location permission denied. Please allow access and try again.',
                        2: 'Position unavailable. Check your GPS or network.',
                        3: 'Location request timed out.'
                    };
                    alert(msgs[err.code] || 'Could not determine your location.');
                },
                { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 }
            );
        });
    }

    // ── Forward Geocoding (Address → Coords) ────────────────────────────────
    async function forwardGeocode(query) {
        try {
            const url = `${NOMINATIM}/search?format=json&q=${encodeURIComponent(query)}&limit=1`;
            const resp = await fetch(url, {
                headers: { 'Accept-Language': 'en' }
            });
            if (!resp.ok) return null;
            const results = await resp.json();
            if (!results.length) return null;
            return { lat: parseFloat(results[0].lat), lng: parseFloat(results[0].lon), name: results[0].display_name };
        } catch {
            return null;
        }
    }

    if (geocodeBtn && geocodeInput) {
        const runSearch = async () => {
            const query = geocodeInput.value.trim();
            if (!query) return;

            geocodeBtn.disabled = true;
            geocodeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

            const result = await forwardGeocode(query);
            geocodeBtn.disabled = false;
            geocodeBtn.innerHTML = '<i class="fas fa-search"></i>';

            if (!result) {
                geocodeInput.style.borderColor = 'var(--danger)';
                setTimeout(() => { geocodeInput.style.borderColor = ''; }, 2000);
                alert('Location not found. Try a more specific query.');
                return;
            }

            map.setView([result.lat, result.lng], 17);
            marker.setLatLng([result.lat, result.lng]);
            syncInputs(result.lat, result.lng, result.name);
            marker.setPopupContent(result.name).openPopup();
        };

        geocodeBtn.addEventListener('click', runSearch);
        geocodeInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); runSearch(); }
        });
    }

    // ── Initial reverse geocode for default pin ─────────────────────────────
    (async () => {
        const address = await reverseGeocode(DEFAULT_LAT, DEFAULT_LNG);
        if (address && !locationInput.value) {
            locationInput.value = address;
        }
        if (latInput && !latInput.value) latInput.value = DEFAULT_LAT.toFixed(7);
        if (lngInput && !lngInput.value) lngInput.value = DEFAULT_LNG.toFixed(7);
    })();

})();
