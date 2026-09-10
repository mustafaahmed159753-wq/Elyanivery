// Elyanivery In-Memory Data Store & Shared Models

export interface User {
  id: number;
  username: string;
  display_name: string;
  role: 'admin' | 'customer' | 'courier' | 'partner' | 'support';
  email?: string;
  email_verified?: boolean;
  phone?: string;
  phone_verified?: boolean;
  vehicle_type?: 'walking' | 'bicycle' | 'scooter' | 'motorcycle' | 'car' | 'van';
  country?: string;
  country_code?: string;
  city?: string;
  avatar_url?: string;
  status: 'approved' | 'pending_approval' | 'rejected' | 'suspended';
  created_at: string;
}

export interface Restaurant {
  id: number;
  name: string;
  description: string;
  address: string;
  country: string;
  country_code: string;
  city: string;
  latitude: number;
  longitude: number;
  is_open: boolean;
  category: string;
  phone: string;
  image_url: string;
  rating: number;
  created_by?: number;
}

export interface MenuItem {
  id: number;
  restaurant_id: number;
  name: string;
  description: string;
  price: number;
  image_url: string;
  is_available: boolean;
  category: string;
}

export interface OrderItem {
  id: number;
  order_id: number;
  item_id: number;
  name: string;
  price: number;
  quantity: number;
}

export interface Order {
  id: number;
  order_number: string; // Distinctive Order Number (e.g. #ELY-8429)
  customer_id: number;
  restaurant_id: number;
  courier_id: number | null;
  courier_name?: string;
  courier_phone?: string;
  courier_vehicle?: string;
  courier_lat?: number;
  courier_lng?: number;
  status: 'pending' | 'accepted' | 'preparing' | 'ready_for_pickup' | 'courier_assigned' | 'order_picked_up' | 'heading_to_customer' | 'delivered' | 'cancelled';
  subtotal: number;
  delivery_fee: number;
  discount: number;
  total: number;
  delivery_address: string;
  delivery_lat: number;
  delivery_lng: number;
  restaurant_lat: number;
  restaurant_lng: number;
  created_at: string;
  updated_at?: string;
  estimated_prep_minutes?: number;
  restaurant_name: string;
  restaurant_address: string;
  customer_name: string;
  customer_phone: string;
  items: OrderItem[];
  log: { status: string; note: string; created_at: string }[];
}

export interface Ticket {
  id: number;
  user_id: number;
  order_id?: number;
  subject: string;
  status: 'open' | 'in_progress' | 'resolved' | 'closed';
  priority: 'low' | 'medium' | 'high';
  created_at: string;
  messages: { id: number; sender_role: string; message: string; created_at: string }[];
}

export interface Notification {
  id: number;
  user_id?: number;
  title: string;
  body: string;
  type: string;
  reference_id?: number;
  order_data?: Partial<Order>;
  is_read: boolean;
  created_at: string;
}

// Global OTP Store
export const otpStore: Record<string, { emailOtp?: string; phoneOtp?: string; expiresAt: number }> = {};

