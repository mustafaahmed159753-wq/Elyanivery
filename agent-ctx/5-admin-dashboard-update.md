# Task 5: Admin Dashboard Feature Updates

## Summary
Updated `/home/z/my-project/download/static/admin/index.html` with 4 new features as requested.

## Changes Made

### 1. Password Change for Any User
- Added `changePasswordModal` HTML (similar style to `createUserModal`)
- Added `showChangePasswordModal(userId, username)`, `closeChangePasswordModal()`, `doChangePassword()` JS functions
- Added "Change Password" button (`btn-changepw` class) next to each user row in the Users table
- Calls `POST /api/admin/users/change-password` with `{user_id, new_password}`
- Includes validation (password required, min 4 chars)

### 2. Maintenance Mode Toggle
- Added prominent `maintenanceIndicator` in the top-bar with LIVE (green) / MAINTENANCE (red) states
- Pulsing animation on maintenance mode indicator
- Click to toggle: calls `POST /api/admin/app-status/toggle`
- On app load: calls `GET /api/admin/app-status` to get current status
- CSS responsive: hides text label on mobile, shows only the dot
- Added `loadAppStatus()`, `updateMaintenanceIndicator()`, `toggleMaintenanceMode()` JS functions

### 3. Vehicle Change Requests Section
- Added new "Vehicle Requests" tab in the tab navigation bar
- Added `tab-vehicleRequests` section with list container
- Added `loadVehicleRequests()`, `renderVehicleRequests()`, `doApproveVehicleRequest(id)`, `doRejectVehicleRequest(id)` JS functions
- Each request shows: courier name, current vehicle (purple badge) → requested vehicle (blue badge), Approve/Reject buttons
- Approve: `POST /api/admin/vehicle-change-requests/approve` with `{request_id}`
- Reject: `POST /api/admin/vehicle-change-requests/reject` with `{request_id}`
- Mock data includes 3 sample requests (Marco Rossi, Liam Chen, Sofia Garcia)

### 4. Mock Data Updates
Added to `getMockResponse`:
- `GET /api/admin/app-status` → `{success:true, data:{maintenance_mode:false}}`
- `POST /api/admin/app-status/toggle` → `{success:true, data:{maintenance_mode:true}}`
- `GET /api/admin/vehicle-change-requests` → `{success:true, data:MOCK_VEHICLE_REQUESTS}`
- `POST /api/admin/vehicle-change-requests/approve` → `{success:true, message:'Approved'}`
- `POST /api/admin/vehicle-change-requests/reject` → `{success:true, message:'Rejected'}`
- `POST /api/admin/users/change-password` → `{success:true, message:'Password changed'}`

### 5. Language Translations (EN/RU/RO)
Added translations for all new labels:
- `changePassword`, `newPassword`, `live`, `maintenance`
- `vehicleRequests`, `courier`, `currentVehicle`, `requestedVehicle`
- `approveVRequest`, `rejectVRequest`, `noVehicleRequests`
- `maintenanceModeOn`, `maintenanceModeOff`
- `passwordChanged`, `vehicleApproved`, `vehicleRejected`

### 6. CSS Additions
- `.maintenance-indicator` with `.live` / `.maintenance` states and pulse animation
- `.vrequest-row`, `.vr-info`, `.vr-vehicle`, `.vr-current`, `.vr-requested`, `.vr-arrow`, `.vr-actions`
- `.btn-changepw` and `.btn-reject` button styles
- Glassmorphism theme support for vehicle request rows
- Responsive: `.mi-text` hidden on mobile

### 7. Updated Existing Functions
- `switchTab()`: added `vehicleRequests` tab handler
- `loadAll()`: added `loadAppStatus()` and `loadVehicleRequests()` calls
- `applyTranslations()`: added `renderVehicleRequests()` and `updateMaintenanceIndicator()` calls
- `renderUsers()`: added Change Password button to each user row

## Verification
- HTML structure validated (no unclosed tags)
- JS syntax validated with `node --check` (no errors)
- All 19 feature checks passed
- Dev server running without errors
