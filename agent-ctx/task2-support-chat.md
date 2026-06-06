# Task 2: Support App - Enhanced Order-Based Messaging

## Summary
Enhanced the customer support app's chat section in the order detail panel.

## Changes Made to `/home/z/my-project/download/static/support/index.html`

### 1. CSS Enhancements
- Increased `max-height` of chat section from 400px to 500px
- Increased `max-height` of chat messages from 280px to 340px
- Added `.msg-sender.sender-customer` (amber color)
- Added `.msg-sender.sender-partner` (teal color)
- Added `.msg-sender.sender-courier` (blue color)
- Added `.msg-sender.sender-support` (purple color)
- Added `.msg-sender-icon` styling
- Added `.msg-status-indicator` - small badge showing order status at message time
- Added `.chat-channel-info` and `.chat-live-dot` for live indicator
- Added `.emoji-row` flex-wrap for better emoji layout
- Added `@keyframes livePulse` for the live dot animation

### 2. Message Sender Identification
- 👤 Customer Name (amber) - for role 'customer'
- 🏪 Restaurant Name (teal) - for role 'partner' or 'restaurant'
- 🛵 Courier Name (blue) - for role 'courier'
- 🎧 Support Agent (purple) - for role 'support' or 'admin' (including self-sent messages)

### 3. Message Type Indicators
- Shows order status badge on messages when `order_status` field is present
- Status labels: "Order placed", "Order accepted", "Courier assigned", "Order picked up", "Delivered"
- Each with corresponding icon: 📋, ✅, 🏍️, 🛍️, ✨

### 4. Quick Emoji Replies
Updated from: 😊 👍 🎉 ❤️ 🔥 ⏳
To: 👍 😊 ✅ ⏳ ❌ 🙏 📞 💡 (with titles for accessibility)

### 5. Recipient Selection
- Added dropdown to choose message recipient:
  - 📢 All (default)
  - 👤 Customer
  - 🏪 Restaurant
  - 🛵 Courier
- Maps to `receiver_id` in the API payload based on order participant IDs

### 6. Real-time Polling
- Changed chat message polling from 5s to 3s
- Updated `loadOrderDetail` to fetch ALL messages (not just after_id) for initial load
- Chat header shows "Live · All participants" with pulsing green dot

### 7. Chat Send Enhancement
- `sendChatMsg()` now includes `receiver_id` based on recipient dropdown selection
- Looks up customer_id, restaurant_id, or courier_id from the selected order

## Backend API Used
- `GET /api/chat/messages/{order_id}` - Get all messages for an order
- `POST /api/chat/send` - Send message with `{ order_id, message, message_type, receiver_id? }`
