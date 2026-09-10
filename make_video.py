#!/usr/bin/env python3
"""
Capture screenshots and create demo video for Elyanivery.
Uses a built-in HTTP server and Playwright for screenshots.
"""
import time, os, threading, http.server, socketserver, subprocess
from PIL import Image, ImageDraw, ImageFont

FRAMES_DIR = '/home/z/my-project/download/video_frames'
OUTPUT_DIR = '/home/z/my-project/download'
PORT = 9999

os.makedirs(FRAMES_DIR, exist_ok=True)

# ═══ Start a simple HTTP server ═══
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory='/home/z/my-project/static', **kwargs)
    def log_message(self, format, *args):
        pass

httpd = socketserver.TCPServer(('0.0.0.0', PORT), QuietHandler)
server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
server_thread.start()
print(f"Static server running on port {PORT}")

# Wait for server to be ready
time.sleep(1)

# ═══ Create title/intro frames ═══
def make_title_frame(title, subtitle='', sub2='', color='#ff6b35', filename='frame.png'):
    w, h = 1920, 1080
    img = Image.new('RGB', (w, h), '#0f1128')
    draw = ImageDraw.Draw(img)
    try:
        fl = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 72)
        fm = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 36)
        fs = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 24)
    except:
        fl = fm = fs = ImageFont.load_default()
    
    draw.text((w//2, h//3), title, fill=color, font=fl, anchor='mm')
    if subtitle:
        draw.text((w//2, h//3+80), subtitle, fill='#b0b3d0', font=fm, anchor='mm')
    if sub2:
        draw.text((w//2, h//3+140), sub2, fill='#6c6f9a', font=fs, anchor='mm')
    
    img.save(os.path.join(FRAMES_DIR, filename))
    return filename

# Create intro frames
print("Creating title frames...")
make_title_frame("ELYANIVERY", "Delivery Platform", "5 Integrated Web Applications | Chisinau, Moldova", filename='title_intro.png')

# Architecture frame
w, h = 1920, 1080
arch_img = Image.new('RGB', (w, h), '#0f1128')
draw = ImageDraw.Draw(arch_img)
try:
    ft = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 42)
    fm = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 22)
    fs = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16)
except:
    ft = fm = fs = ImageFont.load_default()

draw.text((w//2, 50), "Platform Architecture & Integration Flow", fill='#ff6b35', font=ft, anchor='mt')

apps_box = [
    ("Customer", "Browse & Order", '#ff6b35', 60, 140),
    ("Courier", "Deliver & Earn", '#5dade2', 410, 140),
    ("Partner", "Manage Menu", '#1abc9c', 760, 140),
    ("Admin", "Full Control", '#9b59b6', 1110, 140),
    ("Support", "Help & Resolve", '#f39c12', 1460, 140),
]
for name, desc, color, x, y in apps_box:
    draw.rounded_rectangle([x, y, x+320, y+140], radius=12, fill='#1a1d42', outline=color, width=3)
    draw.text((x+160, y+50), name, fill=color, font=fm, anchor='mm')
    draw.text((x+160, y+90), desc, fill='#b0b3d0', font=fs, anchor='mm')

# Backend box
draw.rounded_rectangle([300, 340, 1620, 420], radius=12, fill='#22264f', outline='#e8e8f0', width=2)
draw.text((960, 380), "Python HTTP Server + PostgreSQL | JWT Auth | Real-time APIs", fill='#e8e8f0', font=fm, anchor='mm')

# Integration flow
draw.text((w//2, 470), "Order Flow", fill='#ff6b35', font=ft, anchor='mt')
flow = [
    "1. Customer browses restaurants & places order",
    "2. Partner receives order in their dashboard",
    "3. Backend auto-assigns nearest available courier",
    "4. Courier accepts, picks up & delivers order",
    "5. Support monitors all orders & assists via chat",
    "6. Admin manages users, broadcasts & platform",
]
for i, step in enumerate(flow):
    colors = ['#ff6b35', '#1abc9c', '#5dade2', '#5dade2', '#f39c12', '#9b59b6']
    y = 540 + i * 55
    draw.rounded_rectangle([200, y, 1720, y+45], radius=8, fill='#1a1d42', outline=colors[i], width=2)
    draw.text((960, y+22), step, fill=colors[i], font=fm, anchor='mm')

# Features
draw.text((w//2, 900), "Key Features", fill='#ff6b35', font=ft, anchor='mt')
features = "8 Themes | 3 Languages (EN/RU/RO) | 36 Restaurants | 547 Items | Loyalty Points | Voice Calls | In-App Chat | Promo Codes"
draw.text((w//2, 950), features, fill='#6c6f9a', font=fs, anchor='mt')
draw.text((w//2, 980), "Deliver Anything Service | Courier Vehicle Management | Broadcast System | Maintenance Mode | Ticket System | Refund Processing", fill='#6c6f9a', font=fs, anchor='mt')

arch_img.save(os.path.join(FRAMES_DIR, 'architecture.png'))

# Closing frame
make_title_frame("ELYANIVERY", "Built with Python + PostgreSQL", 
                 "Deployed on Railway | 5 SPAs | 8 Themes | 3 Languages | 36 Restaurants | 547 Items",
                 filename='closing.png')

# Section frames for each app
sections = [
    ("Customer App", "Browse restaurants, place orders, track deliveries, chat with courier", '#ff6b35'),
    ("Courier App", "Accept deliveries, navigate routes, track earnings, manage vehicle", '#5dade2'),
    ("Admin Dashboard", "Manage users, view statistics, broadcast messages, approve couriers", '#9b59b6'),
    ("Support Dashboard", "Handle tickets, process refunds, chat with customers, manage orders", '#f39c12'),
    ("Partner Dashboard", "Manage menu items, accept orders, track stats, toggle availability", '#1abc9c'),
]
for name, desc, color in sections:
    safe = name.lower().replace(' ', '_')
    make_title_frame(name, desc, color=color, filename=f'section_{safe}.png')

# ═══ Capture screenshots ═══
print("Capturing screenshots with Playwright...")
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
    )
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        device_scale_factor=1,
        color_scheme='dark',
    )
    
    app_configs = [
        ('customer_app', '/customer/', 'customer1', '1234'),
        ('courier_app', '/courier/', 'courier1', '1234'),
        ('admin_dashboard', '/admin/', 'admin', 'admin'),
        ('support_dashboard', '/support/', 'support1', '1234'),
        ('partner_dashboard', '/partner/', 'andyspizza', '1234'),
    ]
    
    for name, path, username, password in app_configs:
        print(f"  {name}...")
        page = context.new_page()
        try:
            page.goto(f'http://127.0.0.1:{PORT}{path}', wait_until='domcontentloaded', timeout=20000)
            time.sleep(4)
            page.screenshot(path=os.path.join(FRAMES_DIR, f'{name}_login.png'))
            
            # Login
            page.evaluate(f'''() => {{
                const inputs = document.querySelectorAll('input');
                for(let inp of inputs) {{
                    if(inp.type==='text'||inp.type==='username'||inp.placeholder?.toLowerCase().includes('user'))
                        {{inp.value='{username}';inp.dispatchEvent(new Event('input',{{bubbles:true}}));}}
                    if(inp.type==='password')
                        {{inp.value='{password}';inp.dispatchEvent(new Event('input',{{bubbles:true}}));}}
                }}
                const btns=document.querySelectorAll('button');
                for(let btn of btns) {{
                    if(btn.textContent?.includes('Sign')||btn.textContent?.includes('Login')||btn.classList.contains('login-btn'))
                        {{btn.click();break;}}
                }}
            }}''')
            time.sleep(3)
            page.screenshot(path=os.path.join(FRAMES_DIR, f'{name}_dashboard.png'))
            
            # Scroll
            page.evaluate('window.scrollTo(0, 500)')
            time.sleep(0.5)
            page.screenshot(path=os.path.join(FRAMES_DIR, f'{name}_scrolled.png'))
            
            print(f"    OK")
        except Exception as e:
            print(f"    Error: {e}")
        page.close()
    
    browser.close()

# Shutdown server
httpd.shutdown()

# ═══ Build the video ═══
print("Building video...")

# Frame sequence with durations
frame_sequence = [
    ('title_intro.png', 5),
    ('architecture.png', 7),
    
    ('section_customer_app.png', 3),
    ('customer_app_login.png', 3),
    ('customer_app_dashboard.png', 4),
    ('customer_app_scrolled.png', 3),
    
    ('section_courier_app.png', 3),
    ('courier_app_login.png', 3),
    ('courier_app_dashboard.png', 4),
    ('courier_app_scrolled.png', 3),
    
    ('section_admin_dashboard.png', 3),
    ('admin_dashboard_login.png', 3),
    ('admin_dashboard_dashboard.png', 4),
    ('admin_dashboard_scrolled.png', 3),
    
    ('section_support_dashboard.png', 3),
    ('support_dashboard_login.png', 3),
    ('support_dashboard_dashboard.png', 4),
    ('support_dashboard_scrolled.png', 3),
    
    ('section_partner_dashboard.png', 3),
    ('partner_dashboard_login.png', 3),
    ('partner_dashboard_dashboard.png', 4),
    ('partner_dashboard_scrolled.png', 3),
    
    ('closing.png', 5),
]

# Write concat file
list_file = os.path.join(FRAMES_DIR, 'framelist.txt')
with open(list_file, 'w') as f:
    for fname, duration in frame_sequence:
        fpath = os.path.join(FRAMES_DIR, fname)
        if os.path.exists(fpath):
            f.write(f"file '{fpath}'\n")
            f.write(f"duration {duration}\n")
    # Last frame
    last = os.path.join(FRAMES_DIR, frame_sequence[-1][0])
    if os.path.exists(last):
        f.write(f"file '{last}'\n")

output_video = os.path.join(OUTPUT_DIR, 'elyanivery_demo.mp4')
cmd = [
    'ffmpeg', '-y',
    '-f', 'concat', '-safe', '0',
    '-i', list_file,
    '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0f1128,format=yuv420p',
    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
    '-movflags', '+faststart',
    output_video
]

result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
if result.returncode != 0:
    print(f"FFmpeg error: {result.stderr[-500:]}")
else:
    size_mb = os.path.getsize(output_video) / (1024*1024)
    print(f"Video created: {output_video} ({size_mb:.1f} MB)")