// Initial Users
export const users: User[] = [
  {
    id: 1,
    username: 'admin',
    display_name: 'Administrator',
    role: 'admin',
    email: 'admin@elyanivery.com',
    email_verified: true,
    phone: '+20 10 0000 0001',
    phone_verified: true,
    country: 'Egypt',
    country_code: 'EG',
    city: 'Cairo',
    avatar_url: '/static/logo.png',
    status: 'approved',
    created_at: new Date().toISOString()
  },
  {
    id: 2,
    username: 'customer1',
    display_name: 'Alexandru Popescu',
    role: 'customer',
    email: 'elyan123eg@gmail.com',
    email_verified: true,
    phone: '+20 10 1234 5678',
    phone_verified: true,
    country: 'Egypt',
    country_code: 'EG',
    city: 'Cairo',
    avatar_url: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150',
    status: 'approved',
    created_at: new Date().toISOString()
  },
  {
    id: 3,
    username: 'courier1',
    display_name: 'Mahmoud Courier',
    role: 'courier',
    email: 'mahmoud.courier@gmail.com',
    email_verified: true,
    phone: '+20 11 2345 6789',
    phone_verified: true,
    vehicle_type: 'bicycle',
    country: 'Egypt',
    country_code: 'EG',
    city: 'Cairo',
    avatar_url: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150',
    status: 'approved',
    created_at: new Date().toISOString()
  },
  {
    id: 4,
    username: 'support1',
    display_name: 'Elena Support Lead',
    role: 'support',
    email: 'support@elyanivery.com',
    email_verified: true,
    phone: '+20 10 9999 8888',
    phone_verified: true,
    country: 'Egypt',
    country_code: 'EG',
    avatar_url: 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150',
    status: 'approved',
    created_at: new Date().toISOString()
  },
  {
    id: 5,
    username: 'aboutarek',
    display_name: 'Abou Tarek Partner',
    role: 'partner',
    email: 'partner.aboutarek@gmail.com',
    email_verified: true,
    phone: '+20 2 2577 5935',
    country: 'Egypt',
    country_code: 'EG',
    city: 'Cairo',
    avatar_url: '/static/logo.png',
    status: 'approved',
    created_at: new Date().toISOString()
  },
  {
    id: 6,
    username: 'laplacinte',
    display_name: 'La Placinte Partner',
    role: 'partner',
    email: 'partner.laplacinte@gmail.com',
    email_verified: true,
    phone: '+373 22 123 456',
    country: 'Moldova',
    country_code: 'MD',
    city: 'Chisinau',
    avatar_url: '/static/uploads/logo_laplacinte.png',
    status: 'approved',
    created_at: new Date().toISOString()
  },
  {
    id: 7,
    username: 'tariq_courier',
    display_name: 'Tariq Hassan',
    role: 'courier',
    email: 'tariq.hassan@gmail.com',
    email_verified: true,
    phone: '+20 12 8765 4321',
    phone_verified: true,
    vehicle_type: 'motorcycle',
    country: 'Egypt',
    country_code: 'EG',
    city: 'Cairo',
    avatar_url: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150',
    status: 'pending_approval',
    created_at: new Date(Date.now() - 35 * 60 * 1000).toISOString()
  },
  {
    id: 8,
    username: 'omar_courier',
    display_name: 'Omar Nabil',
    role: 'courier',
    email: 'omar.nabil@gmail.com',
    email_verified: true,
    phone: '+20 15 3344 5566',
    phone_verified: true,
    vehicle_type: 'scooter',
    country: 'Egypt',
    country_code: 'EG',
    city: 'Cairo',
    avatar_url: 'https://images.unsplash.com/photo-1492562080023-ab3db95bfbce?w=150',
    status: 'pending_approval',
    created_at: new Date(Date.now() - 10 * 60 * 1000).toISOString()
  }
];

