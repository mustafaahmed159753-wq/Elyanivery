// ═══════════════════════════════════════════
// ELYANIVERY — COURIER APP
// ═══════════════════════════════════════════

let token = localStorage.getItem('ely_courier_token');
let user = JSON.parse(localStorage.getItem('ely_courier_user') || 'null');
let isOnline = false;
let myLat = 41.3874, myLng = 2.1686;
let pollInterval = null;
let locationInterval = null;
let adminMap = null;
let deliveredCount = 0;

// ─── API ───
async function api(method, path, body = null) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (token) opts.headers['Authorization'] = `Bearer ${token}`;
    if (body) opts.body = JSON.stringify(body);
    try {
        const res = await fetch(path, opts);
        return await res.json();
    } catch (e) {
        toast('Network error', 'error');
        return { success: false, message: 'Network error' };
    }
}

// ─── TOAST ───
function toast(msg, type = 'info') {
    const container = document.getElementById('toastContainer');
    const t = document.createElement('div');
    const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
    t.className = `toast toast-${type}`;
    t.innerHTML = `<span>${icons[type] || ''}</span><span>${msg}</span>`;
    container.appendChild(t);
    setTimeout(() => { t.classList.add('out'); setTimeout(() => t.remove(), 300); }, 3500);
}
// ─── AVATAR UPLOAD ───
function triggerAvatarUpload() { document.getElementById('avatarInput').click(); }

async function uploadAvatar(e) {
    const file = e.target.files[0]; if (!file) return;
    const reader = new FileReader();
    reader.onload = async function (ev) {
        const d = await api('POST', '/api/upload/avatar', { avatar: ev.target.result });
        if (d.success) {
            user.avatar_url = d.data.avatar_url;
            localStorage.setItem('ely_courier_user', JSON.stringify(user));
            initApp();
            toast('Photo updated! 📷', 'success');
        } else toast(d.message || 'Upload failed', 'error');
    };
    reader.readAsDataURL(file);
}
// ─── AUTH ───
function switchAuthTab(tab) {
    const indicator = document.getElementById('tabIndicator');
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const btns = document.querySelectorAll('.tab-btn');

    if (tab === 'register') {
        indicator.classList.add('right');
        loginForm.style.display = 'none';
        registerForm.style.display = 'block';
        btns[0].classList.remove('active');
        btns[1].classList.add('active');
    } else {
        indicator.classList.remove('right');
        loginForm.style.display = 'block';
        registerForm.style.display = 'none';
        btns[0].classList.add('active');
        btns[1].classList.remove('active');
    }
}

async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('loginUser').value.trim();
    const password = document.getElementById('loginPass').value;
    if (!username || !password) return toast('Enter username & password', 'error');

    const data = await api('POST', '/api/auth/login', { username, password });
    if (data.success) {
        saveAuth(data.data);
        toast(`Welcome back!`, 'success');
    } else {
        toast(data.message || 'Login failed', 'error');
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const username = document.getElementById('regUser').value.trim();
    const password = document.getElementById('regPass').value;
    const display_name = document.getElementById('regName').value.trim() || username;
    if (!username || !password) return toast('Enter username & password', 'error');

    const data = await api('POST', '/api/auth/register', { username, password, role: 'courier', display_name });
    if (data.success) {
        saveAuth(data.data);
        toast('Account created!', 'success');
    } else {
        toast(data.message || 'Registration failed', 'error');
    }
}

function saveAuth(u) {
    token = u.token;
    user = u;
    localStorage.setItem('ely_courier_token', token);
    localStorage.setItem('ely_courier_user', JSON.stringify(u));
    initApp();
}

function logout() {
    if (pollInterval) clearInterval(pollInterval);
    if (locationInterval) clearInterval(locationInterval);
    api('POST', '/api/courier/online', { is_online: false });
    token = null; user = null;
    localStorage.removeItem('ely_courier_token');
    localStorage.removeItem('ely_courier_user');
    location.reload();
}

