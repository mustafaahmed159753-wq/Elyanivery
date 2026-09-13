/**
 * Elyanivery Over-The-Air (OTA) Live Update Listener
 * Ensures any code update pushed to GitHub and deployed on Render
 * is automatically detected, downloaded, and applied to all APKs
 * and mobile/web viewers without requiring rebuilding APKs.
 */

(function () {
  'use strict';

  let currentVersion = localStorage.getItem('elyanivery_app_version') || '2.1.0';

  async function checkForLiveUpdate() {
    try {
      const res = await fetch('/api/version?t=' + Date.now(), {
        cache: 'no-store',
        headers: { 'Cache-Control': 'no-cache, no-store, must-revalidate' }
      });
      if (!res.ok) return;

      const data = await res.json();
      const remoteVersion = data.version;

      if (remoteVersion && remoteVersion !== currentVersion) {
        console.log(`[Elyanivery OTA] New update deployed on Render/GitHub: ${remoteVersion} (current: ${currentVersion})`);
        
        // Show non-intrusive live update banner
        showUpdateBanner(remoteVersion);

        // Update local version
        localStorage.setItem('elyanivery_app_version', remoteVersion);
        currentVersion = remoteVersion;

        // Clear cache and reload after 2.5 seconds
        setTimeout(() => {
          if ('caches' in window) {
            caches.keys().then((keys) => {
              Promise.all(keys.map(k => caches.delete(k))).then(() => {
                window.location.reload();
              });
            });
          } else {
            window.location.reload();
          }
        }, 2200);
      }
    } catch (e) {
      // Non-blocking offline check
    }
  }

  function showUpdateBanner(newVer) {
    if (document.getElementById('elyanivery-ota-toast')) return;

    const toast = document.createElement('div');
    toast.id = 'elyanivery-ota-toast';
    toast.style.cssText = `
      position: fixed;
      top: 16px;
      left: 50%;
      transform: translateX(-50%);
      z-index: 100000;
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      color: #ffffff;
      border: 1px solid #ea580c;
      padding: 10px 18px;
      border-radius: 9999px;
      font-size: 13px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 10px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.35);
      animation: elOtaSlideDown 0.35s cubic-bezier(0.16, 1, 0.3, 1) forwards;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    `;

    toast.innerHTML = `
      <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #10b981; box-shadow: 0 0 8px #10b981;"></span>
      <span>Live update detected! Applying latest version ${newVer}...</span>
    `;

    document.body.appendChild(toast);
  }

  // Check immediately on app launch
  setTimeout(checkForLiveUpdate, 3000);

  // Poll for updates every 45 seconds
  setInterval(checkForLiveUpdate, 45000);

  // Also listen for ServiceWorker controller changes
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      console.log('[Elyanivery OTA] Service worker controller changed — new deploy active.');
      window.location.reload();
    });
  }
})();