// Multi-Country Restaurants with Coordinates
export const restaurants: Restaurant[] = [
  // ─── EGYPT (EG) ───
  {
    id: 10,
    name: 'Koshary Abou Tarek',
    description: 'The world-famous authentic Egyptian Koshary with secret spicy Da’ah & fried onions',
    address: '16 Marouf St, Downtown, Cairo, Egypt',
    country: 'Egypt',
    country_code: 'EG',
    city: 'Cairo',
    latitude: 30.0511,
    longitude: 31.2384,
    is_open: true,
    category: 'restaurant',
    phone: '+20 2 2577 5935',
    image_url: 'https://images.unsplash.com/photo-1541518763669-27fef04b14ea?w=600&h=400&fit=crop',
    rating: 4.9,
    created_by: 5
  },
  {
    id: 11,
    name: 'Zooba Egyptian Street Food',
    description: 'Modern gourmet Egyptian street food: slow-cooked fava beans, hawawshi, and beet falafel',
    address: '16 26th of July St, Zamalek, Cairo, Egypt',
    country: 'Egypt',
    country_code: 'EG',
    city: 'Cairo',
    latitude: 30.0626,
    longitude: 31.2197,
    is_open: true,
    category: 'restaurant',
    phone: '+20 16088',
    image_url: 'https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=600&h=400&fit=crop',
    rating: 4.8
  },
  {
    id: 12,
    name: 'Kazaz Grill & Shawarma',
    description: 'Crispy Alexandrian liver sandwiches, sizzling grilled kofta, and spit-roasted shawarma',
    address: '38 Sabri Abou Alam St, Bab El Louk, Downtown, Cairo',
    country: 'Egypt',
    country_code: 'EG',
    city: 'Cairo',
    latitude: 30.0465,
    longitude: 31.2423,
    is_open: true,
    category: 'fast_food',
    phone: '+20 2 2396 0626',
    image_url: 'https://images.unsplash.com/photo-1529006557810-274b9b2fc783?w=600&h=400&fit=crop',
    rating: 4.7
  },
  {
    id: 13,
    name: 'Abou El Sid',
    description: 'Heritage Egyptian culinary dining: Royal Molokhia with rabbit, stuffed pigeon & clay tagines',
    address: '157 26th of July St, Zamalek, Cairo, Egypt',
    country: 'Egypt',
    country_code: 'EG',
    city: 'Cairo',
    latitude: 30.0601,
    longitude: 31.2185,
    is_open: true,
    category: 'restaurant',
    phone: '+20 2 2735 9640',
    image_url: 'https://images.unsplash.com/photo-1544025162-d76694265947?w=600&h=400&fit=crop',
    rating: 4.9
  },
  {
    id: 14,
    name: 'Buffalo Burger Cairo',
    description: '100% pure beef smashed patties, loaded cheddar bacon fries and signature craft sauces',
    address: 'Road 9, Maadi, Cairo, Egypt',
    country: 'Egypt',
    country_code: 'EG',
    city: 'Cairo',
    latitude: 29.9592,
    longitude: 31.2589,
    is_open: true,
    category: 'fast_food',
    phone: '+20 19914',
    image_url: 'https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=600&h=400&fit=crop',
    rating: 4.7
  },
  {
    id: 15,
    name: 'Cilantro Specialty Cafe',
    description: 'Artisan espresso blends, matcha lattes, fresh club sandwiches, and decadent cakes',
    address: 'Nasr City, Cairo, Egypt',
    country: 'Egypt',
    country_code: 'EG',
    city: 'Cairo',
    latitude: 30.0558,
    longitude: 31.3412,
    is_open: true,
    category: 'cafe',
    phone: '+20 2 2270 4111',
    image_url: 'https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=600&h=400&fit=crop',
    rating: 4.8
  },

  // ─── MOLDOVA (MD) ───
  {
    id: 1,
    name: 'La Placinte',
    description: 'Traditional Moldovan cuisine with modern twist & homemade placinte',
    address: 'Str. Stefan cel Mare 67, Chisinau',
    country: 'Moldova',
    country_code: 'MD',
    city: 'Chisinau',
    latitude: 47.0258,
    longitude: 28.8328,
    is_open: true,
    category: 'restaurant',
    phone: '+373 22 123 456',
    image_url: 'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=600&h=400&fit=crop',
    rating: 4.8,
    created_by: 6
  },
  {
    id: 2,
    name: 'Andys Pizza',
    description: 'Popular Italian-style pizza, pasta, fresh salads & desserts',
    address: 'Bulevardul Stefan cel Mare 32, Chisinau',
    country: 'Moldova',
    country_code: 'MD',
    city: 'Chisinau',
    latitude: 47.0312,
    longitude: 28.8407,
    is_open: true,
    category: 'restaurant',
    phone: '+373 22 345 678',
    image_url: 'https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=600&h=400&fit=crop',
    rating: 4.7
  },
  {
    id: 3,
    name: 'Carpe Diem',
    description: 'Fine dining & wine bar with exquisite European courses',
    address: 'Str. V. Pircalab 52, Chisinau',
    country: 'Moldova',
    country_code: 'MD',
    city: 'Chisinau',
    latitude: 47.0189,
    longitude: 28.8451,
    is_open: true,
    category: 'restaurant',
    phone: '+373 22 234 567',
    image_url: 'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=600&h=400&fit=crop',
    rating: 4.9
  },
  {
    id: 4,
    name: 'Shawarma King',
    description: 'Best authentic shawarma, crispy falafel & signature garlic sauces',
    address: 'Str. Ismail 49, Chisinau',
    country: 'Moldova',
    country_code: 'MD',
    city: 'Chisinau',
    latitude: 47.0198,
    longitude: 28.8379,
    is_open: true,
    category: 'fast_food',
    phone: '+373 22 890 123',
    image_url: 'https://images.unsplash.com/photo-1529006557810-274b9b2fc783?w=600&h=400&fit=crop',
    rating: 4.6
  },
  {
    id: 5,
    name: 'Burger Box',
    description: 'Artisan smashed gourmet burgers, loaded fries and craft shakes',
    address: 'Str. M. Eminescu 79, Chisinau',
    country: 'Moldova',
    country_code: 'MD',
    city: 'Chisinau',
    latitude: 47.0234,
    longitude: 28.8412,
    is_open: true,
    category: 'fast_food',
    phone: '+373 22 890 124',
    image_url: 'https://images.unsplash.com/photo-1561758033-d89a9ad46330?w=600&h=400&fit=crop',
    rating: 4.8
  },
  {
    id: 6,
    name: 'Sushi Master',
    description: 'Premium fresh Japanese sushi sets, sashimi and poke bowls',
    address: 'Bulevardul Decebal 8, Chisinau',
    country: 'Moldova',
    country_code: 'MD',
    city: 'Chisinau',
    latitude: 47.0100,
    longitude: 28.8450,
    is_open: true,
    category: 'restaurant',
    phone: '+373 22 012 800',
    image_url: 'https://images.unsplash.com/photo-1579871494447-9811cf80d66c?w=600&h=400&fit=crop',
    rating: 4.9
  },
  {
    id: 7,
    name: 'Tucano Coffee',
    description: 'Specialty coffee, matcha lattes, cheesecake & vegan desserts',
    address: 'Str. Alexandru cel Bun 56, Chisinau',
    country: 'Moldova',
    country_code: 'MD',
    city: 'Chisinau',
    latitude: 47.0225,
    longitude: 28.8521,
    is_open: true,
    category: 'cafe',
    phone: '+373 22 345 100',
    image_url: 'https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=600&h=400&fit=crop',
    rating: 4.9
  }
];