// ─── INIT ───
function initApp() {
    if (!token || !user) return;
    document.getElementById('authScreen').style.display = 'none';
    document.getElementById('mainScreen').style.display = 'block';

        const initial = (user.display_name || user.username || 'U')[0].toUpperCase();

    document.getElementById('userAvatar').textContent = '';
    if (user.avatar_url) {
        document.getElementById('userAvatar').style.backgroundImage = `url(${user.avatar_url})`;
        document.getElementById('userAvatar').style.backgroundSize = 'cover';
        document.getElementById('userAvatar').style.fontSize = '0';
    } else {
        document.getElementById('userAvatar').textContent = initial;
        document.getElementById('userAvatar').style.backgroundImage = '';
        document.getElementById('userAvatar').style.fontSize = '14px';
    }

    document.getElementById('pmAvatar').textContent = '';
    if (user.avatar_url) {
        document.getElementById('pmAvatar').style.backgroundImage = `url(${user.avatar_url})`;
        document.getElementById('pmAvatar').style.backgroundSize = 'cover';
        document.getElementById('pmAvatar').style.fontSize = '0';
    } else {
        document.getElementById('pmAvatar').textContent = initial;
        document.getElementById('pmAvatar').style.backgroundImage = '';
        document.getElementById('pmAvatar').style.fontSize = '18px';
    }

    const isAdmin = user.role === 'admin';
    document.getElementById('adminBtn').style.display = isAdmin ? 'flex' : 'none';
    document.getElementById('pmAdmin').style.display = isAdmin ? 'block' : 'none';

    startLocationTracking();
    goOnline();
    pollInterval = setInterval(checkForOrders, 2000);
    loadDeliveredCount();
}

// ─── LOCATION ───
function startLocationTracking() {
    if (navigator.geolocation) {
        navigator.geolocation.watchPosition(pos => {
            myLat = pos.coords.latitude;
            myLng = pos.coords.longitude;
            document.getElementById('locStatus').textContent = `${myLat.toFixed(4)}, ${myLng.toFixed(4)}`;
            if (isOnline) sendLocation();
        }, () => {
            document.getElementById('locStatus').textContent = 'Test mode (default)';
        }, { enableHighAccuracy: true });
    }

    locationInterval = setInterval(() => {
        if (isOnline && myLat) sendLocation();
    }, 5000);
}

async function sendLocation() {
    await api('POST', '/api/courier/location', { latitude: myLat, longitude: myLng });
}

// ─── ONLINE/OFFLINE ───
async function goOnline() {
    isOnline = true;
    await api('POST', '/api/courier/online', { is_online: true });
    updateOnlineUI();
    toast('You are now online 🟢', 'success');
}

async function goOffline() {
    isOnline = false;
    await api('POST', '/api/courier/online', { is_online: false });
    updateOnlineUI();
    toast('You are now offline', 'info');
}

function toggleOnline() {
    if (isOnline) goOffline(); else goOnline();
}

function updateOnlineUI() {
    document.getElementById('onlineDot').className = `status-dot ${isOnline ? 'online' : 'offline'}`;
    document.getElementById('onlineText').textContent = isOnline ? 'Online' : 'Offline';
}

async function loadDeliveredCount() {
    // Simple count from orders API
    const data = await api('GET', '/api/courier/orders');
    if (data.success) {
        deliveredCount = 0; // Reset - we'd need a delivered endpoint for real count
        document.getElementById('deliveredCount').textContent = `${deliveredCount} delivered`;
    }
}

// ─── NAVIGATION ───
function hideAllViews() {
    document.querySelectorAll('.view').forEach(v => { v.classList.remove('active'); v.style.display = 'none'; });
}

function showView(id) {
    hideAllViews();
    const v = document.getElementById(id);
    v.style.display = 'block';
    requestAnimationFrame(() => v.classList.add('active'));
}

function navWaiting(btn) {
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    checkForOrders();
}

async function navHistory(btn) {
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    showView('historyView');
    await loadHistory();
}

function backToWaiting() {
    showView('waitingView');
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.nav-btn')[0].classList.add('active');
}

function showProfileMenu() {
    document.getElementById('profileMenu').style.display = 'block';
    document.getElementById('overlay').style.display = 'block';
}

function closeOverlays() {
    document.getElementById('profileMenu').style.display = 'none';
    document.getElementById('overlay').style.display = 'none';
}

