// ═══════════════════════════════════════════
// ELYANIVERY — CUSTOMER APP
// Full: Ratings, Avatar, Favorites, Promo, Cancel, Reorder, Admin CRUD
// ═══════════════════════════════════════════

let token = localStorage.getItem('ely_token');
let user = JSON.parse(localStorage.getItem('ely_user') || 'null');
let cartData = { items: [], restaurant_id: null };
let userLat = 41.3874, userLng = 2.1686;
let trackingMap = null, courierMarker = null, trackingInterval = null;
let currentCategory = 0, allRestaurants = [];
let ratingOrder = null, courierRatingVal = 0, serviceRatingVal = 0;
let appliedPromo = null; // {code, discount, description}

const coverBgs = ['rest-cover-bg1','rest-cover-bg2','rest-cover-bg3','rest-cover-bg4','rest-cover-bg5'];
const foodEmojis = ['🍔','🍕','🍣','🥗','🌯','🍜','🌮','🥩','🍗','🍟','🥤','🍰'];


// ═══════════════════════════════════════════
// API
// ═══════════════════════════════════════════
async function api(method, path, body = null) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (token) opts.headers['Authorization'] = `Bearer ${token}`;
    if (body) opts.body = JSON.stringify(body);
    try {
        const res = await fetch(path, opts);
        const text = await res.text();
        try { return JSON.parse(text); }
        catch { return { success: false, message: 'Non-JSON response' }; }
    } catch { toast('Network error','error'); return { success: false, message: 'Network error' }; }
}


// ═══════════════════════════════════════════
// TOAST
// ═══════════════════════════════════════════
function toast(msg, type='info') {
    const c = document.getElementById('toastContainer'); if(!c) return;
    const t = document.createElement('div');
    const icons = {success:'✅',error:'❌',info:'ℹ️',warning:'⚠️'};
    t.className = `toast toast-${type}`;
    t.innerHTML = `<span>${icons[type]||''}</span><span>${msg}</span>`;
    c.appendChild(t);
    setTimeout(()=>{ t.classList.add('out'); setTimeout(()=>t.remove(),300); }, 3000);
}


// ═══════════════════════════════════════════
// AUTH
// ═══════════════════════════════════════════
function switchAuthTab(tab) {
    const ind=document.getElementById('tabIndicator'), lf=document.getElementById('loginForm'),
          rf=document.getElementById('registerForm'), bs=document.querySelectorAll('.tab-btn');
    if(tab==='register'){ind.classList.add('right');lf.style.display='none';rf.style.display='block';bs[0].classList.remove('active');bs[1].classList.add('active');}
    else{ind.classList.remove('right');lf.style.display='block';rf.style.display='none';bs[0].classList.add('active');bs[1].classList.remove('active');}
}

async function handleLogin(e) {
    e.preventDefault();
    const u=document.getElementById('loginUser').value.trim(), p=document.getElementById('loginPass').value;
    if(!u||!p) return toast('Enter username & password','error');
    const d=await api('POST','/api/auth/login',{username:u,password:p});
    if(d.success){saveAuth(d.data);toast(`Welcome back!`,'success');}else toast(d.message||'Login failed','error');
}

async function handleRegister(e) {
    e.preventDefault();
    const u=document.getElementById('regUser').value.trim(),p=document.getElementById('regPass').value,dn=document.getElementById('regName').value.trim()||u;
    if(!u||!p) return toast('Enter username & password','error');
    const d=await api('POST','/api/auth/register',{username:u,password:p,role:'customer',display_name:dn});
    if(d.success){saveAuth(d.data);toast('Account created!','success');}else toast(d.message||'Failed','error');
}

function saveAuth(u){
    if (!u) return;
    token = u.token || (u.data && u.data.token) || token;
    user = u.user || u.data || u;
    if (token) localStorage.setItem('ely_token', token);
    if (user) localStorage.setItem('ely_user', JSON.stringify(user));
    initApp();
}
function logout(){token=null;user=null;localStorage.removeItem('ely_token');localStorage.removeItem('ely_user');if(trackingInterval)clearInterval(trackingInterval);location.reload();}


