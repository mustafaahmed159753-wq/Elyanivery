# Task 6: Courier Vehicle Change Approval Flow

## Summary
Updated the Courier app to handle the vehicle change approval flow where vehicle changes require admin approval before taking effect.

## Changes Made

### Server (`/home/z/my-project/download/server.py`)
1. **New endpoint `GET /api/courier/vehicle-status`** — Returns the courier's current vehicle type and any pending vehicle change request
   - Added `handle_courier_vehicle_status()` function that queries `CourierLocations` for current vehicle and `VehicleChangeRequests` for pending changes
   - Registered in both `do_GET` and `do_POST` handlers

### Courier App (`/home/z/my-project/download/static/courier/index.html`)

#### State Variables
- Added `pendingVehicleChange` — tracks when a vehicle change request is pending admin approval
- Added `vehicleNotifPollTimer` — interval timer for polling vehicle approval/rejection notifications
- Persisted `pendingVehicleChange` in localStorage as `courier_pending_vehicle`

#### Language Strings (EN/RU/RO)
- `vehicleChangePending` — Title for pending notification
- `vehicleChangePendingMsg` — Message shown when confirming a vehicle change that needs approval
- `pendingVehicleChangeMsg` — Message shown when trying to change vehicle while a change is already pending
- `vehicleChangeApproved` / `vehicleChangeApprovedMsg` — Notification for approved change
- `vehicleChangeRejected` / `vehicleChangeRejectedMsg` — Notification for rejected change
- `requestedVehicle` — Label for requested vehicle display

#### Updated Functions
1. **`confirmVehicle()`** — Now checks API response for `pending_approval`:
   - If `pending_approval: true`: Sets `pendingVehicleChange`, does NOT update `vehicleType`, closes overlay, shows pending notification
   - If `pending_approval: false` (first-time set): Updates vehicle immediately as before

2. **`openVehicleSelector()`** — If `pendingVehicleChange` is set, shows a warning popup instead of the vehicle selector

3. **`updateVehicleBadge()`** — Adds ⏳ emoji to vehicle badge when a change is pending

4. **`loadProfile()`** — Shows pending vehicle change request info in profile

5. **`enterApp()`** — Restores `pendingVehicleChange` from localStorage, starts vehicle notification polling, calls `refreshVehicleFromServer()` on app entry

6. **`stopAllPolling()`** — Now includes `stopVehicleNotifPolling()`

#### New Functions
- `startVehicleNotifPolling()` — Starts 15-second interval to check for vehicle approval/rejection notifications
- `stopVehicleNotifPolling()` — Clears the interval
- `checkVehicleNotifications()` — Polls `/api/notifications`, filters for `vehicle_approved`/`vehicle_rejected` unread notifications, shows appropriate notifications, marks them as read, then refreshes vehicle from server
- `refreshVehicleFromServer()` — Calls `GET /api/courier/vehicle-status` to sync local vehicle type and pending change state with server

#### HTML Changes
- Added `vehiclePendingBanner` div in the vehicle overlay for showing pending status (reserved for future use if the selector is opened despite pending change)
