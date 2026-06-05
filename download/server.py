"""
Elyanivery — Pure Python HTTP Server + PostgreSQL
  v3.0 — PostgreSQL migration, In-App Chat, Voice Calling (WebRTC Signaling),
         Notifications, Address Book, Loyalty Points
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
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
from db import query, insert, init_db, seed_data, close_conn
from services.auth import AuthService


# ────────────────────────────────────────────
# EXTRA TABLES (auto-created on startup)
# ────────────────────────────────────────────
def ensure_default_users():
    """Ensure the default admin, customer1, courier1 accounts exist with known passwords."""
    defaults = [
        ('admin', 'admin', 'admin', 'Administrator'),
        ('customer1', '1234', 'customer', 'Customer One'),
        ('courier1', '1234', 'courier', 'Courier One'),
    ]
    for username, password, role, display_name in defaults:
        existing = query("SELECT id FROM Users WHERE username=?", (username,), fetch_one=True)
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
            # Always reset password to known value so login always works
            pw_hash = AuthService.hash_pw(password)
            try:
                query("UPDATE Users SET password_hash=?, display_name=? WHERE username=?",
                      (pw_hash, display_name, username))
            except:
                pass

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
            # Ensure password stays as '1234' and link to restaurant
            pw_hash = AuthService.hash_pw('1234')
            try:
                query("UPDATE Users SET password_hash=?, display_name=? WHERE username=?",
                      (pw_hash, r['name'], username))
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


def handle_partner_accept_order(payload, oid):
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
        est_minutes = 30  # default estimate
        query("UPDATE Orders SET status='accepted', updated_at=CURRENT_TIMESTAMP WHERE id=?", (oid,))
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


def handle_partner_ready_order(payload, oid):
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
        query("UPDATE Orders SET status='ready_for_pickup', updated_at=CURRENT_TIMESTAMP WHERE id=?", (oid,))
        query("INSERT INTO OrderLog (order_id, status, note) VALUES (?, 'ready_for_pickup', 'Order is ready for pickup')", (oid,))
        # Auto-assign courier now that the order is ready
        courier_id = auto_assign_courier(oid, float(restaurant['latitude']), float(restaurant['longitude']))
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


def auto_assign_courier(order_id, restaurant_lat, restaurant_lng):
    try:
        couriers = query("""
            SELECT cl.courier_id, cl.latitude, cl.longitude
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
            for c in couriers:
                try:
                    c['dist_km'] = haversine(restaurant_lat, restaurant_lng,
                                             float(c['latitude']), float(c['longitude']))
                except:
                    c['dist_km'] = 9999
            couriers.sort(key=lambda x: x['dist_km'])
            c = couriers[0]
            query("UPDATE Orders SET courier_id=?, status='courier_assigned', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (c['courier_id'], order_id))
            query("INSERT INTO OrderLog (order_id, status, note) VALUES (?, 'courier_assigned', ?)",
                  (order_id, f"Courier {c['courier_id']} assigned ({c['dist_km']:.1f}km away)"))
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
# API HANDLERS — AUTH / PROFILE
# ────────────────────────────────────────────
def handle_register(body):
    try:
        username = (body.get('username') or '').strip()
        password = body.get('password') or ''
        role = body.get('role', 'customer')
        display_name = body.get('display_name', username)
        if not username or not password:
            return 400, {"success": False, "message": "Username and password required"}
        if role not in ('customer', 'courier', 'admin'):
            role = 'customer'
        existing = query("SELECT id FROM Users WHERE username=?", (username,), fetch_one=True)
        if existing:
            return 409, {"success": False, "message": "Username already taken"}
        pw_hash = AuthService.hash_pw(password)
        uid = insert("INSERT INTO Users (username,password_hash,role,display_name) VALUES (?,?,?,?)",
                     (username, pw_hash, role, display_name))
        if role == 'courier':
            insert("INSERT INTO CourierLocations (courier_id,latitude,longitude,is_online) VALUES (?,0,0,FALSE)", (uid,))
        # Init loyalty
        try:
            insert("INSERT INTO LoyaltyPoints (user_id,points,total_earned) VALUES (?,0,0)", (uid,))
        except:
            pass
        token_val = AuthService.make_token(uid, role)
        return 201, {"success": True, "data": {"id": uid, "username": username, "role": role, "token": token_val, "display_name": display_name, "avatar_url": None}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_login(body):
    try:
        username = body.get('username', '')
        password = body.get('password', '')
        user = query("SELECT * FROM Users WHERE username=?", (username,), fetch_one=True)
        if not user or not AuthService.verify_pw(password, user['password_hash']):
            return 401, {"success": False, "message": "Invalid credentials"}
        token_val = AuthService.make_token(user['id'], user['role'])
        return 200, {"success": True, "data": {
            "id": user['id'], "username": user['username'], "role": user['role'],
            "token": token_val, "display_name": user.get('display_name', ''),
            "avatar_url": user.get('avatar_url')}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_me(payload):
    try:
        user = query("SELECT id,username,role,display_name,avatar_url FROM Users WHERE id=?", (payload['uid'],), fetch_one=True)
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
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
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
        order_number = f"ELY-{random.randint(100000, 999999)}"
        while query("SELECT id FROM Orders WHERE order_number=?", (order_number,), fetch_one=True):
            order_number = f"ELY-{random.randint(100000, 999999)}"

        delivery_lat = body.get('delivery_lat', 41.3900) or 41.3900
        delivery_lng = body.get('delivery_lng', 2.1700) or 2.1700

        # Insert order — status starts as 'pending' waiting for restaurant acceptance
        oid = insert(
            "INSERT INTO Orders (order_number,customer_id,restaurant_id,status,"
            "subtotal,delivery_fee,total,delivery_address,delivery_lat,delivery_lng)"
            " VALUES (?,?,?,'pending',?,?,?,?,?,?)",
            (order_number, uid, restaurant_id, subtotal, delivery_fee, total,
             'Customer Location', delivery_lat, delivery_lng)
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
        query("UPDATE CourierLocations SET is_online=? WHERE courier_id=?", (is_online, payload['uid']))
        return 200, {"success": True, "data": {"is_online": is_online}}
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
            auto_assign_courier(oid, float(restaurant['latitude']), float(restaurant['longitude']))
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
            auto_assign_courier(oid, float(restaurant['latitude']), float(restaurant['longitude']))
        return 200, {"success": True, "message": "Order reassigned to another courier."}
    except Exception as e:
        traceback.print_exc()
        return 500, {"success": False, "message": str(e)}


# ── ADMIN ──
def handle_admin_couriers(payload):
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        rows = query("SELECT u.id, u.username, u.display_name, u.avatar_url, cl.latitude, cl.longitude, cl.is_online FROM Users u LEFT JOIN CourierLocations cl ON u.id=cl.courier_id WHERE u.role='courier'", fetch=True)
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_unassigned_orders(payload):
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        rows = query("SELECT o.*, r.name as restaurant_name FROM Orders o JOIN Restaurants r ON o.restaurant_id=r.id WHERE o.courier_id IS NULL AND o.status NOT IN ('delivered','cancelled') ORDER BY o.created_at", fetch=True)
        return 200, {"success": True, "data": rows or []}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


def handle_admin_assign_order(body, payload):
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        oid, cid = body.get('order_id'), body.get('courier_id')
        if not oid or not cid:
            return 400, {"success": False, "message": "order_id and courier_id required"}
        query("UPDATE Orders SET courier_id=?, status='courier_assigned', updated_at=CURRENT_TIMESTAMP WHERE id=?", (cid, oid))
        query("INSERT INTO OrderLog (order_id,status,note) VALUES (?,'courier_assigned','Manually assigned')", (oid,))
        push_notification(cid, 'Order Assigned', f'Admin assigned you to order #{oid}', 'order_assigned', oid)
        return 200, {"success": True, "message": "Courier assigned"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ══════════════════════════════════════════════
#  NEW: IN-APP CHAT (Customer <-> Courier)
# ══════════════════════════════════════════════
def handle_chat_send(body, payload):
    """Send a chat message. Both customer and courier can use this."""
    try:
        order_id = body.get('order_id')
        message = (body.get('message') or '').strip()
        msg_type = body.get('message_type', 'text')  # text, image, location
        if not order_id or not message:
            return 400, {"success": False, "message": "order_id and message required"}

        # Verify the user is part of this order
        order = query("SELECT customer_id, courier_id FROM Orders WHERE id=?", (order_id,), fetch_one=True)
        if not order:
            return 404, {"success": False, "message": "Order not found"}

        uid = payload['uid']
        if uid != order['customer_id'] and uid != order['courier_id']:
            return 403, {"success": False, "message": "Not authorized for this conversation"}

        # Determine receiver
        receiver_id = order['courier_id'] if uid == order['customer_id'] else order['customer_id']
        if not receiver_id:
            return 400, {"success": False, "message": "No courier assigned yet"}

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
        if uid != order['customer_id'] and uid != order['courier_id']:
            return 403, {"success": False, "message": "Not authorized"}

        rows = query(
            "SELECT cm.*, u.display_name as sender_name, u.avatar_url as sender_avatar "
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

            # ── Admin ──
            elif path == '/api/admin/couriers':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_couriers(p)
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
            # ── Auth ──
            if path == '/api/auth/register':
                code, data = handle_register(body)
                return self._json(code, data)
            elif path == '/api/auth/login':
                code, data = handle_login(body)
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

            # ── Admin ──
            elif path == '/api/admin/assign':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_assign_order(body, p)
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
                code, data = handle_partner_accept_order(p, oid)
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
                code, data = handle_partner_ready_order(p, oid)
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
            else:
                self._json(404, {"success": False, "message": "Not found"})
        except Exception as e:
            traceback.print_exc()
            self._json(500, {"success": False, "message": str(e)})

    def do_DELETE(self):
        path = self.path.split('?')[0]
        try:
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
    print("  ELYANIVERY v3.0 - Delivery Platform (PostgreSQL)")
    print("  + Chat, Voice Calls, Notifications,")
    print("    Address Book, Loyalty Points")
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
        try:
            seed_data()
        except Exception as e:
            print(f"  Seed data note: {e}")
        try:
            init_extra_tables()
        except Exception as e:
            print(f"  Extra tables note: {e}")
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
    print(f"\n  admin / admin | customer1 / 1234 | courier1 / 1234\n")
    print("  New API Endpoints:")
    print("    Chat:    /api/chat/send | /api/chat/messages/{oid} | /api/chat/conversations | /api/chat/unread")
    print("    Call:    /api/call/initiate | /api/call/answer | /api/call/end | /api/call/reject | /api/call/incoming | /api/call/ice-candidate")
    print("    Notif:   /api/notifications | /api/notifications/unread-count")
    print("    Address: /api/addresses")
    print("    Loyalty: /api/loyalty | /api/loyalty/history")

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nBye!")
        srv.server_close()
