"""
Elyanivery — Pure Python HTTP Server + SQL Server
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
from config import Config
from db import query, insert, init_db, seed_data, close_conn
from services.auth import AuthService


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
            WHERE cl.is_online = 1 AND u.role = 'courier'
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
            query("UPDATE Orders SET courier_id=?, status='courier_assigned', updated_at=GETUTCDATE() WHERE id=?",
                  (c['courier_id'], order_id))
            query("INSERT INTO OrderLog (order_id, status, note) VALUES (?, 'courier_assigned', ?)",
                  (order_id, f"Courier {c['courier_id']} assigned ({c['dist_km']:.1f}km away)"))
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
# API HANDLERS
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
            insert("INSERT INTO CourierLocations (courier_id,latitude,longitude,is_online) VALUES (?,0,0,0)", (uid,))
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
            WHERE f.user_id=? AND s.is_open=1
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
        promo = query("SELECT * FROM PromoCodes WHERE code=? AND is_active=1 AND valid_from<=GETUTCDATE() AND valid_until>=GETUTCDATE()", (code,), fetch_one=True)
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


# ── CANCEL ORDER ──
def handle_cancel_order(payload, oid):
    try:
        order = query("SELECT * FROM Orders WHERE id=? AND customer_id=?", (oid, payload['uid']), fetch_one=True)
        if not order:
            return 404, {"success": False, "message": "Order not found"}
        if order['status'] not in ('pending', 'confirmed', 'courier_assigned'):
            return 400, {"success": False, "message": "Cannot cancel order in current status"}
        query("UPDATE Orders SET status='cancelled', cancelled_at=GETUTCDATE(), updated_at=GETUTCDATE() WHERE id=?", (oid,))
        query("INSERT INTO OrderLog (order_id,status,note) VALUES (?,'cancelled','Cancelled by customer')", (oid,))
        # Free up courier if assigned
        return 200, {"success": True, "message": "Order cancelled"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── REORDER ──
def handle_reorder(payload, oid):
    try:
        items = query("SELECT item_id, item_name, item_price, quantity FROM OrderItems WHERE order_id=?", (oid,), fetch=True)
        if not items:
            return 404, {"success": False, "message": "Order items not found"}
        order = query("SELECT restaurant_id FROM Orders WHERE id=? AND customer_id=?", (oid, payload['uid']), fetch_one=True)
        if not order:
            return 404, {"success": False, "message": "Order not found"}
        rid = order['restaurant_id']
        # Build cart
        cart = {"restaurant_id": rid, "items": []}
        for i in items:
            # Check item still exists
            item = query("SELECT id, name, price FROM Items WHERE id=? AND is_available=1", (i['item_id'],), fetch_one=True)
            if item:
                cart['items'].append({"item_id": item['id'], "name": item['name'], "price": float(item['price']), "quantity": i['quantity']})
        if not cart['items']:
            return 400, {"success": False, "message": "Items no longer available"}
        _carts[payload['uid']] = cart
        return 200, {"success": True, "data": cart}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── ADMIN TOGGLE RESTAURANT ──
def handle_toggle_restaurant(payload, rid):
    try:
        if payload['role'] != 'admin':
            return 403, {"success": False, "message": "Admin only"}
        r = query("SELECT is_open FROM Restaurants WHERE id=?", (rid,), fetch_one=True)
        if not r:
            return 404, {"success": False, "message": "Not found"}
        new_val = 0 if r['is_open'] else 1
        query("UPDATE Restaurants SET is_open=? WHERE id=?", (new_val, rid))
        return 200, {"success": True, "data": {"is_open": bool(new_val)}}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ── ADMIN ALL ORDERS ──
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
        rid = insert("INSERT INTO Restaurants (name,description,address,latitude,longitude,is_open,created_by) VALUES (?,?,?,?,?,1,?)",
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
            params.append(1 if body['is_open'] else 0)
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
            params.append(1 if body['is_available'] else 0)
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

        # Check promo code BEFORE calculating total
        discount = 0
        promo_code_str = body.get('promo_code', '').strip().upper()
        if promo_code_str:
            promo = query(
                "SELECT * FROM PromoCodes WHERE code=? AND is_active=1 "
                "AND valid_from<=GETUTCDATE() AND valid_until>=GETUTCDATE()",
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

        delivery_fee = 2.50
        total = round(subtotal + delivery_fee - discount, 2)

        # Generate unique order number
        import random
        order_number = f"ELY-{random.randint(100000, 999999)}"
        while query("SELECT id FROM Orders WHERE order_number=?", (order_number,), fetch_one=True):
            order_number = f"ELY-{random.randint(100000, 999999)}"

        delivery_lat = body.get('delivery_lat', 41.3900) or 41.3900
        delivery_lng = body.get('delivery_lng', 2.1700) or 2.1700

        # Insert order ONCE — discount is already subtracted from total
        oid = insert(
            "INSERT INTO Orders (order_number,customer_id,restaurant_id,status,"
            "subtotal,delivery_fee,total,delivery_address,delivery_lat,delivery_lng)"
            " VALUES (?,?,?,'confirmed',?,?,?,?,?,?)",
            (order_number, uid, restaurant_id, subtotal, delivery_fee, total,
             'Customer Location', delivery_lat, delivery_lng)
        )

        # Insert order items
        for item in cart['items']:
            insert(
                "INSERT INTO OrderItems (order_id,item_id,item_name,item_price,quantity) VALUES (?,?,?,?,?)",
                (oid, item['item_id'], item['name'], item['price'], item['quantity'])
            )

        # Clear cart
        _carts.pop(uid, None)

        # Auto-assign courier
        courier_id = auto_assign_courier(oid, float(restaurant['latitude']), float(restaurant['longitude']))

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
        if courier_id:
            c = query("SELECT id,display_name FROM Users WHERE id=?", (courier_id,), fetch_one=True)
            order['courier_name'] = c['display_name'] if c else 'Courier'
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
            cloc = query("SELECT TOP 1 u.display_name, u.avatar_url, cl.latitude, cl.longitude FROM CourierLocations cl JOIN Users u ON cl.courier_id=u.id WHERE cl.courier_id=? ORDER BY cl.updated_at DESC", (order['courier_id'],), fetch_one=True)
            order['courier_location'] = cloc
            order['courier_name'] = cloc['display_name'] if cloc else 'Courier'
            order['courier_avatar'] = cloc.get('avatar_url') if cloc else None
        # Check if rated
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
        return 201, {"success": True, "message": "Rating submitted!"}
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
            query("UPDATE CourierLocations SET latitude=?,longitude=?,updated_at=GETUTCDATE() WHERE courier_id=?", (lat, lng, payload['uid']))
        else:
            insert("INSERT INTO CourierLocations (courier_id,latitude,longitude,is_online) VALUES (?,?,?,1)", (payload['uid'], lat, lng))
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
        update_fields, params = "status=?, updated_at=GETUTCDATE()", [new_status]
        if new_status == 'arrived_at_restaurant':
            update_fields += ", courier_arrived_restaurant_at=GETUTCDATE()"
            if lat and lng:
                try:
                    landmark = reverse_geocode(lat, lng)
                except:
                    landmark = f"Near {lat:.4f}, {lng:.4f}"
                update_fields += ", landmark=?"
                params.append(landmark)
        elif new_status == 'order_picked_up':
            update_fields += ", order_picked_up_at=GETUTCDATE()"
        elif new_status == 'arrived_at_customer':
            update_fields += ", courier_arrived_customer_at=GETUTCDATE()"
        elif new_status == 'delivered':
            update_fields += ", delivered_at=GETUTCDATE()"
        params.append(oid)
        query(f"UPDATE Orders SET {update_fields} WHERE id=?", tuple(params))
        query("INSERT INTO OrderLog (order_id,status) VALUES (?,?)", (oid, new_status))
        return 200, {"success": True, "data": {"status": new_status}}
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
        query("UPDATE Orders SET courier_id=?, status='courier_assigned', updated_at=GETUTCDATE() WHERE id=?", (cid, oid))
        query("INSERT INTO OrderLog (order_id,status,note) VALUES (?,'courier_assigned','Manually assigned')", (oid,))
        return 200, {"success": True, "message": "Courier assigned"}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}


# ────────────────────────────────────────────
# HTTP SERVER
# ────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"  [{self.log_date_time_string()}] {args[0]}")

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
            if path == '/' or path == '/customer':
                self._serve('/static/customer/index.html')
            elif path == '/courier':
                self._serve('/static/courier/index.html')
            elif path.startswith('/static/'):
                self._serve(path)
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
            elif path == '/api/cart':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_get_cart(p)
                self._json(code, data)
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
            elif path == '/api/courier/orders':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_courier_assigned_orders(p)
                self._json(code, data)
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
                # GET /api/favorites/{rid} — check if favorite
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
            if path == '/api/auth/register':
                code, data = handle_register(body)
                return self._json(code, data)
            elif path == '/api/auth/login':
                code, data = handle_login(body)
                return self._json(code, data)
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
            elif path.startswith('/api/restaurants/') and '/items' in path:
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
            elif path == '/api/admin/assign':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_admin_assign_order(body, p)
                self._json(code, data)
            elif path == '/api/favorites':
                p = self._auth()
                if not p:
                    return self._json(401, {"success": False, "message": "Auth required"})
                code, data = handle_add_favorite(body, p)
                self._json(code, data)
            elif path == '/api/promo/validate':
                code, data = handle_validate_promo(body)
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
            if path.startswith('/api/restaurants/') and '/items/' in path:
                # PUT /api/restaurants/{rid}/items/{iid}
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
            if path.startswith('/api/restaurants/') and '/items/' in path:
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
    print("  ELYANIVERY - Delivery Platform")
    print("=" * 50)
    try:
        import pyodbc
        conn = pyodbc.connect(Config.master_conn_string(), autocommit=True)
        conn.close()
        print("DB connection OK")
    except Exception as e:
        print(f"DB connection failed: {e}")
        input("Press Enter to exit...")
        exit(1)

    init_db()
    seed_data()

    try:
        srv = ThreadedServer((Config.HOST, Config.PORT), Handler)
    except OSError:
        print(f"\nPort {Config.PORT} in use!")
        input("Press Enter...")
        exit(1)

    print(f"\nServer: http://localhost:{Config.PORT}")
    print(f"  Customer: http://localhost:{Config.PORT}/customer")
    print(f"  Courier:  http://localhost:{Config.PORT}/courier")
    print(f"\n  admin / admin | customer1 / 1234 | courier1 / 1234\n")

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nBye!")
        srv.server_close()