// ═══════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════
function initApp(){
    if(!token||!user) return;
    document.getElementById('authScreen').style.display='none'; document.getElementById('mainScreen').style.display='block';
    const initial=(user.display_name||user.username||'U')[0].toUpperCase();
    // Header avatar
    const ha=document.getElementById('userAvatar'); ha.textContent='';
    if(user.avatar_url){ha.style.backgroundImage=`url(${user.avatar_url})`;ha.style.backgroundSize='cover';ha.style.fontSize='0';}
    else{ha.textContent=initial;ha.style.backgroundImage='';ha.style.fontSize='14px';}
    // Profile avatar
    const pa=document.getElementById('pmAvatar'); pa.textContent='';
    if(user.avatar_url){pa.style.backgroundImage=`url(${user.avatar_url})`;pa.style.backgroundSize='cover';pa.style.fontSize='0';}
    else{pa.textContent=initial;pa.style.backgroundImage='';pa.style.fontSize='18px';}
    document.getElementById('pmName').textContent=user.display_name||user.username;
    document.getElementById('pmRole').textContent=user.role;
    document.getElementById('adminBtn').style.display=user.role==='admin'?'flex':'none';
    document.getElementById('pmAdmin').style.display=user.role==='admin'?'block':'none';
    if(navigator.geolocation){navigator.geolocation.getCurrentPosition(p=>{userLat=p.coords.latitude;userLng=p.coords.longitude;document.getElementById('locText').textContent=`${userLat.toFixed(4)}, ${userLng.toFixed(4)}`;},()=>{document.getElementById('locText').textContent='Test mode';});}
    loadRestaurants(); loadCart();
}

function hideAllViews(){document.querySelectorAll('.view').forEach(v=>{v.classList.remove('active');v.style.display='none';});}
function showView(id){hideAllViews();const v=document.getElementById(id);v.style.display='block';requestAnimationFrame(()=>v.classList.add('active'));}
function navTo(btn,cb){document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));btn.classList.add('active');cb();}
function showHome(){showView('homeView');loadRestaurants();}
function showOrders(){showView('ordersView');loadOrders();}
function showProfileMenu(){document.getElementById('profileMenu').style.display='block';document.getElementById('overlay').style.display='block';}
function closeOverlays(){document.getElementById('profileMenu').style.display='none';document.getElementById('overlay').style.display='none';}


// ═══════════════════════════════════════════
// AVATAR UPLOAD
// ═══════════════════════════════════════════
function triggerAvatarUpload(){document.getElementById('avatarInput').click();}
async function uploadAvatar(e){
    const file=e.target.files[0];if(!file)return;
    if(file.size>5*1024*1024){toast('Image too large (max 5MB)','error');return;}
    const reader=new FileReader();
    reader.onload=async function(ev){
        const d=await api('POST','/api/upload/avatar',{avatar:ev.target.result});
        if(d.success){user.avatar_url=d.data.avatar_url;localStorage.setItem('ely_user',JSON.stringify(user));initApp();toast('Photo updated! 📷','success');}
        else toast(d.message||'Upload failed','error');
    };
    reader.readAsDataURL(file);
}


// ═══════════════════════════════════════════
// CATEGORIES
// ═══════════════════════════════════════════
function renderCategories(){
    const cats=[{id:0,name:'All',emoji:'🍽️'},{id:1,name:'Burgers',emoji:'🍔'},{id:2,name:'Pizza',emoji:'🍕'},{id:3,name:'Sushi',emoji:'🍣'},{id:4,name:'Healthy',emoji:'🥗'},{id:5,name:'Shawarma',emoji:'🌯'},{id:6,name:'Drinks',emoji:'🥤'}];
    document.getElementById('categoriesGrid').innerHTML=cats.map(c=>`<div class="cat-card ${currentCategory===c.id?'active':''}" onclick="filterByCategory(${c.id})"><div class="cat-icon">${c.emoji}</div><div class="cat-name">${c.name}</div></div>`).join('');
}
function filterByCategory(id){currentCategory=id;renderCategories();renderRestaurants();}


// ═══════════════════════════════════════════
// FAVORITES
// ═══════════════════════════════════════════
async function toggleFavorite(rid, btnEl){
    const d=await api('POST','/api/favorites',{restaurant_id:rid});
    if(d.success){
        const isFav=d.data.is_favorite;
        if(btnEl){btnEl.textContent=isFav?'❤️':'🤍';btnEl.classList.toggle('active',isFav);}
        toast(isFav?'Added to favorites ❤️':'Removed from favorites','info');
    }
}

