# Splash Screen Upgrade Task

## Task ID: splash-upgrade
## Agent: coder

## Summary
Upgraded splash screens across all 5 Elyanivery delivery apps (Customer, Courier, Admin, Partner, Support) with:

1. **3D Letter Animation**: Each letter of "Elyanivery" now appears FROM NOTHING - starting as invisible/transparent, scaling up from 0 with a 3D rotateY effect, and settling next to each other in the center of the screen. Uses `perspective: 600px` and `cubic-bezier(.16,1,.3,1)` easing.

2. **App-Specific Surrounding Items**:
   - Customer: 🍕🥫🍦🍦🍔🌮🥤 (food items floating/bobbing around the word)
   - Courier: 🚲🚗🛵🚚 (vehicles driving across from sides with driveRight/driveLeft animations)
   - Admin: 🍕🍔🍦🥫🌮🥤 (food variety items floating around)
   - Partner: 🍕🍳🥘🍽️🧑‍🍳 (cooking/restaurant items floating around)
   - Support: 💬🎧📞🎯 (support/communication items floating around)

3. **Circular Progress Bar**: Consistent across all apps - 64x64px SVG circle with animated stroke-dashoffset from 0% to 100% over 2.2 seconds, with percentage text in the center.

4. **Common Design**: 
   - Same gradient background: `linear-gradient(135deg,#FF6B00 0%,#CC5500 30%,#1a1a2e 65%,#0f3460 100%)`
   - Animated gradient with `splashGradient` and `splashShift` keyframes
   - Fade-out with `scale(1.05)` transition after 2.5s
   - Subtitle text below progress bar per app

## Files Modified
- `/home/z/my-project/download/static/customer/index.html` - CSS + HTML + JS
- `/home/z/my-project/download/static/courier/index.html` - CSS + HTML + JS  
- `/home/z/my-project/download/static/admin/index.html` - CSS + HTML + JS
- `/home/z/my-project/download/static/partner/index.html` - CSS + HTML + JS
- `/home/z/my-project/download/static/support/index.html` - CSS + HTML + JS

## Key CSS Classes Created/Updated
- `.splash-screen` - container
- `.splash-bg` - gradient background with animations
- `.splash-content` - centered content
- `.splash-letters` - letter container with perspective
- `.splash-letter` - individual letter with 3D animation
- `.splash-surround` - surrounding items container (absolute positioned)
- `.splash-item` - individual floating item with itemFloat animation
- `.splash-item.drive-right` / `.splash-item.drive-left` - courier driving animations
- `.splash-progress` - circular SVG progress bar
- `.splash-subtitle` - subtitle text with fadeInUp animation

## Preserved
- All initApp/init() calls after splash fade-out
- Theme variables and other app styles untouched
- All existing app functionality preserved
