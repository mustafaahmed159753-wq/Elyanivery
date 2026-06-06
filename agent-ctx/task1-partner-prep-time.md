# Task 1: Partner App - Order Duration Feature

## Summary
Enhanced the partner (restaurant) app's prep time modal and order flow.

## Changes Made to `/home/z/my-project/download/static/partner/index.html`

### 1. Prep Time Modal Enhancement (HTML)
- Added `10 min` option (was missing)
- Replaced `35, 40` min options with more useful `45, 60` min options (as per requirements: 10, 15, 20, 25, 30, 45, 60)
- Added **custom input** option allowing any prep time between 1-180 min
- Added `prepMode` hidden field to distinguish accept vs update mode
- Added `confirmUpdateBtn` for the update prep time flow
- Added courier notification note: "The courier will be notified when the order is expected to be ready"

### 2. New CSS
- `.prep-option.prep-custom` - styling for the custom input option
- `.btn-update-prep` - styling for the Update Prep button on accepted orders

### 3. JavaScript - Prep Time Modal Functions
- `openPrepModal(oid, mode)` - now accepts mode ('accept' or 'update')
  - In 'accept' mode: shows Accept Order button
  - In 'update' mode: shows Update Prep Time button, pre-selects current prep time
- `focusCustomPrep()` - focuses the custom input field
- `selectCustomPrep(val)` - handles custom input changes
- `enableConfirmBtn()` / `disableConfirmBtn()` - toggles button state based on mode
- `selectPrepTime(mins, el)` - clears custom input when preset is selected
- `confirmUpdatePrep()` - sends updated prep time via same accept endpoint
- `confirmAcceptWithPrep()` - updated notification to mention courier

### 4. Order Card - Update Prep Button
- Added "Update Prep" button alongside "Mark Ready" for accepted orders
- Button opens prep modal in 'update' mode

### 5. Mark Ready Flow
- Added confirmation dialog when prep time still has >1 minute remaining
- Allows partner to cancel and update prep time instead

## Backend API Used
- `POST /api/partner/order/{id}/accept` with `{ "estimated_prep_minutes": 20 }` - used for both accept and update