async function loadFavorites(){
    const d=await api('GET','/api/favorites');
    if(d.success&&d.data.length){
        document.getElementById('featuredStores').innerHTML=d.data.map((r,i)=>`
            <div class="feat-card" onclick="openRestaurant(${r.id})">
                <div class="feat-cover ${coverBgs[i%5]}">${foodEmojis[i%12]}<span class="rest-badge">❤️ Favorite</span></div>
                <div class="feat-info"><div class="feat-name">${r.name}</div><div class="feat-meta"><span class="feat-time">🕐 30 min</span><span class="feat-fee">€2.50</span></div></div>
            </div>`).join('')+document.getElementById('featuredStores').innerHTML;
    }
}


// ═══════════════════════════════════════════
// RESTAURANTS
// ═══════════════════════════════════════════
async function loadRestaurants(){
    const d=await api('GET',`/api/restaurants?lat=${userLat}&lng=${userLng}`);
    if(d.success)allRestaurants=d.data||[];else allRestaurants=[];
    renderCategories();renderRestaurants();loadFavorites();
}

function renderRestaurants(){
    let f=allRestaurants;const s=(document.getElementById('searchInput')?.value||'').toLowerCase();
    if(s)f=f.filter(r=>r.name.toLowerCase().includes(s)||(r.description||'').toLowerCase().includes(s));
    document.getElementById('featuredStores').innerHTML=f.slice(0,5).map((r,i)=>`
        <div class="feat-card" onclick="openRestaurant(${r.id})"><div class="feat-cover ${coverBgs[i%5]}">${foodEmojis[i%12]}<span class="rest-badge">⭐ Featured</span></div><div class="feat-info"><div class="feat-name">${r.name}</div><div class="feat-meta"><span class="feat-time">🕐 30 min</span><span class="feat-fee">€2.50</span></div></div></div>`).join('')||'';
    document.getElementById('restaurantList').innerHTML=f.map((r,i)=>`
        <div class="rest-card" onclick="openRestaurant(${r.id})"><div class="rest-cover ${coverBgs[i%5]}">${foodEmojis[(i+3)%12]}</div><div class="rest-info"><div class="rest-name">${r.name}</div><div class="rest-meta"><span class="rest-rating">⭐ ${r.rating||'4.5'}</span><span>${r.distance_km||'?'} km</span></div></div></div>`).join('')||'<div class="empty-state"><div class="empty-icon">🔍</div><h3>No restaurants found</h3></div>';
}
function handleSearch(){renderRestaurants();}


// ═══════════════════════════════════════════
// RESTAURANT DETAIL
// ═══════════════════════════════════════════
async function openRestaurant(id){
    const d=await api('GET',`/api/restaurants/${id}`);if(!d.success)return toast('Failed','error');
    const r=d.data;showView('restaurantView');document.getElementById('restViewTitle').textContent=r.name;
    // Check if favorite
    const favD=await api('GET',`/api/favorites`);let isFav=false;
    if(favD.success){isFav=(favD.data||[]).some(f=>f.id===r.id);}
    document.getElementById('restaurantHero').innerHTML=`
        <h2>${r.name} <button class="fav-btn ${isFav?'active':''}" onclick="toggleFavorite(${r.id},this)">${isFav?'❤️':'🤍'}</button></h2>
        <p>${r.description||'Delicious food delivered fast'}</p>
        <div class="rest-hero-stats">
            <span class="rest-stat">⭐ ${r.rating||'4.5'}</span>
            <span class="rest-stat">🕐 30 min</span>
            <span class="rest-stat">📦 €2.50</span>
            <span class="rest-stat">${r.is_open?'🟢 Open':'🔴 Closed'}</span>
        </div>`;
    document.getElementById('itemList').innerHTML=(r.items||[]).map((item,i)=>`
        <div class="item-card">
            <div class="item-emoji">${foodEmojis[(i+5)%12]}</div>
            <div class="item-info"><div class="item-name">${item.name}</div><div class="item-desc">${item.description||''}</div><div class="item-price">€${parseFloat(item.price).toFixed(2)}</div></div>
            <button class="btn-add" onclick="addToCart(${item.id},${r.id})">+</button>
        </div>`).join('')||'<div class="empty-state"><div class="empty-icon">🍽️</div><h3>No items</h3></div>';
}