// ─── CHECK FOR ORDERS ───
async function checkForOrders() {
    if (!isOnline) return;
    const data = await api('GET', '/api/courier/orders');
    if (data.success && data.data && data.data.length > 0) {
        showActiveOrder(data.data[0]);
    } else {
        if (document.getElementById('orderView').classList.contains('active')) {
            // Back to waiting if order was delivered
            showView('waitingView');
        }
    }
}

// ─── ACTIVE ORDER ───
function showActiveOrder(order) {
    showView('orderView');
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

    const status = order.status;
    const restUrl = `https://www.google.com/maps/dir/?api=1&destination=${order.restaurant_lat},${order.restaurant_lng}&travelmode=driving`;
    const custUrl = `https://www.google.com/maps/dir/?api=1&destination=${order.delivery_lat},${order.delivery_lng}&travelmode=driving`;

    const items = (order.items || []).map(i =>
        `<div class="order-item-row"><span>${i.item_name} <span class="qty">x${i.quantity}</span></span><span>€${parseFloat(i.item_price).toFixed(2)}</span></div>`
    ).join('');

    // Determine phase
    let phase, bannerClass, bannerIcon, bannerTitle, bannerSub;
    if (['courier_assigned', 'heading_to_restaurant'].includes(status)) {
        phase = 'restaurant';
        bannerClass = 'phase-restaurant';
        bannerIcon = '🍔';
        bannerTitle = 'Head to Restaurant';
        bannerSub = status === 'courier_assigned' ? 'Accept and start navigation' : 'On your way';
    } else if (status === 'arrived_at_restaurant') {
        phase = 'pickup';
        bannerClass = 'phase-pickup';
        bannerIcon = '📦';
        bannerTitle = 'At Restaurant';
        bannerSub = 'Collect the order';
    } else if (['order_picked_up', 'heading_to_customer', 'arrived_at_customer'].includes(status)) {
        phase = 'delivery';
        bannerClass = 'phase-delivery';
        bannerIcon = '🚴';
        bannerTitle = status === 'arrived_at_customer' ? 'At Customer!' : 'Deliver to Customer';
        bannerSub = status === 'arrived_at_customer' ? 'Hand over the order' : 'On your way';
    } else if (status === 'delivered') {
        phase = 'done';
        bannerClass = 'phase-done';
        bannerIcon = '🎉';
        bannerTitle = 'Delivery Complete!';
        bannerSub = 'Great job!';
    }

    // Progress bar
    const steps = ['confirmed', 'courier_assigned', 'heading_to_restaurant', 'arrived_at_restaurant',
                    'order_picked_up', 'heading_to_customer', 'arrived_at_customer', 'delivered'];
    const stepIdx = steps.indexOf(status);
    const progressSteps = [0, 1, 2, 3, 4, 5, 6, 7].map(i => {
        let cls = '';
        if (i < stepIdx) cls = 'done';
        else if (i === stepIdx) cls = 'active';
        return `<div class="mp-step ${cls}"></div>`;
    }).join('');

    // Action buttons
    let actions = '';
    if (status === 'courier_assigned') {
        actions = `
            <a href="${restUrl}" target="_blank" class="btn-action btn-navigate" onclick="updateStatus(${order.id},'heading_to_restaurant')">
                🗺️ Navigate to Restaurant
            </a>
        `;
    } else if (status === 'heading_to_restaurant') {
        actions = `
            <a href="${restUrl}" target="_blank" class="btn-action btn-navigate">
                🗺️ Open Navigation
            </a>
            <button class="btn-action btn-arrive" onclick="updateStatus(${order.id},'arrived_at_restaurant')">
                📍 I Arrived at Restaurant
            </button>
        `;
    } else if (status === 'arrived_at_restaurant') {
        const landmarkHtml = order.landmark
            ? `<div class="landmark-info">📍 Near: ${order.landmark}</div>` : '';
        actions = `
            ${landmarkHtml}
            <button class="btn-action btn-pickup" onclick="updateStatus(${order.id},'order_picked_up')">
                📦 Order is Ready & Taken
            </button>
        `;
    } else if (status === 'order_picked_up') {
        actions = `
            <a href="${custUrl}" target="_blank" class="btn-action btn-navigate" onclick="updateStatus(${order.id},'heading_to_customer')">
                🗺️ Navigate to ${order.customer_name}
            </a>
        `;
    } else if (status === 'heading_to_customer') {
        actions = `
            <a href="${custUrl}" target="_blank" class="btn-action btn-navigate">
                🗺️ Open Navigation
            </a>
            <button class="btn-action btn-arrive" onclick="updateStatus(${order.id},'arrived_at_customer')">
                📍 I'm at the Customer
            </button>
        `;
    } else if (status === 'arrived_at_customer') {
        actions = `
            <button class="btn-action btn-deliver" onclick="markDelivered(${order.id})">
                ✅ Order Delivered to Customer
            </button>
        `;
    }

    document.getElementById('orderContent').innerHTML = `
        <div class="mini-progress">${progressSteps}</div>
        <div class="order-detail-card">
            <div class="order-status-banner ${bannerClass}">
                <div class="banner-icon">${bannerIcon}</div>
                <div class="banner-text">
                    <h3>${bannerTitle}</h3>
                    <p>${bannerSub}</p>
                </div>
            </div>

            <div class="order-body">
                <div class="order-section">
                    <div class="order-section-title">Order Details</div>
                    <div class="order-info-row">
                        <span class="oi-icon">📋</span>
                        <div class="oi-text">
                            <strong>#${order.order_number}</strong>
                        </div>
                    </div>
                </div>

                <div class="order-section">
                    <div class="order-section-title">Restaurant</div>
                    <div class="order-info-row">
                        <span class="oi-icon">🍔</span>
                        <div class="oi-text">
                            <strong>${order.restaurant_name}</strong>
                            <span>${order.restaurant_address || 'Restaurant location'}</span>
                        </div>
                    </div>
                </div>

                <div class="order-section">
                    <div class="order-section-title">Customer</div>
                    <div class="order-info-row">
                        <span class="oi-icon">👤</span>
                        <div class="oi-text">
                            <strong>${order.customer_name}</strong>
                        </div>
                    </div>
                </div>

                <div class="order-section">
                    <div class="order-section-title">Items</div>
                    <div class="order-items-list">${items}</div>
                    <div class="order-total-row">
                        <span>Total</span>
                        <span>€${parseFloat(order.total).toFixed(2)}</span>
                    </div>
                </div>
            </div>

            <div class="action-buttons">
                ${actions}
            </div>
        </div>
    `;
}

