import { NextRequest, NextResponse } from "next/server";
import { sendOtpEmail } from "@/lib/mailer";
import {
  users,
  restaurants,
  menuItems,
  orders,
  tickets,
  notifications,
  broadcasts,
  courierState,
  otpStore,
  Order,
  User,
} from "@/lib/mock-data";

// In-memory cart per session / user
const userCarts: Record<number, { restaurant_id: number; items: { item_id: number; quantity: number }[] }> = {
  2: {
    restaurant_id: 10,
    items: [
      { item_id: 1001, quantity: 2 },
      { item_id: 1003, quantity: 1 }
    ]
  }
};

const chatMessages: Record<number, any[]> = {
  1001: [
    { id: 1, order_id: 1001, sender_id: 3, sender_role: 'courier', message: 'Hello! I am picking up your order at Koshary Abou Tarek.', message_type: 'text', created_at: new Date(Date.now() - 10 * 60 * 1000).toISOString() },
    { id: 2, order_id: 1001, sender_id: 2, sender_role: 'customer', message: 'Thank you! Please ring intercom 5 when you arrive.', message_type: 'text', created_at: new Date(Date.now() - 8 * 60 * 1000).toISOString() }
  ]
};

function getAuthUser(req: NextRequest): User | null {
  const authHeader = req.headers.get("authorization");
  if (!authHeader) return users[1]; // default to customer1 for preview convenience
  const token = authHeader.replace("Bearer ", "").trim();
  if (token === "token_admin" || token.includes("admin")) return users.find(u => u.role === 'admin') || users[0];
  if (token === "token_courier" || token.includes("courier")) return users.find(u => u.role === 'courier' && u.status === 'approved') || users[2];
  if (token === "token_partner" || token.includes("partner")) return users.find(u => u.role === 'partner') || users[4];
  if (token === "token_support" || token.includes("support")) return users.find(u => u.role === 'support') || users[3];
  const user = users.find(u => `token_${u.username}` === token || u.username === token);
  return user || users[1];
}

export async function OPTIONS() {
  return new NextResponse(null, {
    status: 200,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
    },
  });
}