// ═══════════════════════════════════════════
// CART
// ═══════════════════════════════════════════
async function addToCart(itemId,restId){
    const d=await api('POST','/api/cart/add',{item_id:itemId,restaurant_id:restId,quantity:1});
    if(d.success){cartData=d.data;updateCartBadge(d.data.items);toast('Added! 📦','success');}
    else toast(d.message||'Failed','error');
}
async function loadCart(){const d=await api('GET','/api/cart');if(d.success){cartData=d.data;updateCartBadge(d.data.items);}}
async function openCart(){showView('cartView');await loadCart();renderCart();appliedPromo=null;}
async function clearCart(){await api('POST','/api/cart/clear');cartData={items:[],restaurant_id:null};updateCartBadge([]);renderCart();appliedPromo=null;toast('Cleared','info');}
function updateCartBadge(items){const c=(items||[]).reduce((s,i)=>s+i.quantity,0);const b=document.getElementById('cartCount');b.textContent=c;b.style.display=c>0?'flex':'none';}

function updateItemQty(itemId, delta){
    const item=(cartData.items||[]).find(i=>i.item_id===itemId);if(!item)return;
    const newQty=item.quantity+delta;
    if(newQty<=0){removeFromCart(itemId);return;}
    item.quantity=newQty;
    // Update server
    api('POST','/api/cart/add',{item_id:itemId,restaurant_id:cartData.restaurant_id,quantity:delta});
    updateCartBadge(cartData.items);renderCart();
}

function renderCart(){
    const items=cartData.items||[],el=document.getElementById('cartItems'),empty=document.getElementById('cartEmpty'),footer=document.getElementById('cartFooter');
    if(!items.length){el.innerHTML='';empty.style.display='block';footer.style.display='none';return;}
    empty.style.display='none';footer.style.display='block';
    el.innerHTML=items.map(i=>`
        <div class="cart-item">
            <div class="ci-info">
                <div class="ci-name">${i.name}</div>
                <div class="ci-price">€${(i.price*i.quantity).toFixed(2)}</div>
            </div>
            <div class="qty-control">
                <button class="qty-btn" onclick="updateItemQty(${i.item_id},-1)">−</button>
                <span class="qty-val">${i.quantity}</span>
                <button class="qty-btn" onclick="updateItemQty(${i.item_id},1)">+</button>
            </div>
        </div>`).join('');
    renderCartTotals();
}

function renderCartTotals(){
    const items=cartData.items||[];
    const sub=items.reduce((s,i)=>s+i.price*i.quantity,0);
    let discount=appliedPromo?appliedPromo.discount:0;
    const total=Math.max(0,sub+2.50-discount);
    let promoHtml='';
    if(appliedPromo){
        promoHtml=`<div class="promo-applied"><span>🎉 ${appliedPromo.description||appliedPromo.code}: -€${appliedPromo.discount.toFixed(2)}</span><button class="promo-remove" onclick="removePromo()">✕ Remove</button></div>`;
    } else {
        promoHtml=`<div class="promo-section"><input id="promoInput" placeholder="Promo code"><button onclick="applyPromo()">Apply</button></div>`;
    }
    document.getElementById('cartFooter').innerHTML=`
        ${promoHtml}
        <div class="cart-summary">
            <div class="summary-row"><span>Subtotal</span><span>€${sub.toFixed(2)}</span></div>
            <div class="summary-row"><span>Delivery Fee</span><span>€2.50</span></div>
            ${discount>0?`<div class="summary-row" style="color:var(--success)"><span>Discount</span><span>-€${discount.toFixed(2)}</span></div>`:''}
            <div class="summary-row total"><span>Total</span><span>€${total.toFixed(2)}</span></div>
        </div>
        <button class="btn-primary btn-checkout" onclick="confirmOrder()"><span>Confirm Order</span><span class="btn-arrow">→</span></button>`;
}

async function applyPromo(){
    const code=(document.getElementById('promoInput')?.value||'').trim();
    if(!code)return toast('Enter a promo code','warning');
    const sub=(cartData.items||[]).reduce((s,i)=>s+i.price*i.quantity,0);
    const d=await api('POST','/api/promo/validate',{code,subtotal:sub});
    if(d.success){appliedPromo=d.data;toast('Promo applied! 🎉','success');renderCartTotals();}
    else toast(d.message||'Invalid code','error');
}
function removePromo(){appliedPromo=null;toast('Promo removed','info');renderCartTotals();}

async function removeFromCart(itemId){const d=await api('POST',`/api/cart/remove/${itemId}`);if(d.success){cartData=d.data;updateCartBadge(d.data.items);renderCart();}}