// ─── STATUS UPDATES ───
async function updateStatus(oid, newStatus) {
    await api('POST', `/api/courier/order/${oid}/status`, {
        status: newStatus,
        latitude: myLat,
        longitude: myLng
    });
    toast(formatStatus(newStatus), 'info');
    setTimeout(() => checkForOrders(), 500);
}

async function markArrivedRestaurant(oid) {
    await api('POST', `/api/courier/order/${oid}/status`, {
        status: 'arrived_at_restaurant',
        latitude: myLat,
        longitude: myLng
    });
    toast('Arrived at restaurant! 📍', 'success');
    setTimeout(() => checkForOrders(), 500);
}

async function markDelivered(oid) {
    await api('POST', `/api/courier/order/${oid}/status`, {
        status: 'delivered'
    });
    toast('Order delivered! Great job! 🎉', 'success');
    deliveredCount++;
    document.getElementById('deliveredCount').textContent = `${deliveredCount} delivered`;
    setTimeout(() => {
        showView('waitingView');
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.nav-btn')[0].classList.add('active');
    }, 1500);
}

function formatStatus(s) {
    return (s || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// ─── HISTORY ───
async function loadHistory() {
    // For now, we don't have a dedicated history endpoint
    // We'll show a placeholder
    document.getElementById('historyList').innerHTML = `
        <div class="empty-state">
            <div class="empty-icon">📋</div>
            <h3>Delivery History</h3>
            <p>Your completed deliveries will appear here</p>
        </div>
    `;
}

// ─── ADMIN ───
function openAdmin() {
    closeOverlays();
    showView('adminView');
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    loadAdminData();
}

function switchAdminTab(tab, btn) {
    document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('adminMapTab').style.display = tab === 'map' ? 'block' : 'none';
    document.getElementById('adminOrdersTab').style.display = tab === 'orders' ? 'block' : 'none';
    if (tab === 'map') loadAdminMap();
}

async function loadAdminData() {
    const [couriersData, ordersData] = await Promise.all([
        api('GET', '/api/admin/couriers'),
        api('GET', '/api/admin/unassigned')
    ]);

    // Render courier list
    if (couriersData.success) {
        document.getElementById('courierList').innerHTML = (couriersData.data || []).map(c => `
            <div class="courier-card">
                <div class="cc-left">
                    <div class="cc-avatar">🏍️</div>
                    <div>
                        <div class="cc-name">${c.display_name || c.username}</div>
                        <div class="cc-coords">${c.latitude ? parseFloat(c.latitude).toFixed(4) + ', ' + parseFloat(c.longitude).toFixed(4) : 'No location'}</div>
                    </div>
                </div>
                <span class="cc-status ${c.is_online ? 'cc-online' : 'cc-offline'}">${c.is_online ? '● Online' : '○ Offline'}</span>
            </div>
        `).join('') || '<p style="padding:16px;color:var(--gray-500)">No couriers registered</p>';
    }

    // Render unassigned orders
    if (ordersData.success) {
        const couriers = (couriersData.data || []).filter(c => c.is_online);
        document.getElementById('unassignedOrders').innerHTML = (ordersData.data || []).map(o => `
            <div class="unassigned-card">
                <div class="ua-header">
                    <span class="ua-num">#${o.order_number}</span>
                    <span class="ua-price">€${parseFloat(o.total).toFixed(2)}</span>
                </div>
                <div class="ua-rest">🍔 ${o.restaurant_name}</div>
                <div class="ua-assign">
                    <select id="assignSel_${o.id}">
                        <option value="">Select courier...</option>
                        ${couriers.map(c => `<option value="${c.id}">${c.display_name || c.username}</option>`).join('')}
                    </select>
                    <button onclick="assignCourier(${o.id})">Assign</button>
                </div>
            </div>
        `).join('') || '<div class="empty-state"><div class="empty-icon">✅</div><h3>All orders assigned</h3></div>';
    }

    loadAdminMap();
}

function loadAdminMap() {
    setTimeout(async () => {
        const mapEl = document.getElementById('adminMap');
        if (!mapEl) return;
        if (adminMap) { adminMap.remove(); adminMap = null; }

        adminMap = L.map(mapEl).setView([41.3874, 2.1686], 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OSM'
        }).addTo(adminMap);

        const couriersData = await api('GET', '/api/admin/couriers');
        if (couriersData.success) {
            (couriersData.data || []).forEach(c => {
                if (c.latitude && c.longitude && (parseFloat(c.latitude) != 0 || parseFloat(c.longitude) != 0)) {
                    const icon = L.divIcon({
                        className: '',
                        html: `<div style="font-size:28px;filter:${c.is_online ? 'none' : 'grayscale(1)'}">🏍️</div>`,
                        iconSize: [32, 32]
                    });
                    L.marker([parseFloat(c.latitude), parseFloat(c.longitude)], { icon })
                        .addTo(adminMap)
                        .bindPopup(`<strong>${c.display_name || c.username}</strong><br>${c.is_online ? '🟢 Online' : '🔴 Offline'}`);
                }
            });
        }
    }, 200);
}

async function assignCourier(orderId) {
    const sel = document.getElementById(`assignSel_${orderId}`);
    const courierId = sel ? sel.value : null;
    if (!courierId) return toast('Select a courier first', 'warning');

    const data = await api('POST', '/api/admin/assign', { order_id: orderId, courier_id: parseInt(courierId) });
    if (data.success) {
        toast('Courier assigned! 🎉', 'success');
        loadAdminData();
    } else {
        toast(data.message || 'Failed to assign', 'error');
    }
}

// ─── BOOT ───
window.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        document.getElementById('splashScreen').classList.add('hide');
        setTimeout(() => {
            document.getElementById('splashScreen').style.display = 'none';
            if (token && user) {
                initApp();
            } else {
                document.getElementById('authScreen').style.display = 'block';
            }
        }, 600);
    }, 1800);
});