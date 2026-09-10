#!/usr/bin/env python3
"""
Capture screenshots of Elyanivery apps using Playwright with proper rendering.
"""
import time, os
from playwright.sync_api import sync_playwright

FRAMES_DIR = '/home/z/my-project/download/video_frames'
BASE_URL = 'http://localhost:8888'
os.makedirs(FRAMES_DIR, exist_ok=True)

def capture():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--single-process'
        ])
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=1,
            color_scheme='dark',
            java_script_enabled=True,
        )
        
        apps = [
            ('customer_app', '/customer/', 'customer1', '1234'),
            ('courier_app', '/courier/', 'courier1', '1234'),
            ('admin_dashboard', '/admin/', 'admin', 'admin'),
            ('support_dashboard', '/support/', 'support1', '1234'),
            ('partner_dashboard', '/partner/', 'andyspizza', '1234'),
        ]
        
        for name, path, username, password in apps:
            print(f"Capturing {name}...")
            page = context.new_page()
            
            try:
                # Navigate
                resp = page.goto(f'{BASE_URL}{path}', wait_until='load', timeout=20000)
                print(f"  Page loaded: status={resp.status if resp else 'N/A'}")
                
                # Wait for content to render
                time.sleep(4)  # Wait for splash animation
                
                # Capture login screen
                page.screenshot(path=os.path.join(FRAMES_DIR, f'{name}_login.png'))
                print(f"  Saved login screenshot")
                
                # Try to login using JavaScript injection
                page.evaluate(f'''() => {{
                    const inputs = document.querySelectorAll('input');
                    console.log('Found ' + inputs.length + ' inputs');
                    for (let inp of inputs) {{
                        if (inp.type === 'text' || inp.type === 'username' || inp.placeholder?.toLowerCase().includes('user')) {{
                            inp.value = '{username}';
                            inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                        }}
                        if (inp.type === 'password') {{
                            inp.value = '{password}';
                            inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                        }}
                    }}
                    // Click login button
                    const btns = document.querySelectorAll('button');
                    for (let btn of btns) {{
                        if (btn.textContent?.includes('Sign') || btn.textContent?.includes('Login') || btn.classList.contains('login-btn')) {{
                            btn.click();
                            break;
                        }}
                    }}
                }}''')
                
                time.sleep(3)  # Wait for dashboard to load
                
                # Capture dashboard
                page.screenshot(path=os.path.join(FRAMES_DIR, f'{name}_dashboard.png'))
                print(f"  Saved dashboard screenshot")
                
                # Scroll and capture second view
                page.evaluate('window.scrollTo(0, 500)')
                time.sleep(0.5)
                page.screenshot(path=os.path.join(FRAMES_DIR, f'{name}_scrolled.png'))
                print(f"  Saved scrolled screenshot")
                
            except Exception as e:
                print(f"  Error: {e}")
            finally:
                page.close()
        
        browser.close()
        print("Done capturing screenshots!")

if __name__ == '__main__':
    capture()