// ═══════════════════════════════════════════
// ORDER
// ═══════════════════════════════════════════
async function confirmOrder(){
    if(!confirm('Confirm your order?'))return;
    const body={delivery_lat:userLat,delivery_lng:userLng,delivery_address:'Customer Location'};
    if(appliedPromo)body.promo_code=appliedPromo.code;
    const d=await api('POST','/api/orders',body);
    if(d.success){
        toast(`Order #${d.data.order_number} confirmed! 🎉`,'success');updateCartBadge([]);cartData={items:[],restaurant_id:null};appliedPromo=null;
        if(d.data.courier_name)toast(`🏍️ ${d.data.courier_name} is your courier!`,'info');else toast('⏳ Looking for courier...','warning');
        trackOrder(d.data.id);
    } else toast(d.message||'Failed','error');
}


// ═══════════════════════════════════════════
// ORDERS LIST
// ═══════════════════════════════════════════
async function loadOrders(){
    const d=await api('GET','/api/orders');if(!d.success)return;
    const orders=d.data||[],el=document.getElementById('ordersList'),empty=document.getElementById('ordersEmpty');
    if(!orders.length){el.innerHTML='';empty.style.display='block';return;}
    empty.style.display='none';
    el.innerHTML=orders.map(o=>`
        <div class="order-card" onclick="trackOrder(${o.id})">
            <div class="oc-top">
                <span class="oc-num">#${o.order_number}</span>
                <span class="oc-status s-${o.status}">${formatStatus(o.status)}</span>
            </div>
            <div class="oc-rest">🍔 ${o.restaurant_name}</div>
            <div class="oc-bottom">
                <span class="oc-price">€${parseFloat(o.total).toFixed(2)}</span>
                <span class="oc-date">${new Date(o.created_at).toLocaleString()}</span>
            </div>
        </div>`).join('');
}


// ═══════════════════════════════════════════
// TRACKING
// ═══════════════════════════════════════════
async function trackOrder(oid){showView('trackingView');if(trackingInterval)clearInterval(trackingInterval);await refreshTracking(oid);trackingInterval=setInterval(()=>refreshTracking(oid),3000);}
async function refreshTracking(oid){const d=await api('GET',`/api/orders/${oid}`);if(!d.success)return;renderTracking(d.data);}

function renderTracking(o){
    const steps=[{key:'confirmed',l:'Order Confirmed',i:'✅'},{key:'courier_assigned',l:'Courier Assigned',i:'🏍️'},{key:'heading_to_restaurant',l:'Heading to Restaurant',i:'🚴'},{key:'arrived_at_restaurant',l:'At Restaurant',i:'📍'},{key:'order_picked_up',l:'Order Picked Up',i:'📦'},{key:'heading_to_customer',l:'Heading to You',i:'🚴'},{key:'arrived_at_customer',l:'Courier is Here!',i:'📍'},{key:'delivered',l:'Delivered!',i:'🎉'}];
    const keys=steps.map(s=>s.key),ci=keys.indexOf(o.status),pct=Math.max(5,((ci+1)/steps.length)*100);
    const courierInfo=o.courier_name?`<div class="courier-info-card"><div class="courier-avatar">🏍️</div><div class="courier-details"><h4>${o.courier_name}</h4><p>Your delivery rider</p></div></div>`:'';
    const landmark=o.landmark?`<div class="landmark-card"><span>📍</span> Near: ${o.landmark}</div>`:'';
    let sHtml=steps.map((s,i)=>{const cls=i<ci?'done':i===ci?'active':'';const lc=i<ci?'done':'';return`<div class="progress-step">${i<7?`<div class="step-line ${lc}"></div>`:''}<div class="step-dot ${cls}">${cls==='done'?'✓':s.i}</div><div class="step-text"><div class="step-label">${s.l}</div></div></div>`;}).join('');

    // Action buttons based on status
    let actions='';
    if(o.status==='delivered'&&!o.is_rated){
        actions=`<button class="btn-primary" style="margin-top:16px" onclick="showRatingModal();ratingOrder=${o.id}">⭐ Rate This Order</button>`;
    }
    if(['pending','confirmed','courier_assigned'].includes(o.status)){
        actions+=`<button class="btn-cancel-order" onclick="cancelOrder(${o.id})">🚫 Cancel Order</button>`;
    }
    if(o.status==='delivered'){
        actions+=`<button class="btn-reorder" onclick="reorder(${o.id})">🔄 Reorder</button>`;
    }

    document.getElementById('trackingContent').innerHTML=`
        <div class="tracking-card"><h3>Order #${o.order_number}</h3><p style="color:var(--gray-500)">🍔 ${o.restaurant_name}</p><p style="font-size:22px;font-weight:900;color:var(--success);margin-top:8px">€${parseFloat(o.total).toFixed(2)}</p></div>
        ${courierInfo}${landmark}
        <div class="tracking-card"><h3>Progress</h3><div class="progress-bar-container"><div class="progress-bar-fill" style="width:${pct}%"></div></div><div class="progress-steps">${sHtml}</div></div>
        ${actions}
        <div id="trackingMapContainer"><div id="trackingMap" class="tracking-map"></div></div>`;

    if(o.status==='delivered'&&o.is_rated){
        // Show rated badge
    }
    setTimeout(()=>initTrackingMap(o),150);
}