export async function GET(
  req: NextRequest,
  context: { params: Promise<{ path?: string[] }> }
) {
  const resolvedParams = await context.params;
  const path = resolvedParams.path || [];
  const route = path.join("/");
  const user = getAuthUser(req);
  const searchParams = req.nextUrl.searchParams;

  // Root api
  if (!route) {
    return NextResponse.json({ success: true, message: "Elyanivery API active" });
  }

  // Google Maps API config endpoint
  if (route === "config/maps") {
    const key = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || process.env.GOOGLE_MAPS_API_KEY || "";
    return NextResponse.json({
      success: true,
      apiKey: key,
      hasKey: !!key,
      solutionId: "gmp_git_agentskills_v1"
    });
  }

  // Current User
  if (route === "me" || route === "auth/me") {
    return NextResponse.json({ success: true, data: user, user });
  }

  // Broadcasts
  if (route === "broadcasts" || route === "admin/broadcasts") {
    return NextResponse.json({ success: true, data: broadcasts, broadcasts });
  }

  // Notifications
  if (route === "notifications") {
    const userNotifs = notifications.filter(n => !n.user_id || n.user_id === user?.id);
    return NextResponse.json({ success: true, data: userNotifs, notifications: userNotifs });
  }

  if (route === "notifications/unread-count") {
    const count = notifications.filter(n => (!n.user_id || n.user_id === user?.id) && !n.is_read).length;
    return NextResponse.json({ success: true, count, unread_count: count });
  }

  // Restaurants with Country / Location Filtering
  if (route === "restaurants") {
    const country = searchParams.get("country")?.toLowerCase();
    const countryCode = searchParams.get("country_code")?.toUpperCase();
    let filtered = [...restaurants];

    if (countryCode) {
      filtered = filtered.filter(r => r.country_code.toUpperCase() === countryCode);
    } else if (country) {
      filtered = filtered.filter(r => r.country.toLowerCase().includes(country) || r.country_code.toLowerCase() === country);
    } else if (user?.country_code) {
      // Prioritize user's country if set
      const userMatched = filtered.filter(r => r.country_code.toUpperCase() === user.country_code?.toUpperCase());
      if (userMatched.length > 0) {
        filtered = userMatched;
      }
    }

    return NextResponse.json({
      success: true,
      data: filtered,
      restaurants: filtered,
      total: filtered.length,
      available_countries: [
        { code: 'EG', name: 'Egypt', flag: '🇪🇬', cities: ['Cairo', 'Alexandria'] },
        { code: 'MD', name: 'Moldova', flag: '🇲🇩', cities: ['Chisinau'] },
        { code: 'RO', name: 'Romania', flag: '🇷🇴', cities: ['Bucharest'] }
      ]
    });
  }

  if (route.startsWith("restaurants/")) {
    const restId = parseInt(path[1], 10);
    const rest = restaurants.find(r => r.id === restId);
    if (!rest) return NextResponse.json({ success: false, message: "Restaurant not found" }, { status: 404 });
    const items = menuItems.filter(m => m.restaurant_id === restId);
    return NextResponse.json({
      success: true,
      data: {
        ...rest,
        menu: items,
        items
      }
    });
  }

  // Cart
  if (route === "cart") {
    const uid = user?.id || 2;
    const cart = userCarts[uid] || { restaurant_id: 10, items: [] };
    const rest = restaurants.find(r => r.id === cart.restaurant_id);
    const populatedItems = cart.items.map(ci => {
      const m = menuItems.find(item => item.id === ci.item_id);
      return {
        item_id: ci.item_id,
        quantity: ci.quantity,
        name: m?.name || 'Item',
        price: m?.price || 5.0,
        image_url: m?.image_url || '',
        subtotal: (m?.price || 5.0) * ci.quantity
      };
    });
    const subtotal = populatedItems.reduce((acc, i) => acc + i.subtotal, 0);
    const delivery_fee = subtotal > 0 ? 2.00 : 0;
    const total = subtotal + delivery_fee;

    return NextResponse.json({
      success: true,
      cart: {
        restaurant_id: cart.restaurant_id,
        restaurant_name: rest?.name || 'Restaurant',
        items: populatedItems,
        subtotal,
        delivery_fee,
        total
      }
    });
  }

  // Orders
  if (route === "orders") {
    const uid = user?.id;
    let userOrders = orders;
    if (user?.role === 'customer') {
      userOrders = orders.filter(o => o.customer_id === uid);
    } else if (user?.role === 'courier') {
      userOrders = orders.filter(o => o.courier_id === uid);
    } else if (user?.role === 'partner') {
      userOrders = orders.filter(o => o.restaurant_id === 10 || o.restaurant_id === 1);
    }
    return NextResponse.json({ success: true, data: userOrders, orders: userOrders });
  }

  if (route.startsWith("orders/")) {
    const orderId = parseInt(path[1], 10);
    const order = orders.find(o => o.id === orderId);
    if (!order) return NextResponse.json({ success: false, message: "Order not found" }, { status: 404 });
    return NextResponse.json({ success: true, data: order, order });
  }

  // Active tracking order for customer
  if (route === "customer/active-order") {
    const active = orders.find(o => o.customer_id === (user?.id || 2) && !['delivered', 'cancelled'].includes(o.status));
    return NextResponse.json({ success: true, order: active || null });
  }

  // Courier Status & Active Orders
  if (route === "courier/status") {
    const courierUser = users.find(u => u.id === user?.id && u.role === 'courier') || users[2];
    return NextResponse.json({
      success: true,
      status: courierUser.status,
      is_approved: courierUser.status === 'approved',
      vehicle_type: courierUser.vehicle_type || courierState.vehicle_type,
      is_online: courierState.is_online,
      state: courierState
    });
  }

  if (route === "courier/active-order") {
    const cid = user?.id || 3;
    const active = orders.find(o => (o.courier_id === cid || (!o.courier_id && o.status === 'ready_for_pickup')) && !['delivered', 'cancelled'].includes(o.status));
    return NextResponse.json({ success: true, order: active || null });
  }

  if (route === "courier/orders" || route === "courier/available-orders") {
    const available = orders.filter(o => !['delivered', 'cancelled'].includes(o.status));
    return NextResponse.json({ success: true, data: available, orders: available });
  }

  if (route === "courier/stats") {
    return NextResponse.json({
      success: true,
      data: {
        active_deliveries: orders.filter(o => o.courier_id === 3 && !['delivered', 'cancelled'].includes(o.status)).length,
        delivered_count: orders.filter(o => o.courier_id === 3 && o.status === 'delivered').length + 8,
        total_earnings: courierState.balance,
        rating: courierState.rating,
        today_deliveries: courierState.today_deliveries,
        vehicle_type: courierState.vehicle_type,
        is_online: courierState.is_online
      }
    });
  }

  // Admin Pending Courier Applications
  if (route === "admin/pending-couriers") {
    const pendingCouriers = users.filter(u => u.role === 'courier' && u.status === 'pending_approval');
    return NextResponse.json({
      success: true,
      data: pendingCouriers,
      couriers: pendingCouriers,
      count: pendingCouriers.length
    });
  }

  // Admin Stats & Lists
  if (route === "admin/stats" || route === "admin/full-stats") {
    return NextResponse.json({
      success: true,
      data: {
        total_orders: orders.length + 154,
        active_orders: orders.filter(o => !['delivered', 'cancelled'].includes(o.status)).length,
        total_revenue: 3890.50,
        active_couriers: users.filter(u => u.role === 'courier' && u.status === 'approved').length,
        pending_couriers: users.filter(u => u.role === 'courier' && u.status === 'pending_approval').length,
        active_restaurants: restaurants.length,
        total_users: users.length
      }
    });
  }

  if (route === "admin/users") {
    return NextResponse.json({ success: true, data: users, users });
  }

  if (route === "admin/couriers") {
    const couriers = users.filter(u => u.role === 'courier');
    return NextResponse.json({ success: true, data: couriers, couriers });
  }

  if (route === "admin/orders") {
    return NextResponse.json({ success: true, data: orders, orders });
  }

  // Support tickets
  if (route === "support/tickets" || route === "tickets") {
    return NextResponse.json({ success: true, data: tickets, tickets });
  }

  if (route.startsWith("chat/")) {
    const orderId = parseInt(path[1], 10);
    const msgs = chatMessages[orderId] || [];
    return NextResponse.json({ success: true, messages: msgs, data: msgs });
  }

  // Fallback
  return NextResponse.json({ success: true, data: [] });
}

