# Task: Upgrade Elyanivery Food Delivery App

## Summary
Made significant changes to 3 files in `/home/z/my-project/download/`:
1. `static/courier/index.html` - Courier frontend
2. `static/customer/index.html` - Customer frontend
3. `server.py` - Python HTTP server backend

## Changes Implemented

### 1. Fixed Chat Text Box Bug (Highest Priority)
**Courier HTML:**
- Added `position:sticky;bottom:0;z-index:10` to `.chat-input-bar` CSS
- Updated `showScreen()` function to hide `#bottomNav` when `chatScreen` is shown and show it otherwise

**Customer HTML:**
- Added `z-index:10` to `.chat-input-bar` CSS (already had `position:sticky;bottom:0`)
- Updated `showScreen()` function to hide `#bottomNav` when `chatScreen` is shown

### 2. Added Multiple Themes with Theme Switcher (8 Themes)
Both courier and customer HTML now have:
- **Default** - Green (courier) / Orange (customer)
- **Ocean Blue** - Blue tones
- **Sunset** - Warm red/orange tones
- **Dark Mode** - Dark background, light text
- **Glassy Aurora** - Glassmorphism with purple/teal gradient, blur effects, semi-transparent cards
- **Glassy Frost** - Glassmorphism with cool blue/white, frost effect
- **Midnight Gold** - Dark with gold accents
- **Lavender Dream** - Soft purple/pink tones

Glassy themes include:
- `backdrop-filter: blur(12px)` on cards and containers
- Semi-transparent backgrounds `rgba(255,255,255,0.15)`
- Subtle borders `border: 1px solid rgba(255,255,255,0.2)`
- Background gradients on body

Implementation:
- Theme CSS as `html[data-theme="themename"]` selectors overriding `:root` variables
- Theme picker button in Profile screen (before Logout button)
- Theme picker modal with colored swatches
- Save theme choice to `localStorage` (`courier_theme` / `customer_theme`)
- On page load, apply saved theme via `document.documentElement.setAttribute('data-theme', savedTheme)`

### 3. Added Reassign Button
In courier's order overlay (`.oo-actions` div):
- Added third button: "Reassign" with amber/orange color
- Added CSS for `.oo-btn-reassign`
- Also added reassign button in order cards (in the `btn-row`)
- Added `reassignOrder()` and `reassignOrderFromCard(oid)` JS functions
- Both call `/api/courier/order/{id}/reassign` endpoint
- Shown only when `o.status === 'courier_assigned'` (same condition as reject)

### 4. Show Full Order Details on Courier Overlay
- Updated `showOrderOverlayWithData()` to use `customer_address` from server response (falls back to `delivery_address`)
- Updated server `handle_courier_assigned_orders()` to include reverse-geocoded `customer_address`
- Also display customer_address in order cards on dashboard

### 5. Added Navigate to Restaurant Button
- When order status is `heading_to_restaurant` or `arrived_at_restaurant`:
  - Shows "Navigate to Restaurant" button in floating order overlay
  - Shows "Nav Restaurant" button in order cards on dashboard
- Opens Google Maps with directions from courier's current GPS to restaurant
- `navigateToRestaurant(oid)` function for card buttons
- `navigateToRestaurantOverlay()` function for overlay button

### 6. Added Navigate to Customer Button
- When order status is `order_picked_up` or `heading_to_customer`:
  - Shows "Navigate to Customer" button in floating order overlay
  - Shows "Nav Customer" button in order cards on dashboard
- Opens Google Maps with directions from restaurant to customer's delivery location
- `navigateToCustomer(oid)` function for card buttons
- `navigateToCustomerOverlay()` function for overlay button

### 7. Server.py Backend Changes
**Added reassign endpoint:**
- New handler function `handle_courier_reassign_order(payload, oid)` similar to reject but with different messaging
- Sets `courier_id=NULL`, `status='confirmed'`, logs as 'reassigned'
- Notifies customer about courier change
- Auto-assigns to another courier
- Added routing in `do_POST` for `/api/courier/order/{id}/reassign`

**Improved courier orders API:**
- `handle_courier_assigned_orders()` now includes `customer_address` field
- Reverse-geocodes from `delivery_lat`/`delivery_lng` using Nominatim
- Falls back to coordinates or `delivery_address` if geocoding fails

## Files Modified
- `/home/z/my-project/download/static/courier/index.html` (63329 bytes)
- `/home/z/my-project/download/static/customer/index.html` (73341 bytes)
- `/home/z/my-project/download/server.py` (Python syntax verified)