function initTrackingMap(o){
    const el=document.getElementById('trackingMap');if(!el)return;
    if(trackingMap){trackingMap.remove();trackingMap=null;}
    const rLat=parseFloat(o.restaurant_lat||41.3874),rLng=parseFloat(o.restaurant_lng||2.1686);
    trackingMap=L.map(el).setView([rLat,rLng],14);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OSM'}).addTo(trackingMap);
    L.marker([rLat,rLng]).addTo(trackingMap).bindPopup(`🍔 ${o.restaurant_name}`).openPopup();
    L.marker([parseFloat(o.delivery_lat||userLat),parseFloat(o.delivery_lng||userLng)]).addTo(trackingMap).bindPopup('📍 You');
    if(o.courier_location&&o.courier_location.latitude){
        const cl=parseFloat(o.courier_location.latitude),cn=parseFloat(o.courier_location.longitude);
        if(cl||cn){const ic=L.divIcon({className:'',html:'<div style="font-size:28px">🏍️</div>',iconSize:[32,32]});if(courierMarker)trackingMap.removeLayer(courierMarker);courierMarker=L.marker([cl,cn],{icon:ic}).addTo(trackingMap).bindPopup(o.courier_name||'Courier');}
    }
}

function formatStatus(s){return(s||'').replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());}

// ─── CANCEL ORDER ───
async function cancelOrder(oid){
    if(!confirm('Cancel this order?'))return;
    const d=await api('POST',`/api/orders/${oid}/cancel`);
    if(d.success){toast('Order cancelled','info');refreshTracking(oid);}
    else toast(d.message||'Cannot cancel','error');
}

// ─── REORDER ───
async function reorder(oid){
    const d=await api('POST',`/api/orders/${oid}/reorder`);
    if(d.success){cartData=d.data;updateCartBadge(cartData.items);toast('Items added to your box! 📦','success');openCart();}
    else toast(d.message||'Cannot reorder','error');
}


// ═══════════════════════════════════════════
// RATING
// ═══════════════════════════════════════════
function showRatingModal(){document.getElementById('ratingModal').style.display='flex';courierRatingVal=0;serviceRatingVal=0;updateStars('courier',0);updateStars('service',0);document.getElementById('ratingComment').value='';}
function hideRatingModal(){document.getElementById('ratingModal').style.display='none';ratingOrder=null;}
function setRating(type,val){if(type==='courier'){courierRatingVal=val;updateStars('courier',val);}else{serviceRatingVal=val;updateStars('service',val);}}
function updateStars(type,val){const el=document.getElementById(type==='courier'?'courierStars':'serviceStars');el.querySelectorAll('.star').forEach(s=>{s.classList.toggle('active',parseInt(s.dataset.val)<=val);});}
async function submitRating(){
    if(!courierRatingVal||!serviceRatingVal)return toast('Please rate both','warning');
    if(!ratingOrder)return;
    const d=await api('POST',`/api/orders/${ratingOrder}/rate`,{courier_rating:courierRatingVal,service_rating:serviceRatingVal,comment:document.getElementById('ratingComment').value.trim()});
    if(d.success){toast('Thank you! ⭐','success');hideRatingModal();if(trackingInterval)clearInterval(trackingInterval);refreshTracking(ratingOrder);}
    else toast(d.message||'Failed','error');
}
function skipRating(){hideRatingModal();toast('Skipped','info');}


// ═══════════════════════════════════════════
// ADMIN
// ═══════════════════════════════════════════
function openAdmin(){closeOverlays();showView('adminView');loadRestSelect();loadAdminRestList();}
function switchAdminTab(tab,btn){document.querySelectorAll('.admin-tab').forEach(t=>t.classList.remove('active'));btn.classList.add('active');document.getElementById('adminRestTab').style.display=tab==='restaurants'?'block':'none';document.getElementById('adminItemsTab').style.display=tab==='items'?'block':'none';if(tab==='items')loadRestSelect();}