export async function POST(
  req: NextRequest,
  context: { params: Promise<{ path?: string[] }> }
) {
  const resolvedParams = await context.params;
  const path = resolvedParams.path || [];
  const rawRoute = path.join("/");
  const route = rawRoute.replace(/^\/+|\/+$/g, '').toLowerCase();
  const user = getAuthUser(req);
  let body: any = {};
  try {
    body = await req.json();
  } catch {
    body = {};
  }

  // ────────────────────────────────────────────────────────
  // OTP AUTHENTICATION (Gmail Email OTP Verification)
  // ────────────────────────────────────────────────────────
  if (route === "auth/send-otp" || route === "send-otp" || route === "otp/send" || route === "auth/otp/send" || route === "auth/email/send-otp") {
    const targetEmail = (body.email || body.identifier || body.target || (body.channel === 'email' ? body.target : '') || body.username || '').toString().trim();
    if (!targetEmail) {
      return NextResponse.json({ success: false, message: "Please provide a valid Gmail / email address" }, { status: 400 });
    }

    // Generate random 6-digit OTP
    const generatedOtp = Math.floor(100000 + Math.random() * 900000).toString();
    const cleanEmail = targetEmail.toLowerCase();
    const key = `email:${cleanEmail}`;
    otpStore[key] = {
      emailOtp: generatedOtp,
      expiresAt: Date.now() + 10 * 60 * 1000
    };
    otpStore[cleanEmail] = {
      emailOtp: generatedOtp,
      expiresAt: Date.now() + 10 * 60 * 1000
    };

    let sentViaEmail = false;
    let emailMsg = "";
    const mailRes = await sendOtpEmail(cleanEmail, generatedOtp);
    sentViaEmail = mailRes.sentViaEmail;
    emailMsg = mailRes.message;

    return NextResponse.json({
      success: true,
      message: emailMsg || `Verification code successfully sent to ${cleanEmail}.`,
      code: generatedOtp,
      otp: generatedOtp,
      dev_otp: generatedOtp,
      sentViaEmail,
      channel: 'email',
      target: cleanEmail,
      email: cleanEmail
    });
  }

  if (route === "auth/verify-otp" || route === "verify-otp" || route === "otp/verify" || route === "auth/otp/verify") {
    const targetEmail = (body.email || body.identifier || body.target || body.username || '').toString().trim().toLowerCase();
    const enteredCode = (body.otp || body.code || body.verification_code || "").toString().trim();

    if (!enteredCode) {
      return NextResponse.json({ success: false, message: "OTP verification code is required" }, { status: 400 });
    }

    const key = `email:${targetEmail}`;
    const stored = otpStore[key] || otpStore[targetEmail];

    // Accept valid generated OTP, universal test codes (123456 / 000000), or matched store
    const expectedOtp = stored?.emailOtp;
    const isValid = enteredCode === expectedOtp || enteredCode === "123456" || enteredCode === "000000" || (stored && (enteredCode === stored.emailOtp || enteredCode === stored.phoneOtp));

    if (!isValid) {
      return NextResponse.json({ success: false, message: "Invalid or expired OTP code. Tip: For demo or Render deployment without SMTP, use code 123456." }, { status: 400 });
    }

    return NextResponse.json({
      success: true,
      verified: true,
      channel: 'email',
      code: enteredCode,
      message: "Gmail address verified successfully!"
    });
  }

  // ────────────────────────────────────────────────────────
  // CUSTOMER REGISTRATION (Gmail-Focused + Instant Loyalty Points)
  // ────────────────────────────────────────────────────────
  if (route === "auth/register-customer" || route === "register-customer" || route === "auth/customer/register") {
    const { username, display_name, email, phone, country, country_code, city, address, delivery_address } = body;
    const cleanEmail = (email || '').toString().trim();
    if (!cleanEmail) {
      return NextResponse.json({ success: false, message: "Gmail address is required for customer registration" }, { status: 400 });
    }

    const uname = username || cleanEmail.split('@')[0].replace(/[^a-zA-Z0-9_]/g, '') || `user_${Date.now().toString().slice(-4)}`;
    let customerUser = users.find(u => u.email?.toLowerCase() === cleanEmail.toLowerCase() || u.username.toLowerCase() === uname.toLowerCase());

    if (!customerUser) {
      customerUser = {
        id: users.length + 1,
        username: uname,
        display_name: display_name || uname,
        role: 'customer',
        email: cleanEmail,
        email_verified: true,
        phone: phone || '+20 10 0000 0000',
        phone_verified: true,
        country: country || (country_code === 'RO' ? 'Romania' : (country_code === 'MD' ? 'Moldova' : 'Egypt')),
        country_code: country_code || 'EG',
        city: city || (country_code === 'RO' ? 'Bucharest' : (country_code === 'MD' ? 'Chisinau' : 'Cairo')),
        avatar_url: `https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150`,
        status: 'approved',
        created_at: new Date().toISOString()
      };
      (customerUser as any).address = address || delivery_address || 'Cairo';
      users.push(customerUser);
    } else {
      customerUser.email = cleanEmail;
      customerUser.email_verified = true;
      if (phone) customerUser.phone = phone;
      if (display_name) customerUser.display_name = display_name;
      if (country) customerUser.country = country;
      if (country_code) customerUser.country_code = country_code;
      if (city) customerUser.city = city;
      if (address || delivery_address) (customerUser as any).address = address || delivery_address;
    }

    const tokenStr = `token_${customerUser.username}`;
    const authData = {
      token: tokenStr,
      user: customerUser,
      ...customerUser
    };

    return NextResponse.json({
      success: true,
      token: tokenStr,
      user: customerUser,
      data: authData,
      message: `Welcome ${customerUser.display_name}! You are registered and verified.`
    });
  }

  // ────────────────────────────────────────────────────────
  // COURIER REGISTRATION (Gmail-Focused + Vehicle + Admin Approval)
  // ────────────────────────────────────────────────────────
  if (route === "auth/register-courier" || route === "register-courier" || route === "auth/courier/register") {
    const { username, display_name, email, phone, vehicle, vehicle_type, country_code } = body;
    const cleanEmail = (email || '').toString().trim();
    if (!cleanEmail) {
      return NextResponse.json({ success: false, message: "Gmail address is required for courier registration" }, { status: 400 });
    }

    const chosenVehicle = vehicle || vehicle_type || 'motorcycle';
    const uname = username || cleanEmail.split('@')[0].replace(/[^a-zA-Z0-9_]/g, '') || `courier_${Date.now().toString().slice(-4)}`;
    const newCourier: User = {
      id: users.length + 1,
      username: uname,
      display_name: display_name || uname,
      role: 'courier',
      email: cleanEmail,
      email_verified: true,
      phone: phone || '+20 10 0000 0000',
      phone_verified: true,
      vehicle_type: chosenVehicle,
      country: country_code === 'RO' ? 'Romania' : (country_code === 'MD' ? 'Moldova' : 'Egypt'),
      country_code: country_code || 'EG',
      city: country_code === 'RO' ? 'Bucharest' : (country_code === 'MD' ? 'Chisinau' : 'Cairo'),
      avatar_url: `https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150`,
      status: 'pending_approval', // Strictly pending admin approval!
      created_at: new Date().toISOString()
    };
    (newCourier as any).approval_status = 'pending';
    (newCourier as any).vehicle = chosenVehicle;
    users.push(newCourier);

    // Notify Admin of new courier application
    notifications.unshift({
      id: Date.now(),
      user_id: 1, // Admin user id
      title: '📋 New Courier Application Pending',
      body: `${newCourier.display_name} has registered with Gmail (${cleanEmail}) for vehicle: ${chosenVehicle.toUpperCase()}. Review and approve in Admin Portal.`,
      type: 'courier_application',
      reference_id: newCourier.id,
      is_read: false,
      created_at: new Date().toISOString()
    });

    const tokenStr = `token_${newCourier.username}`;
    const authData = {
      token: tokenStr,
      user: newCourier,
      ...newCourier
    };

    return NextResponse.json({
      success: true,
      token: tokenStr,
      user: newCourier,
      data: authData,
      approval_status: 'pending',
      message: "Application submitted! Your account is pending admin approval."
    });
  }

  // ────────────────────────────────────────────────────────
  // ADMIN PASSWORD CHANGE
  // ────────────────────────────────────────────────────────
  if (route === "admin/change-password" || route === "auth/change-password") {
    const { old_password, new_password, password } = body;
    const newPw = new_password || password;
    if (!newPw) {
      return NextResponse.json({ success: false, message: "New password is required" }, { status: 400 });
    }
    const adminUser = users.find(u => u.username === 'admin' || u.role === 'admin');
    if (adminUser) {
      (adminUser as any).password = newPw;
    }
    return NextResponse.json({
      success: true,
      message: "Admin password updated successfully!"
    });
  }

  // ────────────────────────────────────────────────────────
  // ADMIN COURIER & USER APPROVAL WORKFLOW
  // ────────────────────────────────────────────────────────
  if (route === "admin/courier-approval" || route === "admin/users/approve") {
    const courier_id = body.courier_id || body.user_id;
    const action = body.action || 'approve';
    const targetCourier = users.find(u => u.id === courier_id);
    if (!targetCourier) {
      return NextResponse.json({ success: false, message: "User not found" }, { status: 404 });
    }

    if (action === 'approve') {
      targetCourier.status = 'approved';
      (targetCourier as any).approval_status = 'approved';
      courierState.is_online = true;

      // Dispatch approval notification to courier
      notifications.unshift({
        id: Date.now(),
        user_id: targetCourier.id,
        title: '🎉 Courier Account Approved by Admin!',
        body: 'Your courier profile and vehicle have been approved. You are now authorized to go online and receive delivery orders on Google Maps!',
        type: 'courier_approval',
        reference_id: targetCourier.id,
        is_read: false,
        created_at: new Date().toISOString()
      });

      return NextResponse.json({
        success: true,
        message: `Courier ${targetCourier.display_name} has been approved successfully!`,
        courier: targetCourier
      });
    } else {
      targetCourier.status = 'rejected';
      (targetCourier as any).approval_status = 'rejected';
      return NextResponse.json({
        success: true,
        message: `Courier application for ${targetCourier.display_name} rejected.`,
        courier: targetCourier
      });
    }
  }

  // ────────────────────────────────────────────────────────
  // STANDARD AUTH: Generic Register & Login
  // ────────────────────────────────────────────────────────
  if (route === "auth/register") {
    const { username, password, display_name, email, phone, role, country_code } = body;
    const assignedRole = role || 'customer';
    const emailTarget = email || `${username || 'user'}@gmail.com`;
    const uname = username || emailTarget.split('@')[0] || `user_${Date.now().toString().slice(-4)}`;

    let existing = users.find(u => u.username.toLowerCase() === uname.toLowerCase() || u.email?.toLowerCase() === emailTarget.toLowerCase());
    if (!existing) {
      existing = {
        id: users.length + 1,
        username: uname,
        display_name: display_name || uname,
        role: assignedRole,
        email: emailTarget,
        email_verified: true,
        phone: phone || '+20 10 1234 5678',
        phone_verified: true,
        country: country_code === 'RO' ? 'Romania' : (country_code === 'MD' ? 'Moldova' : 'Egypt'),
        country_code: country_code || 'EG',
        city: country_code === 'RO' ? 'Bucharest' : (country_code === 'MD' ? 'Chisinau' : 'Cairo'),
        avatar_url: '/static/logo.png',
        status: assignedRole === 'courier' ? 'pending_approval' : 'approved',
        created_at: new Date().toISOString()
      };
      users.push(existing);
    }

    const tokenStr = `token_${existing.username}`;
    const authData = {
      token: tokenStr,
      user: existing,
      ...existing
    };

    return NextResponse.json({
      success: true,
      token: tokenStr,
      user: existing,
      data: authData,
      message: `Account registered successfully for ${existing.display_name}!`
    });
  }

  if (route === "auth/login") {
    const { username, password } = body;
    const uname = (username || "").toLowerCase();
    const matched = users.find(u => u.username.toLowerCase() === uname || u.email?.toLowerCase() === uname);
    if (matched) {
      const curStatus = matched.status || (matched as any).approval_status;
      if (matched.role === 'courier' && (curStatus === 'pending_approval' || curStatus === 'pending')) {
        return NextResponse.json({
          success: false,
          approval_status: 'pending',
          message: 'Your courier account is pending admin approval. An admin must approve your profile before you can log in.'
        }, { status: 403 });
      }
      const tokenStr = `token_${matched.username}`;
      const authData = {
        token: tokenStr,
        user: matched,
        ...matched
      };
      return NextResponse.json({
        success: true,
        token: tokenStr,
        user: matched,
        data: authData
      });
    }
    // Auto-create customer user if not found for seamless test flow
    const newUser: User = {
      id: users.length + 1,
      username: username || "guest",
      display_name: username || "Guest Customer",
      role: 'customer',
      email: `${username || 'guest'}@elyanivery.com`,
      phone: '+20 10 0000 0000',
      country: 'Egypt',
      country_code: 'EG',
      city: 'Cairo',
      avatar_url: '/static/logo.png',
      status: 'approved',
      created_at: new Date().toISOString()
    };
    users.push(newUser);
    const tokenStr = `token_${newUser.username}`;
    const authData = {
      token: tokenStr,
      user: newUser,
      ...newUser
    };
    return NextResponse.json({
      success: true,
      token: tokenStr,
      user: newUser,
      data: authData
    });
  }

  // ────────────────────────────────────────────────────────
  // CART OPERATIONS
  // ────────────────────────────────────────────────────────
  if (route === "cart/add") {
    const uid = user?.id || 2;
    if (!userCarts[uid]) userCarts[uid] = { restaurant_id: body.restaurant_id || 10, items: [] };
    const cart = userCarts[uid];
    if (body.restaurant_id && cart.restaurant_id !== body.restaurant_id) {
      cart.restaurant_id = body.restaurant_id;
      cart.items = [];
    }
    const existingIndex = cart.items.findIndex(i => i.item_id === body.item_id);
    const qty = body.quantity || 1;
    if (existingIndex > -1) {
      cart.items[existingIndex].quantity += qty;
      if (cart.items[existingIndex].quantity <= 0) {
        cart.items.splice(existingIndex, 1);
      }
    } else if (qty > 0) {
      cart.items.push({ item_id: body.item_id, quantity: qty });
    }
    return NextResponse.json({ success: true, cart });
  }

  if (route.startsWith("cart/remove/")) {
    const uid = user?.id || 2;
    const itemId = parseInt(path[2], 10);
    if (userCarts[uid]) {
      userCarts[uid].items = userCarts[uid].items.filter(i => i.item_id !== itemId);
    }
    return NextResponse.json({ success: true, cart: userCarts[uid] });
  }

  if (route === "cart/clear") {
    const uid = user?.id || 2;
    if (userCarts[uid]) userCarts[uid].items = [];
    return NextResponse.json({ success: true });
  }

  // ────────────────────────────────────────────────────────
  // ORDER CREATION: Distinctive Order Number & Courier Assignment
  // ────────────────────────────────────────────────────────
  if (route === "orders" || route === "deliver-anything") {
    const newId = Math.floor(1000 + Math.random() * 9000);
    const distinctiveNumber = `#ELY-${newId}`; // Distinctive order number format

    const rest = restaurants.find(r => r.id === (body.restaurant_id || 10)) || restaurants[0];

    // Find available approved online courier
    const assignedCourier = users.find(u => u.role === 'courier' && u.status === 'approved') || users[2];

    const customerLat = body.delivery_lat || 30.0444;
    const customerLng = body.delivery_lng || 31.2357;

    const newOrder: Order = {
      id: newId,
      order_number: distinctiveNumber,
      customer_id: user?.id || 2,
      restaurant_id: rest.id,
      courier_id: assignedCourier ? assignedCourier.id : null,
      courier_name: assignedCourier ? assignedCourier.display_name : undefined,
      courier_phone: assignedCourier ? assignedCourier.phone : undefined,
      courier_vehicle: assignedCourier ? assignedCourier.vehicle_type : 'bicycle',
      courier_lat: (rest.latitude + customerLat) / 2,
      courier_lng: (rest.longitude + customerLng) / 2,
      status: assignedCourier ? 'courier_assigned' : 'pending',
      subtotal: body.subtotal || 14.50,
      delivery_fee: 2.00,
      discount: body.discount || 0,
      total: (body.subtotal || 14.50) + 2.00 - (body.discount || 0),
      delivery_address: body.delivery_address || body.dropoff_address || 'Tahrir Square 5, Downtown, Cairo',
      delivery_lat: customerLat,
      delivery_lng: customerLng,
      restaurant_lat: rest.latitude,
      restaurant_lng: rest.longitude,
      created_at: new Date().toISOString(),
      restaurant_name: rest.name,
      restaurant_address: rest.address,
      customer_name: user?.display_name || 'Alexandru Popescu',
      customer_phone: user?.phone || '+20 10 1234 5678',
      estimated_prep_minutes: 18,
      items: body.items && body.items.length > 0 ? body.items : [
        { id: 1, order_id: newId, item_id: 1001, name: 'Special Koshary Meal', price: 14.50, quantity: 1 }
      ],
      log: [
        { status: 'pending', note: `Order placed with distinctive code ${distinctiveNumber}`, created_at: new Date().toISOString() },
        { status: 'courier_assigned', note: `Assigned to courier ${assignedCourier?.display_name || 'Courier'} on Google Maps`, created_at: new Date().toISOString() }
      ]
    };

    orders.unshift(newOrder);

    // Clear cart
    const uid = user?.id || 2;
    if (userCarts[uid]) userCarts[uid].items = [];

    // Notify Customer
    notifications.unshift({
      id: Date.now(),
      user_id: user?.id || 2,
      title: `Order Placed: ${distinctiveNumber}`,
      body: `Your order from ${rest.name} has been placed. Courier ${assignedCourier?.display_name} assigned!`,
      type: 'order_created',
      reference_id: newId,
      order_data: newOrder,
      is_read: false,
      created_at: new Date().toISOString()
    });

    // Notify Courier with all order data!
    if (assignedCourier) {
      notifications.unshift({
        id: Date.now() + 1,
        user_id: assignedCourier.id,
        title: `🚨 New Order Assigned: ${distinctiveNumber}`,
        body: `Pickup: ${rest.name} (${rest.address}) ➡️ Dropoff: ${newOrder.delivery_address} for ${newOrder.customer_name}. Total: €${newOrder.total.toFixed(2)}`,
        type: 'order_assigned',
        reference_id: newId,
        order_data: newOrder,
        is_read: false,
        created_at: new Date().toISOString()
      });
    }

    return NextResponse.json({
      success: true,
      order: newOrder,
      order_id: newId,
      order_number: distinctiveNumber,
      message: `Order ${distinctiveNumber} placed successfully and assigned to courier!`
    });
  }

  // ────────────────────────────────────────────────────────
  // COURIER ACTIONS
  // ────────────────────────────────────────────────────────
  if (route.startsWith("courier/order/") && path[3] === "status") {
    const orderId = parseInt(path[2], 10);
    const order = orders.find(o => o.id === orderId);
    if (order) {
      order.status = body.status || 'delivered';
      order.courier_id = user?.id || 3;
      order.courier_name = user?.display_name || 'Mahmoud Courier';
      if (body.courier_lat) order.courier_lat = body.courier_lat;
      if (body.courier_lng) order.courier_lng = body.courier_lng;

      order.log?.push({
        status: order.status,
        note: `Courier updated status to ${order.status}`,
        created_at: new Date().toISOString()
      });

      // Update customer with notification
      notifications.unshift({
        id: Date.now(),
        user_id: order.customer_id,
        title: `Order ${order.order_number} Update`,
        body: `Status updated to: ${order.status.replace(/_/g, ' ').toUpperCase()}`,
        type: 'order_update',
        reference_id: order.id,
        order_data: order,
        is_read: false,
        created_at: new Date().toISOString()
      });
    }
    return NextResponse.json({ success: true, message: "Status updated", order });
  }

  if (route.startsWith("courier/order/") && path[3] === "accept") {
    const orderId = parseInt(path[2], 10);
    const order = orders.find(o => o.id === orderId);
    if (order) {
      order.courier_id = user?.id || 3;
      order.courier_name = user?.display_name || 'Mahmoud Courier';
      order.status = 'courier_assigned';
      order.log.push({
        status: 'courier_assigned',
        note: `Order accepted by courier ${order.courier_name}`,
        created_at: new Date().toISOString()
      });
    }
    return NextResponse.json({ success: true, message: "Order accepted", order });
  }

  if (route === "courier/online") {
    courierState.is_online = body.is_online ?? true;
    if (body.vehicle_type) courierState.vehicle_type = body.vehicle_type;
    return NextResponse.json({ success: true, is_online: courierState.is_online, vehicle_type: courierState.vehicle_type });
  }

  if (route === "courier/set-vehicle") {
    courierState.vehicle_type = body.vehicle_type || 'bicycle';
    if (user && user.role === 'courier') {
      user.vehicle_type = courierState.vehicle_type;
    }
    return NextResponse.json({ success: true, vehicle_type: courierState.vehicle_type });
  }

  if (route === "courier/location") {
    courierState.latitude = body.latitude || courierState.latitude;
    courierState.longitude = body.longitude || courierState.longitude;
    // Also update any active orders assigned to this courier
    const activeOrder = orders.find(o => o.courier_id === (user?.id || 3) && !['delivered', 'cancelled'].includes(o.status));
    if (activeOrder) {
      activeOrder.courier_lat = courierState.latitude;
      activeOrder.courier_lng = courierState.longitude;
    }
    return NextResponse.json({ success: true, lat: courierState.latitude, lng: courierState.longitude });
  }

  // ────────────────────────────────────────────────────────
  // CHAT & SUPPORT
  // ────────────────────────────────────────────────────────
  if (route === "chat/send") {
    const { order_id, message } = body;
    if (!chatMessages[order_id]) chatMessages[order_id] = [];
    const newMsg = {
      id: chatMessages[order_id].length + 1,
      order_id,
      sender_id: user?.id || 2,
      sender_role: user?.role || 'customer',
      message,
      message_type: 'text',
      created_at: new Date().toISOString()
    };
    chatMessages[order_id].push(newMsg);
    return NextResponse.json({ success: true, message: newMsg });
  }

  // Fallback
  return NextResponse.json({ success: true, message: "Request processed" });
}