export const menuItems: MenuItem[] = [
  // Abou Tarek (id: 10)
  { id: 1001, restaurant_id: 10, name: 'Special Abou Tarek Koshary', description: 'Rice, macaroni, brown lentils, chickpeas, crispy caramelized onions with spicy tomato salsa & garlic Da’ah', price: 4.20, image_url: 'https://images.unsplash.com/photo-1541518763669-27fef04b14ea?w=400', is_available: true, category: 'Koshary' },
  { id: 1002, restaurant_id: 10, name: 'Royal Family Koshary Bowl', description: 'Extra large portion with double crunchy onions, golden lentils, and spicy chili oil pot', price: 6.50, image_url: 'https://images.unsplash.com/photo-1512058564366-18510be2db19?w=400', is_available: true, category: 'Koshary' },
  { id: 1003, restaurant_id: 10, name: 'Traditional Roz Bel Laban', description: 'Silky Egyptian rice pudding baked with cream and topped with crushed pistachios', price: 2.50, image_url: 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400', is_available: true, category: 'Desserts' },

  // Zooba (id: 11)
  { id: 1101, restaurant_id: 11, name: 'Beef Hawawshi Loaf', description: 'Spiced minced beef baked inside fresh baladi bread with garlic herbs and tahini dip', price: 5.50, image_url: 'https://images.unsplash.com/photo-1544025162-d76694265947?w=400', is_available: true, category: 'Hawawshi' },
  { id: 1102, restaurant_id: 11, name: 'Signature Beetroot Falafel Box', description: 'Crispy Egyptian fava bean falafel with beetroot puree, rocket, and roasted cumin yogurt', price: 4.80, image_url: 'https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=400', is_available: true, category: 'Falafel' },
  { id: 1103, restaurant_id: 11, name: 'Spicy Dukkah Shakshuka', description: 'Poached farm eggs in rich tomato, bell pepper, and Egyptian hazelnut dukkah spice', price: 5.20, image_url: 'https://images.unsplash.com/photo-1590301157890-4810ed352733?w=400', is_available: true, category: 'Mains' },

  // Kazaz (id: 12)
  { id: 1201, restaurant_id: 12, name: 'Alexandrian Liver Sandwich', description: 'Thinly sliced beef liver sautéed with chili peppers, garlic, and fresh lime in fino bread', price: 3.80, image_url: 'https://images.unsplash.com/photo-1529006557810-274b9b2fc783?w=400', is_available: true, category: 'Sandwiches' },
  { id: 1202, restaurant_id: 12, name: 'Charcoal Shish Tawook Platter', description: 'Marinated chicken breast skewers served with spiced yellow basmati rice and garlic toum', price: 7.90, image_url: 'https://images.unsplash.com/photo-1555939594-58d7cb561ad1?w=400', is_available: true, category: 'Grill' },

  // Abou El Sid (id: 13)
  { id: 1301, restaurant_id: 13, name: 'Royal Molokhia with Half Chicken', description: 'Traditional Egyptian green jute mallow stew with garlic coriander ta’shaa and aromatic rice', price: 9.50, image_url: 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=400', is_available: true, category: 'Tagines' },
  { id: 1302, restaurant_id: 13, name: 'Stuffed Pigeon (Hamam Mahshi)', description: 'Oven-roasted tender squab pigeon stuffed with seasoned cracked green wheat (Freekeh)', price: 11.00, image_url: 'https://images.unsplash.com/photo-1544025162-d76694265947?w=400', is_available: true, category: 'Heritage' },
  { id: 1303, restaurant_id: 13, name: 'Om Ali Palace Dessert', description: 'Puff pastry baked in sweetened hot milk, clotted cream, raisins, and toasted almonds', price: 4.50, image_url: 'https://images.unsplash.com/photo-1559339352-11d035aa65de?w=400', is_available: true, category: 'Desserts' },

  // Buffalo Burger (id: 14)
  { id: 1401, restaurant_id: 14, name: 'The Muscular Double Burger', description: 'Double black angus beef, smoked beef bacon, caramelized onion rings and melted cheddar', price: 8.90, image_url: 'https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=400', is_available: true, category: 'Burgers' },
  { id: 1402, restaurant_id: 14, name: 'Buffalo Curly Cheesy Fries', description: 'Spiral seasoned fries smothered in hot cheddar cheese and jalapeno relish', price: 3.90, image_url: 'https://images.unsplash.com/photo-1573080496219-bb080dd4f877?w=400', is_available: true, category: 'Sides' },

  // Cilantro (id: 15)
  { id: 1501, restaurant_id: 15, name: 'Iced Spanish Latte', description: 'Double shot espresso shaken with sweetened condensed milk and cold froth', price: 3.80, image_url: 'https://images.unsplash.com/photo-1517701550927-30cf4ba1dba5?w=400', is_available: true, category: 'Coffee' },
  { id: 1502, restaurant_id: 15, name: 'Smoked Turkey & Emmental Club', description: 'Triple-decker toasted brown bread with smoked turkey, Swiss cheese, and honey mustard', price: 5.20, image_url: 'https://images.unsplash.com/photo-1528735602780-2552fd46c7af?w=400', is_available: true, category: 'Bakery' },

  // La Placinte (id: 1)
  { id: 101, restaurant_id: 1, name: 'Placinta cu Branza si Marar', description: 'Crispy traditional layered pastry with sheep cheese and fresh dill', price: 4.50, image_url: 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400', is_available: true, category: 'Placinte' },
  { id: 102, restaurant_id: 1, name: 'Placinta cu Cartofi si Ceapa', description: 'Savory pastry filled with spiced potato purée and caramelised onion', price: 4.00, image_url: 'https://images.unsplash.com/photo-1555507036-ab1f4038024a?w=400', is_available: true, category: 'Placinte' },
  { id: 103, restaurant_id: 1, name: 'Sarmale in Foi de Vita', description: 'Tender cabbage and grape leaf rolls with seasoned pork and sour cream', price: 7.80, image_url: 'https://images.unsplash.com/photo-1544025162-d76694265947?w=400', is_available: true, category: 'Mains' },
  { id: 104, restaurant_id: 1, name: 'Zeama Moldoveneasca cu Taitei', description: 'Free-range chicken soup with homemade egg noodles and lovage', price: 5.20, image_url: 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=400', is_available: true, category: 'Soups' },

  // Andy's Pizza (id: 2)
  { id: 201, restaurant_id: 2, name: 'Pizza Diavola', description: 'Tomato sauce, mozzarella, spicy Italian salami, jalapeño & oregano', price: 8.50, image_url: 'https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=400', is_available: true, category: 'Pizza' },
  { id: 202, restaurant_id: 2, name: 'Pizza Quattro Formaggi', description: 'Mozzarella, gorgonzola, parmesan, and creamy fontina cheese', price: 9.20, image_url: 'https://images.unsplash.com/photo-1513104890138-7c749659a591?w=400', is_available: true, category: 'Pizza' }
];

export const orders: Order[] = [
  {
    id: 1001,
    order_number: '#ELY-8429',
    customer_id: 2,
    restaurant_id: 10,
    courier_id: 3,
    courier_name: 'Mahmoud Courier',
    courier_phone: '+20 11 2345 6789',
    courier_vehicle: 'bicycle',
    status: 'heading_to_customer',
    subtotal: 10.70,
    delivery_fee: 2.00,
    discount: 0,
    total: 12.70,
    delivery_address: 'Tahrir Square 5, Downtown, Cairo',
    delivery_lat: 30.0444,
    delivery_lng: 31.2357,
    restaurant_lat: 30.0511,
    restaurant_lng: 31.2384,
    courier_lat: 30.0478,
    courier_lng: 31.2369,
    created_at: new Date(Date.now() - 22 * 60 * 1000).toISOString(),
    restaurant_name: 'Koshary Abou Tarek',
    restaurant_address: '16 Marouf St, Downtown, Cairo',
    customer_name: 'Alexandru Popescu',
    customer_phone: '+20 10 1234 5678',
    estimated_prep_minutes: 15,
    items: [
      { id: 1, order_id: 1001, item_id: 1001, name: 'Special Abou Tarek Koshary', price: 4.20, quantity: 2 },
      { id: 2, order_id: 1001, item_id: 1003, name: 'Traditional Roz Bel Laban', price: 2.50, quantity: 1 }
    ],
    log: [
      { status: 'pending', note: 'Order placed by customer with distinctive #ELY-8429', created_at: new Date(Date.now() - 22 * 60 * 1000).toISOString() },
      { status: 'accepted', note: 'Accepted by Koshary Abou Tarek kitchen', created_at: new Date(Date.now() - 19 * 60 * 1000).toISOString() },
      { status: 'courier_assigned', note: 'Courier Mahmoud Courier chosen & assigned', created_at: new Date(Date.now() - 15 * 60 * 1000).toISOString() },
      { status: 'order_picked_up', note: 'Courier received order parcel', created_at: new Date(Date.now() - 7 * 60 * 1000).toISOString() },
      { status: 'heading_to_customer', note: 'Courier en route to customer on Google Maps', created_at: new Date(Date.now() - 3 * 60 * 1000).toISOString() }
    ]
  },
  {
    id: 1002,
    order_number: '#ELY-9102',
    customer_id: 2,
    restaurant_id: 11,
    courier_id: null,
    status: 'pending',
    subtotal: 15.50,
    delivery_fee: 2.00,
    discount: 1.50,
    total: 16.00,
    delivery_address: '12 Zamalek Island St, Cairo',
    delivery_lat: 30.0580,
    delivery_lng: 31.2210,
    restaurant_lat: 30.0626,
    restaurant_lng: 31.2197,
    created_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
    restaurant_name: 'Zooba Egyptian Street Food',
    restaurant_address: '16 26th of July St, Zamalek, Cairo',
    customer_name: 'Alexandru Popescu',
    customer_phone: '+20 10 1234 5678',
    estimated_prep_minutes: 20,
    items: [
      { id: 3, order_id: 1002, item_id: 1101, name: 'Beef Hawawshi Loaf', price: 5.50, quantity: 2 },
      { id: 4, order_id: 1002, item_id: 1102, name: 'Signature Beetroot Falafel Box', price: 4.80, quantity: 1 }
    ],
    log: [
      { status: 'pending', note: 'Order placed by customer', created_at: new Date(Date.now() - 5 * 60 * 1000).toISOString() }
    ]
  }
];

export const tickets: Ticket[] = [
  {
    id: 501,
    user_id: 2,
    order_id: 1001,
    subject: 'Request extra spicy da\'ah sauce for #ELY-8429',
    status: 'open',
    priority: 'medium',
    created_at: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
    messages: [
      { id: 1, sender_role: 'customer', message: 'Hello! Please tell the courier to include extra spicy sauce for #ELY-8429.', created_at: new Date(Date.now() - 15 * 60 * 1000).toISOString() },
      { id: 2, sender_role: 'support', message: 'Confirmed! We notified courier Mahmoud.', created_at: new Date(Date.now() - 10 * 60 * 1000).toISOString() }
    ]
  }
];

export const notifications: Notification[] = [
  {
    id: 1,
    user_id: 3,
    title: '🚨 New Order Assigned: #ELY-8429',
    body: 'You have been chosen for delivery #ELY-8429 from Koshary Abou Tarek to Tahrir Square (Total: €12.70)',
    type: 'order_assigned',
    reference_id: 1001,
    is_read: false,
    created_at: new Date(Date.now() - 15 * 60 * 1000).toISOString()
  },
  {
    id: 2,
    user_id: 2,
    title: 'Order En Route: #ELY-8429',
    body: 'Courier Mahmoud is heading to your address on Google Maps.',
    type: 'order_update',
    reference_id: 1001,
    is_read: false,
    created_at: new Date(Date.now() - 3 * 60 * 1000).toISOString()
  }
];

export const broadcasts = [
  {
    id: 1,
    title: 'Welcome to Elyanivery!',
    message: 'Experience fast doorstep delivery powered by Google Maps and verified OTP authentication.',
    type: 'info',
    active: true,
    created_at: new Date().toISOString()
  }
];

export const courierState = {
  is_online: true,
  vehicle_type: 'bicycle',
  latitude: 30.0478,
  longitude: 31.2369,
  balance: 48.50,
  today_deliveries: 6,
  today_earnings: 32.00,
  rating: 4.96
};