async function loadRestSelect(){
    const d=await api('GET',`/api/restaurants?lat=${userLat}&lng=${userLng}`);if(!d.success)return;
    const opts=(d.data||[]).map(r=>`<option value="${r.id}">${r.name}</option>`).join('');
    document.getElementById('restSelect').innerHTML=`<option value="">-- Choose --</option>${opts}`;
    document.getElementById('viewItemsSelect').innerHTML=`<option value="">-- Choose --</option>${opts}`;
}

async function loadAdminRestList(){
    const d=await api('GET',`/api/restaurants?lat=${userLat}&lng=${userLng}`);if(!d.success)return;
    const rests=d.data||[];
    document.getElementById('adminRestList').innerHTML=rests.length?rests.map(r=>{
        const sn=r.name.replace(/'/g,"\\'"),sd=(r.description||'').replace(/'/g,"\\'"),sa=(r.address||'').replace(/'/g,"\\'");
        return`<div class="admin-list-item">
            <div class="ali-info"><div class="ali-name">${r.name} ${r.is_open?'🟢':'🔴'}</div><div class="ali-sub">${r.description||''}</div></div>
            <div class="ali-actions">
                <label class="toggle-switch"><input type="checkbox" ${r.is_open?'checked':''} onchange="toggleRestOpen(${r.id},this.checked)"><span class="toggle-slider"></span></label>
                <button class="btn-edit-sm" onclick="editRestaurant(${r.id},'${sn}','${sd}','${sa}',${r.latitude},${r.longitude})">✏️</button>
                <button class="btn-delete-sm" onclick="deleteRestaurant(${r.id},'${sn}')">🗑️</button>
            </div></div>`;
    }).join(''):'<p style="color:var(--gray-500)">No restaurants yet</p>';
}

async function toggleRestOpen(rid,isOpen){const d=await api('POST',`/api/restaurants/${rid}/toggle`);if(d.success)toast(isOpen?'Opened 🟢':'Closed 🔴','info');else toast('Failed','error');}

async function addRestaurant(){
    const name=document.getElementById('newRestName').value.trim();if(!name)return toast('Name required','error');
    const d=await api('POST','/api/restaurants',{name,description:document.getElementById('newRestDesc').value.trim()||'',address:document.getElementById('newRestAddr').value.trim()||'',latitude:parseFloat(document.getElementById('newRestLat').value)||41.3874,longitude:parseFloat(document.getElementById('newRestLng').value)||2.1686});
    if(d.success){toast('Added! 🎉','success');document.getElementById('newRestName').value='';document.getElementById('newRestDesc').value='';document.getElementById('newRestAddr').value='';await loadRestSelect();await loadRestaurants();await loadAdminRestList();}
    else toast(d.message||'Failed','error');
}

function editRestaurant(id,name,desc,addr,lat,lng){
    closeOverlays();const m=document.createElement('div');m.className='edit-modal-overlay';m.id='editModal';
    m.innerHTML=`<div class="edit-modal"><h3>Edit Restaurant</h3>
        <div class="form-group"><label>Name</label><input id="editRestName" value="${name}"></div>
        <div class="form-group"><label>Description</label><input id="editRestDesc" value="${desc}"></div>
        <div class="form-group"><label>Address</label><input id="editRestAddr" value="${addr}"></div>
        <div class="form-row"><div class="form-group half"><label>Lat</label><input id="editRestLat" type="number" step="0.0001" value="${lat}"></div><div class="form-group half"><label>Lng</label><input id="editRestLng" type="number" step="0.0001" value="${lng}"></div></div>
        <div class="edit-btns"><button class="btn-cancel" onclick="closeEditModal()">Cancel</button><button class="btn-save" onclick="saveRestEdit(${id})">Save</button></div></div>`;
    document.body.appendChild(m);
}

async function saveRestEdit(id){
    const d=await api('PUT',`/api/restaurants/${id}`,{name:document.getElementById('editRestName').value.trim(),description:document.getElementById('editRestDesc').value.trim(),address:document.getElementById('editRestAddr').value.trim(),latitude:parseFloat(document.getElementById('editRestLat').value),longitude:parseFloat(document.getElementById('editRestLng').value)});
    if(d.success){toast('Updated! ✅','success');closeEditModal();await loadRestSelect();await loadRestaurants();await loadAdminRestList();}
    else toast(d.message||'Failed','error');
}

