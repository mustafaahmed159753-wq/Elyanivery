/**
 * Elyanivery Universal Notification & Audio Sound Engine
 * Provides:
 * 1. Mobile Phone Notification Panel Alerts (Service Worker & Notification API)
 * 2. High-Fidelity Synthesized Web Audio Notification Sounds (Works on all phones without external audio file failures)
 * 3. Haptic Phone Vibration Feedback
 * 4. Step-by-Step Notification Triggers for Customer, Courier, Partner, Support, & Admin
 */

(function(window) {
  'use strict';

  let audioCtx = null;
  let audioUnlocked = false;

  function getAudioContext() {
    if (!audioCtx) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass) {
        audioCtx = new AudioContextClass();
      }
    }
    if (audioCtx && audioCtx.state === 'suspended') {
      audioCtx.resume().catch(() => {});
    }
    return audioCtx;
  }

  // Unlock audio on first touch/click (browser requirement on mobile iOS & Android)
  function unlockAudio() {
    if (audioUnlocked) return;
    const ctx = getAudioContext();
    if (ctx) {
      if (ctx.state === 'suspended') {
        ctx.resume().then(() => {
          audioUnlocked = true;
        }).catch(() => {});
      } else {
        audioUnlocked = true;
      }
    }
  }

  ['click', 'touchstart', 'touchend', 'keydown'].forEach(evt => {
    window.addEventListener(evt, unlockAudio, { once: false, passive: true });
  });

  const SoundEngine = {
    playChime(notes, tempo = 0.12, type = 'sine') {
      try {
        const ctx = getAudioContext();
        if (!ctx) return;
        const now = ctx.currentTime;

        notes.forEach((item, index) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = item.type || type;
          osc.frequency.setValueAtTime(item.freq, now + (index * tempo));

          const startTime = now + (index * tempo);
          const dur = item.dur || 0.18;

          gain.gain.setValueAtTime(0.001, startTime);
          gain.gain.exponentialRampToValueAtTime(item.gain || 0.35, startTime + 0.02);
          gain.gain.exponentialRampToValueAtTime(0.0001, startTime + dur);

          osc.connect(gain);
          gain.connect(ctx.destination);

          osc.start(startTime);
          osc.stop(startTime + dur + 0.05);
        });
      } catch (e) {
        console.warn('Notification audio playback error:', e);
      }
    },

    orderPlaced() {
      // Ascending joyful chime (C5 -> E5 -> G5 -> C6)
      this.playChime([
        { freq: 523.25, dur: 0.14, gain: 0.3 },
        { freq: 659.25, dur: 0.14, gain: 0.35 },
        { freq: 783.99, dur: 0.16, gain: 0.4 },
        { freq: 1046.50, dur: 0.35, gain: 0.45 }
      ], 0.10);
    },

    orderStepUpdate() {
      // Clean confirmation chime (F5 -> A5 -> C6)
      this.playChime([
        { freq: 698.46, dur: 0.15, gain: 0.35 },
        { freq: 880.00, dur: 0.18, gain: 0.4 },
        { freq: 1046.50, dur: 0.28, gain: 0.45 }
      ], 0.11);
    },

    courierAlert() {
      // Energetic alert chime (G5 -> C6 -> E6 -> G6)
      this.playChime([
        { freq: 783.99, dur: 0.12, gain: 0.4 },
        { freq: 1046.50, dur: 0.12, gain: 0.45 },
        { freq: 1318.51, dur: 0.20, gain: 0.5 }
      ], 0.09, 'triangle');
    },

    cooking() {
      // Warm kitchen bell chime
      this.playChime([
        { freq: 587.33, dur: 0.18, gain: 0.3 },
        { freq: 880.00, dur: 0.28, gain: 0.38 }
      ], 0.14);
    },

    delivered() {
      // Triumphant delivery fanfare
      this.playChime([
        { freq: 523.25, dur: 0.12, gain: 0.35 },
        { freq: 659.25, dur: 0.12, gain: 0.35 },
        { freq: 783.99, dur: 0.14, gain: 0.4 },
        { freq: 1046.50, dur: 0.45, gain: 0.5 }
      ], 0.10);
    },

    message() {
      // Gentle bubble message pop
      this.playChime([
        { freq: 880.00, dur: 0.08, gain: 0.3 },
        { freq: 1174.66, dur: 0.18, gain: 0.35 }
      ], 0.07);
    },

    warning() {
      // Attention warning
      this.playChime([
        { freq: 440.00, dur: 0.15, gain: 0.4, type: 'sawtooth' },
        { freq: 349.23, dur: 0.25, gain: 0.45, type: 'sawtooth' }
      ], 0.15);
    }
  };

  const ElyaniveryNotify = {
    permission: 'default',

    init() {
      if ('Notification' in window) {
        this.permission = Notification.permission;
      }
      this.injectPermissionPrompt();
    },

    async requestPermission() {
      unlockAudio();
      if ('Notification' in window) {
        try {
          const perm = await Notification.requestPermission();
          this.permission = perm;
          this.updatePromptUI();
          if (perm === 'granted') {
            SoundEngine.orderPlaced();
            this.sendSystemNotification('Notifications & Sound Active 🔔', {
              body: 'You will receive real-time order alerts and phone panel notifications on every step.',
              tag: 'welcome-notification'
            });
          }
          return perm;
        } catch (e) {
          console.warn('Error requesting notification permission:', e);
        }
      }
      return 'denied';
    },

    // Send a real phone notification to the Android / Mobile Notification Panel
    async sendSystemNotification(title, options = {}) {
      const defaultOptions = {
        icon: '/splash-logo.png',
        badge: '/icons/icon-72x72.png',
        vibrate: [200, 100, 200, 100, 200],
        tag: options.tag || 'elyanivery-status',
        renotify: true,
        requireInteraction: false,
        data: options.data || { url: window.location.pathname },
        ...options
      };

      // Vibrate mobile phone if supported
      if ('vibrate' in navigator) {
        try {
          navigator.vibrate([200, 100, 200]);
        } catch (e) {}
      }

      // Check permission
      if (!('Notification' in window) || Notification.permission !== 'granted') {
        return false;
      }

      // 1. Try ServiceWorker Registration (Android Notification Panel standard)
      if ('serviceWorker' in navigator) {
        try {
          const reg = await navigator.serviceWorker.ready;
          if (reg && reg.showNotification) {
            await reg.showNotification(title, defaultOptions);
            return true;
          }
        } catch (e) {
          console.warn('ServiceWorker showNotification failed, trying fallback:', e);
        }
      }

      // 2. Direct Notification Fallback
      try {
        new Notification(title, defaultOptions);
        return true;
      } catch (e) {
        console.warn('Notification API fallback error:', e);
      }

      return false;
    },

    /**
     * Complete Order Lifecycle Notification Trigger
     * Plays customized synthesized sound + displays mobile panel notification + vibrates phone
     */
    notifyStep(stepName, detailText, appPortal = 'customer') {
      unlockAudio();

      let title = 'Elyanivery';
      let soundFn = 'orderStepUpdate';

      switch (stepName) {
        case 'order_placed':
          title = '📦 Order Placed Successfully!';
          soundFn = 'orderPlaced';
          break;
        case 'order_confirmed':
        case 'accepted':
          title = '👨‍🍳 Restaurant Accepted Order';
          soundFn = 'cooking';
          break;
        case 'preparing':
        case 'cooking':
          title = '🍳 Order is Being Prepared';
          soundFn = 'cooking';
          break;
        case 'ready_for_pickup':
          title = '🥡 Order Ready for Pickup';
          soundFn = 'orderStepUpdate';
          break;
        case 'courier_assigned':
        case 'driver_assigned':
          title = '🛵 Courier Assigned to Order';
          soundFn = 'courierAlert';
          break;
        case 'picked_up':
        case 'on_the_way':
          title = '🚀 Courier On The Way to You!';
          soundFn = 'courierAlert';
          break;
        case 'delivered':
        case 'completed':
          title = '🎉 Order Delivered! Enjoy your meal';
          soundFn = 'delivered';
          break;
        case 'new_order_alert':
          title = '🚨 New Incoming Order Received!';
          soundFn = 'orderPlaced';
          break;
        case 'new_task_alert':
          title = '🛵 New Delivery Task Available!';
          soundFn = 'courierAlert';
          break;
        case 'message':
        case 'chat':
          title = '💬 New Message';
          soundFn = 'message';
          break;
        default:
          title = `🔔 Elyanivery: ${stepName.replace(/_/g, ' ')}`;
          soundFn = 'orderStepUpdate';
      }

      // 1. Play sound
      if (SoundEngine[soundFn]) {
        SoundEngine[soundFn]();
      }

      // 2. Send System Notification to Phone Panel
      this.sendSystemNotification(title, {
        body: detailText || 'Tap to view live order tracking in Elyanivery.',
        tag: `order-${stepName}-${Date.now()}`
      });

      // 3. Trigger In-App visual notification if app has toast function
      if (typeof window.toast === 'function') {
        window.toast(`${title}: ${detailText || ''}`, 'info');
      } else if (typeof window.showToast === 'function') {
        window.showToast(`${title} - ${detailText || ''}`);
      }
    },

    // Floating non-intrusive prompt allowing user to grant sound and panel alerts
    injectPermissionPrompt() {
      if (!('Notification' in window) || Notification.permission === 'granted') {
        return;
      }
      if (document.getElementById('ely-perm-bar')) return;

      const bar = document.createElement('div');
      bar.id = 'ely-perm-bar';
      bar.style.cssText = `
        position: fixed;
        bottom: 80px;
        left: 50%;
        transform: translateX(-50%);
        max-width: 440px;
        width: 90%;
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border: 1px solid rgba(255, 107, 0, 0.4);
        box-shadow: 0 10px 30px rgba(0,0,0,0.5), 0 0 20px rgba(255,107,0,0.25);
        color: #ffffff;
        padding: 12px 16px;
        border-radius: 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        z-index: 9998;
        font-family: inherit;
        animation: slideUpPrompt 0.5s cubic-bezier(0.16, 1, 0.3, 1);
      `;

      bar.innerHTML = `
        <div style="display:flex;align-items:center;gap:10px;">
          <div style="width:36px;height:36px;border-radius:10px;background:rgba(255,107,0,0.2);display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;">
            🔔
          </div>
          <div>
            <div style="font-size:13px;font-weight:700;color:#fff;line-height:1.2;">Enable Live Alerts</div>
            <div style="font-size:11px;color:#94a3b8;line-height:1.2;">Phone panel & sound on every step</div>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:6px;flex-shrink:0;">
          <button id="ely-perm-btn" style="background:#FF6B00;color:#fff;border:none;border-radius:8px;padding:7px 12px;font-size:12px;font-weight:700;cursor:pointer;">
            Enable
          </button>
          <button id="ely-perm-close" style="background:none;border:none;color:#64748b;font-size:16px;cursor:pointer;padding:4px;">
            ✕
          </button>
        </div>
      `;

      const style = document.createElement('style');
      style.textContent = `
        @keyframes slideUpPrompt {
          from { opacity: 0; transform: translate(-50%, 20px); }
          to { opacity: 1; transform: translate(-50%, 0); }
        }
      `;
      document.head.appendChild(style);
      document.body.appendChild(bar);

      document.getElementById('ely-perm-btn')?.addEventListener('click', async () => {
        await ElyaniveryNotify.requestPermission();
        bar.remove();
      });

      document.getElementById('ely-perm-close')?.addEventListener('click', () => {
        bar.remove();
      });
    },

    updatePromptUI() {
      const bar = document.getElementById('ely-perm-bar');
      if (bar) bar.remove();
    }
  };

  window.ElyaniveryNotify = ElyaniveryNotify;
  window.ElyaniverySound = SoundEngine;

  // Auto initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => ElyaniveryNotify.init());
  } else {
    ElyaniveryNotify.init();
  }

})(window);
