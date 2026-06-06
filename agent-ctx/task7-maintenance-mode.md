# Task 7: Add Maintenance Mode Checks to Client-Facing Apps

## Summary
Added maintenance mode overlay and periodic checks to all 4 client-facing apps. When the admin enables maintenance mode via the admin dashboard, these apps will show a full-screen overlay blocking interaction.

## Files Modified
1. `/home/z/my-project/download/static/customer/index.html`
2. `/home/z/my-project/download/static/courier/index.html`
3. `/home/z/my-project/download/static/partner/index.html`
4. `/home/z/my-project/download/static/support/index.html`

## Changes Per File

### All 4 files:
1. **Maintenance overlay div** — Added right after `<body>` tag with:
   - `id="maintenanceOverlay"` 
   - Hidden by default (`display:none` appears twice in inline style to ensure it's hidden)
   - z-index 99999 (above everything)
   - Dark semi-transparent background, centered white text
   - Lock icon, "Service Temporarily Unavailable" heading, maintenance message

2. **`API_PORT` constant** — Added `const API_PORT = '8080';` (matching the admin app's port)

3. **`checkMaintenanceMode()` function** — Fetches `/api/admin/app-status?XTransformPort=8080`, checks `data.maintenance_mode`, shows/hides overlay accordingly

4. **Initialization call** — Added `checkMaintenanceMode()` and `setInterval(checkMaintenanceMode, 30000)` to each app's entry point:
   - Customer: `enterApp()` function
   - Courier: `enterApp()` function
   - Partner: `enterApp()` function
   - Support: `showDashboard()` function

### Customer app specifically:
- Added maintenance check **before `placeOrder()`** — prevents placing restaurant orders during maintenance
- Added maintenance check **before `submitDeliverAnything()`** — prevents placing delivery requests during maintenance
- Both checks show the overlay and display an in-app notification if maintenance mode is active

## API Endpoint Used
- `GET /api/admin/app-status?XTransformPort=8080`
- Response: `{ success: true, data: { maintenance_mode: true/false } }`

## How It Works
1. On app entry, `checkMaintenanceMode()` is called immediately
2. Every 30 seconds, the check runs again via `setInterval`
3. If `maintenance_mode` is `true`, the overlay is shown (display:flex)
4. If `maintenance_mode` is `false`, the overlay is hidden (display:none)
5. For the customer app, additional checks run before order placement to block orders even if the overlay hasn't refreshed yet
6. Network errors are silently ignored (catch block is empty) so the app still works if the server is unreachable