async function deleteRestaurant(id,name){
    if(!confirm(`Delete "${name}"? This deletes ALL items too!`))return;
    const d=await api('DELETE',`/api/restaurants/${id}`);
    if(d.success){toast('Deleted! 🗑️','success');await loadRestSelect();await loadRestaurants();await loadAdminRestList();}
    else toast(d.message||'Failed','error');
}

async function addItem(){
    const rid=document.getElementById('restSelect').value,name=document.getElementById('newItemName').value.trim(),price=document.getElementById('newItemPrice').value;
    if(!rid)return toast('Select restaurant','error');if(!name)return toast('Name required','error');if(!price||parseFloat(price)<=0)return toast('Valid price required','error');
    const d=await api('POST',`/api/restaurants/${rid}/items`,{name,price:parseFloat(price),description:document.getElementById('newItemDesc').value.trim()});
    if(d.success){toast(`"${name}" added! 🎉`,'success');document.getElementById('newItemName').value='';document.getElementById('newItemPrice').value='';document.getElementById('newItemDesc').value='';loadExistingItems();}
    else toast(d.message||'Failed','error');
}

async function loadExistingItems(){
    const rid=document.getElementById('viewItemsSelect').value;if(!rid){document.getElementById('existingItemsList').innerHTML='';return;}
    const d=await api('GET',`/api/restaurants/${rid}`);
    if(d.success){
        const items=d.data.items||[];
        document.getElementById('existingItemsList').innerHTML=items.length?items.map(i=>{
            const sn=i.name.replace(/'/g,"\\'"),sd=(i.description||'').replace(/'/g,"\\'");
            return`<div class="admin-list-item">
                <div class="ali-info"><div class="ali-name">${i.name} ${i.is_available?'':'🔴'}</div><div class="ali-sub">${i.description||''}</div></div>
                <span class="ali-price">€${parseFloat(i.price).toFixed(2)}</span>
                <div class="ali-actions">
                    <button class="btn-edit-sm" onclick="editItem(${i.id},'${sn}','${sd}',${i.price})">✏️</button>
                    <button class="btn-delete-sm" onclick="deleteItem(${i.id},'${sn}')">🗑️</button>
                </div></div>`;
        }).join(''):'<p style="color:var(--gray-500)">No items</p>';
    }
}

function editItem(id,name,desc,price){
    closeOverlays();const m=document.createElement('div');m.className='edit-modal-overlay';m.id='editModal';
    m.innerHTML=`<div class="edit-modal"><h3>Edit Item</h3>
        <div class="form-group"><label>Name</label><input id="editItemName" value="${name}"></div>
        <div class="form-group"><label>Description</label><input id="editItemDesc" value="${desc}"></div>
        <div class="form-group"><label>Price (€)</label><input id="editItemPrice" type="number" step="0.01" value="${price}"></div>
        <div class="edit-btns"><button class="btn-cancel" onclick="closeEditModal()">Cancel</button><button class="btn-save" onclick="saveItemEdit(${id})">Save</button></div></div>`;
    document.body.appendChild(m);
}

async function saveItemEdit(id){
    const d=await api('PUT',`/api/restaurants/0/items/${id}`,{name:document.getElementById('editItemName').value.trim(),description:document.getElementById('editItemDesc').value.trim(),price:parseFloat(document.getElementById('editItemPrice').value)});
    if(d.success){toast('Updated! ✅','success');closeEditModal();loadExistingItems();}
    else toast(d.message||'Failed','error');
}

async function deleteItem(id,name){if(!confirm(`Delete "${name}"?`))return;const d=await api('DELETE',`/api/restaurants/0/items/${id}`);if(d.success){toast('Deleted! 🗑️','success');loadExistingItems();}else toast(d.message||'Failed','error');}
function closeEditModal(){const m=document.getElementById('editModal');if(m)m.remove();}


// ═══════════════════════════════════════════
// BOOT
// ═══════════════════════════════════════════
window.addEventListener('DOMContentLoaded',()=>{
    setTimeout(()=>{document.getElementById('splashScreen').classList.add('hide');setTimeout(()=>{document.getElementById('splashScreen').style.display='none';if(token&&user)initApp();else document.getElementById('authScreen').style.display='block';},600);},1800);
});