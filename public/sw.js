// Elyanivery Service Worker for PWA and Offline Support
const CACHE_NAME = 'elyanivery-v1.2.0';
const STATIC_ASSETS = [
  '/',
  '/customer',
  '/courier',
  '/partner',
  '/admin',
  '/support',
  '/manifest.json',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png',
  '/icons/maskable-icon-192x192.png',
  '/icons/maskable-icon-512x512.png',
  '/apple-touch-icon.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('PWA Precache non-blocking error:', err);
      });
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // Only handle GET requests and skip API requests from hard caching
  if (event.request.method !== 'GET' || event.request.url.includes('/api/')) {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const responseClone = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone);
          });
        }
        return networkResponse;
      })
      .catch(() => {
        return caches.match(event.request).then((cachedResponse) => {
          if (cachedResponse) {
            return cachedResponse;
          }
          if (event.request.mode === 'navigate') {
            return caches.match('/customer') || caches.match('/');
          }
        });
      })
  );
});

// ═══════════════════════════════════════════════════════
//  PHONE NOTIFICATION PANEL & PUSH EVENT HANDLERS
// ═══════════════════════════════════════════════════════

// Handle incoming Web Push notifications
self.addEventListener('push', (event) => {
  let data = {
    title: 'Elyanivery Update',
    body: 'You have a new update on Elyanivery',
    icon: '/splash-logo.png',
    badge: '/icons/icon-72x72.png',
    data: { url: '/customer' }
  };
  try {
    if (event.data) {
      data = { ...data, ...event.data.json() };
    }
  } catch (e) {
    if (event.data) data.body = event.data.text();
  }

  const options = {
    body: data.body,
    icon: data.icon || '/splash-logo.png',
    badge: data.badge || '/icons/icon-72x72.png',
    vibrate: [200, 100, 200, 100, 200],
    tag: data.tag || 'elyanivery-order-step',
    renotify: true,
    requireInteraction: false,
    data: data.data || { url: '/' }
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Handle clicks on Android Notification Panel
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) ? event.notification.data.url : '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          if (targetUrl && client.url !== self.location.origin + targetUrl) {
            client.navigate(targetUrl);
          }
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});

// Allow client pages to trigger background/panel notifications via Service Worker
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SHOW_NOTIFICATION') {
    const { title, options } = event.data;
    self.registration.showNotification(title, {
      icon: '/splash-logo.png',
      badge: '/icons/icon-72x72.png',
      vibrate: [200, 100, 200, 100, 200],
      tag: 'elyanivery-live-update',
      renotify: true,
      ...options
    });
  }
});
