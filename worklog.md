---
Task ID: 1
Agent: Main
Task: Massive v5.0 Elyanivery platform upgrade

Work Log:
- Updated db.py with new schema: Users (phone, approval_status), Orders (is_deliver_anything, delivery_type, pickup_address, pickup_lat, pickup_lng, pickup_contact_name, pickup_contact_phone, delivery_contact_name, delivery_contact_phone, item_description), Restaurants (phone), Broadcasts table
- Updated db.py seed data: 15 Moldova-based restaurants across categories (restaurant, fast_food, pharmacy, supermarket, delivery_service) with Chisinau addresses
- Updated server.py: courier approval_status in register/login, deliver anything with address-based inputs, admin user management APIs, broadcast system, support order detail with contacts
- Updated admin dashboard: User management tab, courier approval/suspend/block, create user modal, broadcast system, multi-language (EN/RU/RO)
- Updated customer app: Deliver Anything redesign (addresses not coords, send/receive toggle, contact names/phones), multi-language, broadcast display
- Updated courier app: Approval flow (pending/suspended/blocked), phone field in registration, multi-language, broadcast display
- Updated partner app: Multi-language (EN/RU/RO), broadcast display
- Updated support app: Ongoing orders with contact details (customer/courier/partner phone+address), color-coded contact cards, multi-language, broadcast display

Stage Summary:
- v5.0 upgrade complete with all requested features
- Admin is the maestro: approves, suspends, blocks, deletes users; creates support users; manages broadcasts
- Deliver Anything now uses practical addresses/contacts instead of lat/lng
- All 5 apps support English, Russian, Romanian languages
- Broadcast system lets admin target specific roles
- Support sees all contact details for ongoing orders
- Database seeded with Moldova (Chisinau) restaurants, pharmacies, supermarkets
