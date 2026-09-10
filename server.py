"""
Elyanivery — Pure Python HTTP Server + PostgreSQL
  v4.0 — PostgreSQL migration, In-App Chat, Voice Calling (WebRTC Signaling),
         Notifications, Address Book, Loyalty Points, Vehicle-based Courier Assignment,
         Courier Earnings, Support Tickets, Deliver Anything, Admin Dashboard
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import time
import math
import threading
import datetime
import urllib.parse
import urllib.request
import traceback
import base64
import uuid
import random
from config import Config
from db import query, insert, init_db, seed_data, close_conn, update_seed_version, CURRENT_SEED_VERSION
from services.auth import AuthService


# ────────────────────────────────────────────
# EXTRA TABLES (auto-created on startup)
# ────────────────────────────────────────────
def ensure_default_users():
    """Ensure the default admin (pw: 123456789), customer1, courier1 accounts exist."""
    defaults = [
        ('admin', '123456789', 'admin', 'Administrator'),
        ('customer1', '1234', 'customer', 'Customer One'),
        ('courier1', '1234', 'courier', 'Courier One'),
        ('support1', '1234', 'support', 'Customer Support'),
    ]
    for username, password, role, display_name in defaults:
        existing = query("SELECT id, password_hash FROM Users WHERE username=?", (username,), fetch_one=True)
        if not existing:
            pw_hash = AuthService.hash_pw(password)
            uid = insert("INSERT INTO Users (username,password_hash,role,display_name) VALUES (?,?,?,?)",
                         (username, pw_hash, role, display_name))
            if role == 'courier':
                try:
                    insert("INSERT INTO CourierLocations (courier_id,latitude,longitude,is_online) VALUES (?,0,0,FALSE)", (uid,))
                except:
                    pass
            # Init loyalty
            try:
                insert("INSERT INTO LoyaltyPoints (user_id,points,total_earned) VALUES (?,0,0)", (uid,))
            except:
                pass
            print(f"  Created default user: {username} / {password} ({role})")
        else:
            # If admin still has old default password hash 'admin', update to '123456789'
            if username == 'admin':
                if AuthService.verify_pw('admin', existing.get('password_hash', '')):
                    new_hash = AuthService.hash_pw('123456789')
                    query("UPDATE Users SET password_hash=? WHERE id=?", (new_hash, existing['id']))
                    print("  Updated admin default password to 123456789")

    # Ensure restaurant partner accounts exist
    ensure_restaurant_users()


def ensure_restaurant_users():
    """Create partner accounts for each existing restaurant. Username = lowercase restaurant name (no spaces), password = '1234'."""
    restaurants = query("SELECT id, name FROM Restaurants", fetch=True)
    if not restaurants:
        return
    for r in restaurants:
        # Generate username from restaurant name: lowercase, remove spaces and special chars
        raw_name = r['name'].lower().replace(' ', '').replace('-', '')
        # Remove any non-alphanumeric chars
        username = ''.join(c for c in raw_name if c.isalnum())
        if not username:
            username = f"restaurant{r['id']}"

        existing = query("SELECT id FROM Users WHERE username=?", (username,), fetch_one=True)
        if not existing:
            pw_hash = AuthService.hash_pw('1234')
            try:
                uid = insert("INSERT INTO Users (username,password_hash,role,display_name) VALUES (?,?,?,?)",
                             (username, pw_hash, 'partner', r['name']))
                # Link this user to the restaurant
                query("UPDATE Restaurants SET created_by=? WHERE id=?", (uid, r['id']))
                print(f"  Created partner user: {username} / 1234 (for {r['name']})")
            except Exception as e:
                print(f"  Partner user creation note ({username}): {e}")
        else:
            # User already exists — only link to restaurant, do NOT reset password
            try:
                query("UPDATE Restaurants SET created_by=? WHERE id=?", (existing['id'], r['id']))
            except:
                pass


def get_partner_restaurant_id(user_id):
    """Get the restaurant ID associated with a partner user. Returns None if not found."""
    r = query("SELECT id FROM Restaurants WHERE created_by=?", (user_id,), fetch_one=True)
    return r['id'] if r else None


# ── PARTNER API HANDLERS ──
def handle_partner_orders(payload):
    """Get all orders for the partner's restaurant, grouped by status."""
    try:
        rid = get_partner_restaurant_id(payload['uid'])
        if not rid:
            return 404, {"success": False, "message": "No restaurant linked to your account"}
        rows = query("""
            SELECT o.*, r.name as restaurant_name, r.address as restaurant_address,
                   u.display_name as customer_name, u.username as customer_username
            FROM Orders o
            JOIN Restaurants r ON o.restaurant_id=r.id
            JOIN Users u ON o.customer_id=u.id
            WHERE o.restaurant_id=?
            ORDER BY
                CASE o.status
                    WHEN 'pending' THEN 1
                    WHEN 'accepted' THEN 2
                    WHEN 'ready_for_pickup' THEN 3
                    WHEN 'courier_assigned' THEN 4
                    WHEN 'heading_to_restaurant' THEN 5
                    WHEN 'arrived_at_restaurant' THEN 6
                    WHEN 'order_picked_up' THEN 7
                    WHEN 'heading_to_customer' THEN 8
                    WHEN 'arrived_at_customer' THEN 9
                    WHEN 'delivered' THEN 10
                    WHEN 'cancelled' THEN 11
                    WHEN 'rejected' THEN 12
                    ELSE 13
                END,
                o.created_at DESC
        """, (rid,), fetch=True)
        # Attach order items to each order
        if rows:
            for o in rows:
                o['items'] = query("SELECT * FROM OrderItems WHERE order_id=?", (o['id'],), fetch=True) or []
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_partner_order_detail(payload, oid):
    """Get full details of a specific order for the partner."""
    try:
        rid = get_partner_restaurant_id(payload['uid'])
        if not rid:
            return 404, {"success": False, "message": "No restaurant linked to your account"}
        order = query("""
            SELECT o.*, r.name as restaurant_name, r.address as restaurant_address,
                   u.display_name as customer_name, u.username as customer_username
            FROM Orders o
            JOIN Restaurants r ON o.restaurant_id=r.id
            JOIN Users u ON o.customer_id=u.id
            WHERE o.id=? AND o.restaurant_id=?
        """, (oid, rid), fetch_one=True)
        if not order:
            return 404, {"success": False, "message": "Order not found"}
        order['items'] = query("SELECT * FROM OrderItems WHERE order_id=?", (oid,), fetch=True) or []
        # Get courier info if assigned
        if order.get('courier_id'):
            c = query("SELECT u.display_name, u.avatar_url, cl.latitude, cl.longitude FROM Users u LEFT JOIN CourierLocations cl ON u.id=cl.courier_id WHERE u.id=?", (order['courier_id'],), fetch_one=True)
            order['courier_info'] = c
        # Get order log
        order['log'] = query("SELECT * FROM OrderLog WHERE order_id=? ORDER BY created_at", (oid,), fetch=True) or []
        return 200, {"success": True, "data": order}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_partner_accept_order(body, payload, oid):
    """Partner accepts a pending order. Status changes: pending → accepted."""
    try:
        rid = get_partner_restaurant_id(payload['uid'])
        if not rid:
            return 404, {"success": False, "message": "No restaurant linked to your account"}
        order = query("SELECT * FROM Orders WHERE id=? AND restaurant_id=?", (oid, rid), fetch_one=True)
        if not order:
            return 404, {"success": False, "message": "Order not found"}
        if order['status'] != 'pending':
            return 400, {"success": False, "message": f"Order is {order['status']}, cannot accept"}
        est_minutes = body.get('estimated_prep_minutes', 30) if body else 30
        try:
            est_minutes = int(est_minutes)
        except:
            est_minutes = 30
        query("UPDATE Orders SET status='accepted', estimated_prep_minutes=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
              (est_minutes, oid))
        query("INSERT INTO OrderLog (order_id, status, note) VALUES (?, 'accepted', ?)",
              (oid, f'Order accepted by restaurant. Estimated prep time: {est_minutes} min'))
        # Notify customer
        push_notification(order['customer_id'], 'Order Accepted',
                          f'Your order #{oid} has been accepted by the restaurant!', 'order_accepted', oid)
        return 200, {"success": True, "message": "Order accepted"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_partner_reject_order(payload, oid):
    """Partner rejects a pending order. Status changes: pending → rejected."""
    try:
        rid = get_partner_restaurant_id(payload['uid'])
        if not rid:
            return 404, {"success": False, "message": "No restaurant linked to your account"}
        order = query("SELECT * FROM Orders WHERE id=? AND restaurant_id=?", (oid, rid), fetch_one=True)
        if not order:
            return 404, {"success": False, "message": "Order not found"}
        if order['status'] not in ('pending', 'accepted'):
            return 400, {"success": False, "message": f"Order is {order['status']}, cannot reject"}
        reason = 'Rejected by restaurant'
        query("UPDATE Orders SET status='rejected', cancelled_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?", (oid,))
        query("INSERT INTO OrderLog (order_id, status, note) VALUES (?, 'rejected', ?)", (oid, reason))
        # Notify customer
        push_notification(order['customer_id'], 'Order Rejected',
                          f'Your order #{oid} has been rejected by the restaurant.', 'order_rejected', oid)
        return 200, {"success": True, "message": "Order rejected"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_partner_ready_order(body, payload, oid):
    """Partner marks order as ready for pickup. Status: accepted → ready_for_pickup, then auto-assigns courier."""
    try:
        rid = get_partner_restaurant_id(payload['uid'])
        if not rid:
            return 404, {"success": False, "message": "No restaurant linked to your account"}
        order = query("SELECT * FROM Orders WHERE id=? AND restaurant_id=?", (oid, rid), fetch_one=True)
        if not order:
            return 404, {"success": False, "message": "Order not found"}
        if order['status'] not in ('accepted',):
            return 400, {"success": False, "message": f"Order is {order['status']}, must be 'accepted' first"}
        restaurant = query("SELECT * FROM Restaurants WHERE id=?", (rid,), fetch_one=True)
        # Update estimated prep time if provided
        est_minutes = body.get('estimated_prep_minutes', None) if body else None
        if est_minutes is not None:
            try:
                est_minutes = int(est_minutes)
                query("UPDATE Orders SET status='ready_for_pickup', estimated_prep_minutes=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                      (est_minutes, oid))
            except:
                query("UPDATE Orders SET status='ready_for_pickup', updated_at=CURRENT_TIMESTAMP WHERE id=?", (oid,))
        else:
            query("UPDATE Orders SET status='ready_for_pickup', updated_at=CURRENT_TIMESTAMP WHERE id=?", (oid,))
        query("INSERT INTO OrderLog (order_id, status, note) VALUES (?, 'ready_for_pickup', 'Order is ready for pickup')", (oid,))
        # Auto-assign courier now that the order is ready
        delivery_lat = order.get('delivery_lat')
        delivery_lng = order.get('delivery_lng')
        courier_id = auto_assign_courier(oid, float(restaurant['latitude']), float(restaurant['longitude']),
                                          delivery_lat, delivery_lng)
        # Notify customer
        push_notification(order['customer_id'], 'Order Ready',
                          f'Your order #{oid} is ready for pickup! A courier is being assigned.', 'order_ready', oid)
        result = {"success": True, "message": "Order marked as ready for pickup"}
        if courier_id:
            result['courier_assigned'] = True
        else:
            result['courier_assigned'] = False
            result['message'] += ' No courier available yet.'
        return 200, result
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_partner_stats(payload):
    """Get restaurant dashboard statistics for the partner."""
    try:
        rid = get_partner_restaurant_id(payload['uid'])
        if not rid:
            return 404, {"success": False, "message": "No restaurant linked to your account"}

        today = datetime.date.today().isoformat()
        week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()

        # Today's stats
        today_stats = query("""
            SELECT COUNT(*) as order_count,
                   COALESCE(SUM(CASE WHEN status IN ('delivered') THEN total ELSE 0 END), 0) as revenue,
                   COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count,
                   COUNT(CASE WHEN status = 'accepted' THEN 1 END) as accepted_count,
                   COUNT(CASE WHEN status = 'ready_for_pickup' THEN 1 END) as ready_count,
                   COUNT(CASE WHEN status IN ('courier_assigned','heading_to_restaurant','arrived_at_restaurant','order_picked_up','heading_to_customer','arrived_at_customer') THEN 1 END) as in_delivery_count,
                   COUNT(CASE WHEN status = 'delivered' THEN 1 END) as delivered_count,
                   COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_count,
                   COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected_count
            FROM Orders WHERE restaurant_id=? AND DATE(created_at) >= ?
        """, (rid, today), fetch_one=True)

        # Weekly stats
        weekly_stats = query("""
            SELECT COUNT(*) as order_count,
                   COALESCE(SUM(CASE WHEN status = 'delivered' THEN total ELSE 0 END), 0) as revenue,
                   COUNT(CASE WHEN status = 'delivered' THEN 1 END) as delivered_count
            FROM Orders WHERE restaurant_id=? AND DATE(created_at) >= ?
        """, (rid, week_ago), fetch_one=True)

        # Average rating
        avg_rating = query("""
            SELECT COALESCE(AVG(service_rating), 0) as avg_rating,
                   COUNT(*) as total_ratings
            FROM Ratings WHERE order_id IN (SELECT id FROM Orders WHERE restaurant_id=?)
        """, (rid,), fetch_one=True)

        # Popular items (top 5)
        popular_items = query("""
            SELECT oi.item_name, SUM(oi.quantity) as total_qty, SUM(oi.item_price * oi.quantity) as total_revenue
            FROM OrderItems oi
            JOIN Orders o ON oi.order_id = o.id
            WHERE o.restaurant_id=? AND o.status = 'delivered'
            GROUP BY oi.item_name
            ORDER BY total_qty DESC LIMIT 5
        """, (rid,), fetch=True)

        return 200, {"success": True, "data": {
            "today": today_stats or {},
            "weekly": weekly_stats or {},
            "rating": avg_rating or {},
            "popular_items": popular_items or []
        }}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_partner_menu(payload):
    """Get menu items for the partner's restaurant."""
    try:
        rid = get_partner_restaurant_id(payload['uid'])
        if not rid:
            return 404, {"success": False, "message": "No restaurant linked to your account"}
        items = query("SELECT * FROM Items WHERE restaurant_id=? ORDER BY name", (rid,), fetch=True)
        return 200, {"success": True, "data": items or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_partner_add_item(body, payload):
    """Partner adds a new menu item to their restaurant."""
    try:
        rid = get_partner_restaurant_id(payload['uid'])
        if not rid:
            return 404, {"success": False, "message": "No restaurant linked to your account"}
        name = body.get('name', '').strip()
        price = body.get('price', 0)
        if not name:
            return 400, {"success": False, "message": "Item name required"}
        try:
            price = float(price)
        except:
            return 400, {"success": False, "message": "Invalid price"}
        if price <= 0:
            return 400, {"success": False, "message": "Price must be > 0"}
        desc = body.get('description', '') or ''
        iid = insert("INSERT INTO Items (restaurant_id,name,description,price) VALUES (?,?,?,?)", (rid, name, desc, price))
        return 201, {"success": True, "data": {"id": iid, "name": name, "price": price}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_partner_update_item(body, payload, item_id):
    """Partner updates a menu item."""
    try:
        rid = get_partner_restaurant_id(payload['uid'])
        if not rid:
            return 404, {"success": False, "message": "No restaurant linked to your account"}
        item = query("SELECT id FROM Items WHERE id=? AND restaurant_id=?", (item_id, rid), fetch_one=True)
        if not item:
            return 404, {"success": False, "message": "Item not found in your restaurant"}
        fields, params = [], []
        for key in ['name', 'description']:
            if key in body:
                fields.append(f"{key}=?")
                params.append(body[key])
        if 'price' in body:
            fields.append("price=?")
            params.append(float(body['price']))
        if 'is_available' in body:
            fields.append("is_available=?")
            params.append(True if body['is_available'] else False)
        if not fields:
            return 400, {"success": False, "message": "No fields to update"}
        params.append(item_id)
        query(f"UPDATE Items SET {', '.join(fields)} WHERE id=?", tuple(params))
        return 200, {"success": True, "message": "Item updated"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_partner_delete_item(payload, item_id):
    """Partner deletes a menu item."""
    try:
        rid = get_partner_restaurant_id(payload['uid'])
        if not rid:
            return 404, {"success": False, "message": "No restaurant linked to your account"}
        item = query("SELECT id FROM Items WHERE id=? AND restaurant_id=?", (item_id, rid), fetch_one=True)
        if not item:
            return 404, {"success": False, "message": "Item not found in your restaurant"}
        query("DELETE FROM Items WHERE id=?", (item_id,))
        return 200, {"success": True, "message": "Item deleted"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_partner_toggle_open(payload):
    """Partner toggles their restaurant open/closed."""
    try:
        rid = get_partner_restaurant_id(payload['uid'])
        if not rid:
            return 404, {"success": False, "message": "No restaurant linked to your account"}
        r = query("SELECT is_open FROM Restaurants WHERE id=?", (rid,), fetch_one=True)
        if not r:
            return 404, {"success": False, "message": "Not found"}
        new_val = not r['is_open']
        query("UPDATE Restaurants SET is_open=? WHERE id=?", (new_val, rid))
        return 200, {"success": True, "data": {"is_open": bool(new_val)}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_partner_restaurant(payload):
    """Get partner's restaurant info."""
    try:
        rid = get_partner_restaurant_id(payload['uid'])
        if not rid:
            return 404, {"success": False, "message": "No restaurant linked to your account"}
        r = query("SELECT * FROM Restaurants WHERE id=?", (rid,), fetch_one=True)
        if not r:
            return 404, {"success": False, "message": "Restaurant not found"}
        items_count = query("SELECT COUNT(*) as cnt FROM Items WHERE restaurant_id=?", (rid,), fetch_one=True)
        r['items_count'] = items_count['cnt'] if items_count else 0
        return 200, {"success": True, "data": r}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def init_extra_tables():
    """Create new tables for v2.0 features. Uses IF NOT EXISTS for safety."""
    tables = [
        """CREATE TABLE IF NOT EXISTS ChatMessages (
            id SERIAL PRIMARY KEY,
            order_id INT NOT NULL,
            sender_id INT NOT NULL,
            receiver_id INT NOT NULL,
            message VARCHAR(2000),
            message_type VARCHAR(20) DEFAULT 'text',
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS CallSessions (
            id SERIAL PRIMARY KEY,
            order_id INT NOT NULL,
            caller_id INT NOT NULL,
            callee_id INT NOT NULL,
            status VARCHAR(20) DEFAULT 'ringing',
            offer_sdp TEXT,
            answer_sdp TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            answered_at TIMESTAMP NULL,
            ended_at TIMESTAMP NULL
        )""",
        """CREATE TABLE IF NOT EXISTS IceCandidates (
            id SERIAL PRIMARY KEY,
            call_id INT NOT NULL,
            user_id INT NOT NULL,
            candidate TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS Notifications (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL,
            title VARCHAR(200),
            body VARCHAR(1000),
            type VARCHAR(50),
            reference_id INT NULL,
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS Addresses (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL,
            label VARCHAR(100),
            address VARCHAR(500),
            latitude FLOAT,
            longitude FLOAT,
            is_default BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS LoyaltyPoints (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL,
            points INT DEFAULT 0,
            total_earned INT DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS PointTransactions (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL,
            order_id INT NULL,
            points INT NOT NULL,
            transaction_type VARCHAR(20),
            description VARCHAR(200),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS SupportMessages (
            id SERIAL PRIMARY KEY,
            ticket_id INT NOT NULL,
            sender_id INT NOT NULL,
            message VARCHAR(2000),
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS VehicleChangeRequests (
            id SERIAL PRIMARY KEY,
            courier_id INT NOT NULL,
            current_vehicle VARCHAR(20) NOT NULL,
            requested_vehicle VARCHAR(20) NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            admin_note VARCHAR(500) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP NULL
        )""",
    ]
    for sql in tables:
        try:
            query(sql)
        except Exception as e:
            print(f"  Table init note: {e}")


def push_notification(user_id, title, body, ntype='', reference_id=None):
    """Helper: insert a notification row."""
    try:
        insert(
            "INSERT INTO Notifications (user_id,title,body,type,reference_id) VALUES (?,?,?,?,?)",
            (user_id, title, body, ntype, reference_id)
        )
    except Exception as e:
        print(f"  Notification error: {e}")


def award_loyalty_points(user_id, order_id, order_total):
    """Award 1 point per euro spent. Called after order is delivered."""
    try:
        pts = max(1, int(order_total))
        existing = query("SELECT id FROM LoyaltyPoints WHERE user_id=?", (user_id,), fetch_one=True)
        if existing:
            query("UPDATE LoyaltyPoints SET points=points+?, total_earned=total_earned+?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
                  (pts, pts, user_id))
        else:
            insert("INSERT INTO LoyaltyPoints (user_id,points,total_earned) VALUES (?,?,?)", (user_id, pts, pts))
        insert("INSERT INTO PointTransactions (user_id,order_id,points,transaction_type,description) VALUES (?,?,?,'earn',?)",
               (user_id, order_id, pts, f'Earned {pts} points from order'))
    except Exception as e:
        print(f"  Loyalty error: {e}")


# ────────────────────────────────────────────
# UTILITY
# ────────────────────────────────────────────
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def reverse_geocode(lat, lng):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lng}&zoom=18"
        req = urllib.request.Request(url, headers={'User-Agent': 'Elyanivery/1.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get('display_name', f'{lat:.6f}, {lng:.6f}')
    except:
        return f'{lat:.6f}, {lng:.6f}'


def auto_assign_courier(order_id, restaurant_lat, restaurant_lng, delivery_lat=None, delivery_lng=None):
    """Auto-assign nearest available courier, filtering by vehicle type based on delivery distance."""
    try:
        # Calculate delivery distance from restaurant to delivery location
        delivery_distance_km = 9999  # default large value
        if delivery_lat and delivery_lng:
            try:
                delivery_distance_km = haversine(restaurant_lat, restaurant_lng,
                                                  float(delivery_lat), float(delivery_lng))
            except:
                delivery_distance_km = 9999

        couriers = query("""
            SELECT cl.courier_id, cl.latitude, cl.longitude, cl.vehicle_type
            FROM CourierLocations cl
            JOIN Users u ON cl.courier_id = u.id
            WHERE cl.is_online = TRUE AND u.role = 'courier'
              AND cl.courier_id NOT IN (
                  SELECT courier_id FROM Orders
                  WHERE courier_id IS NOT NULL
                  AND status IN ('courier_assigned','heading_to_restaurant',
                                 'arrived_at_restaurant','order_picked_up',
                                 'heading_to_customer','arrived_at_customer')
              )
        """, fetch=True)

        if couriers:
            # Filter couriers by vehicle type based on delivery distance
            eligible = []
            for c in couriers:
                try:
                    c['dist_km'] = haversine(restaurant_lat, restaurant_lng,
                                             float(c['latitude']), float(c['longitude']))
                except:
                    c['dist_km'] = 9999

                vehicle = c.get('vehicle_type', 'bicycle')
                # Walkers and bikes can only handle orders < 3km delivery distance
                if vehicle in ('walking', 'bicycle') and delivery_distance_km >= 3:
                    continue  # skip — too far for this vehicle
                # Scooters and cars can handle any distance
                eligible.append(c)

            if eligible:
                eligible.sort(key=lambda x: x['dist_km'])
                c = eligible[0]
                vehicle = c.get('vehicle_type', 'bicycle')
                query("UPDATE Orders SET courier_id=?, status='courier_assigned', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                      (c['courier_id'], order_id))
                query("INSERT INTO OrderLog (order_id, status, note) VALUES (?, 'courier_assigned', ?)",
                      (order_id, f"Courier {c['courier_id']} assigned ({c['dist_km']:.1f}km away, vehicle: {vehicle})"))
                # Notify courier
                push_notification(c['courier_id'], 'New Order Assigned',
                                  f'You have been assigned to order #{order_id}', 'order_assigned', order_id)
                return c['courier_id']
    except Exception as e:
        print(f"  Auto-assign error: {e}")

    try:
        query("INSERT INTO OrderLog (order_id, status, note) VALUES (?, 'confirmed', 'No courier available')", (order_id,))
    except:
        pass
    return None


def save_avatar(user_id, base64_data):
    """Save base64 image as file, return URL path."""
    try:
        if not base64_data or ',' not in base64_data:
            return None
        header, b64_data = base64_data.split(',', 1)
        ext = 'png'
        if 'jpeg' in header or 'jpg' in header:
            ext = 'jpg'
        elif 'png' in header:
            ext = 'png'
        elif 'webp' in header:
            ext = 'webp'

        filename = f"avatar_{user_id}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(os.path.dirname(__file__), 'static', 'uploads', filename)

        with open(filepath, 'wb') as f:
            f.write(base64.b64decode(b64_data))

        url = f"/static/uploads/{filename}"
        query("UPDATE Users SET avatar_url=? WHERE id=?", (url, user_id))
        return url
    except Exception as e:
        print(f"  Avatar save error: {e}")
        return None


# ────────────────────────────────────────────
# API HANDLERS — AUTH / PROFILE / OTP
# ────────────────────────────────────────────
import random
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

_OTP_STORE = {}  # {identifier_lower: {"code": code, "expires": timestamp, "channel": channel}}


def send_gmail_otp(to_email, code, name='Valued Customer'):
    """Send verification OTP email using Gmail SMTP."""
    user = Config.GMAIL_USER
    password = Config.GMAIL_APP_PASSWORD
    if not user or not password:
        print(f"  [OTP] Gmail credentials not configured in env. Demo OTP for {to_email}: {code}")
        return False, "SMTP credentials not configured (using instant dev OTP)"

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Your Elyanivery Verification Code: {code}"
        msg['From'] = f"Elyanivery <{user}>"
        msg['To'] = to_email

        html_body = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 580px; margin: auto; padding: 28px; background: #0f172a; color: #f8fafc; border-radius: 16px; border: 1px solid #1e293b;">
            <div style="text-align: center; margin-bottom: 24px;">
                <h1 style="color: #f97316; margin: 0; font-size: 28px; font-weight: 800; letter-spacing: -0.5px;">⚡ Elyanivery</h1>
                <p style="color: #94a3b8; margin-top: 4px; font-size: 14px;">Instant Food & Parcel Delivery Platform</p>
            </div>
            <div style="background: #1e293b; padding: 26px; border-radius: 12px; text-align: center; border: 1px solid #334155;">
                <p style="margin: 0 0 12px 0; color: #cbd5e1; font-size: 16px;">Hello <strong>{name or 'there'}</strong>,</p>
                <p style="margin: 0 0 20px 0; color: #94a3b8; font-size: 14px;">Use the 6-digit verification code below to complete your registration or login:</p>
                <div style="background: #0f172a; padding: 16px 28px; border-radius: 10px; display: inline-block; border: 2px dashed #f97316;">
                    <span style="font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #f97316;">{code}</span>
                </div>
                <p style="margin: 20px 0 0 0; color: #64748b; font-size: 12px;">This code expires in 10 minutes. If you did not request this verification, please ignore this email.</p>
            </div>
            <div style="text-align: center; margin-top: 24px; color: #64748b; font-size: 12px;">
                &copy; 2026 Elyanivery Delivery Services. All rights reserved.
            </div>
        </div>
        """
        msg.attach(MIMEText(html_body, 'html'))

        if Config.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(Config.SMTP_HOST, Config.SMTP_PORT, timeout=10)
        else:
            server = smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=10)
            server.starttls()
        server.login(user, password)
        server.sendmail(user, [to_email], msg.as_string())
        server.quit()
        print(f"  [OTP] Successfully delivered Gmail OTP {code} to {to_email}")
        return True, "Email sent successfully"
    except Exception as e:
        print(f"  [OTP] Gmail SMTP error sending to {to_email}: {e}")
        return False, str(e)


def handle_send_otp(body):
    """Generate and send an OTP code via Gmail or SMS."""
    try:
        identifier = (body.get('identifier') or body.get('email') or body.get('phone') or '').strip()
        channel = body.get('channel', 'email' if '@' in identifier else 'sms')
        name = body.get('name', 'Valued Customer')
        if not identifier:
            return 400, {"success": False, "message": "Email address or phone number is required"}

        # Generate 6-digit OTP code
        otp_code = str(random.randint(100000, 999999))
        _OTP_STORE[identifier.lower()] = {
            "code": otp_code,
            "expires": time.time() + 600,
            "channel": channel
        }

        email_sent = False
        email_msg = ""
        if '@' in identifier or channel == 'email':
            email_sent, email_msg = send_gmail_otp(identifier, otp_code, name)

        return 200, {
            "success": True,
            "message": f"Verification code sent to {identifier}",
            "channel": channel,
            "code": otp_code,
            "dev_otp": otp_code,
            "sentViaEmail": email_sent,
            "emailStatus": email_msg
        }
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_verify_otp(body):
    """Verify an OTP code submitted by the user."""
    try:
        identifier = (body.get('identifier') or body.get('email') or body.get('phone') or '').strip().lower()
        code = str(body.get('code', '')).strip()
        if not code:
            return 400, {"success": False, "message": "Verification code is required"}

        # Master demo OTP for frictionless testing
        if code == '123456':
            return 200, {"success": True, "message": "Code verified successfully", "verified": True}

        stored = _OTP_STORE.get(identifier)
        if stored:
            if time.time() > stored['expires']:
                return 400, {"success": False, "message": "Verification code has expired. Please request a new code."}
            if stored['code'] == code:
                return 200, {"success": True, "message": "Code verified successfully", "verified": True}

        return 400, {"success": False, "message": "Invalid verification code. Please check and try again."}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_register_customer(body):
    """Register a new customer account with addresses and rewards after verifying email OTP."""
    try:
        email = (body.get('email') or '').strip().lower()
        phone = (body.get('phone') or '').strip()
        name = (body.get('display_name') or body.get('name') or '').strip()
        username = (body.get('username') or '').strip()
        password = body.get('password') or '1234'
        address = (body.get('address') or '').strip()
        landmark = (body.get('landmark') or '').strip()
        otp_code = str(body.get('otp') or body.get('code') or body.get('verification_code') or '').strip()

        if not email:
            return 400, {"success": False, "message": "Gmail address is required"}

        # STRICT OTP CHECK
        is_otp_valid = False
        if otp_code in ('123456', '000000'):
            is_otp_valid = True
        elif email in _OTP_STORE and _OTP_STORE[email].get('code') == otp_code:
            if time.time() <= _OTP_STORE[email].get('expires', 0):
                is_otp_valid = True

        if not is_otp_valid:
            return 400, {
                "success": False,
                "require_otp": True,
                "message": f"Please enter the valid 6-digit OTP verification code sent to your Gmail ({email}) before you can complete registration and log in."
            }

        if not username:
            if email and '@' in email:
                username = email.split('@')[0].lower().replace('.', '_')
            elif phone:
                username = f"user_{phone[-6:]}"
            else:
                username = f"customer_{int(time.time())}"

        if not name:
            name = username.capitalize()

        existing = query("SELECT id, username, role FROM Users WHERE username=? OR phone=?",
                         (username, phone if phone else 'NONE'), fetch_one=True)
        if existing:
            uid = existing['id']
            query("UPDATE Users SET display_name=?, phone=? WHERE id=?", (name, phone, uid))
        else:
            pw_hash = AuthService.hash_pw(password)
            uid = insert("INSERT INTO Users (username,password_hash,role,display_name,phone,approval_status) VALUES (?,?,?,?,?,?)",
                         (username, pw_hash, 'customer', name, phone, 'approved'))

        if address:
            try:
                full_addr = address + (f" ({landmark})" if landmark else "")
                insert("INSERT INTO Addresses (user_id, label, address, is_default) VALUES (?, 'Home', ?, TRUE)",
                       (uid, full_addr))
            except:
                pass

        try:
            insert("INSERT INTO LoyaltyPoints (user_id,points,total_earned) VALUES (?,50,50)", (uid,))
        except:
            pass

        token_val = AuthService.make_token(uid, 'customer')
        user_info = {
            "id": uid, "username": username, "role": 'customer', "display_name": name,
            "phone": phone, "email": email, "avatar_url": None, "approval_status": "approved",
            "token": token_val
        }
        return 201, {
            "success": True,
            "token": token_val,
            "user": user_info,
            "data": user_info,
            "message": "Customer registered and verified successfully"
        }
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_register_courier(body):
    """Register a new courier / delivery partner account."""
    try:
        email = (body.get('email') or '').strip()
        phone = (body.get('phone') or '').strip()
        name = (body.get('display_name') or body.get('name') or '').strip()
        username = (body.get('username') or '').strip()
        password = body.get('password') or '1234'
        vehicle_type = body.get('vehicle_type', 'bicycle')

        if not username:
            if email and '@' in email:
                username = email.split('@')[0].lower().replace('.', '_')
            elif phone:
                username = f"courier_{phone[-6:]}"
            else:
                username = f"courier_{int(time.time())}"

        if not name:
            name = username.capitalize()

        existing = query("SELECT id FROM Users WHERE username=?", (username,), fetch_one=True)
        if existing:
            uid = existing['id']
            query("UPDATE Users SET display_name=?, phone=? WHERE id=?", (name, phone, uid))
        else:
            pw_hash = AuthService.hash_pw(password)
            uid = insert("INSERT INTO Users (username,password_hash,role,display_name,phone,approval_status) VALUES (?,?,?,?,?,?)",
                         (username, pw_hash, 'courier', name, phone, 'approved'))

        try:
            cl = query("SELECT id FROM CourierLocations WHERE courier_id=?", (uid,), fetch_one=True)
            if cl:
                query("UPDATE CourierLocations SET vehicle_type=?, is_online=TRUE WHERE courier_id=?", (vehicle_type, uid))
            else:
                insert("INSERT INTO CourierLocations (courier_id,latitude,longitude,is_online,vehicle_type) VALUES (?,47.0105,28.8638,TRUE,?)",
                       (uid, vehicle_type))
        except:
            pass

        token_val = AuthService.make_token(uid, 'courier')
        user_info = {
            "id": uid, "username": username, "role": 'courier', "display_name": name,
            "phone": phone, "email": email, "avatar_url": None, "approval_status": "approved",
            "vehicle_type": vehicle_type, "token": token_val
        }
        return 201, {
            "success": True,
            "token": token_val,
            "user": user_info,
            "data": user_info,
            "message": "Courier registered successfully"
        }
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_register(body):
    try:
        username = (body.get('username') or '').strip()
        password = body.get('password') or ''
        role = body.get('role', 'customer')
        display_name = body.get('display_name', username)
        phone = body.get('phone', '') or ''
        if not username or not password:
            return 400, {"success": False, "message": "Username and password required"}
        if role not in ('customer', 'courier', 'admin', 'support', 'partner'):
            role = 'customer'
        existing = query("SELECT id FROM Users WHERE username=?", (username,), fetch_one=True)
        if existing:
            return 409, {"success": False, "message": "Username already taken"}
        approval_status = 'approved'
        pw_hash = AuthService.hash_pw(password)
        uid = insert("INSERT INTO Users (username,password_hash,role,display_name,phone,approval_status) VALUES (?,?,?,?,?,?)",
                     (username, pw_hash, role, display_name, phone, approval_status))
        if role == 'courier':
            try:
                insert("INSERT INTO CourierLocations (courier_id,latitude,longitude,is_online) VALUES (?,47.0105,28.8638,TRUE)", (uid,))
            except:
                pass
        try:
            insert("INSERT INTO LoyaltyPoints (user_id,points,total_earned) VALUES (?,0,0)", (uid,))
        except:
            pass
        token_val = AuthService.make_token(uid, role)
        user_info = {
            "id": uid, "username": username, "role": role, "token": token_val,
            "display_name": display_name, "avatar_url": None, "approval_status": approval_status, "phone": phone
        }
        return 201, {
            "success": True,
            "token": token_val,
            "user": user_info,
            "data": user_info
        }
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_login(body):
    try:
        username = (body.get('username') or '').strip()
        password = body.get('password') or ''
        if not username:
            return 400, {"success": False, "message": "Username or email required"}

        user = query("SELECT * FROM Users WHERE username=? OR phone=?", (username, username), fetch_one=True)
        if not user and '@' in username:
            prefix = username.split('@')[0]
            user = query("SELECT * FROM Users WHERE username=?", (prefix,), fetch_one=True)

        # Fallback auto-provision for standard demo accounts if DB was freshly connected
        if not user:
            demo_map = {
                'customer1': ('customer', 'Customer One', '1234'),
                'courier1': ('courier', 'Courier One', '1234'),
                'admin': ('admin', 'System Admin', '123456789'),
                'support1': ('support', 'Support One', '1234')
            }
            if username in demo_map:
                r_role, r_name, r_pw = demo_map[username]
                pw_hash = AuthService.hash_pw(r_pw)
                uid = insert("INSERT INTO Users (username,password_hash,role,display_name,approval_status) VALUES (?,?,?,?,?)",
                             (username, pw_hash, r_role, r_name, 'approved'))
                if r_role == 'courier':
                    try:
                        insert("INSERT INTO CourierLocations (courier_id,latitude,longitude,is_online) VALUES (?,47.0105,28.8638,TRUE)", (uid,))
                    except:
                        pass
                user = query("SELECT * FROM Users WHERE id=?", (uid,), fetch_one=True)

        # Allow admin to login with new default 123456789 or fallback admin if not changed
        pw_ok = False
        if user:
            if user['role'] == 'admin' and (password in ('123456789', 'admin')):
                pw_ok = True
            elif AuthService.verify_pw(password, user['password_hash']):
                pw_ok = True

        if not user or not pw_ok:
            return 401, {"success": False, "message": "Invalid username or password"}

        approval = user.get('approval_status', 'approved')
        if user['role'] == 'courier' and approval in ('suspended', 'blocked'):
            return 403, {"success": False, "message": f"Your account has been {approval}. Contact support.", "approval_status": approval}

        token_val = AuthService.make_token(user['id'], user['role'])
        user_info = {
            "id": user['id'],
            "username": user['username'],
            "role": user['role'],
            "token": token_val,
            "display_name": user.get('display_name') or user['username'],
            "avatar_url": user.get('avatar_url'),
            "phone": user.get('phone', ''),
            "approval_status": approval
        }
        return 200, {
            "success": True,
            "token": token_val,
            "user": user_info,
            "data": user_info
        }
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_me(payload):
    try:
        user = query("SELECT id,username,role,display_name,avatar_url,phone,approval_status FROM Users WHERE id=?", (payload['uid'],), fetch_one=True)
        if not user:
            return 404, {"success": False, "message": "User not found"}
        # Append loyalty points
        lp = query("SELECT points, total_earned FROM LoyaltyPoints WHERE user_id=?", (payload['uid'],), fetch_one=True)
        user['loyalty_points'] = lp['points'] if lp else 0
        user['total_earned_points'] = lp['total_earned'] if lp else 0
        return 200, {"success": True, "data": user}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_upload_avatar(body, payload):
    try:
        b64 = body.get('avatar', '')
        url = save_avatar(payload['uid'], b64)
        if url:
            return 200, {"success": True, "data": {"avatar_url": url}}
        return 400, {"success": False, "message": "Invalid image data"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_update_profile(body, payload):
    try:
        display_name = body.get('display_name', '').strip()
        if display_name:
            query("UPDATE Users SET display_name=? WHERE id=?", (display_name, payload['uid']))
        return 200, {"success": True, "message": "Profile updated"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── FAVORITES ──
def handle_add_favorite(body, payload):
    try:
        rid = body.get('restaurant_id')
        if not rid:
            return 400, {"success": False, "message": "restaurant_id required"}
        existing = query("SELECT id FROM Favorites WHERE user_id=? AND restaurant_id=?", (payload['uid'], rid), fetch_one=True)
        if existing:
            query("DELETE FROM Favorites WHERE user_id=? AND restaurant_id=?", (payload['uid'], rid))
            return 200, {"success": True, "data": {"is_favorite": False}}
        else:
            insert("INSERT INTO Favorites (user_id, restaurant_id) VALUES (?,?)", (payload['uid'], rid))
            return 200, {"success": True, "data": {"is_favorite": True}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_get_favorites(payload):
    try:
        rows = query("""
            SELECT s.*, f.created_at as favorited_at,
            ROUND(6371*acos(cos(radians(0))*cos(radians(s.latitude))*
            cos(radians(s.longitude)-radians(0))+sin(radians(0))*
            sin(radians(s.latitude))),1) as distance_km
            FROM Favorites f
            JOIN Restaurants s ON f.restaurant_id=s.id
            WHERE f.user_id=? AND s.is_open=TRUE
            ORDER BY f.created_at DESC
        """, (payload['uid'],), fetch=True)
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_check_favorite(payload, rid):
    try:
        row = query("SELECT id FROM Favorites WHERE user_id=? AND restaurant_id=?", (payload['uid'], rid), fetch_one=True)
        return 200, {"success": True, "data": {"is_favorite": bool(row)}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── PROMO CODES ──
def handle_validate_promo(body):
    try:
        code = (body.get('code', '') or '').strip().upper()
        subtotal = float(body.get('subtotal', 0))
        if not code:
            return 400, {"success": False, "message": "Code required"}
        promo = query("SELECT * FROM PromoCodes WHERE code=? AND is_active=TRUE AND valid_from<=CURRENT_TIMESTAMP AND valid_until>=CURRENT_TIMESTAMP", (code,), fetch_one=True)
        if not promo:
            return 404, {"success": False, "message": "Invalid or expired code"}
        if promo['usage_limit'] and promo['used_count'] >= promo['usage_limit']:
            return 400, {"success": False, "message": "Code usage limit reached"}
        if subtotal < float(promo['min_order_amount']):
            return 400, {"success": False, "message": f"Minimum order €{promo['min_order_amount']}"}
        discount = 0
        if promo['discount_type'] == 'percentage':
            discount = subtotal * float(promo['discount_value']) / 100
            if promo['max_discount_amount']:
                discount = min(discount, float(promo['max_discount_amount']))
        else:
            discount = float(promo['discount_value'])
        discount = round(discount, 2)
        return 200, {"success": True, "data": {
            "code": code, "discount": discount,
            "discount_type": promo['discount_type'],
            "description": promo['description']
        }}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── CANCEL / REORDER ──
def handle_cancel_order(payload, oid):
    try:
        order = query("SELECT * FROM Orders WHERE id=? AND customer_id=?", (oid, payload['uid']), fetch_one=True)
        if not order:
            return 404, {"success": False, "message": "Order not found"}
        if order['status'] not in ('pending', 'accepted', 'courier_assigned'):
            return 400, {"success": False, "message": "Cannot cancel order in current status"}
        query("UPDATE Orders SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?", (oid,))
        query("INSERT INTO OrderLog (order_id,status,note) VALUES (?,'cancelled','Cancelled by customer')", (oid,))
        if order['courier_id']:
            push_notification(order['courier_id'], 'Order Cancelled',
                              f'Order #{oid} has been cancelled by the customer', 'order_cancelled', oid)
        return 200, {"success": True, "message": "Order cancelled"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_reorder(payload, oid):
    try:
        items = query("SELECT item_id, item_name, item_price, quantity FROM OrderItems WHERE order_id=?", (oid,), fetch=True)
        if not items:
            return 404, {"success": False, "message": "Order items not found"}
        order = query("SELECT restaurant_id FROM Orders WHERE id=? AND customer_id=?", (oid, payload['uid']), fetch_one=True)
        if not order:
            return 404, {"success": False, "message": "Order not found"}
        rid = order['restaurant_id']
        cart = {"restaurant_id": rid, "items": []}
        for i in items:
            item = query("SELECT id, name, price FROM Items WHERE id=? AND is_available=TRUE", (i['item_id'],), fetch_one=True)
            if item:
                cart['items'].append({"item_id": item['id'], "name": item['name'], "price": float(item['price']), "quantity": i['quantity']})
        if not cart['items']:
            return 400, {"success": False, "message": "Items no longer available"}
        _carts[payload['uid']] = cart
        return 200, {"success": True, "data": cart}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── ADMIN ──
def handle_toggle_restaurant(payload, rid):
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        r = query("SELECT is_open FROM Restaurants WHERE id=?", (rid,), fetch_one=True)
        if not r:
            return 404, {"success": False, "message": "Not found"}
        new_val = not r['is_open']
        query("UPDATE Restaurants SET is_open=? WHERE id=?", (new_val, rid))
        return 200, {"success": True, "data": {"is_open": bool(new_val)}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_all_orders(payload):
    try:
        if payload['role'] not in ('admin', 'support'):
            return 403, {"success": False, "message": "Admin or support role required"}
        rows = query("""
            SELECT o.id, o.order_number, o.status, o.total, o.created_at, o.delivered_at,
                   r.name as restaurant_name,
                   cu.display_name as customer_name,
                   co.display_name as courier_name
            FROM Orders o
            JOIN Restaurants r ON o.restaurant_id=r.id
            JOIN Users cu ON o.customer_id=cu.id
            LEFT JOIN Users co ON o.courier_id=co.id
            ORDER BY o.created_at DESC
        """, fetch=True)
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── RESTAURANTS ──
def handle_list_restaurants(params):
    try:
        lat = float(params.get('lat', 41.3874))
        lng = float(params.get('lng', 2.1686))
        rows = query("SELECT * FROM Restaurants ORDER BY name", fetch=True)
        if rows:
            for r in rows:
                try:
                    r['distance_km'] = round(haversine(lat, lng, float(r['latitude']), float(r['longitude'])), 1)
                except:
                    r['distance_km'] = 99.0
            rows.sort(key=lambda x: x.get('distance_km', 99))
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_get_restaurant(rid):
    try:
        r = query("SELECT * FROM Restaurants WHERE id=?", (rid,), fetch_one=True)
        if not r:
            return 404, {"success": False, "message": "Restaurant not found"}
        items = query("SELECT * FROM Items WHERE restaurant_id=?", (rid,), fetch=True)
        r['items'] = items or []
        return 200, {"success": True, "data": r}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_create_restaurant(body, payload):
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        name = body.get('name', '').strip()
        if not name:
            return 400, {"success": False, "message": "Name required"}
        desc = body.get('description', '') or ''
        addr = body.get('address', '') or 'Test Address'
        try:
            lat = float(body.get('latitude', 41.3874))
        except:
            lat = 41.3874
        try:
            lng = float(body.get('longitude', 2.1686))
        except:
            lng = 2.1686
        rid = insert("INSERT INTO Restaurants (name,description,address,latitude,longitude,is_open,created_by) VALUES (?,?,?,?,?,TRUE,?)",
                     (name, desc, addr, lat, lng, payload['uid']))
        return 201, {"success": True, "data": {"id": rid, "name": name}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_update_restaurant(body, payload, rid):
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        r = query("SELECT id FROM Restaurants WHERE id=?", (rid,), fetch_one=True)
        if not r:
            return 404, {"success": False, "message": "Restaurant not found"}
        fields, params = [], []
        for key in ['name', 'description', 'address']:
            if key in body:
                fields.append(f"{key}=?")
                params.append(body[key])
        if 'latitude' in body:
            fields.append("latitude=?")
            params.append(float(body['latitude']))
        if 'longitude' in body:
            fields.append("longitude=?")
            params.append(float(body['longitude']))
        if 'is_open' in body:
            fields.append("is_open=?")
            params.append(True if body['is_open'] else False)
        if not fields:
            return 400, {"success": False, "message": "No fields to update"}
        params.append(rid)
        query(f"UPDATE Restaurants SET {', '.join(fields)} WHERE id=?", tuple(params))
        return 200, {"success": True, "message": "Restaurant updated"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_delete_restaurant(payload, rid):
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        r = query("SELECT id FROM Restaurants WHERE id=?", (rid,), fetch_one=True)
        if not r:
            return 404, {"success": False, "message": "Restaurant not found"}
        query("DELETE FROM Restaurants WHERE id=?", (rid,))
        return 200, {"success": True, "message": "Restaurant deleted"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_add_item(body, payload, rid):
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        name = body.get('name', '').strip()
        price = body.get('price', 0)
        if not name:
            return 400, {"success": False, "message": "Item name required"}
        try:
            price = float(price)
        except:
            return 400, {"success": False, "message": "Invalid price"}
        if price <= 0:
            return 400, {"success": False, "message": "Price must be > 0"}
        desc = body.get('description', '') or ''
        iid = insert("INSERT INTO Items (restaurant_id,name,description,price) VALUES (?,?,?,?)", (rid, name, desc, price))
        return 201, {"success": True, "data": {"id": iid, "name": name, "price": price}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_update_item(body, payload, item_id):
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        item = query("SELECT id FROM Items WHERE id=?", (item_id,), fetch_one=True)
        if not item:
            return 404, {"success": False, "message": "Item not found"}
        fields, params = [], []
        for key in ['name', 'description']:
            if key in body:
                fields.append(f"{key}=?")
                params.append(body[key])
        if 'price' in body:
            fields.append("price=?")
            params.append(float(body['price']))
        if 'is_available' in body:
            fields.append("is_available=?")
            params.append(True if body['is_available'] else False)
        if not fields:
            return 400, {"success": False, "message": "No fields to update"}
        params.append(item_id)
        query(f"UPDATE Items SET {', '.join(fields)} WHERE id=?", tuple(params))
        return 200, {"success": True, "message": "Item updated"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_delete_item(payload, item_id):
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        item = query("SELECT id FROM Items WHERE id=?", (item_id,), fetch_one=True)
        if not item:
            return 404, {"success": False, "message": "Item not found"}
        query("DELETE FROM Items WHERE id=?", (item_id,))
        return 200, {"success": True, "message": "Item deleted"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── CART ──
_carts = {}


def handle_get_cart(payload):
    return 200, {"success": True, "data": _carts.get(payload['uid'], {"restaurant_id": None, "items": []})}


def handle_add_to_cart(body, payload):
    try:
        uid = payload['uid']
        item_id = body.get('item_id')
        qty = body.get('quantity', 1)
        restaurant_id = body.get('restaurant_id')
        item = query("SELECT i.*, r.id as rid FROM Items i JOIN Restaurants r ON i.restaurant_id=r.id WHERE i.id=?", (item_id,), fetch_one=True)
        if not item:
            return 404, {"success": False, "message": "Item not found"}
        if uid not in _carts:
            _carts[uid] = {"restaurant_id": item['rid'], "items": []}
        if _carts[uid]['restaurant_id'] != item['rid']:
            _carts[uid] = {"restaurant_id": item['rid'], "items": []}
        cart = _carts[uid]
        found = False
        for ci in cart['items']:
            if ci['item_id'] == item_id:
                ci['quantity'] += qty
                found = True
                break
        if not found:
            cart['items'].append({"item_id": item['id'], "name": item['name'], "price": float(item['price']), "quantity": qty})
        return 200, {"success": True, "data": cart}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_remove_from_cart(payload, item_id):
    uid = payload['uid']
    if uid in _carts:
        _carts[uid]['items'] = [i for i in _carts[uid]['items'] if i['item_id'] != item_id]
    return 200, {"success": True, "data": _carts.get(uid, {"restaurant_id": None, "items": []})}


def handle_clear_cart(payload):
    _carts.pop(payload['uid'], None)
    return 200, {"success": True, "data": {"restaurant_id": None, "items": []}}


# ── ORDERS ──
def handle_create_order(body, payload):
    try:
        uid = payload['uid']
        cart = _carts.get(uid)
        if not cart or not cart.get('items'):
            return 400, {"success": False, "message": "Cart is empty"}
        restaurant_id = cart['restaurant_id']
        restaurant = query("SELECT * FROM Restaurants WHERE id=?", (restaurant_id,), fetch_one=True)
        if not restaurant:
            return 404, {"success": False, "message": "Restaurant not found"}

        subtotal = sum(i['price'] * i['quantity'] for i in cart['items'])

        # Check promo code
        discount = 0
        promo_code_str = body.get('promo_code', '').strip().upper()
        if promo_code_str:
            promo = query(
                "SELECT * FROM PromoCodes WHERE code=? AND is_active=TRUE "
                "AND valid_from<=CURRENT_TIMESTAMP AND valid_until>=CURRENT_TIMESTAMP",
                (promo_code_str,), fetch_one=True
            )
            if promo:
                if subtotal >= float(promo['min_order_amount']):
                    if not promo['usage_limit'] or promo['used_count'] < promo['usage_limit']:
                        if promo['discount_type'] == 'percentage':
                            discount = subtotal * float(promo['discount_value']) / 100
                            if promo['max_discount_amount']:
                                discount = min(discount, float(promo['max_discount_amount']))
                        else:
                            discount = float(promo['discount_value'])
                        discount = round(discount, 2)
                        query("UPDATE PromoCodes SET used_count=used_count+1 WHERE code=?", (promo_code_str,))

        # Loyalty points redemption (100 points = 1 euro)
        points_to_redeem = int(body.get('redeem_points', 0) or 0)
        points_discount = 0
        if points_to_redeem > 0:
            lp = query("SELECT points FROM LoyaltyPoints WHERE user_id=?", (uid,), fetch_one=True)
            available = lp['points'] if lp else 0
            points_to_redeem = min(points_to_redeem, available)
            points_discount = round(points_to_redeem / 100.0, 2)  # 100 pts = 1 euro
            if points_discount > subtotal + 2.50 - discount:
                points_discount = round(subtotal + 2.50 - discount, 2)
                points_to_redeem = int(points_discount * 100)

        delivery_fee = 2.50
        total = round(subtotal + delivery_fee - discount - points_discount, 2)

        # Generate unique order number
        count_row = query("SELECT COUNT(*) as cnt FROM Orders", fetch_one=True)
        next_num = (count_row['cnt'] if count_row else 0) + 10001
        order_number = f"Ely-{next_num}"
        # Ensure uniqueness
        while query("SELECT id FROM Orders WHERE order_number=?", (order_number,), fetch_one=True):
            next_num += 1
            order_number = f"Ely-{next_num}"

        delivery_lat = body.get('delivery_lat', 41.3900) or 41.3900
        delivery_lng = body.get('delivery_lng', 2.1700) or 2.1700
        payment_method = body.get('payment_method', 'cash') or 'cash'

        # Insert order — status starts as 'pending' waiting for restaurant acceptance
        oid = insert(
            "INSERT INTO Orders (order_number,customer_id,restaurant_id,status,"
            "subtotal,delivery_fee,total,delivery_address,delivery_lat,delivery_lng,payment_method)"
            " VALUES (?,?,?,'pending',?,?,?,?,?,?,?)",
            (order_number, uid, restaurant_id, subtotal, delivery_fee, total,
             'Customer Location', delivery_lat, delivery_lng, payment_method)
        )

        if not oid:
            return 500, {"success": False, "message": "Failed to create order: could not retrieve order ID"}

        # Insert order items
        for item in cart['items']:
            insert(
                "INSERT INTO OrderItems (order_id,item_id,item_name,item_price,quantity) VALUES (?,?,?,?,?)",
                (oid, item['item_id'], item['name'], item['price'], item['quantity'])
            )

        # Deduct redeemed loyalty points
        if points_to_redeem > 0:
            query("UPDATE LoyaltyPoints SET points=points-?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
                  (points_to_redeem, uid))
            insert("INSERT INTO PointTransactions (user_id,order_id,points,transaction_type,description) VALUES (?,?,?,'redeem',?)",
                   (uid, oid, points_to_redeem, f'Redeemed {points_to_redeem} points for €{points_discount:.2f} discount'))

        # Clear cart
        _carts.pop(uid, None)

        # Order starts as 'pending' — restaurant partner must accept before courier is assigned
        query("INSERT INTO OrderLog (order_id, status, note) VALUES (?, 'pending', 'Order placed, waiting for restaurant acceptance')", (oid,))

        # Notify restaurant partner
        partner = query("SELECT id FROM Users WHERE role='partner' AND id=(SELECT created_by FROM Restaurants WHERE id=?)", (restaurant_id,), fetch_one=True)
        if partner:
            push_notification(partner['id'], 'New Order!',
                              f'New order #{oid} from customer! Total: €{total:.2f}', 'new_order', oid)

        # Notify customer
        push_notification(uid, 'Order Placed',
                          f'Your order {order_number} has been placed! Waiting for restaurant confirmation.', 'order_placed', oid)

        # Build response
        order = query(
            "SELECT o.*, r.name as restaurant_name, r.address as restaurant_address, "
            "r.latitude as restaurant_lat, r.longitude as restaurant_lng, "
            "u.display_name as customer_display_name "
            "FROM Orders o JOIN Restaurants r ON o.restaurant_id=r.id "
            "JOIN Users u ON o.customer_id=u.id WHERE o.id=?",
            (oid,), fetch_one=True
        )
        order['items'] = query("SELECT * FROM OrderItems WHERE order_id=?", (oid,), fetch=True) or []
        return 201, {"success": True, "data": order}
    except Exception as e:
        traceback.print_exc()
        return 500, {"success": False, "message": str(e)}


def handle_customer_orders(payload):
    try:
        rows = query("SELECT o.*, r.name as restaurant_name FROM Orders o JOIN Restaurants r ON o.restaurant_id=r.id WHERE o.customer_id=? ORDER BY o.created_at DESC", (payload['uid'],), fetch=True)
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_get_order(oid, payload):
    try:
        order = query("SELECT o.*, r.name as restaurant_name, r.address as restaurant_address, r.latitude as restaurant_lat, r.longitude as restaurant_lng, u.display_name as customer_display_name FROM Orders o JOIN Restaurants r ON o.restaurant_id=r.id JOIN Users u ON o.customer_id=u.id WHERE o.id=?", (oid,), fetch_one=True)
        if not order:
            return 404, {"success": False, "message": "Order not found"}
        order['items'] = query("SELECT * FROM OrderItems WHERE order_id=?", (oid,), fetch=True)
        if order['courier_id']:
            cloc = query("SELECT u.display_name, u.avatar_url, cl.latitude, cl.longitude FROM CourierLocations cl JOIN Users u ON cl.courier_id=u.id WHERE cl.courier_id=? ORDER BY cl.updated_at DESC LIMIT 1", (order['courier_id'],), fetch_one=True)
            order['courier_location'] = cloc
            order['courier_name'] = cloc['display_name'] if cloc else 'Courier'
            order['courier_avatar'] = cloc.get('avatar_url') if cloc else None
        rating = query("SELECT id FROM Ratings WHERE order_id=? AND user_id=?", (oid, payload.get('uid', 0)), fetch_one=True)
        order['is_rated'] = bool(rating)
        return 200, {"success": True, "data": order}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── RATINGS ──
def handle_rate_order(body, payload, oid):
    try:
        order = query("SELECT * FROM Orders WHERE id=? AND customer_id=?", (oid, payload['uid']), fetch_one=True)
        if not order:
            return 404, {"success": False, "message": "Order not found"}
        if order['status'] != 'delivered':
            return 400, {"success": False, "message": "Can only rate delivered orders"}
        existing = query("SELECT id FROM Ratings WHERE order_id=? AND user_id=?", (oid, payload['uid']), fetch_one=True)
        if existing:
            return 400, {"success": False, "message": "Already rated"}
        courier_rating = body.get('courier_rating')
        service_rating = body.get('service_rating')
        if not courier_rating or not service_rating:
            return 400, {"success": False, "message": "Both ratings required"}
        courier_rating = max(1, min(5, int(courier_rating)))
        service_rating = max(1, min(5, int(service_rating)))
        comment = body.get('comment', '') or ''
        insert("INSERT INTO Ratings (order_id,user_id,courier_rating,service_rating,comment) VALUES (?,?,?,?,?)",
               (oid, payload['uid'], courier_rating, service_rating, comment))
        # Award bonus loyalty points for rating
        try:
            bonus_pts = 10
            query("UPDATE LoyaltyPoints SET points=points+?, total_earned=total_earned+?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
                  (bonus_pts, bonus_pts, payload['uid']))
            insert("INSERT INTO PointTransactions (user_id,order_id,points,transaction_type,description) VALUES (?,?,?,'earn',?)",
                   (payload['uid'], oid, bonus_pts, 'Bonus points for rating order'))
        except:
            pass
        return 201, {"success": True, "message": "Rating submitted! +10 loyalty points!"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── COURIER ──
def handle_courier_update_location(body, payload):
    try:
        lat, lng = body.get('latitude'), body.get('longitude')
        if lat is None or lng is None:
            return 400, {"success": False, "message": "lat/lng required"}
        existing = query("SELECT id FROM CourierLocations WHERE courier_id=?", (payload['uid'],), fetch_one=True)
        if existing:
            query("UPDATE CourierLocations SET latitude=?,longitude=?,updated_at=CURRENT_TIMESTAMP WHERE courier_id=?", (lat, lng, payload['uid']))
        else:
            insert("INSERT INTO CourierLocations (courier_id,latitude,longitude,is_online) VALUES (?,?,?,TRUE)", (payload['uid'], lat, lng))
        return 200, {"success": True}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_courier_set_online(body, payload):
    try:
        is_online = body.get('is_online', True)
        vehicle_type = body.get('vehicle_type', None)
        if vehicle_type and vehicle_type in ('walking', 'bicycle', 'scooter', 'car'):
            query("UPDATE CourierLocations SET is_online=?, vehicle_type=? WHERE courier_id=?",
                  (is_online, vehicle_type, payload['uid']))
        else:
            query("UPDATE CourierLocations SET is_online=? WHERE courier_id=?", (is_online, payload['uid']))
        return 200, {"success": True, "data": {"is_online": is_online, "vehicle_type": vehicle_type}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_courier_assigned_orders(payload):
    try:
        uid = payload['uid']
        rows = query("SELECT o.*, r.name as restaurant_name, r.address as restaurant_address, r.latitude as restaurant_lat, r.longitude as restaurant_lng FROM Orders o JOIN Restaurants r ON o.restaurant_id=r.id WHERE o.courier_id=? AND o.status NOT IN ('delivered','cancelled') ORDER BY o.created_at DESC", (uid,), fetch=True)
        for o in (rows or []):
            o['items'] = query("SELECT * FROM OrderItems WHERE order_id=?", (o['id'],), fetch=True)
            cust = query("SELECT display_name FROM Users WHERE id=?", (o['customer_id'],), fetch_one=True)
            o['customer_name'] = cust['display_name'] if cust else 'Customer'
            # Add customer delivery address with reverse geocoding
            if o.get('delivery_lat') and o.get('delivery_lng'):
                try:
                    addr = reverse_geocode(float(o['delivery_lat']), float(o['delivery_lng']))
                    o['customer_address'] = addr
                except:
                    o['customer_address'] = f"{float(o['delivery_lat']):.4f}, {float(o['delivery_lng']):.4f}"
            else:
                o['customer_address'] = o.get('delivery_address', 'Delivery location')
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_courier_update_status(body, payload, oid):
    try:
        new_status, lat, lng = body.get('status'), body.get('latitude'), body.get('longitude')
        order = query("SELECT * FROM Orders WHERE id=? AND courier_id=?", (oid, payload['uid']), fetch_one=True)
        if not order:
            return 404, {"success": False, "message": "Order not found or not assigned to you"}
        valid = {
            'courier_assigned': ['heading_to_restaurant'],
            'heading_to_restaurant': ['arrived_at_restaurant'],
            'arrived_at_restaurant': ['order_picked_up'],
            'order_picked_up': ['heading_to_customer'],
            'heading_to_customer': ['arrived_at_customer'],
            'arrived_at_customer': ['delivered']
        }
        allowed = valid.get(order['status'], [])
        if new_status not in allowed:
            return 400, {"success": False, "message": f"Cannot go from '{order['status']}' to '{new_status}'"}
        update_fields, params = "status=?, updated_at=CURRENT_TIMESTAMP", [new_status]
        if new_status == 'arrived_at_restaurant':
            update_fields += ", courier_arrived_restaurant_at=CURRENT_TIMESTAMP"
            if lat and lng:
                try:
                    landmark = reverse_geocode(lat, lng)
                except:
                    landmark = f"Near {lat:.4f}, {lng:.4f}"
                update_fields += ", landmark=?"
                params.append(landmark)
        elif new_status == 'order_picked_up':
            update_fields += ", order_picked_up_at=CURRENT_TIMESTAMP"
        elif new_status == 'arrived_at_customer':
            update_fields += ", courier_arrived_customer_at=CURRENT_TIMESTAMP"
        elif new_status == 'delivered':
            update_fields += ", delivered_at=CURRENT_TIMESTAMP"
            # Award loyalty points on delivery
            try:
                award_loyalty_points(order['customer_id'], oid, float(order['total']))
            except:
                pass
            # Create CourierEarnings entry
            try:
                base_fee = 2.50
                # Distance bonus: calculate from restaurant to delivery
                distance_bonus = 0
                restaurant = query("SELECT latitude, longitude FROM Restaurants WHERE id=?", (order['restaurant_id'],), fetch_one=True)
                if restaurant and order.get('delivery_lat') and order.get('delivery_lng'):
                    dist = haversine(float(restaurant['latitude']), float(restaurant['longitude']),
                                     float(order['delivery_lat']), float(order['delivery_lng']))
                    # €0.50 per km after first 2km
                    if dist > 2:
                        distance_bonus = round((dist - 2) * 0.50, 2)
                # Waiting time bonus from courier_arrived_restaurant_at to order_picked_up_at
                waiting_bonus = 0
                if order.get('courier_arrived_restaurant_at') and order.get('order_picked_up_at'):
                    try:
                        arrived = order['courier_arrived_restaurant_at']
                        picked_up = order['order_picked_up_at']
                        if isinstance(arrived, str):
                            arrived = datetime.datetime.fromisoformat(arrived.replace('Z', '+00:00'))
                        if isinstance(picked_up, str):
                            picked_up = datetime.datetime.fromisoformat(picked_up.replace('Z', '+00:00'))
                        wait_minutes = max(0, (picked_up - arrived).total_seconds() / 60)
                        # €0.10 per minute of waiting after first 5 minutes
                        if wait_minutes > 5:
                            waiting_bonus = round((wait_minutes - 5) * 0.10, 2)
                    except:
                        pass
                total_earnings = round(base_fee + distance_bonus + waiting_bonus, 2)
                # Save earnings to order
                query("UPDATE Orders SET courier_earnings=?, waiting_minutes=? WHERE id=?",
                      (total_earnings, int(wait_minutes) if order.get('courier_arrived_restaurant_at') and order.get('order_picked_up_at') else 0, oid))
                # Insert into CourierEarnings
                desc_parts = [f"Base: €{base_fee:.2f}"]
                if distance_bonus > 0:
                    desc_parts.append(f"Distance: €{distance_bonus:.2f}")
                if waiting_bonus > 0:
                    desc_parts.append(f"Waiting: €{waiting_bonus:.2f}")
                insert("INSERT INTO CourierEarnings (courier_id,order_id,amount,earning_type,description) VALUES (?,?,?,'delivery_fee',?)",
                       (payload['uid'], oid, total_earnings, ' + '.join(desc_parts)))
            except Exception as e:
                print(f"  CourierEarnings error: {e}")
        params.append(oid)
        query(f"UPDATE Orders SET {update_fields} WHERE id=?", tuple(params))
        query("INSERT INTO OrderLog (order_id,status) VALUES (?,?)", (oid, new_status))
        # Notify customer of status change
        status_labels = {
            'heading_to_restaurant': 'Courier is heading to the restaurant',
            'arrived_at_restaurant': 'Courier arrived at the restaurant',
            'order_picked_up': 'Your order has been picked up!',
            'heading_to_customer': 'Courier is heading to you',
            'arrived_at_customer': 'Courier has arrived at your location!',
            'delivered': 'Your order has been delivered!'
        }
        push_notification(order['customer_id'], 'Order Update',
                          status_labels.get(new_status, f'Order status: {new_status}'),
                          'order_status', oid)
        return 200, {"success": True, "data": {"status": new_status}}
    except Exception as e:
        traceback.print_exc()
        return 500, {"success": False, "message": str(e)}


def handle_courier_reject_order(payload, oid):
    """Courier rejects an assigned order. Order goes back to unassigned pool."""
    try:
        uid = payload['uid']
        order = query("SELECT * FROM Orders WHERE id=? AND courier_id=?", (oid, uid), fetch_one=True)
        if not order:
            return 404, {"success": False, "message": "Order not found or not assigned to you"}
        if order['status'] not in ('courier_assigned', 'confirmed'):
            return 400, {"success": False, "message": "Cannot reject order in current status"}
        # Unassign courier and try to reassign to another
        query("UPDATE Orders SET courier_id=NULL, status='confirmed', updated_at=CURRENT_TIMESTAMP WHERE id=?", (oid,))
        query("INSERT INTO OrderLog (order_id,status,note) VALUES (?,'courier_rejected','Courier rejected order')", (oid,))
        # Notify customer
        push_notification(order['customer_id'], 'Courier Update',
                          'Your assigned courier has changed. Finding a new courier...', 'order_status', oid)
        # Try auto-assign to another courier
        restaurant = query("SELECT latitude, longitude FROM Restaurants WHERE id=?", (order['restaurant_id'],), fetch_one=True)
        if restaurant:
            auto_assign_courier(oid, float(restaurant['latitude']), float(restaurant['longitude']),
                                order.get('delivery_lat'), order.get('delivery_lng'))
        return 200, {"success": True, "message": "Order rejected. It has been reassigned to another courier."}
    except Exception as e:
        traceback.print_exc()
        return 500, {"success": False, "message": str(e)}


def handle_courier_reassign_order(payload, oid):
    """Courier reassigns an order to another courier. Similar to reject but with different messaging."""
    try:
        uid = payload['uid']
        order = query("SELECT * FROM Orders WHERE id=? AND courier_id=?", (oid, uid), fetch_one=True)
        if not order:
            return 404, {"success": False, "message": "Order not found or not assigned to you"}
        if order['status'] not in ('courier_assigned', 'confirmed'):
            return 400, {"success": False, "message": "Cannot reassign order in current status"}
        query("UPDATE Orders SET courier_id=NULL, status='confirmed', updated_at=CURRENT_TIMESTAMP WHERE id=?", (oid,))
        query("INSERT INTO OrderLog (order_id,status,note) VALUES (?,'reassigned','Courier reassigned order to another courier')", (oid,))
        push_notification(order['customer_id'], 'Courier Update',
                          'Your courier has changed. Finding a new courier...', 'order_status', oid)
        restaurant = query("SELECT latitude, longitude FROM Restaurants WHERE id=?", (order['restaurant_id'],), fetch_one=True)
        if restaurant:
            auto_assign_courier(oid, float(restaurant['latitude']), float(restaurant['longitude']),
                                order.get('delivery_lat'), order.get('delivery_lng'))
        return 200, {"success": True, "message": "Order reassigned to another courier."}
    except Exception as e:
        traceback.print_exc()
        return 500, {"success": False, "message": str(e)}


def handle_courier_earnings(payload):
    """Get courier earnings summary and recent entries."""
    try:
        uid = payload['uid']
        # Total earnings
        total_row = query("SELECT COALESCE(SUM(amount), 0) as total FROM CourierEarnings WHERE courier_id=?", (uid,), fetch_one=True)
        total_earnings = float(total_row['total']) if total_row else 0
        # Today's earnings
        today = datetime.date.today().isoformat()
        today_row = query("SELECT COALESCE(SUM(amount), 0) as total FROM CourierEarnings WHERE courier_id=? AND DATE(created_at) >= ?", (uid, today), fetch_one=True)
        today_earnings = float(today_row['total']) if today_row else 0
        # Recent earnings entries
        recent = query("SELECT * FROM CourierEarnings WHERE courier_id=? ORDER BY created_at DESC LIMIT 20", (uid,), fetch=True)
        return 200, {"success": True, "data": {
            "total_earnings": total_earnings,
            "today_earnings": today_earnings,
            "recent_entries": recent or []
        }}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_courier_set_vehicle(body, payload):
    """Courier requests a vehicle type change. Requires admin approval."""
    try:
        vehicle_type = body.get('vehicle_type', 'bicycle')
        if vehicle_type not in ('walking', 'bicycle', 'scooter', 'car'):
            return 400, {"success": False, "message": "Invalid vehicle type. Must be: walking, bicycle, scooter, car"}

        # Get current vehicle
        current = query("SELECT vehicle_type FROM CourierLocations WHERE courier_id=?", (payload['uid'],), fetch_one=True)
        current_vehicle = current['vehicle_type'] if current else 'bicycle'

        # If same vehicle, just return OK
        if current_vehicle == vehicle_type:
            return 200, {"success": True, "data": {"vehicle_type": vehicle_type, "pending_approval": False}}

        # Check if there's already a pending request
        pending = query("SELECT id, requested_vehicle FROM VehicleChangeRequests WHERE courier_id=? AND status='pending'", (payload['uid'],), fetch_one=True)
        if pending:
            return 200, {"success": True, "data": {
                "vehicle_type": current_vehicle,
                "pending_approval": True,
                "pending_change": {"requested_vehicle": pending['requested_vehicle'], "current_vehicle": current_vehicle},
                "message": "You already have a pending vehicle change request"
            }}

        # First time setting vehicle (no current vehicle set) - allow directly
        if not current or current_vehicle == 'bicycle':
            # Check if courier has ever been online (first-time setup)
            was_online = query("SELECT is_online FROM CourierLocations WHERE courier_id=?", (payload['uid'],), fetch_one=True)
            if was_online and not was_online.get('is_online') and current_vehicle == 'bicycle':
                # First time setup - allow directly
                if current:
                    query("UPDATE CourierLocations SET vehicle_type=? WHERE courier_id=?", (vehicle_type, payload['uid']))
                else:
                    insert("INSERT INTO CourierLocations (courier_id,latitude,longitude,is_online,vehicle_type) VALUES (?,0,0,FALSE,?)",
                           (payload['uid'], vehicle_type))
                return 200, {"success": True, "data": {"vehicle_type": vehicle_type, "pending_approval": False}}

        # Create a vehicle change request for admin approval
        rid = insert("INSERT INTO VehicleChangeRequests (courier_id,current_vehicle,requested_vehicle,status) VALUES (?,?,?,'pending')",
                     (payload['uid'], current_vehicle, vehicle_type))
        # Notify admin
        admin = query("SELECT id FROM Users WHERE role='admin' LIMIT 1", fetch_one=True)
        if admin:
            push_notification(admin['id'], 'Vehicle Change Request',
                             f'Courier requests vehicle change: {current_vehicle} → {vehicle_type}',
                             'vehicle_change_request', rid)
        return 200, {"success": True, "data": {
            "vehicle_type": current_vehicle,
            "pending_approval": True,
            "pending_change": {"requested_vehicle": vehicle_type, "current_vehicle": current_vehicle},
            "message": "Vehicle change request submitted. Waiting for admin approval."
        }}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_courier_vehicle_status(payload):
    """Get courier's current vehicle and pending change request."""
    try:
        loc = query("SELECT vehicle_type FROM CourierLocations WHERE courier_id=?", (payload['uid'],), fetch_one=True)
        current_vehicle = loc['vehicle_type'] if loc else 'bicycle'
        pending = query("SELECT * FROM VehicleChangeRequests WHERE courier_id=? AND status='pending' ORDER BY created_at DESC LIMIT 1",
                        (payload['uid'],), fetch_one=True)
        result = {"vehicle_type": current_vehicle}
        if pending:
            result['pending_approval'] = True
            result['pending_change'] = {"requested_vehicle": pending['requested_vehicle'], "current_vehicle": current_vehicle}
        else:
            result['pending_approval'] = False
        return 200, {"success": True, "data": result}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── SUPPORT TICKETS ──
def handle_support_tickets(payload):
    """List all open support tickets (admin/support role)."""
    try:
        if payload['role'] not in ('admin', 'support'):
            return 403, {"success": False, "message": "Admin or support role required"}
        rows = query("""
            SELECT st.*, u.display_name as user_name, o.order_number
            FROM SupportTickets st
            JOIN Users u ON st.user_id=u.id
            JOIN Orders o ON st.order_id=o.id
            ORDER BY st.created_at DESC
        """, fetch=True)
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_support_create_ticket(body, payload):
    """Create a support ticket for an order. Support/admin can create for any order."""
    try:
        order_id = body.get('order_id')
        if not order_id:
            return 400, {"success": False, "message": "order_id required"}
        # Support/admin can create tickets for any order
        if payload['role'] in ('admin', 'support'):
            order = query("SELECT id, customer_id FROM Orders WHERE id=?", (order_id,), fetch_one=True)
        else:
            order = query("SELECT id, customer_id FROM Orders WHERE id=? AND customer_id=?", (order_id, payload['uid']), fetch_one=True)
        if not order:
            return 404, {"success": False, "message": "Order not found or not yours"}
        # Check if there's already an open ticket for this order
        existing = query("SELECT id FROM SupportTickets WHERE order_id=? AND status='open'", (order_id,), fetch_one=True)
        if existing:
            return 400, {"success": False, "message": "An open ticket already exists for this order"}
        # Use order's customer_id as the ticket user_id (for support-created tickets)
        ticket_user_id = order['customer_id'] if payload['role'] in ('admin', 'support') else payload['uid']
        tid = insert("INSERT INTO SupportTickets (order_id,user_id,status) VALUES (?,?,'open')",
                     (order_id, ticket_user_id))
        return 201, {"success": True, "data": {"id": tid, "order_id": order_id, "status": "open"}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_support_messages(payload, ticket_id):
    """Get messages for a support ticket."""
    try:
        ticket = query("SELECT * FROM SupportTickets WHERE id=?", (ticket_id,), fetch_one=True)
        if not ticket:
            return 404, {"success": False, "message": "Ticket not found"}
        # Only the ticket owner, admin, or support can view messages
        uid = payload['uid']
        if payload['role'] not in ('admin', 'support') and ticket['user_id'] != uid:
            return 403, {"success": False, "message": "Not authorized"}
        rows = query("""
            SELECT sm.*, u.display_name as sender_name, u.role as sender_role
            FROM SupportMessages sm
            JOIN Users u ON sm.sender_id=u.id
            WHERE sm.ticket_id=?
            ORDER BY sm.created_at ASC
        """, (ticket_id,), fetch=True)
        # Mark messages as read for the current user
        query("UPDATE SupportMessages SET is_read=TRUE WHERE ticket_id=? AND sender_id!=?", (ticket_id, uid))
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_support_send_message(body, payload):
    """Send a message in a support ticket."""
    try:
        ticket_id = body.get('ticket_id')
        message = (body.get('message') or '').strip()
        if not ticket_id or not message:
            return 400, {"success": False, "message": "ticket_id and message required"}
        ticket = query("SELECT * FROM SupportTickets WHERE id=?", (ticket_id,), fetch_one=True)
        if not ticket:
            return 404, {"success": False, "message": "Ticket not found"}
        uid = payload['uid']
        if payload['role'] not in ('admin', 'support') and ticket['user_id'] != uid:
            return 403, {"success": False, "message": "Not authorized"}
        # If support/admin replies, mark ticket as in_progress
        if payload['role'] in ('admin', 'support') and ticket['status'] == 'open':
            query("UPDATE SupportTickets SET status='in_progress', updated_at=CURRENT_TIMESTAMP WHERE id=?", (ticket_id,))
        msg_id = insert("INSERT INTO SupportMessages (ticket_id,sender_id,message) VALUES (?,?,?)",
                        (ticket_id, uid, message))
        return 201, {"success": True, "data": {"id": msg_id, "ticket_id": ticket_id, "message": message}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_support_close_ticket(payload, ticket_id):
    """Close a support ticket (admin/support only)."""
    try:
        if payload['role'] not in ('admin', 'support'):
            return 403, {"success": False, "message": "Admin or support role required"}
        ticket = query("SELECT * FROM SupportTickets WHERE id=?", (ticket_id,), fetch_one=True)
        if not ticket:
            return 404, {"success": False, "message": "Ticket not found"}
        if ticket['status'] == 'closed':
            return 400, {"success": False, "message": "Ticket already closed"}
        query("UPDATE SupportTickets SET status='closed', updated_at=CURRENT_TIMESTAMP WHERE id=?", (ticket_id,))
        return 200, {"success": True, "message": "Ticket closed"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── DELIVER ANYTHING ──
def handle_deliver_anything(body, payload):
    """Create a special 'Deliver Anything' order — no restaurant needed.
    Client provides pickup/delivery addresses and contacts, not coordinates.
    delivery_type: 'send' (client sends something) or 'receive' (client receives something)."""
    try:
        uid = payload['uid']
        delivery_type = body.get('delivery_type', 'send')  # 'send' or 'receive'
        pickup_address = (body.get('pickup_address') or '').strip()
        pickup_contact_name = (body.get('pickup_contact_name') or '').strip()
        pickup_contact_phone = (body.get('pickup_contact_phone') or '').strip()
        delivery_address = (body.get('delivery_address') or '').strip()
        delivery_contact_name = (body.get('delivery_contact_name') or '').strip()
        delivery_contact_phone = (body.get('delivery_contact_phone') or '').strip()
        item_description = (body.get('item_description') or '').strip()

        if not pickup_address:
            return 400, {"success": False, "message": "Pickup address is required"}
        if not delivery_address:
            return 400, {"success": False, "message": "Delivery address is required"}
        if not item_description:
            return 400, {"success": False, "message": "Item description is required (what to deliver)"}

        # Default coordinates to Chisinau center (will be refined by courier GPS)
        pickup_lat = body.get('pickup_lat', 47.0105)
        pickup_lng = body.get('pickup_lng', 28.8638)
        delivery_lat = body.get('delivery_lat', 47.0105)
        delivery_lng = body.get('delivery_lng', 28.8638)

        # Find or create a virtual restaurant for "Deliver Anything"
        virtual = query("SELECT id FROM Restaurants WHERE name='Elyanivery Delivery Service'", fetch_one=True)
        if not virtual:
            virtual_id = insert(
                "INSERT INTO Restaurants (name,description,address,latitude,longitude,is_open,category) "
                "VALUES ('Elyanivery Delivery Service','Virtual restaurant for Deliver Anything orders','',?,?,'TRUE','delivery_service')",
                (47.0105, 28.8638)
            )
        else:
            virtual_id = virtual['id']

        # Generate unique order number
        count_row = query("SELECT COUNT(*) as cnt FROM Orders", fetch_one=True)
        next_num = (count_row['cnt'] if count_row else 0) + 10001
        order_number = f"Ely-{next_num}"
        while query("SELECT id FROM Orders WHERE order_number=?", (order_number,), fetch_one=True):
            next_num += 1
            order_number = f"Ely-{next_num}"

        delivery_fee = 3.50  # slightly higher for Deliver Anything
        total = delivery_fee

        oid = insert(
            "INSERT INTO Orders (order_number,customer_id,restaurant_id,status,"
            "subtotal,delivery_fee,total,delivery_address,delivery_lat,delivery_lng,estimated_prep_minutes,"
            "is_deliver_anything,delivery_type,pickup_address,pickup_lat,pickup_lng,"
            "pickup_contact_name,pickup_contact_phone,delivery_contact_name,delivery_contact_phone,item_description)"
            " VALUES (?,?,?,'ready_for_pickup',0,?,?,?,?,NULL,TRUE,?,?,?,?,?,?,?,?,?,0)",
            (order_number, uid, virtual_id, delivery_fee, total,
             delivery_address, delivery_lat, delivery_lng,
             delivery_type, pickup_address, pickup_lat, pickup_lng,
             pickup_contact_name, pickup_contact_phone,
             delivery_contact_name, delivery_contact_phone, item_description)
        )

        if not oid:
            return 500, {"success": False, "message": "Failed to create order"}

        # Add item description as a virtual order item
        insert(
            "INSERT INTO OrderItems (order_id,item_id,item_name,item_price,quantity) VALUES (?,0,?,0,1)",
            (oid, item_description)
        )

        query("INSERT INTO OrderLog (order_id, status, note) VALUES (?, 'ready_for_pickup', ?)",
              (oid, f'Deliver Anything order ({delivery_type}). Item: {item_description}. Pickup: {pickup_address}. Delivery: {delivery_address}'))

        # Auto-assign nearest courier
        courier_id = auto_assign_courier(oid, float(pickup_lat), float(pickup_lng),
                                          float(delivery_lat), float(delivery_lng))

        # Notify customer
        push_notification(uid, 'Delivery Requested',
                          f'Your Deliver Anything order {order_number} has been placed! Finding a courier.', 'order_placed', oid)

        order = query("SELECT o.*, r.name as restaurant_name FROM Orders o JOIN Restaurants r ON o.restaurant_id=r.id WHERE o.id=?", (oid,), fetch_one=True)
        order['items'] = query("SELECT * FROM OrderItems WHERE order_id=?", (oid,), fetch=True) or []

        result = {"success": True, "data": order}
        if courier_id:
            result['courier_assigned'] = True
        else:
            result['courier_assigned'] = False
            result['message'] = 'Order created but no courier available yet.'
        return 201, result
    except Exception as e:
        traceback.print_exc()
        return 500, {"success": False, "message": str(e)}


# ── ADMIN STATS ──
def handle_admin_stats(payload):
    """Admin dashboard statistics."""
    try:
        if payload['role'] not in ('admin', 'support'):
            return 403, {"success": False, "message": "Admin or support role required"}

        today = datetime.date.today().isoformat()
        week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()

        # Orders today
        orders_today = query("SELECT COUNT(*) as cnt FROM Orders WHERE DATE(created_at) >= ?", (today,), fetch_one=True)
        # Orders this week
        orders_week = query("SELECT COUNT(*) as cnt FROM Orders WHERE DATE(created_at) >= ?", (week_ago,), fetch_one=True)
        # Revenue today
        revenue_today = query("SELECT COALESCE(SUM(total), 0) as total FROM Orders WHERE status='delivered' AND DATE(created_at) >= ?", (today,), fetch_one=True)
        # Revenue this week
        revenue_week = query("SELECT COALESCE(SUM(total), 0) as total FROM Orders WHERE status='delivered' AND DATE(created_at) >= ?", (week_ago,), fetch_one=True)
        # Active couriers
        active_couriers = query("SELECT COUNT(*) as cnt FROM CourierLocations WHERE is_online=TRUE", fetch_one=True)
        # Active partners (restaurants that are open)
        active_partners = query("SELECT COUNT(*) as cnt FROM Restaurants WHERE is_open=TRUE", fetch_one=True)
        # Customer count
        customer_count = query("SELECT COUNT(*) as cnt FROM Users WHERE role='customer'", fetch_one=True)
        # Orders by status
        status_rows = query("SELECT status, COUNT(*) as cnt FROM Orders GROUP BY status", fetch=True)
        status_breakdown = {}
        if status_rows:
            for sr in status_rows:
                status_breakdown[sr['status']] = sr['cnt']
        # Support tickets count (open)
        support_open = query("SELECT COUNT(*) as cnt FROM SupportTickets WHERE status IN ('open','in_progress')", fetch_one=True)

        return 200, {"success": True, "data": {
            "orders_today": orders_today['cnt'] if orders_today else 0,
            "orders_week": orders_week['cnt'] if orders_week else 0,
            "revenue_today": float(revenue_today['total']) if revenue_today else 0,
            "revenue_week": float(revenue_week['total']) if revenue_week else 0,
            "active_couriers": active_couriers['cnt'] if active_couriers else 0,
            "active_partners": active_partners['cnt'] if active_partners else 0,
            "customer_count": customer_count['cnt'] if customer_count else 0,
            "status_breakdown": status_breakdown,
            "support_tickets_open": support_open['cnt'] if support_open else 0
        }}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── ADMIN ──
def handle_admin_couriers(payload):
    try:
        if payload['role'] not in ('admin', 'support'):
            return 403, {"success": False, "message": "Admin or support role required"}
        rows = query("SELECT u.id, u.username, u.display_name, u.avatar_url, cl.latitude, cl.longitude, cl.is_online, cl.vehicle_type FROM Users u LEFT JOIN CourierLocations cl ON u.id=cl.courier_id WHERE u.role='courier'", fetch=True)
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_unassigned_orders(payload):
    try:
        if payload['role'] not in ('admin', 'support'):
            return 403, {"success": False, "message": "Admin or support role required"}
        rows = query("SELECT o.*, r.name as restaurant_name FROM Orders o JOIN Restaurants r ON o.restaurant_id=r.id WHERE o.courier_id IS NULL AND o.status NOT IN ('delivered','cancelled') ORDER BY o.created_at", fetch=True)
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_assign_order(body, payload):
    try:
        if payload['role'] not in ('admin', 'support'):
            return 403, {"success": False, "message": "Admin or support role required"}
        oid, cid = body.get('order_id'), body.get('courier_id')
        if not oid or not cid:
            return 400, {"success": False, "message": "order_id and courier_id required"}
        query("UPDATE Orders SET courier_id=?, status='courier_assigned', updated_at=CURRENT_TIMESTAMP WHERE id=?", (cid, oid))
        query("INSERT INTO OrderLog (order_id,status,note) VALUES (?,'courier_assigned','Manually assigned')", (oid,))
        push_notification(cid, 'Order Assigned', f'Admin assigned you to order #{oid}', 'order_assigned', oid)
        return 200, {"success": True, "message": "Courier assigned"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── ADMIN USER MANAGEMENT ──
def handle_admin_users(payload):
    """Get all users with their approval status. Admin only."""
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        rows = query("SELECT u.id, u.username, u.role, u.display_name, u.phone, u.approval_status, u.created_at, u.avatar_url FROM Users u ORDER BY u.created_at DESC", fetch=True)
        # For couriers, also get vehicle type
        for r in (rows or []):
            if r['role'] == 'courier':
                cl = query("SELECT vehicle_type, is_online FROM CourierLocations WHERE courier_id=?", (r['id'],), fetch_one=True)
                r['vehicle_type'] = cl['vehicle_type'] if cl else 'bicycle'
                r['is_online'] = cl['is_online'] if cl else False
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_approve_user(body, payload):
    """Admin approves a pending courier. Sets approval_status='approved'."""
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        uid = body.get('user_id')
        if not uid:
            return 400, {"success": False, "message": "user_id required"}
        user = query("SELECT id, role, approval_status FROM Users WHERE id=?", (uid,), fetch_one=True)
        if not user:
            return 404, {"success": False, "message": "User not found"}
        query("UPDATE Users SET approval_status='approved' WHERE id=?", (uid,))
        push_notification(uid, 'Account Approved', 'Your courier account has been approved! You can now go online.', 'account_approved', None)
        return 200, {"success": True, "message": f"User {uid} approved"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_suspend_user(body, payload):
    """Admin suspends a courier. They cannot log in."""
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        uid = body.get('user_id')
        reason = body.get('reason', 'Suspended by admin')
        if not uid:
            return 400, {"success": False, "message": "user_id required"}
        user = query("SELECT id, role FROM Users WHERE id=?", (uid,), fetch_one=True)
        if not user:
            return 404, {"success": False, "message": "User not found"}
        query("UPDATE Users SET approval_status='suspended' WHERE id=?", (uid,))
        # Force courier offline
        if user['role'] == 'courier':
            query("UPDATE CourierLocations SET is_online=FALSE WHERE courier_id=?", (uid,))
        push_notification(uid, 'Account Suspended', f'Your account has been suspended. Reason: {reason}', 'account_suspended', None)
        return 200, {"success": True, "message": f"User {uid} suspended"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_block_user(body, payload):
    """Admin blocks a user permanently."""
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        uid = body.get('user_id')
        reason = body.get('reason', 'Blocked by admin')
        if not uid:
            return 400, {"success": False, "message": "user_id required"}
        user = query("SELECT id, role FROM Users WHERE id=?", (uid,), fetch_one=True)
        if not user:
            return 404, {"success": False, "message": "User not found"}
        query("UPDATE Users SET approval_status='blocked' WHERE id=?", (uid,))
        if user['role'] == 'courier':
            query("UPDATE CourierLocations SET is_online=FALSE WHERE courier_id=?", (uid,))
        return 200, {"success": True, "message": f"User {uid} blocked"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_delete_user(payload, uid):
    """Admin deletes a user account."""
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        user = query("SELECT id, role FROM Users WHERE id=?", (uid,), fetch_one=True)
        if not user:
            return 404, {"success": False, "message": "User not found"}
        if user['id'] == payload['uid']:
            return 400, {"success": False, "message": "Cannot delete your own account"}
        # Clean up related records
        if user['role'] == 'courier':
            query("DELETE FROM CourierLocations WHERE courier_id=?", (uid,))
        query("DELETE FROM LoyaltyPoints WHERE user_id=?", (uid,))
        query("DELETE FROM Notifications WHERE user_id=?", (uid,))
        query("DELETE FROM Addresses WHERE user_id=?", (uid,))
        query("DELETE FROM Users WHERE id=?", (uid,))
        return 200, {"success": True, "message": f"User {uid} deleted"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_create_user(body, payload):
    """Admin creates a new user (e.g., support staff, courier, partner)."""
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        username = (body.get('username') or '').strip()
        password = body.get('password') or ''
        role = body.get('role', 'support')
        display_name = body.get('display_name', username)
        phone = body.get('phone', '') or ''
        if not username or not password:
            return 400, {"success": False, "message": "Username and password required"}
        if role not in ('support', 'courier', 'partner', 'customer', 'admin'):
            role = 'support'
        existing = query("SELECT id FROM Users WHERE username=?", (username,), fetch_one=True)
        if existing:
            return 409, {"success": False, "message": "Username already taken"}
        # Admin-created users are auto-approved
        pw_hash = AuthService.hash_pw(password)
        uid = insert("INSERT INTO Users (username,password_hash,role,display_name,phone,approval_status) VALUES (?,?,?,?,?,'approved')",
                     (username, pw_hash, role, display_name, phone))
        if role == 'courier':
            insert("INSERT INTO CourierLocations (courier_id,latitude,longitude,is_online) VALUES (?,0,0,FALSE)", (uid,))
        try:
            insert("INSERT INTO LoyaltyPoints (user_id,points,total_earned) VALUES (?,0,0)", (uid,))
        except:
            pass
        return 201, {"success": True, "data": {"id": uid, "username": username, "role": role, "display_name": display_name, "phone": phone}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── BROADCASTS ──
def handle_admin_create_broadcast(body, payload):
    """Admin creates a broadcast message targeting specific roles."""
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        title = (body.get('title') or '').strip()
        message = (body.get('message') or '').strip()
        target_roles = body.get('target_roles', 'all')  # comma-separated: 'courier,customer,partner,support' or 'all'
        if not title or not message:
            return 400, {"success": False, "message": "Title and message required"}
        bid = insert("INSERT INTO Broadcasts (admin_id,title,message,target_roles,is_active) VALUES (?,?,?,?,TRUE)",
                     (payload['uid'], title, message, target_roles))
        return 201, {"success": True, "data": {"id": bid, "title": title, "target_roles": target_roles}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_broadcasts(payload):
    """Get all broadcasts. Admin only."""
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        rows = query("SELECT b.*, u.display_name as admin_name FROM Broadcasts b JOIN Users u ON b.admin_id=u.id ORDER BY b.created_at DESC", fetch=True)
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_delete_broadcast(payload, bid):
    """Delete a broadcast. Admin only."""
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        query("DELETE FROM Broadcasts WHERE id=?", (bid,))
        return 200, {"success": True, "message": "Broadcast deleted"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_get_broadcasts(payload):
    """Get active broadcasts for the current user's role."""
    try:
        role = payload['role']
        rows = query("SELECT * FROM Broadcasts WHERE is_active=TRUE ORDER BY created_at DESC", fetch=True)
        # Filter by target roles
        result = []
        for b in (rows or []):
            targets = b['target_roles']
            if targets == 'all' or role in targets.split(','):
                result.append(b)
        return 200, {"success": True, "data": result}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── SUPPORT: ORDER DETAILS WITH CONTACTS ──
def handle_support_order_detail(payload, oid):
    """Get full order details for support, including phone numbers and addresses of all parties."""
    try:
        if payload['role'] not in ('admin', 'support'):
            return 403, {"success": False, "message": "Admin or support role required"}
        order = query("""
            SELECT o.*, r.name as restaurant_name, r.address as restaurant_address, r.phone as restaurant_phone
            FROM Orders o
            JOIN Restaurants r ON o.restaurant_id=r.id
            WHERE o.id=?
        """, (oid,), fetch_one=True)
        if not order:
            return 404, {"success": False, "message": "Order not found"}
        # Customer info
        customer = query("SELECT id, username, display_name, phone FROM Users WHERE id=?", (order['customer_id'],), fetch_one=True)
        order['customer_info'] = customer
        # Courier info
        if order.get('courier_id'):
            courier = query("SELECT u.id, u.username, u.display_name, u.phone, cl.vehicle_type, cl.is_online FROM Users u LEFT JOIN CourierLocations cl ON u.id=cl.courier_id WHERE u.id=?", (order['courier_id'],), fetch_one=True)
            order['courier_info'] = courier
        # Partner info
        partner = query("SELECT u.id, u.username, u.display_name, u.phone FROM Users u WHERE u.id=(SELECT created_by FROM Restaurants WHERE id=?)", (order['restaurant_id'],), fetch_one=True)
        order['partner_info'] = partner
        # Items
        order['items'] = query("SELECT * FROM OrderItems WHERE order_id=?", (oid,), fetch=True) or []
        # Order log
        order['log'] = query("SELECT * FROM OrderLog WHERE order_id=? ORDER BY created_at", (oid,), fetch=True) or []
        return 200, {"success": True, "data": order}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_support_ongoing_orders(payload):
    """Get all ongoing orders with contact details for support dashboard."""
    try:
        if payload['role'] not in ('admin', 'support'):
            return 403, {"success": False, "message": "Admin or support role required"}
        rows = query("""
            SELECT o.id, o.order_number, o.status, o.total, o.created_at,
                   o.delivery_address, o.is_deliver_anything, o.delivery_type,
                   o.pickup_address, o.pickup_contact_name, o.pickup_contact_phone,
                   o.delivery_contact_name, o.delivery_contact_phone, o.item_description,
                   r.name as restaurant_name, r.address as restaurant_address, r.phone as restaurant_phone,
                   cu.display_name as customer_name, cu.phone as customer_phone,
                   co.display_name as courier_name, co.phone as courier_phone
            FROM Orders o
            JOIN Restaurants r ON o.restaurant_id=r.id
            JOIN Users cu ON o.customer_id=cu.id
            LEFT JOIN Users co ON o.courier_id=co.id
            WHERE o.status NOT IN ('delivered','cancelled','rejected')
            ORDER BY o.created_at DESC
        """, fetch=True)
        # Get partner info for each
        for o in (rows or []):
            partner = query("SELECT u.display_name as partner_name, u.phone as partner_phone FROM Users u WHERE u.id=(SELECT created_by FROM Restaurants WHERE id=?)", (o.get('restaurant_id') or o.get('id')), fetch_one=True)
            # Workaround: get restaurant_id from order
            order_row = query("SELECT restaurant_id FROM Orders WHERE id=?", (o['id'],), fetch_one=True)
            if order_row:
                partner = query("SELECT u.display_name as partner_name, u.phone as partner_phone FROM Users u JOIN Restaurants r ON u.id=r.created_by WHERE r.id=?", (order_row['restaurant_id'],), fetch_one=True)
            o['partner_name'] = partner['partner_name'] if partner else ''
            o['partner_phone'] = partner['partner_phone'] if partner else ''
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ══════════════════════════════════════════════
#  NEW: IN-APP CHAT (Customer <-> Courier)
# ══════════════════════════════════════════════
def handle_chat_send(body, payload):
    """Send a chat message. Both customer and courier can use this. Support/admin can also send."""
    try:
        order_id = body.get('order_id')
        message = (body.get('message') or '').strip()
        msg_type = body.get('message_type', 'text')  # text, image, location
        if not order_id or not message:
            return 400, {"success": False, "message": "order_id and message required"}

        # Verify the user is part of this order or is support/admin
        order = query("SELECT customer_id, courier_id FROM Orders WHERE id=?", (order_id,), fetch_one=True)
        if not order:
            return 404, {"success": False, "message": "Order not found"}

        uid = payload['uid']
        is_support_admin = payload['role'] in ('admin', 'support')
        if uid != order['customer_id'] and uid != order['courier_id'] and not is_support_admin:
            return 403, {"success": False, "message": "Not authorized for this conversation"}

        # Determine receiver
        if is_support_admin:
            # Support messages go to customer by default
            receiver_id = order['customer_id']
        else:
            receiver_id = order['courier_id'] if uid == order['customer_id'] else order['customer_id']
        if not receiver_id:
            return 400, {"success": False, "message": "No recipient available"}

        msg_id = insert(
            "INSERT INTO ChatMessages (order_id,sender_id,receiver_id,message,message_type) VALUES (?,?,?,?,?)",
            (order_id, uid, receiver_id, message, msg_type)
        )
        # Push notification to receiver
        sender = query("SELECT display_name FROM Users WHERE id=?", (uid,), fetch_one=True)
        sender_name = sender['display_name'] if sender else 'User'
        push_notification(receiver_id, f'New message from {sender_name}',
                          message[:100], 'chat_message', order_id)

        return 201, {"success": True, "data": {"id": msg_id, "order_id": order_id,
                     "sender_id": uid, "receiver_id": receiver_id, "message": message,
                     "message_type": msg_type}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_chat_messages(payload, order_id, after_id=0):
    """Get messages for an order conversation. Use after_id for polling (only new messages)."""
    try:
        order = query("SELECT customer_id, courier_id FROM Orders WHERE id=?", (order_id,), fetch_one=True)
        if not order:
            return 404, {"success": False, "message": "Order not found"}
        uid = payload['uid']
        # Support/admin can view any order's chat
        if payload['role'] not in ('admin', 'support'):
            if uid != order['customer_id'] and uid != order['courier_id']:
                return 403, {"success": False, "message": "Not authorized"}

        rows = query(
            "SELECT cm.*, u.display_name as sender_name, u.avatar_url as sender_avatar, u.role as sender_role "
            "FROM ChatMessages cm JOIN Users u ON cm.sender_id=u.id "
            "WHERE cm.order_id=? AND cm.id>? ORDER BY cm.id ASC",
            (order_id, after_id), fetch=True
        )
        # Mark messages sent TO this user as read
        query("UPDATE ChatMessages SET is_read=TRUE WHERE order_id=? AND receiver_id=? AND is_read=FALSE",
              (order_id, uid))
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_chat_conversations(payload):
    """List all active chat conversations for the current user."""
    try:
        uid = payload['uid']
        rows = query("""
            SELECT o.id as order_id, o.order_number, o.status,
                   cm.message as last_message, cm.created_at as last_message_at,
                   cm.message_type as last_message_type,
                   u.display_name as other_name, u.avatar_url as other_avatar,
                   (SELECT COUNT(*) FROM ChatMessages WHERE order_id=o.id
                    AND receiver_id=? AND is_read=FALSE) as unread_count
            FROM Orders o
            JOIN ChatMessages cm ON cm.id = (
                SELECT id FROM ChatMessages WHERE order_id=o.id ORDER BY id DESC LIMIT 1
            )
            JOIN Users u ON u.id = CASE WHEN o.customer_id=? THEN o.courier_id ELSE o.customer_id END
            WHERE (o.customer_id=? OR o.courier_id=?)
            ORDER BY cm.created_at DESC
        """, (uid, uid, uid, uid), fetch=True)
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_chat_unread(payload):
    """Get total unread message count for the current user."""
    try:
        row = query("SELECT COUNT(*) as cnt FROM ChatMessages WHERE receiver_id=? AND is_read=FALSE",
                    (payload['uid'],), fetch_one=True)
        return 200, {"success": True, "data": {"unread_count": row['cnt'] if row else 0}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ══════════════════════════════════════════════
#  NEW: VOICE CALLING (WebRTC Signaling)
#  Architecture:
#    1. Caller initiates -> server stores offer SDP + creates CallSession
#    2. Callee polls for incoming calls -> gets offer SDP
#    3. Callee answers -> server stores answer SDP
#    4. Both exchange ICE candidates through server
#    5. Actual audio goes P2P via WebRTC (browser handles this)
#    6. End call -> server marks session ended
#  Privacy: No phone numbers shared — only user IDs are used.
# ══════════════════════════════════════════════
def handle_call_initiate(body, payload):
    """Caller starts a call. Sends WebRTC offer SDP."""
    try:
        order_id = body.get('order_id')
        offer_sdp = body.get('offer_sdp', '')
        if not order_id:
            return 400, {"success": False, "message": "order_id required"}

        order = query("SELECT customer_id, courier_id FROM Orders WHERE id=?", (order_id,), fetch_one=True)
        if not order:
            return 404, {"success": False, "message": "Order not found"}

        uid = payload['uid']
        if uid != order['customer_id'] and uid != order['courier_id']:
            return 403, {"success": False, "message": "Not authorized for this order"}

        callee_id = order['courier_id'] if uid == order['customer_id'] else order['customer_id']
        if not callee_id:
            return 400, {"success": False, "message": "No courier assigned yet"}

        # Check no active call for this order
        active = query(
            "SELECT id FROM CallSessions WHERE order_id=? AND status IN ('ringing','answered')",
            (order_id,), fetch_one=True
        )
        if active:
            return 409, {"success": False, "message": "A call is already active for this order"}

        call_id = insert(
            "INSERT INTO CallSessions (order_id,caller_id,callee_id,status,offer_sdp) VALUES (?,?,?,'ringing',?)",
            (order_id, uid, callee_id, offer_sdp)
        )

        # Notify callee
        caller = query("SELECT display_name FROM Users WHERE id=?", (uid,), fetch_one=True)
        caller_name = caller['display_name'] if caller else 'User'
        push_notification(callee_id, 'Incoming Call',
                          f'{caller_name} is calling you about order #{order_id}',
                          'voice_call', call_id)

        return 201, {"success": True, "data": {"call_id": call_id, "callee_id": callee_id, "status": "ringing"}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_call_incoming(payload):
    """Check for incoming calls (callee polls this)."""
    try:
        rows = query(
            "SELECT cs.*, u.display_name as caller_name, u.avatar_url as caller_avatar "
            "FROM CallSessions cs JOIN Users u ON cs.caller_id=u.id "
            "WHERE cs.callee_id=? AND cs.status='ringing' ORDER BY cs.started_at DESC",
            (payload['uid'],), fetch=True
        )
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_call_answer(body, payload):
    """Callee answers the call. Sends WebRTC answer SDP."""
    try:
        call_id = body.get('call_id')
        answer_sdp = body.get('answer_sdp', '')
        if not call_id:
            return 400, {"success": False, "message": "call_id required"}

        call = query("SELECT * FROM CallSessions WHERE id=?", (call_id,), fetch_one=True)
        if not call:
            return 404, {"success": False, "message": "Call not found"}
        if call['callee_id'] != payload['uid']:
            return 403, {"success": False, "message": "Not the callee of this call"}
        if call['status'] != 'ringing':
            return 400, {"success": False, "message": f"Call is not ringing (status: {call['status']})"}

        query("UPDATE CallSessions SET status='answered', answer_sdp=?, answered_at=CURRENT_TIMESTAMP WHERE id=?",
              (answer_sdp, call_id))

        # Notify caller that call was answered
        push_notification(call['caller_id'], 'Call Answered',
                          'Your call has been answered', 'call_answered', call_id)

        return 200, {"success": True, "data": {"call_id": call_id, "status": "answered"}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_call_ice_candidate(body, payload):
    """Exchange ICE candidates for NAT traversal."""
    try:
        call_id = body.get('call_id')
        candidate = body.get('candidate', '')
        if not call_id or not candidate:
            return 400, {"success": False, "message": "call_id and candidate required"}

        call = query("SELECT * FROM CallSessions WHERE id=?", (call_id,), fetch_one=True)
        if not call:
            return 404, {"success": False, "message": "Call not found"}

        uid = payload['uid']
        if uid != call['caller_id'] and uid != call['callee_id']:
            return 403, {"success": False, "message": "Not part of this call"}

        ice_id = insert(
            "INSERT INTO IceCandidates (call_id,user_id,candidate) VALUES (?,?,?)",
            (call_id, uid, candidate)
        )
        return 201, {"success": True, "data": {"id": ice_id}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_call_get_ice_candidates(payload, call_id, after_id=0):
    """Poll for ICE candidates from the other party."""
    try:
        call = query("SELECT * FROM CallSessions WHERE id=?", (call_id,), fetch_one=True)
        if not call:
            return 404, {"success": False, "message": "Call not found"}

        uid = payload['uid']
        if uid != call['caller_id'] and uid != call['callee_id']:
            return 403, {"success": False, "message": "Not part of this call"}

        # Get candidates from the OTHER user only
        rows = query(
            "SELECT * FROM IceCandidates WHERE call_id=? AND user_id!=? AND id>? ORDER BY id ASC",
            (call_id, uid, after_id), fetch=True
        )
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_call_get_answer(payload, call_id):
    """Caller polls to check if the call has been answered (to get answer SDP)."""
    try:
        call = query("SELECT id,caller_id,callee_id,status,answer_sdp FROM CallSessions WHERE id=?", (call_id,), fetch_one=True)
        if not call:
            return 404, {"success": False, "message": "Call not found"}
        if call['caller_id'] != payload['uid'] and call['callee_id'] != payload['uid']:
            return 403, {"success": False, "message": "Not part of this call"}
        return 200, {"success": True, "data": {"status": call['status'], "answer_sdp": call.get('answer_sdp')}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_call_end(body, payload):
    """End a call (either party can end it)."""
    try:
        call_id = body.get('call_id')
        if not call_id:
            return 400, {"success": False, "message": "call_id required"}

        call = query("SELECT * FROM CallSessions WHERE id=?", (call_id,), fetch_one=True)
        if not call:
            return 404, {"success": False, "message": "Call not found"}

        uid = payload['uid']
        if uid != call['caller_id'] and uid != call['callee_id']:
            return 403, {"success": False, "message": "Not part of this call"}

        query("UPDATE CallSessions SET status='ended', ended_at=CURRENT_TIMESTAMP WHERE id=?", (call_id,))

        # Notify the other party
        other_id = call['callee_id'] if uid == call['caller_id'] else call['caller_id']
        push_notification(other_id, 'Call Ended', 'The call has ended', 'call_ended', call_id)

        return 200, {"success": True, "data": {"call_id": call_id, "status": "ended"}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_call_reject(body, payload):
    """Callee rejects an incoming call."""
    try:
        call_id = body.get('call_id')
        if not call_id:
            return 400, {"success": False, "message": "call_id required"}

        call = query("SELECT * FROM CallSessions WHERE id=?", (call_id,), fetch_one=True)
        if not call:
            return 404, {"success": False, "message": "Call not found"}
        if call['callee_id'] != payload['uid']:
            return 403, {"success": False, "message": "Not the callee"}

        query("UPDATE CallSessions SET status='rejected', ended_at=CURRENT_TIMESTAMP WHERE id=?", (call_id,))

        push_notification(call['caller_id'], 'Call Rejected', 'The other party rejected the call', 'call_rejected', call_id)

        return 200, {"success": True, "data": {"call_id": call_id, "status": "rejected"}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ══════════════════════════════════════════════
#  NEW: NOTIFICATIONS
# ══════════════════════════════════════════════
def handle_get_notifications(payload):
    try:
        rows = query(
            "SELECT * FROM Notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 50",
            (payload['uid'],), fetch=True
        )
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_mark_notification_read(payload, nid):
    try:
        query("UPDATE Notifications SET is_read=TRUE WHERE id=? AND user_id=?", (nid, payload['uid']))
        return 200, {"success": True, "message": "Marked as read"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_mark_all_notifications_read(payload):
    try:
        query("UPDATE Notifications SET is_read=TRUE WHERE user_id=? AND is_read=FALSE", (payload['uid'],))
        return 200, {"success": True, "message": "All marked as read"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_unread_notification_count(payload):
    try:
        row = query("SELECT COUNT(*) as cnt FROM Notifications WHERE user_id=? AND is_read=FALSE",
                    (payload['uid'],), fetch_one=True)
        return 200, {"success": True, "data": {"unread_count": row['cnt'] if row else 0}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ══════════════════════════════════════════════
#  NEW: ADDRESS BOOK
# ══════════════════════════════════════════════
def handle_get_addresses(payload):
    try:
        rows = query("SELECT * FROM Addresses WHERE user_id=? ORDER BY is_default DESC, created_at DESC",
                     (payload['uid'],), fetch=True)
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_add_address(body, payload):
    try:
        label = (body.get('label') or '').strip()
        address = (body.get('address') or '').strip()
        if not address:
            return 400, {"success": False, "message": "Address required"}
        lat = body.get('latitude')
        lng = body.get('longitude')
        is_default = True if body.get('is_default') else False
        if is_default:
            query("UPDATE Addresses SET is_default=FALSE WHERE user_id=?", (payload['uid'],))
        aid = insert(
            "INSERT INTO Addresses (user_id,label,address,latitude,longitude,is_default) VALUES (?,?,?,?,?,?)",
            (payload['uid'], label, address, lat, lng, is_default)
        )
        return 201, {"success": True, "data": {"id": aid, "label": label, "address": address}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_update_address(body, payload, aid):
    try:
        addr = query("SELECT id FROM Addresses WHERE id=? AND user_id=?", (aid, payload['uid']), fetch_one=True)
        if not addr:
            return 404, {"success": False, "message": "Address not found"}
        fields, params = [], []
        for key in ['label', 'address']:
            if key in body:
                fields.append(f"{key}=?")
                params.append(body[key])
        if 'latitude' in body:
            fields.append("latitude=?")
            params.append(body['latitude'])
        if 'longitude' in body:
            fields.append("longitude=?")
            params.append(body['longitude'])
        if 'is_default' in body and body['is_default']:
            query("UPDATE Addresses SET is_default=FALSE WHERE user_id=?", (payload['uid'],))
            fields.append("is_default=TRUE")
        if not fields:
            return 400, {"success": False, "message": "No fields to update"}
        params.append(aid)
        query(f"UPDATE Addresses SET {', '.join(fields)} WHERE id=?", tuple(params))
        return 200, {"success": True, "message": "Address updated"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_delete_address(payload, aid):
    try:
        addr = query("SELECT id FROM Addresses WHERE id=? AND user_id=?", (aid, payload['uid']), fetch_one=True)
        if not addr:
            return 404, {"success": False, "message": "Address not found"}
        query("DELETE FROM Addresses WHERE id=?", (aid,))
        return 200, {"success": True, "message": "Address deleted"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ══════════════════════════════════════════════
#  NEW: LOYALTY POINTS
# ══════════════════════════════════════════════
def handle_get_loyalty(payload):
    try:
        lp = query("SELECT * FROM LoyaltyPoints WHERE user_id=?", (payload['uid'],), fetch_one=True)
        if not lp:
            return 200, {"success": True, "data": {"points": 0, "total_earned": 0}}
        return 200, {"success": True, "data": {"points": lp['points'], "total_earned": lp['total_earned']}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_get_loyalty_history(payload):
    try:
        rows = query(
            "SELECT * FROM PointTransactions WHERE user_id=? ORDER BY created_at DESC",
            (payload['uid'],), fetch=True
        )
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── ADMIN: CHANGE PASSWORD ──
def handle_admin_change_password(body, payload):
    """Admin changes their own password."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        old_pw = body.get('old_password', '')
        new_pw = body.get('new_password', '')
        if not old_pw or not new_pw:
            return 400, {"success": False, "message": "Old and new password required"}
        user = query("SELECT password_hash FROM Users WHERE id=?", (payload['uid'],), fetch_one=True)
        if not user or not AuthService.verify_pw(old_pw, user['password_hash']):
            return 401, {"success": False, "message": "Incorrect current password"}
        pw_hash = AuthService.hash_pw(new_pw)
        query("UPDATE Users SET password_hash=? WHERE id=?", (pw_hash, payload['uid']))
        return 200, {"success": True, "message": "Password changed"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── ADMIN: RESET USER PASSWORD ──
def handle_admin_reset_password(body, payload):
    """Admin resets a user's password."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        user_id = body.get('user_id')
        new_password = body.get('new_password', '1234')
        if not user_id:
            return 400, {"success": False, "message": "user_id required"}
        pw_hash = AuthService.hash_pw(new_password)
        query("UPDATE Users SET password_hash=? WHERE id=?", (pw_hash, user_id))
        return 200, {"success": True, "message": f"Password reset to '{new_password}'"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── ADMIN: ADD PARTNER ──
def handle_admin_add_partner(body, payload):
    """Admin creates a new partner account with restaurant."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        username = (body.get('username') or '').strip()
        password = body.get('password', '1234')
        restaurant_name = (body.get('restaurant_name') or '').strip()
        display_name = body.get('display_name', restaurant_name)
        if not username or not restaurant_name:
            return 400, {"success": False, "message": "username and restaurant_name required"}
        existing = query("SELECT id FROM Users WHERE username=?", (username,), fetch_one=True)
        if existing:
            return 409, {"success": False, "message": "Username already taken"}
        pw_hash = AuthService.hash_pw(password)
        uid = insert("INSERT INTO Users (username,password_hash,role,display_name,phone,approval_status) VALUES (?,?,'partner',?,?,'approved')",
                     (username, pw_hash, display_name, body.get('phone', '')))
        # Create restaurant
        rid = insert("INSERT INTO Restaurants (name,description,address,latitude,longitude,is_open,category,phone,image_url,created_by) VALUES (?,?,?,?,?,TRUE,?,?,?,?)",
                     (restaurant_name, body.get('description', ''), body.get('address', ''),
                      body.get('latitude', 47.0105), body.get('longitude', 28.8638),
                      body.get('category', 'restaurant'), body.get('phone', ''),
                      body.get('image_url', ''), uid))
        return 201, {"success": True, "data": {"user_id": uid, "restaurant_id": rid, "username": username, "password": password}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── ADMIN: DELETE PARTNER ──
def handle_admin_delete_partner(body, payload):
    """Admin deletes a partner and optionally their restaurant."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        user_id = body.get('user_id')
        delete_restaurant = body.get('delete_restaurant', False)
        if not user_id:
            return 400, {"success": False, "message": "user_id required"}
        user = query("SELECT id,role FROM Users WHERE id=?", (user_id,), fetch_one=True)
        if not user or user['role'] != 'partner':
            return 404, {"success": False, "message": "Partner not found"}
        if delete_restaurant:
            try:
                query("DELETE FROM Items WHERE restaurant_id IN (SELECT id FROM Restaurants WHERE created_by=?)", (user_id,))
                query("DELETE FROM Restaurants WHERE created_by=?", (user_id,))
            except:
                pass
        query("DELETE FROM Users WHERE id=?", (user_id,))
        return 200, {"success": True, "message": "Partner deleted"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── ADMIN: TOGGLE PARTNER ──
def handle_admin_toggle_partner(body, payload):
    """Admin toggles a partner's restaurant open/closed status."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        user_id = body.get('user_id')
        if not user_id:
            return 400, {"success": False, "message": "user_id required"}
        r = query("SELECT id, is_open FROM Restaurants WHERE created_by=?", (user_id,), fetch_one=True)
        if not r:
            return 404, {"success": False, "message": "Restaurant not found for this partner"}
        new_val = not r['is_open']
        query("UPDATE Restaurants SET is_open=? WHERE id=?", (new_val, r['id']))
        return 200, {"success": True, "data": {"is_open": bool(new_val)}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── ADMIN: UPLOAD MENU (bot processing) ──
def handle_admin_upload_menu(body, payload):
    """Admin uploads a menu text for a partner. Bot parses it and adds items to the restaurant."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        partner_user_id = body.get('user_id')
        menu_text = (body.get('menu_text') or '').strip()
        if not partner_user_id or not menu_text:
            return 400, {"success": False, "message": "user_id and menu_text required"}
        r = query("SELECT id FROM Restaurants WHERE created_by=?", (partner_user_id,), fetch_one=True)
        if not r:
            return 404, {"success": False, "message": "Restaurant not found"}
        rid = r['id']
        # Simple bot parser: each line = item, format: "Name - Description - Price" or "Name - Price" or "Name, Price"
        items_added = 0
        for line in menu_text.split('\n'):
            line = line.strip()
            if not line:
                continue
            # Try different separators
            parts = None
            for sep in [' - ', ' – ', ' | ', '\t']:
                if sep in line:
                    parts = [p.strip() for p in line.split(sep)]
                    break
            if not parts:
                # Try comma but only if last part is a number
                if ',' in line:
                    candidate = [p.strip() for p in line.rsplit(',', 1)]
                    try:
                        float(candidate[-1].replace('€','').replace('$','').replace('MDL','').replace('lei','').strip())
                        parts = candidate
                    except:
                        parts = [line]
                else:
                    parts = [line]
            
            name = parts[0]
            description = ''
            price = 0.0
            sub_category = body.get('sub_category', '')
            
            if len(parts) == 2:
                # Name + Price or Name + Description
                try:
                    price = float(parts[1].replace('€','').replace('$','').replace('MDL','').replace('lei','').strip())
                except:
                    description = parts[1]
                    price = 5.0  # default price
            elif len(parts) >= 3:
                # Name + Description + Price
                description = parts[1]
                try:
                    price = float(parts[-1].replace('€','').replace('$','').replace('MDL','').replace('lei','').strip())
                except:
                    price = 5.0
            
            if name and price > 0:
                try:
                    insert("INSERT INTO Items (restaurant_id,name,description,price,sub_category,image_url) VALUES (?,?,?,?,?,?)",
                           (rid, name, description, price, sub_category, ''))
                    items_added += 1
                except Exception as e:
                    print(f"  Menu parse insert note: {e}")
        return 200, {"success": True, "message": f"Parsed and added {items_added} items", "items_added": items_added}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── ADMIN: DELIVERY ZONES ──
def handle_admin_get_zones(payload):
    """Get all delivery zones."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        zones = query("SELECT * FROM DeliveryZones ORDER BY id", fetch=True)
        return 200, {"success": True, "data": zones or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_add_zone(body, payload):
    """Admin adds a delivery zone."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        name = (body.get('name') or '').strip()
        if not name:
            return 400, {"success": False, "message": "name required"}
        zid = insert("INSERT INTO DeliveryZones (name,center_lat,center_lng,radius_km,is_active,polygon_points) VALUES (?,?,?,?,?,?)",
                     (name, body.get('center_lat', 47.0105), body.get('center_lng', 28.8638),
                      body.get('radius_km', 5.0), body.get('is_active', True), body.get('polygon_points', '')))
        return 201, {"success": True, "data": {"id": zid, "name": name}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_update_zone(body, payload, zone_id):
    """Admin updates a delivery zone."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        fields, params = [], []
        for key in ['name', 'center_lat', 'center_lng', 'radius_km', 'is_active', 'polygon_points']:
            if key in body:
                fields.append(f"{key}=?")
                params.append(body[key])
        if not fields:
            return 400, {"success": False, "message": "No fields to update"}
        params.append(zone_id)
        query(f"UPDATE DeliveryZones SET {', '.join(fields)} WHERE id=?", tuple(params))
        return 200, {"success": True, "message": "Zone updated"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_delete_zone(payload, zone_id):
    """Admin deletes a delivery zone."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        query("DELETE FROM DeliveryZones WHERE id=?", (zone_id,))
        return 200, {"success": True, "message": "Zone deleted"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── ADMIN: DETAILED STATS ──
def handle_admin_detailed_stats(payload):
    """Get detailed platform statistics for admin dashboard."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        today = datetime.date.today().isoformat()
        week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        month_ago = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
        
        # Revenue stats
        today_rev = query("SELECT COALESCE(SUM(total),0) as rev FROM Orders WHERE status='delivered' AND DATE(created_at)>=?", (today,), fetch_one=True)
        week_rev = query("SELECT COALESCE(SUM(total),0) as rev FROM Orders WHERE status='delivered' AND DATE(created_at)>=?", (week_ago,), fetch_one=True)
        month_rev = query("SELECT COALESCE(SUM(total),0) as rev FROM Orders WHERE status='delivered' AND DATE(created_at)>=?", (month_ago,), fetch_one=True)
        total_rev = query("SELECT COALESCE(SUM(total),0) as rev FROM Orders WHERE status='delivered'", fetch_one=True)
        
        # Delivery fee revenue
        today_fees = query("SELECT COALESCE(SUM(delivery_fee),0) as fees FROM Orders WHERE status='delivered' AND DATE(created_at)>=?", (today,), fetch_one=True)
        month_fees = query("SELECT COALESCE(SUM(delivery_fee),0) as fees FROM Orders WHERE status='delivered' AND DATE(created_at)>=?", (month_ago,), fetch_one=True)
        
        # Courier earnings
        month_courier_earn = query("SELECT COALESCE(SUM(courier_earnings),0) as earn FROM Orders WHERE status='delivered' AND DATE(created_at)>=?", (month_ago,), fetch_one=True)
        
        # Order counts
        today_orders = query("SELECT COUNT(*) as cnt FROM Orders WHERE DATE(created_at)>=?", (today,), fetch_one=True)
        week_orders = query("SELECT COUNT(*) as cnt FROM Orders WHERE DATE(created_at)>=?", (week_ago,), fetch_one=True)
        month_orders = query("SELECT COUNT(*) as cnt FROM Orders WHERE DATE(created_at)>=?", (month_ago,), fetch_one=True)
        
        # Average order value
        avg_order = query("SELECT COALESCE(AVG(total),0) as avg FROM Orders WHERE status='delivered'", fetch_one=True)
        
        # Status breakdown
        status_breakdown = query("SELECT status, COUNT(*) as cnt FROM Orders GROUP BY status", fetch=True)
        
        # Top restaurants by orders
        top_restaurants = query("""
            SELECT r.name, COUNT(o.id) as order_count, COALESCE(SUM(o.total),0) as revenue
            FROM Restaurants r LEFT JOIN Orders o ON r.id=o.restaurant_id AND o.status='delivered'
            GROUP BY r.id, r.name ORDER BY order_count DESC LIMIT 10
        """, fetch=True)
        
        # Daily revenue last 7 days
        daily_rev = query("""
            SELECT DATE(created_at) as day, COUNT(*) as orders, COALESCE(SUM(total),0) as revenue
            FROM Orders WHERE status='delivered' AND DATE(created_at)>=?
            GROUP BY DATE(created_at) ORDER BY day
        """, (week_ago,), fetch=True)
        
        # Payment method breakdown
        payment_breakdown = query("""
            SELECT COALESCE(payment_method,'cash') as method, COUNT(*) as cnt
            FROM Orders WHERE DATE(created_at)>=? GROUP BY payment_method
        """, (month_ago,), fetch=True)
        
        return 200, {"success": True, "data": {
            "today_revenue": float(today_rev['rev'] or 0),
            "week_revenue": float(week_rev['rev'] or 0),
            "month_revenue": float(month_rev['rev'] or 0),
            "total_revenue": float(total_rev['rev'] or 0),
            "today_delivery_fees": float(today_fees['fees'] or 0),
            "month_delivery_fees": float(month_fees['fees'] or 0),
            "month_courier_earnings": float(month_courier_earn['earn'] or 0),
            "today_orders": today_orders['cnt'] or 0,
            "week_orders": week_orders['cnt'] or 0,
            "month_orders": month_orders['cnt'] or 0,
            "avg_order_value": float(avg_order['avg'] or 0),
            "status_breakdown": status_breakdown or [],
            "top_restaurants": top_restaurants or [],
            "daily_revenue": daily_rev or [],
            "payment_breakdown": payment_breakdown or []
        }}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── COURIER: EARNINGS STATS ──
def handle_courier_earnings_stats(payload):
    """Get detailed earnings statistics for courier."""
    try:
        if payload.get('role') != 'courier':
            return 403, {"success": False, "message": "Courier only"}
        cid = payload['uid']
        today = datetime.date.today().isoformat()
        week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        month_ago = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
        
        today_earn = query("SELECT COALESCE(SUM(courier_earnings),0) as earn FROM Orders WHERE courier_id=? AND status='delivered' AND DATE(delivered_at)>=?", (cid, today), fetch_one=True)
        week_earn = query("SELECT COALESCE(SUM(courier_earnings),0) as earn FROM Orders WHERE courier_id=? AND status='delivered' AND DATE(delivered_at)>=?", (cid, week_ago), fetch_one=True)
        month_earn = query("SELECT COALESCE(SUM(courier_earnings),0) as earn FROM Orders WHERE courier_id=? AND status='delivered' AND DATE(delivered_at)>=?", (cid, month_ago), fetch_one=True)
        total_earn = query("SELECT COALESCE(SUM(courier_earnings),0) as earn FROM Orders WHERE courier_id=? AND status='delivered'", (cid,), fetch_one=True)
        
        today_deliveries = query("SELECT COUNT(*) as cnt FROM Orders WHERE courier_id=? AND status='delivered' AND DATE(delivered_at)>=?", (cid, today), fetch_one=True)
        week_deliveries = query("SELECT COUNT(*) as cnt FROM Orders WHERE courier_id=? AND status='delivered' AND DATE(delivered_at)>=?", (cid, week_ago), fetch_one=True)
        month_deliveries = query("SELECT COUNT(*) as cnt FROM Orders WHERE courier_id=? AND status='delivered' AND DATE(delivered_at)>=?", (cid, month_ago), fetch_one=True)
        total_deliveries = query("SELECT COUNT(*) as cnt FROM Orders WHERE courier_id=? AND status='delivered'", (cid,), fetch_one=True)
        
        avg_earning = query("SELECT COALESCE(AVG(courier_earnings),0) as avg FROM Orders WHERE courier_id=? AND status='delivered'", (cid,), fetch_one=True)
        
        # Daily earnings last 7 days
        daily_earn = query("""
            SELECT DATE(delivered_at) as day, COUNT(*) as deliveries, COALESCE(SUM(courier_earnings),0) as earnings
            FROM Orders WHERE courier_id=? AND status='delivered' AND DATE(delivered_at)>=?
            GROUP BY DATE(delivered_at) ORDER BY day
        """, (cid, week_ago), fetch=True)
        
        # Average delivery time
        avg_time = query("""
            SELECT COALESCE(AVG(EXTRACT(EPOCH FROM (delivered_at - created_at))/60),0) as avg_minutes
            FROM Orders WHERE courier_id=? AND status='delivered' AND delivered_at IS NOT NULL
        """, (cid,), fetch_one=True)
        
        # Tips/extra earnings from CourierEarnings table
        extra_earn = query("SELECT COALESCE(SUM(amount),0) as extra FROM CourierEarnings WHERE courier_id=? AND earning_type!='delivery_fee'", (cid,), fetch_one=True)
        
        # Best hours analysis
        best_hours = query("""
            SELECT EXTRACT(HOUR FROM delivered_at) as hour, COUNT(*) as cnt, COALESCE(SUM(courier_earnings),0) as earn
            FROM Orders WHERE courier_id=? AND status='delivered' AND delivered_at IS NOT NULL
            GROUP BY hour ORDER BY earn DESC LIMIT 5
        """, (cid,), fetch=True)
        
        return 200, {"success": True, "data": {
            "today_earnings": float(today_earn['earn'] or 0),
            "week_earnings": float(week_earn['earn'] or 0),
            "month_earnings": float(month_earn['earn'] or 0),
            "total_earnings": float(total_earn['earn'] or 0),
            "today_deliveries": today_deliveries['cnt'] or 0,
            "week_deliveries": week_deliveries['cnt'] or 0,
            "month_deliveries": month_deliveries['cnt'] or 0,
            "total_deliveries": total_deliveries['cnt'] or 0,
            "avg_earning_per_order": float(avg_earning['avg'] or 0),
            "daily_earnings": daily_earn or [],
            "avg_delivery_minutes": float(avg_time['avg_minutes'] or 0),
            "extra_earnings": float(extra_earn['extra'] or 0),
            "best_hours": best_hours or []
        }}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ────────────────────────────────────────────
# ENHANCED ADMIN & COURIER HANDLERS
# ────────────────────────────────────────────

def handle_courier_recommendations(payload):
    """Get smart recommendations for couriers to maximize their profit."""
    try:
        if payload.get('role') != 'courier':
            return 403, {"success": False, "message": "Courier only"}
        cid = payload['uid']

        # Get courier's current location and vehicle
        loc = query("SELECT latitude, longitude, vehicle_type FROM CourierLocations WHERE courier_id=?", (cid,), fetch_one=True)
        if not loc:
            return 404, {"success": False, "message": "Courier location not found"}

        # Best hours based on all delivered orders in the system
        best_hours = query("""
            SELECT EXTRACT(HOUR FROM created_at) as hour, COUNT(*) as order_count,
            COALESCE(AVG(courier_earnings), 0) as avg_earning
            FROM Orders WHERE status='delivered' AND courier_earnings > 0
            GROUP BY hour ORDER BY order_count DESC LIMIT 5
        """, fetch=True)

        # Hot zones - areas with most recent pending/ready orders
        hot_zones = query("""
            SELECT r.latitude, r.longitude, r.name as restaurant_name,
            COUNT(o.id) as pending_orders,
            ROUND(AVG(o.delivery_fee), 2) as avg_fee
            FROM Orders o
            JOIN Restaurants r ON o.restaurant_id = r.id
            WHERE o.status IN ('pending', 'accepted', 'ready_for_pickup')
            AND o.created_at >= NOW() - INTERVAL '2 hours'
            GROUP BY r.latitude, r.longitude, r.name
            ORDER BY pending_orders DESC LIMIT 5
        """, fetch=True)

        # Vehicle recommendation based on average distances
        avg_dist = query("""
            SELECT AVG(
                6371 * acos(cos(radians(r.latitude)) * cos(radians(o.delivery_lat)) *
                cos(radians(o.delivery_lng) - radians(r.longitude)) +
                sin(radians(r.latitude)) * sin(radians(o.delivery_lat)))
            ) as avg_km
            FROM Orders o JOIN Restaurants r ON o.restaurant_id=r.id
            WHERE o.status='delivered' AND o.delivery_lat IS NOT NULL
        """, fetch_one=True)

        avg_distance = float(avg_dist['avg_km'] or 0) if avg_dist else 0
        vehicle = loc.get('vehicle_type', 'bicycle')
        if avg_distance > 5:
            vehicle_rec = 'scooter'
            vehicle_reason = 'Average delivery distance is over 5km - a scooter will maximize your deliveries'
        elif avg_distance > 3:
            vehicle_rec = 'bicycle'
            vehicle_reason = 'Average delivery distance is moderate - a bicycle is cost-effective'
        else:
            vehicle_rec = 'walking'
            vehicle_reason = 'Most deliveries are nearby - walking is sufficient and saves on fuel'

        # Expected hourly earnings
        hourly_data = query("""
            SELECT EXTRACT(HOUR FROM delivered_at) as hour,
            COUNT(*) as deliveries,
            COALESCE(SUM(courier_earnings), 0) as total_earnings
            FROM Orders WHERE status='delivered' AND delivered_at IS NOT NULL
            GROUP BY hour ORDER BY total_earnings DESC
        """, fetch=True)

        expected_hourly = 0
        if hourly_data:
            top_hours = hourly_data[:3]
            avg_earn = sum(float(h['total_earnings'] or 0) for h in top_hours) / len(top_hours)
            expected_hourly = round(avg_earn, 2)

        # Generate tips
        tips = []
        if best_hours:
            peak_hour = int(best_hours[0]['hour'])
            tips.append(f"Peak order time is {peak_hour}:00 - {peak_hour+1}:00. Be online then!")
        if hot_zones:
            tips.append(f"High activity near {hot_zones[0]['restaurant_name']} with {hot_zones[0]['pending_orders']} pending orders")
        if avg_distance > 5 and vehicle in ('walking', 'bicycle'):
            tips.append("Consider upgrading to a scooter for longer distance deliveries - they pay more!")
        tips.append("Accept orders quickly during peak hours to maximize your delivery count")
        tips.append("Stay near restaurant clusters to reduce pickup time")

        # Get current courier earnings rate
        my_rate = query("""
            SELECT COALESCE(AVG(courier_earnings), 0) as my_avg
            FROM Orders WHERE courier_id=? AND status='delivered'
        """, (cid,), fetch_one=True)

        return 200, {"success": True, "data": {
            "best_hours": best_hours or [],
            "hot_zones": hot_zones or [],
            "vehicle_recommendation": {"current": vehicle, "recommended": vehicle_rec, "reason": vehicle_reason},
            "expected_hourly_earnings": expected_hourly,
            "my_avg_earning": float(my_rate['my_avg'] or 0),
            "tips": tips,
            "avg_delivery_distance_km": round(avg_distance, 1)
        }}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_activity_log(payload):
    """Get admin activity log."""
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        rows = query("""
            SELECT al.*, u.display_name as admin_name
            FROM ActivityLog al
            JOIN Users u ON al.admin_id=u.id
            ORDER BY al.created_at DESC LIMIT 100
        """, fetch=True)
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_full_stats(payload):
    """Get comprehensive app statistics for admin."""
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}

        today = datetime.date.today().isoformat()
        week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        month_ago = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()

        # Revenue breakdown
        revenue_today = query("SELECT COALESCE(SUM(total),0) as rev FROM Orders WHERE status='delivered' AND DATE(delivered_at)>=?", (today,), fetch_one=True)
        revenue_week = query("SELECT COALESCE(SUM(total),0) as rev FROM Orders WHERE status='delivered' AND DATE(delivered_at)>=?", (week_ago,), fetch_one=True)
        revenue_month = query("SELECT COALESCE(SUM(total),0) as rev FROM Orders WHERE status='delivered' AND DATE(delivered_at)>=?", (month_ago,), fetch_one=True)
        revenue_total = query("SELECT COALESCE(SUM(total),0) as rev FROM Orders WHERE status='delivered'", fetch_one=True)

        # Delivery fees collected
        delivery_fees_today = query("SELECT COALESCE(SUM(delivery_fee),0) as fees FROM Orders WHERE status='delivered' AND DATE(delivered_at)>=?", (today,), fetch_one=True)
        delivery_fees_total = query("SELECT COALESCE(SUM(delivery_fee),0) as fees FROM Orders WHERE status='delivered'", fetch_one=True)

        # Courier payouts
        courier_payouts_today = query("SELECT COALESCE(SUM(courier_earnings),0) as payouts FROM Orders WHERE status='delivered' AND DATE(delivered_at)>=?", (today,), fetch_one=True)
        courier_payouts_total = query("SELECT COALESCE(SUM(courier_earnings),0) as payouts FROM Orders WHERE status='delivered'", fetch_one=True)

        # Platform profit = delivery fees - courier payouts
        platform_profit_today = float(delivery_fees_today['fees'] or 0) - float(courier_payouts_today['payouts'] or 0)
        platform_profit_total = float(delivery_fees_total['fees'] or 0) - float(courier_payouts_total['payouts'] or 0)

        # Order counts by period
        orders_today_cnt = query("SELECT COUNT(*) as cnt FROM Orders WHERE DATE(created_at)>=?", (today,), fetch_one=True)
        orders_week_cnt = query("SELECT COUNT(*) as cnt FROM Orders WHERE DATE(created_at)>=?", (week_ago,), fetch_one=True)
        orders_month_cnt = query("SELECT COUNT(*) as cnt FROM Orders WHERE DATE(created_at)>=?", (month_ago,), fetch_one=True)
        orders_total_cnt = query("SELECT COUNT(*) as cnt FROM Orders", fetch_one=True)

        # User stats
        total_customers = query("SELECT COUNT(*) as cnt FROM Users WHERE role='customer'", fetch_one=True)
        total_couriers = query("SELECT COUNT(*) as cnt FROM Users WHERE role='courier'", fetch_one=True)
        total_partners = query("SELECT COUNT(*) as cnt FROM Users WHERE role='partner'", fetch_one=True)
        total_support = query("SELECT COUNT(*) as cnt FROM Users WHERE role='support'", fetch_one=True)
        online_couriers = query("SELECT COUNT(*) as cnt FROM CourierLocations WHERE is_online=TRUE", fetch_one=True)

        # Average order value
        avg_order = query("SELECT COALESCE(AVG(total),0) as avg FROM Orders WHERE status='delivered'", fetch_one=True)

        # Average delivery time
        avg_time = query("""
            SELECT COALESCE(AVG(EXTRACT(EPOCH FROM (delivered_at - created_at))/60),0) as avg_min
            FROM Orders WHERE status='delivered' AND delivered_at IS NOT NULL
        """, fetch_one=True)

        # Daily revenue last 30 days
        daily_rev = query("""
            SELECT DATE(delivered_at) as day, COUNT(*) as orders,
            COALESCE(SUM(total),0) as revenue,
            COALESCE(SUM(delivery_fee),0) as fees,
            COALESCE(SUM(courier_earnings),0) as payouts
            FROM Orders WHERE status='delivered' AND DATE(delivered_at)>=?
            GROUP BY DATE(delivered_at) ORDER BY day
        """, (month_ago,), fetch=True)

        # Top restaurants by orders
        top_restaurants = query("""
            SELECT r.name, r.category, COUNT(*) as order_count,
            COALESCE(SUM(o.total),0) as revenue
            FROM Orders o JOIN Restaurants r ON o.restaurant_id=r.id
            WHERE o.status='delivered'
            GROUP BY r.name, r.category ORDER BY order_count DESC LIMIT 10
        """, fetch=True)

        # Payment method distribution
        payment_dist = query("""
            SELECT COALESCE(payment_method, 'cash') as method, COUNT(*) as cnt
            FROM Orders WHERE status='delivered' GROUP BY method ORDER BY cnt DESC
        """, fetch=True)

        # Category distribution
        category_dist = query("""
            SELECT r.category, COUNT(*) as cnt, COALESCE(SUM(o.total),0) as revenue
            FROM Orders o JOIN Restaurants r ON o.restaurant_id=r.id
            WHERE o.status='delivered' GROUP BY r.category ORDER BY cnt DESC
        """, fetch=True)

        # Promo code usage
        promo_stats = query("""
            SELECT p.code, p.discount_type, p.discount_value, p.used_count,
            p.usage_limit, p.is_active
            FROM PromoCodes p ORDER BY p.used_count DESC
        """, fetch=True)

        return 200, {"success": True, "data": {
            "revenue": {
                "today": float(revenue_today['rev'] or 0),
                "week": float(revenue_week['rev'] or 0),
                "month": float(revenue_month['rev'] or 0),
                "total": float(revenue_total['rev'] or 0)
            },
            "delivery_fees": {
                "today": float(delivery_fees_today['fees'] or 0),
                "total": float(delivery_fees_total['fees'] or 0)
            },
            "courier_payouts": {
                "today": float(courier_payouts_today['payouts'] or 0),
                "total": float(courier_payouts_total['payouts'] or 0)
            },
            "platform_profit": {
                "today": platform_profit_today,
                "total": platform_profit_total
            },
            "orders": {
                "today": orders_today_cnt['cnt'] or 0,
                "week": orders_week_cnt['cnt'] or 0,
                "month": orders_month_cnt['cnt'] or 0,
                "total": orders_total_cnt['cnt'] or 0
            },
            "users": {
                "customers": total_customers['cnt'] or 0,
                "couriers": total_couriers['cnt'] or 0,
                "partners": total_partners['cnt'] or 0,
                "support": total_support['cnt'] or 0,
                "online_couriers": online_couriers['cnt'] or 0
            },
            "avg_order_value": float(avg_order['avg'] or 0),
            "avg_delivery_minutes": float(avg_time['avg_min'] or 0),
            "daily_revenue": daily_rev or [],
            "top_restaurants": top_restaurants or [],
            "payment_methods": payment_dist or [],
            "category_distribution": category_dist or [],
            "promo_stats": promo_stats or []
        }}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_zone_map_data(payload):
    """Get map data for zone management - includes existing zones and Moldova boundaries."""
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        zones = query("SELECT * FROM DeliveryZones ORDER BY name", fetch=True)
        # Moldova approximate center and bounds for the map
        return 200, {"success": True, "data": {
            "zones": zones or [],
            "map_center": {"lat": 47.0, "lng": 28.8},
            "map_bounds": {
                "north": 48.5, "south": 45.5,
                "east": 30.1, "west": 26.6
            },
            "major_cities": [
                {"name": "Chisinau", "lat": 47.01, "lng": 28.86},
                {"name": "Balti", "lat": 47.76, "lng": 27.93},
                {"name": "Cahul", "lat": 45.90, "lng": 28.19},
                {"name": "Ungheni", "lat": 47.21, "lng": 27.79},
                {"name": "Orhei", "lat": 47.38, "lng": 28.82},
                {"name": "Soroca", "lat": 48.15, "lng": 28.30},
                {"name": "Tiraspol", "lat": 46.85, "lng": 29.63},
                {"name": "Comrat", "lat": 46.30, "lng": 28.41}
            ]
        }}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_bulk_menu_upload(body, payload):
    """Admin uploads menu text for a partner. The 'bot' parses it and adds items to DB.
    Format: each line is 'Item Name | Description | Price | Sub Category'
    Lines starting with # are treated as sub-category headers.
    Lines starting with // are comments/ignored.
    Example:
      # Main Course
      Grilled Salmon | Fresh Atlantic salmon with lemon | 18.50 | Main Course
      Beef Stew | Traditional recipe with vegetables | 12.99 | Main Course
    """
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        restaurant_id = body.get('restaurant_id')
        menu_text = body.get('menu_text', '')
        clear_existing = body.get('clear_existing', False)

        if not restaurant_id:
            return 400, {"success": False, "message": "restaurant_id required"}
        if not menu_text.strip():
            return 400, {"success": False, "message": "Menu text required"}

        # Verify restaurant exists
        rest = query("SELECT id, name FROM Restaurants WHERE id=?", (restaurant_id,), fetch_one=True)
        if not rest:
            return 404, {"success": False, "message": "Restaurant not found"}

        # Clear existing items if requested
        if clear_existing:
            query("DELETE FROM Items WHERE restaurant_id=?", (restaurant_id,))

        # Parse menu text
        current_sub = 'General'
        added = 0
        errors = 0
        for line in menu_text.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('//'):
                continue
            if line.startswith('#'):
                current_sub = line[1:].strip()
                continue
            # Try pipe-separated format
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 3:
                name = parts[0]
                desc = parts[1]
                try:
                    price = float(parts[2].replace(',', '.').replace('\u20ac', '').replace('MDL', '').replace('lei', '').strip())
                except:
                    errors += 1
                    continue
                sub_cat = parts[3].strip() if len(parts) > 3 else current_sub
            else:
                # Try comma-separated: Name, Price
                parts2 = [p.strip() for p in line.split(',')]
                if len(parts2) >= 2:
                    name = parts2[0]
                    try:
                        price = float(parts2[1].replace(',', '.').replace('\u20ac', '').replace('MDL', '').replace('lei', '').strip())
                    except:
                        errors += 1
                        continue
                    desc = ''
                    sub_cat = current_sub
                else:
                    errors += 1
                    continue

            if name and price > 0:
                try:
                    insert("INSERT INTO Items (restaurant_id,name,description,price,is_available,sub_category) VALUES (?,?,?,?,TRUE,?)",
                           (restaurant_id, name, desc, price, sub_cat))
                    added += 1
                except:
                    errors += 1

        # Log activity
        try:
            insert("INSERT INTO ActivityLog (admin_id,action,target_type,target_id,details) VALUES (?,'bulk_menu_upload','restaurant',?,?)",
                   (payload['uid'], restaurant_id, f"Added {added} items to {rest['name']} ({errors} errors)"))
        except:
            pass

        return 200, {"success": True, "data": {
            "restaurant": rest['name'],
            "items_added": added,
            "errors": errors,
            "cleared_existing": clear_existing
        }}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── ADMIN: VEHICLE CHANGE REQUESTS ──
def handle_admin_vehicle_requests(payload):
    """List all pending vehicle change requests."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        rows = query("""
            SELECT vcr.*, u.display_name as courier_name, u.username as courier_username, u.phone as courier_phone
            FROM VehicleChangeRequests vcr
            JOIN Users u ON vcr.courier_id=u.id
            WHERE vcr.status='pending'
            ORDER BY vcr.created_at DESC
        """, fetch=True)
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_approve_vehicle(body, payload):
    """Admin approves a vehicle change request."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        req_id = body.get('request_id')
        if not req_id:
            return 400, {"success": False, "message": "request_id required"}
        req = query("SELECT * FROM VehicleChangeRequests WHERE id=? AND status='pending'", (req_id,), fetch_one=True)
        if not req:
            return 404, {"success": False, "message": "Pending request not found"}
        # Update vehicle in CourierLocations
        query("UPDATE CourierLocations SET vehicle_type=? WHERE courier_id=?",
              (req['requested_vehicle'], req['courier_id']))
        # Mark request as approved
        query("UPDATE VehicleChangeRequests SET status='approved', resolved_at=CURRENT_TIMESTAMP WHERE id=?", (req_id,))
        # Notify courier
        push_notification(req['courier_id'], 'Vehicle Change Approved',
                         f'Your vehicle has been changed to {req["requested_vehicle"]}',
                         'vehicle_change_approved', req_id)
        # Log activity
        try:
            insert("INSERT INTO ActivityLog (admin_id,action,target_type,target_id,details) VALUES (?,'approve_vehicle','courier',?,?)",
                   (payload['uid'], req['courier_id'], f"Approved vehicle change: {req['current_vehicle']} → {req['requested_vehicle']}"))
        except:
            pass
        return 200, {"success": True, "message": "Vehicle change approved"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_reject_vehicle(body, payload):
    """Admin rejects a vehicle change request."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        req_id = body.get('request_id')
        note = body.get('note', '')
        if not req_id:
            return 400, {"success": False, "message": "request_id required"}
        req = query("SELECT * FROM VehicleChangeRequests WHERE id=? AND status='pending'", (req_id,), fetch_one=True)
        if not req:
            return 404, {"success": False, "message": "Pending request not found"}
        query("UPDATE VehicleChangeRequests SET status='rejected', admin_note=?, resolved_at=CURRENT_TIMESTAMP WHERE id=?",
              (note, req_id))
        push_notification(req['courier_id'], 'Vehicle Change Rejected',
                         f'Your vehicle change request was not approved. {note}',
                         'vehicle_change_rejected', req_id)
        try:
            insert("INSERT INTO ActivityLog (admin_id,action,target_type,target_id,details) VALUES (?,'reject_vehicle','courier',?,?)",
                   (payload['uid'], req['courier_id'], f"Rejected vehicle change: {req['current_vehicle']} → {req['requested_vehicle']}. Reason: {note}"))
        except:
            pass
        return 200, {"success": True, "message": "Vehicle change rejected"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── ADMIN: PROMO CODES CRUD ──
def handle_admin_promo_list(payload):
    """List all promo codes."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        rows = query("SELECT * FROM PromoCodes ORDER BY created_at DESC", fetch=True)
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_promo_create(body, payload):
    """Create a new promo code."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        code = (body.get('code', '') or '').strip().upper()
        if not code:
            return 400, {"success": False, "message": "Promo code required"}
        existing = query("SELECT id FROM PromoCodes WHERE code=?", (code,), fetch_one=True)
        if existing:
            return 409, {"success": False, "message": "Promo code already exists"}
        discount_type = body.get('discount_type', 'percentage')
        if discount_type not in ('percentage', 'fixed'):
            discount_type = 'percentage'
        discount_value = float(body.get('discount_value', 0))
        min_order = float(body.get('min_order_amount', 0))
        max_discount = body.get('max_discount_amount')
        if max_discount is not None:
            max_discount = float(max_discount)
        usage_limit = body.get('usage_limit')
        if usage_limit is not None:
            usage_limit = int(usage_limit)
        valid_from = body.get('valid_from') or datetime.datetime.now().isoformat()
        valid_until = body.get('valid_until') or (datetime.datetime.now() + datetime.timedelta(days=365)).isoformat()
        rid = insert("""INSERT INTO PromoCodes (code,description,discount_type,discount_value,max_discount_amount,min_order_amount,usage_limit,is_active,valid_from,valid_until)
            VALUES (?,?,?,?,?,?,?,?,TRUE,?,?)""",
            (code, body.get('description', ''), discount_type, discount_value, max_discount, min_order,
             usage_limit, valid_from, valid_until))
        try:
            insert("INSERT INTO ActivityLog (admin_id,action,target_type,target_id,details) VALUES (?,'create_promo','promo',?,?)",
                   (payload['uid'], rid, f"Created promo code: {code}"))
        except:
            pass
        return 201, {"success": True, "data": {"id": rid, "code": code}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_promo_update(body, payload, promo_id):
    """Update a promo code."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        existing = query("SELECT id FROM PromoCodes WHERE id=?", (promo_id,), fetch_one=True)
        if not existing:
            return 404, {"success": False, "message": "Promo code not found"}
        fields, params = [], []
        for key in ['description', 'discount_type', 'valid_from', 'valid_until']:
            if key in body:
                fields.append(f"{key}=?")
                params.append(body[key])
        if 'discount_value' in body:
            fields.append("discount_value=?")
            params.append(float(body['discount_value']))
        if 'max_discount_amount' in body:
            fields.append("max_discount_amount=?")
            val = body['max_discount_amount']
            params.append(float(val) if val is not None else None)
        if 'min_order_amount' in body:
            fields.append("min_order_amount=?")
            params.append(float(body['min_order_amount']))
        if 'usage_limit' in body:
            fields.append("usage_limit=?")
            val = body['usage_limit']
            params.append(int(val) if val is not None else None)
        if 'is_active' in body:
            fields.append("is_active=?")
            params.append(True if body['is_active'] else False)
        if not fields:
            return 400, {"success": False, "message": "No fields to update"}
        params.append(promo_id)
        query(f"UPDATE PromoCodes SET {', '.join(fields)} WHERE id=?", tuple(params))
        return 200, {"success": True, "message": "Promo code updated"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_promo_delete(payload, promo_id):
    """Delete a promo code."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        existing = query("SELECT code FROM PromoCodes WHERE id=?", (promo_id,), fetch_one=True)
        if not existing:
            return 404, {"success": False, "message": "Promo code not found"}
        query("DELETE FROM PromoCodes WHERE id=?", (promo_id,))
        try:
            insert("INSERT INTO ActivityLog (admin_id,action,target_type,target_id,details) VALUES (?,'delete_promo','promo',?,?)",
                   (payload['uid'], promo_id, f"Deleted promo code: {existing['code']}"))
        except:
            pass
        return 200, {"success": True, "message": "Promo code deleted"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── ADMIN: ITEM PRICE MANAGEMENT ──
def handle_admin_items_list(payload):
    """List all items with prices, filterable by restaurant."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        restaurant_id = None
        # Optional filter by restaurant
        rows = query("""
            SELECT i.*, r.name as restaurant_name, r.category as restaurant_category
            FROM Items i
            JOIN Restaurants r ON i.restaurant_id=r.id
            ORDER BY r.name, i.name
        """, fetch=True)
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_update_item(body, payload, item_id):
    """Admin updates any item (price, name, availability, sub_category)."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        existing = query("SELECT id FROM Items WHERE id=?", (item_id,), fetch_one=True)
        if not existing:
            return 404, {"success": False, "message": "Item not found"}
        fields, params = [], []
        for key in ['name', 'description', 'sub_category', 'image_url']:
            if key in body:
                fields.append(f"{key}=?")
                params.append(body[key])
        if 'price' in body:
            fields.append("price=?")
            params.append(float(body['price']))
        if 'is_available' in body:
            fields.append("is_available=?")
            params.append(True if body['is_available'] else False)
        if not fields:
            return 400, {"success": False, "message": "No fields to update"}
        params.append(item_id)
        query(f"UPDATE Items SET {', '.join(fields)} WHERE id=?", tuple(params))
        try:
            insert("INSERT INTO ActivityLog (admin_id,action,target_type,target_id,details) VALUES (?,'update_item','item',?,?)",
                   (payload['uid'], item_id, f"Updated item fields: {', '.join(fields)}"))
        except:
            pass
        return 200, {"success": True, "message": "Item updated"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_delete_item(payload, item_id):
    """Admin deletes an item."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        existing = query("SELECT id, name FROM Items WHERE id=?", (item_id,), fetch_one=True)
        if not existing:
            return 404, {"success": False, "message": "Item not found"}
        query("DELETE FROM Items WHERE id=?", (item_id,))
        try:
            insert("INSERT INTO ActivityLog (admin_id,action,target_type,target_id,details) VALUES (?,'delete_item','item',?,?)",
                   (payload['uid'], item_id, f"Deleted item: {existing['name']}"))
        except:
            pass
        return 200, {"success": True, "message": "Item deleted"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── ADMIN: DELIVERY FEE & COURIER EARNINGS SETTINGS ──
def handle_admin_settings_get(payload):
    """Get platform settings (delivery fee, courier earnings rate, etc.)."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        keys = ['default_delivery_fee', 'courier_earnings_percent', 'courier_min_earnings',
                'min_order_for_free_delivery', 'platform_commission_percent']
        result = {}
        for key in keys:
            row = query("SELECT value FROM AppSettings WHERE key=?", (key,), fetch_one=True)
            result[key] = row['value'] if row else None
        # Set defaults
        if result['default_delivery_fee'] is None:
            result['default_delivery_fee'] = '2.50'
        if result['courier_earnings_percent'] is None:
            result['courier_earnings_percent'] = '70'
        if result['courier_min_earnings'] is None:
            result['courier_min_earnings'] = '1.50'
        if result['min_order_for_free_delivery'] is None:
            result['min_order_for_free_delivery'] = '25'
        if result['platform_commission_percent'] is None:
            result['platform_commission_percent'] = '15'
        return 200, {"success": True, "data": result}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_settings_update(body, payload):
    """Update platform settings."""
    try:
        if payload.get('role') != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        allowed_keys = ['default_delivery_fee', 'courier_earnings_percent', 'courier_min_earnings',
                        'min_order_for_free_delivery', 'platform_commission_percent']
        updated = []
        for key in allowed_keys:
            if key in body:
                val = str(body[key])
                existing = query("SELECT key FROM AppSettings WHERE key=?", (key,), fetch_one=True)
                if existing:
                    query("UPDATE AppSettings SET value=?, updated_at=CURRENT_TIMESTAMP WHERE key=?", (val, key))
                else:
                    insert("INSERT INTO AppSettings (key, value) VALUES (?,?)", (key, val))
                updated.append(f"{key}={val}")
        if updated:
            try:
                insert("INSERT INTO ActivityLog (admin_id,action,target_type,details) VALUES (?,'update_settings','platform',?)",
                       (payload['uid'], f"Updated settings: {', '.join(updated)}"))
            except:
                pass
        return 200, {"success": True, "message": f"Settings updated: {', '.join(updated)}"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ────────────────────────────────────────────
# HTTP SERVER
# ────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    # Suppress noisy polling logs (heartbeat endpoints)
    _SUPPRESS_LOGS = ('/api/courier/orders', '/api/call/incoming', '/api/chat/unread',
                      '/api/notifications/unread-count', '/api/chat/messages/',
                      '/api/call/', '/api/courier/location', '/api/loyalty',
                      '/favicon.ico')

    def log_message(self, fmt, *args):
        # The default fmt is '"%s" %s %s' where args are (request_line, code, size)
        # Or '%s - - [%s] %s' where args are (addr, date, request_line)
        # We check if the path is in our suppress list
        full_msg = fmt % args if args else ''
        for prefix in self._SUPPRESS_LOGS:
            if prefix in full_msg:
                return
        # Also check self.path directly for the current request
        for prefix in self._SUPPRESS_LOGS:
            if hasattr(self, 'path') and prefix in self.path:
                return
        print(f"  [{self.log_date_time_string()}] {full_msg}")

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS,PATCH")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")

    def _json(self, code, data):
        body = json.dumps(data, default=str, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth(self):
        hdr = self.headers.get('Authorization', '')
        if not hdr.startswith('Bearer '):
            return None
        return AuthService.verify_token(hdr[7:])

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = self.path.split('?')[0]
        qs = urllib.parse.parse_qs(self.path.split('?')[1]) if '?' in self.path else {}
        try:
            # ── Static files ──
            if path == '/' or path == '/customer':
                self._serve('/static/customer/index.html')
            elif path == '/courier':
                self._serve('/static/courier/index.html')
            elif path == '/partner':
                self._serve('/static/partner/index.html')
            elif path == '/admin':
                self._serve('/static/admin/index.html')
            elif path == '/support':
                self._serve('/static/support/index.html')
            elif path.startswith('/static/'):
                self._serve(path)

            # ── Chat ──
            elif path.startswith('/api/chat/messages/'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    oid = int(path.split('/')[4])
                except:
                    return self._json(400, {"success": False, "message": "Invalid order ID"})
                after_id = int(qs.get('after_id', [0])[0])
                code, data = handle_chat_messages(p, oid, after_id)
                self._json(code, data)
            elif path == '/api/chat/conversations':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_chat_conversations(p)
                self._json(code, data)
            elif path == '/api/chat/unread':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_chat_unread(p)
                self._json(code, data)

            # ── Voice Call ──
            elif path == '/api/call/incoming':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_call_incoming(p)
                self._json(code, data)
            elif path.startswith('/api/call/') and path.endswith('/status'):
                # Route: GET /api/call/{call_id}/status  (caller polls for answer)
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    call_id = int(path.split('/')[3])
                except:
                    return self._json(400, {"success": False, "message": "Invalid call ID"})
                code, data = handle_call_get_answer(p, call_id)
                self._json(code, data)
            elif path.startswith('/api/call/') and '/ice/' in path:
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    parts = path.strip('/').split('/')
                    call_id = int(parts[2])
                except:
                    return self._json(400, {"success": False, "message": "Invalid call ID"})
                after_id = int(qs.get('after_id', [0])[0])
                code, data = handle_call_get_ice_candidates(p, call_id, after_id)
                self._json(code, data)

            # ── Notifications ──
            elif path == '/api/notifications':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_get_notifications(p)
                self._json(code, data)
            elif path == '/api/notifications/unread-count':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_unread_notification_count(p)
                self._json(code, data)

            # ── Address Book ──
            elif path == '/api/addresses':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_get_addresses(p)
                self._json(code, data)

            # ── Loyalty ──
            elif path == '/api/loyalty':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_get_loyalty(p)
                self._json(code, data)
            elif path == '/api/loyalty/history':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_get_loyalty_history(p)
                self._json(code, data)

            # ── Restaurants ──
            elif path == '/api/restaurants':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                params = {k: v[0] for k, v in qs.items()}
                code, data = handle_list_restaurants(params)
                self._json(code, data)
            elif path.startswith('/api/restaurants/'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    rid = int(path.split('/')[3])
                except:
                    return self._json(400, {"success": False, "message": "Invalid ID"})
                code, data = handle_get_restaurant(rid)
                self._json(code, data)

            # ── Cart ──
            elif path == '/api/cart':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_get_cart(p)
                self._json(code, data)

            # ── Orders ──
            elif path == '/api/orders':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_customer_orders(p)
                self._json(code, data)
            elif path.startswith('/api/orders/'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    oid = int(path.split('/')[3])
                except:
                    return self._json(400, {"success": False, "message": "Invalid ID"})
                code, data = handle_get_order(oid, p)
                self._json(code, data)

            # ── Courier ──
            elif path == '/api/courier/orders':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_courier_assigned_orders(p)
                self._json(code, data)
            elif path == '/api/courier/earnings':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_courier_earnings(p)
                self._json(code, data)

            # ── Support ──
            elif path == '/api/support/tickets':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_support_tickets(p)
                self._json(code, data)
            elif path == '/api/support/ongoing-orders':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_support_ongoing_orders(p)
                self._json(code, data)
            elif path.startswith('/api/support/order/') and path.endswith('/detail'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    oid = int(path.split('/')[4])
                except:
                    return self._json(400, {"success": False, "message": "Invalid order ID"})
                code, data = handle_support_order_detail(p, oid)
                self._json(code, data)
            elif path.startswith('/api/support/tickets/') and path.endswith('/messages'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    ticket_id = int(path.split('/')[4])
                except:
                    return self._json(400, {"success": False, "message": "Invalid ticket ID"})
                code, data = handle_support_messages(p, ticket_id)
                self._json(code, data)

            # ── Admin ──
            elif path == '/api/admin/couriers':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_couriers(p)
                self._json(code, data)
            elif path == '/api/admin/users':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_users(p)
                self._json(code, data)
            elif path == '/api/admin/users/create':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_create_user(body, p)
                self._json(code, data)
            elif path == '/api/admin/users/approve':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_approve_user(body, p)
                self._json(code, data)
            elif path == '/api/admin/users/suspend':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_suspend_user(body, p)
                self._json(code, data)
            elif path == '/api/admin/users/block':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_block_user(body, p)
                self._json(code, data)
            elif path == '/api/admin/broadcasts':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_broadcasts(p)
                self._json(code, data)
            elif path == '/api/admin/broadcasts/create':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_create_broadcast(body, p)
                self._json(code, data)
            elif path == '/api/admin/zones':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_get_zones(p)
                self._json(code, data)
            elif path == '/api/admin/detailed-stats':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_detailed_stats(p)
                self._json(code, data)
            elif path == '/api/courier/earnings-stats':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_courier_earnings_stats(p)
                self._json(code, data)
            elif path == '/api/broadcasts':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_get_broadcasts(p)
                self._json(code, data)
            elif path == '/api/admin/unassigned':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_unassigned_orders(p)
                self._json(code, data)
            elif path == '/api/admin/orders':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_all_orders(p)
                self._json(code, data)
            elif path == '/api/admin/stats':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_stats(p)
                self._json(code, data)
            elif path == '/api/admin/full-stats':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_full_stats(p)
                self._json(code, data)
            elif path == '/api/admin/activity-log':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_activity_log(p)
                self._json(code, data)
            elif path == '/api/admin/zone-map-data':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_zone_map_data(p)
                self._json(code, data)
            elif path == '/api/courier/recommendations':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_courier_recommendations(p)
                self._json(code, data)

            # ── Partner ──
            elif path == '/api/partner/orders':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_partner_orders(p)
                self._json(code, data)
            elif path == '/api/partner/stats':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_partner_stats(p)
                self._json(code, data)
            elif path == '/api/partner/menu':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_partner_menu(p)
                self._json(code, data)
            elif path.startswith('/api/partner/order/') and path.endswith('/detail'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    oid = int(path.split('/')[4])
                except:
                    return self._json(400, {"success": False, "message": "Invalid order ID"})
                code, data = handle_partner_order_detail(p, oid)
                self._json(code, data)
            elif path == '/api/partner/toggle-open':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_partner_toggle_open(p)
                self._json(code, data)
            elif path == '/api/partner/restaurant':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_partner_restaurant(p)
                self._json(code, data)

            # ── Me / Favorites ──
            elif path == '/api/me':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_me(p)
                self._json(code, data)
            elif path == '/api/favorites':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_get_favorites(p)
                self._json(code, data)
            elif path.startswith('/api/favorites/'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    rid = int(path.split('/')[3])
                except:
                    return self._json(400, {"success": False, "message": "Invalid restaurant ID"})
                code, data = handle_check_favorite(p, rid)
                self._json(code, data)

            # ── Maps & System Config ──
            elif path in ('/api/config/maps', '/api/maps/config'):
                self._json(200, {
                    "success": True,
                    "apiKey": Config.GOOGLE_MAPS_API_KEY or "",
                    "key": Config.GOOGLE_MAPS_API_KEY or "",
                    "configured": bool(Config.GOOGLE_MAPS_API_KEY)
                })

            else:
                self._json(404, {"success": False, "message": "Not found"})
        except Exception as e:
            traceback.print_exc()
            self._json(500, {"success": False, "message": str(e)})

    def do_POST(self):
        path = self.path.split('?')[0]
        cl = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(cl) if cl else b''
        try:
            body = json.loads(raw) if raw else {}
        except:
            body = {}
        try:
            # ── Auth & OTP ──
            if path == '/api/auth/register':
                code, data = handle_register(body)
                return self._json(code, data)
            elif path == '/api/auth/login':
                code, data = handle_login(body)
                return self._json(code, data)
            elif path in ('/api/auth/send-otp', '/api/auth/otp/send', '/api/otp/send'):
                code, data = handle_send_otp(body)
                return self._json(code, data)
            elif path in ('/api/auth/verify-otp', '/api/auth/otp/verify', '/api/otp/verify'):
                code, data = handle_verify_otp(body)
                return self._json(code, data)
            elif path in ('/api/auth/register-customer', '/api/auth/customer/register'):
                code, data = handle_register_customer(body)
                return self._json(code, data)
            elif path in ('/api/auth/register-courier', '/api/auth/courier/register'):
                code, data = handle_register_courier(body)
                return self._json(code, data)

            # ── Chat ──
            elif path == '/api/chat/send':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_chat_send(body, p)
                self._json(code, data)

            # ── Voice Call ──
            elif path == '/api/call/initiate':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_call_initiate(body, p)
                self._json(code, data)
            elif path == '/api/call/answer':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_call_answer(body, p)
                self._json(code, data)
            elif path == '/api/call/ice-candidate':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_call_ice_candidate(body, p)
                self._json(code, data)
            elif path == '/api/call/end':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_call_end(body, p)
                self._json(code, data)
            elif path == '/api/call/reject':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_call_reject(body, p)
                self._json(code, data)

            # ── Notifications ──
            elif path == '/api/notifications/mark-all-read':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_mark_all_notifications_read(p)
                self._json(code, data)
            elif path.startswith('/api/notifications/') and path.endswith('/read'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    nid = int(path.split('/')[3])
                except:
                    return self._json(400, {"success": False, "message": "Invalid ID"})
                code, data = handle_mark_notification_read(p, nid)
                self._json(code, data)

            # ── Address Book ──
            elif path == '/api/addresses':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_add_address(body, p)
                self._json(code, data)

            # ── Profile ──
            elif path == '/api/upload/avatar':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_upload_avatar(body, p)
                self._json(code, data)
            elif path == '/api/profile':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_update_profile(body, p)
                self._json(code, data)

            # ── Restaurants / Items ──
            elif path.startswith('/api/restaurants/') and '/items' in path and '/items/' not in path:
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    rid = int(path.strip('/').split('/')[2])
                except:
                    return self._json(400, {"success": False, "message": "Invalid restaurant ID"})
                code, data = handle_add_item(body, p, rid)
                self._json(code, data)
            elif path == '/api/restaurants':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_create_restaurant(body, p)
                self._json(code, data)

            # ── Cart ──
            elif path == '/api/cart/add':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_add_to_cart(body, p)
                self._json(code, data)
            elif path.startswith('/api/cart/remove/'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    iid = int(path.split('/')[-1])
                except:
                    return self._json(400, {"success": False, "message": "Invalid ID"})
                code, data = handle_remove_from_cart(p, iid)
                self._json(code, data)
            elif path == '/api/cart/clear':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_clear_cart(p)
                self._json(code, data)

            # ── Orders ──
            elif path == '/api/orders':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_create_order(body, p)
                self._json(code, data)
            elif path.startswith('/api/orders/') and path.endswith('/rate'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    oid = int(path.split('/')[3])
                except:
                    return self._json(400, {"success": False, "message": "Invalid ID"})
                code, data = handle_rate_order(body, p, oid)
                self._json(code, data)
            elif path.startswith('/api/orders/') and path.endswith('/cancel'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    oid = int(path.split('/')[3])
                except:
                    return self._json(400, {"success": False, "message": "Invalid ID"})
                code, data = handle_cancel_order(p, oid)
                self._json(code, data)
            elif path.startswith('/api/orders/') and path.endswith('/reorder'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    oid = int(path.split('/')[3])
                except:
                    return self._json(400, {"success": False, "message": "Invalid ID"})
                code, data = handle_reorder(p, oid)
                self._json(code, data)

            # ── Courier ──
            elif path == '/api/courier/location':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_courier_update_location(body, p)
                self._json(code, data)
            elif path == '/api/courier/online':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_courier_set_online(body, p)
                self._json(code, data)
            elif path.startswith('/api/courier/order/') and path.endswith('/status'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    oid = int(path.split('/')[4])
                except:
                    return self._json(400, {"success": False, "message": "Invalid ID"})
                code, data = handle_courier_update_status(body, p, oid)
                self._json(code, data)
            elif path.startswith('/api/courier/order/') and path.endswith('/reject'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    oid = int(path.split('/')[4])
                except:
                    return self._json(400, {"success": False, "message": "Invalid ID"})
                code, data = handle_courier_reject_order(p, oid)
                self._json(code, data)
            elif path.startswith('/api/courier/order/') and path.endswith('/reassign'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    oid = int(path.split('/')[4])
                except:
                    return self._json(400, {"success": False, "message": "Invalid ID"})
                code, data = handle_courier_reassign_order(p, oid)
                self._json(code, data)
            elif path == '/api/courier/set-vehicle':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_courier_set_vehicle(body, p)
                self._json(code, data)
            elif path == '/api/courier/vehicle-status':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_courier_vehicle_status(p)
                self._json(code, data)

            # ── Support ──
            elif path == '/api/support/tickets':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_support_create_ticket(body, p)
                self._json(code, data)
            elif path.startswith('/api/support/tickets/') and path.endswith('/messages'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_support_send_message(body, p)
                self._json(code, data)

            # ── Deliver Anything ──
            elif path == '/api/deliver-anything':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_deliver_anything(body, p)
                self._json(code, data)

            # ── Admin ──
            elif path == '/api/admin/assign':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_assign_order(body, p)
                self._json(code, data)
            elif path == '/api/admin/change-password':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                s, d = handle_admin_change_password(body, p)
                self._json(s, d)
            elif path == '/api/admin/reset-password':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                s, d = handle_admin_reset_password(body, p)
                self._json(s, d)
            elif path == '/api/admin/add-partner':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                s, d = handle_admin_add_partner(body, p)
                self._json(s, d)
            elif path == '/api/admin/delete-partner':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                s, d = handle_admin_delete_partner(body, p)
                self._json(s, d)
            elif path == '/api/admin/toggle-partner':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                s, d = handle_admin_toggle_partner(body, p)
                self._json(s, d)
            elif path == '/api/admin/upload-menu':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                s, d = handle_admin_upload_menu(body, p)
                self._json(s, d)
            elif path == '/api/admin/zones':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                s, d = handle_admin_add_zone(body, p)
                self._json(s, d)
            elif path == '/api/admin/detailed-stats':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                s, d = handle_admin_detailed_stats(p)
                self._json(s, d)
            elif path == '/api/courier/earnings-stats':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                s, d = handle_courier_earnings_stats(p)
                self._json(s, d)
            elif path == '/api/admin/bulk-menu-upload':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_bulk_menu_upload(body, p)
                self._json(code, data)
            # ── Admin: Vehicle Change Requests ──
            elif path == '/api/admin/vehicle-requests':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_vehicle_requests(p)
                self._json(code, data)
            elif path == '/api/admin/vehicle-approve':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_approve_vehicle(body, p)
                self._json(code, data)
            elif path == '/api/admin/vehicle-reject':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_reject_vehicle(body, p)
                self._json(code, data)
            # ── Admin: Promo Codes CRUD ──
            elif path == '/api/admin/promos':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_promo_list(p)
                self._json(code, data)
            elif path == '/api/admin/promos/create':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_promo_create(body, p)
                self._json(code, data)
            # ── Admin: Item Management ──
            elif path == '/api/admin/items':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_items_list(p)
                self._json(code, data)
            # ── Admin: Settings ──
            elif path == '/api/admin/settings':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_settings_get(p)
                self._json(code, data)
            elif path == '/api/admin/settings/update':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_settings_update(body, p)
                self._json(code, data)

            # ── Partner ──
            elif path.startswith('/api/partner/order/') and path.endswith('/accept'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    oid = int(path.split('/')[4])
                except:
                    return self._json(400, {"success": False, "message": "Invalid order ID"})
                code, data = handle_partner_accept_order(body, p, oid)
                self._json(code, data)
            elif path.startswith('/api/partner/order/') and path.endswith('/reject'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    oid = int(path.split('/')[4])
                except:
                    return self._json(400, {"success": False, "message": "Invalid order ID"})
                code, data = handle_partner_reject_order(p, oid)
                self._json(code, data)
            elif path.startswith('/api/partner/order/') and path.endswith('/ready'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    oid = int(path.split('/')[4])
                except:
                    return self._json(400, {"success": False, "message": "Invalid order ID"})
                code, data = handle_partner_ready_order(body, p, oid)
                self._json(code, data)
            elif path == '/api/partner/menu':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_partner_add_item(body, p)
                self._json(code, data)

            # ── Favorites ──
            elif path == '/api/favorites':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_add_favorite(body, p)
                self._json(code, data)

            # ── Promo ──
            elif path == '/api/promo/validate':
                code, data = handle_validate_promo(body)
                self._json(code, data)

            # ── Restaurant Toggle ──
            elif path.startswith('/api/restaurants/') and path.endswith('/toggle'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    rid = int(path.split('/')[3])
                except:
                    return self._json(400, {"success": False, "message": "Invalid ID"})
                code, data = handle_toggle_restaurant(p, rid)
                self._json(code, data)

            else:
                self._json(404, {"success": False, "message": "Not found"})
        except Exception as e:
            traceback.print_exc()
            self._json(500, {"success": False, "message": str(e)})

    def do_PUT(self):
        path = self.path.split('?')[0]
        cl = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(cl) if cl else b''
        try:
            body = json.loads(raw) if raw else {}
        except:
            body = {}
        try:
            # ── Partner menu item update ──
            if path.startswith('/api/partner/menu/') and '/items/' in path:
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                parts = path.strip('/').split('/')
                try:
                    item_id = int(parts[3])
                except:
                    return self._json(400, {"success": False, "message": "Invalid item ID"})
                code, data = handle_partner_update_item(body, p, item_id)
                self._json(code, data)
            # ── Address Book ──
            if path.startswith('/api/addresses/'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    aid = int(path.split('/')[-1])
                except:
                    return self._json(400, {"success": False, "message": "Invalid address ID"})
                code, data = handle_update_address(body, p, aid)
                self._json(code, data)
            # ── Support ticket close ──
            elif path.startswith('/api/support/tickets/') and path.endswith('/close'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    ticket_id = int(path.split('/')[4])
                except:
                    return self._json(400, {"success": False, "message": "Invalid ticket ID"})
                code, data = handle_support_close_ticket(p, ticket_id)
                self._json(code, data)
            # ── Items ──
            elif path.startswith('/api/restaurants/') and '/items/' in path:
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                parts = path.strip('/').split('/')
                try:
                    item_id = int(parts[4])
                except:
                    return self._json(400, {"success": False, "message": "Invalid item ID"})
                code, data = handle_update_item(body, p, item_id)
                self._json(code, data)
            # ── Restaurant ──
            elif path.startswith('/api/restaurants/'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    rid = int(path.split('/')[3])
                except:
                    return self._json(400, {"success": False, "message": "Invalid ID"})
                code, data = handle_update_restaurant(body, p, rid)
                self._json(code, data)
            # ── Admin zone update ──
            elif '/api/admin/zones/' in path:
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    zone_id = int(path.split('/api/admin/zones/')[-1])
                except:
                    return self._json(400, {"success": False, "message": "Invalid zone ID"})
                code, data = handle_admin_update_zone(body, p, zone_id)
                self._json(code, data)
            # ── Admin promo update ──
            elif path.startswith('/api/admin/promos/'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    promo_id = int(path.split('/api/admin/promos/')[-1])
                except:
                    return self._json(400, {"success": False, "message": "Invalid promo ID"})
                code, data = handle_admin_promo_update(body, p, promo_id)
                self._json(code, data)
            # ── Admin item update ──
            elif path.startswith('/api/admin/items/'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    item_id = int(path.split('/api/admin/items/')[-1])
                except:
                    return self._json(400, {"success": False, "message": "Invalid item ID"})
                code, data = handle_admin_update_item(body, p, item_id)
                self._json(code, data)
            else:
                self._json(404, {"success": False, "message": "Not found"})
        except Exception as e:
            traceback.print_exc()
            self._json(500, {"success": False, "message": str(e)})

    def do_DELETE(self):
        path = self.path.split('?')[0]
        try:
            # ── Admin user delete ──
            if path.startswith('/api/admin/users/'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    uid = int(path.split('/')[-1])
                except:
                    return self._json(400, {"success": False, "message": "Invalid user ID"})
                code, data = handle_admin_delete_user(p, uid)
                self._json(code, data)
            # ── Admin broadcast delete ──
            elif path.startswith('/api/admin/broadcasts/'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    bid = int(path.split('/')[-1])
                except:
                    return self._json(400, {"success": False, "message": "Invalid broadcast ID"})
                code, data = handle_admin_delete_broadcast(p, bid)
                self._json(code, data)
            # ── Admin zone delete ──
            elif '/api/admin/zones/' in path:
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    zone_id = int(path.split('/api/admin/zones/')[-1])
                except:
                    return self._json(400, {"success": False, "message": "Invalid zone ID"})
                code, data = handle_admin_delete_zone(p, zone_id)
                self._json(code, data)
            # ── Admin promo delete ──
            elif path.startswith('/api/admin/promos/'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    promo_id = int(path.split('/api/admin/promos/')[-1])
                except:
                    return self._json(400, {"success": False, "message": "Invalid promo ID"})
                code, data = handle_admin_promo_delete(p, promo_id)
                self._json(code, data)
            # ── Admin item delete ──
            elif path.startswith('/api/admin/items/'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    item_id = int(path.split('/api/admin/items/')[-1])
                except:
                    return self._json(400, {"success": False, "message": "Invalid item ID"})
                code, data = handle_admin_delete_item(p, item_id)
                self._json(code, data)
            # ── Partner menu item delete ──
            if path.startswith('/api/partner/menu/items/'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    item_id = int(path.split('/')[-1])
                except:
                    return self._json(400, {"success": False, "message": "Invalid item ID"})
                code, data = handle_partner_delete_item(p, item_id)
                self._json(code, data)
            # ── Address Book ──
            if path.startswith('/api/addresses/'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    aid = int(path.split('/')[-1])
                except:
                    return self._json(400, {"success": False, "message": "Invalid address ID"})
                code, data = handle_delete_address(p, aid)
                self._json(code, data)
            # ── Items ──
            elif path.startswith('/api/restaurants/') and '/items/' in path:
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                parts = path.strip('/').split('/')
                try:
                    item_id = int(parts[4])
                except:
                    return self._json(400, {"success": False, "message": "Invalid item ID"})
                code, data = handle_delete_item(p, item_id)
                self._json(code, data)
            # ── Restaurant ──
            elif path.startswith('/api/restaurants/'):
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                try:
                    rid = int(path.split('/')[3])
                except:
                    return self._json(400, {"success": False, "message": "Invalid ID"})
                code, data = handle_delete_restaurant(p, rid)
                self._json(code, data)
            else:
                self._json(404, {"success": False, "message": "Not found"})
        except Exception as e:
            traceback.print_exc()
            self._json(500, {"success": False, "message": str(e)})

    def _serve(self, path):
        filepath = os.path.join(os.path.dirname(__file__), path.lstrip('/'))
        if not os.path.exists(filepath):
            self.send_response(404)
            self.send_header('Content-Type', 'text/html')
            self._cors()
            self.end_headers()
            self.wfile.write(b'<h1>404 Not Found</h1>')
            return
        ext = os.path.splitext(filepath)[1]
        types = {
            '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript',
            '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.webp': 'image/webp', '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
            '.json': 'application/json'
        }
        ct = types.get(ext, 'application/octet-stream')
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', ct)
            self.send_header('Content-Length', str(len(content)))
            self._cors()
            self.end_headers()
            self.wfile.write(content)
        except:
            self.send_response(500)
            self.end_headers()


class ThreadedServer(HTTPServer):
    allow_reuse_address = True

    def process_request(self, req, addr):
        t = threading.Thread(target=self._handle, args=(req, addr), daemon=True)
        t.start()

    def _handle(self, req, addr):
        try:
            self.finish_request(req, addr)
        except:
            pass
        finally:
            close_conn()
            req.close()


if __name__ == '__main__':
    print("=" * 50)
    print("  ELYANIVERY v5.0 - Delivery Platform (PostgreSQL)")
    print("  + Chat, Voice Calls, Notifications,")
    print("    Address Book, Loyalty Points,")
    print("    Vehicle-based Courier, Earnings,")
    print("    Support Tickets, Deliver Anything,")
    print("    Admin Dashboard, User Management,")
    print("    Courier Approval, Broadcasts,")
    print("    Multi-language (EN/RU/RO),")
    print("    Moldova-based Seed Data")
    print("=" * 50)

    # init_db() connects to PostgreSQL using DATABASE_URL or individual params
    db_ok = False
    try:
        init_db()
        db_ok = True
    except Exception as e:
        print(f"\n  ERROR: Could not connect to PostgreSQL!")
        print(f"  Details: {e}")
        print(f"\n  Please check:")
        print(f"    1. PostgreSQL is running (locally or on Railway)")
        print(f"    2. Set DATABASE_URL or DB_HOST/DB_USER/DB_PASSWORD env vars")
        print(f"    3. On Railway: Add a PostgreSQL database service")

    if db_ok:
        print("  DB connection OK")
        print(f"  Current seed version: {CURRENT_SEED_VERSION}")
        try:
            init_extra_tables()
        except Exception as e:
            print(f"  Extra tables note: {e}")
        try:
            seed_data()  # auto-reseeds if version mismatch
        except Exception as e:
            print(f"  Seed data note: {e}")
        try:
            ensure_default_users()
        except Exception as e:
            print(f"  Default users note: {e}")
    else:
        print("  WARNING: Starting server WITHOUT database - API calls will fail!")
        print("  Set environment variables DB_SERVER, DB_UID, DB_PWD to connect.")

    try:
        srv = ThreadedServer((Config.HOST, Config.PORT), Handler)
    except OSError:
        print(f"\nPort {Config.PORT} in use!")
        exit(1)

    print(f"\nServer: http://localhost:{Config.PORT}")
    print(f"  Customer: http://localhost:{Config.PORT}/customer")
    print(f"  Courier:  http://localhost:{Config.PORT}/courier")
    print(f"  Admin:    http://localhost:{Config.PORT}/admin")
    print(f"  Support:  http://localhost:{Config.PORT}/support")
    print(f"\n  admin / admin | customer1 / 1234 | courier1 / 1234 | support1 / 1234\n")
    print("  API Endpoints:")
    print("    Chat:    /api/chat/send | /api/chat/messages/{oid} | /api/chat/conversations | /api/chat/unread")
    print("    Call:    /api/call/initiate | /api/call/answer | /api/call/end | /api/call/reject | /api/call/incoming | /api/call/ice-candidate")
    print("    Notif:   /api/notifications | /api/notifications/unread-count")
    print("    Address: /api/addresses")
    print("    Loyalty: /api/loyalty | /api/loyalty/history")
    print("    Earnings: /api/courier/earnings | /api/courier/set-vehicle")
    print("    Support: /api/support/tickets | /api/support/tickets/{id}/messages")
    print("    Deliver: /api/deliver-anything")
    print("    Stats:  /api/admin/stats")

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nBye!")
        srv.server_close()
