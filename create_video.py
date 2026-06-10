#!/usr/bin/env python3
"""
Create a demo video for Elyanivery - showcasing all 5 web apps and their integration.
"""
import time, os, subprocess
from PIL import Image, ImageDraw, ImageFont

FRAMES_DIR = '/home/z/my-project/download/video_frames'
OUTPUT_DIR = '/home/z/my-project/download'
BASE_URL = 'http://localhost:8888'
FPS = 2

os.makedirs(FRAMES_DIR, exist_ok=True)

def create_title_frame(title, subtitle, color='#ff6b35', sub2='', filename='frame.png', hold=5):
    """Create a title frame image."""
    width, height = 1920, 1080
    img = Image.new('RGB', (width, height), '#0f1128')
    draw = ImageDraw.Draw(img)
    try:
        font_large = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 72)
        font_medium = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 36)
        font_small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 28)
    except:
        font_large = font_medium = font_small = ImageFont.load_default()
    
    draw.text((width//2, height//3), title, fill=color, font=font_large, anchor='mm')
    draw.text((width//2, height//3 + 80), subtitle, fill='#b0b3d0', font=font_medium, anchor='mm')
    if sub2:
        draw.text((width//2, height//3 + 140), sub2, fill='#6c6f9a', font=font_small, anchor='mm')
    
    img.save(os.path.join(FRAMES_DIR, filename))
    return [filename] * hold

def create_architecture_frame(filename='architecture.png', hold=8):
    """Create architecture overview frame."""
    width, height = 1920, 1080
    img = Image.new('RGB', (width, height), '#0f1128')
    draw = ImageDraw.Draw(img)
    try:
        font_large = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 56)
        font_medium = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 24)
        font_title = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 42)
    except:
        font_large = font_medium = font_title = ImageFont.load_default()
    
    draw.text((width//2, 60), "Platform Architecture", fill='#ff6b35', font=font_title, anchor='mt')
    
    apps_info = [
        ("Customer App", "Browse restaurants\nPlace orders\nTrack deliveries\nChat with courier", '#ff6b35', 80, 200, 340, 260),
        ("Courier App", "Accept deliveries\nNavigate routes\nTrack earnings\nVehicle management", '#5dade2', 420, 200, 340, 260),
        ("Partner App", "Manage menu items\nAccept/reject orders\nTrack statistics\nToggle availability", '#1abc9c', 760, 200, 340, 260),
        ("Admin Dashboard", "Manage users\nView statistics\nSend broadcasts\nApprove couriers", '#9b59b6', 1100, 200, 340, 260),
        ("Support Dashboard", "Handle tickets\nProcess refunds\nLive chat\nOrder management", '#f39c12', 1440, 200, 340, 260),
    ]
    
    for name, desc, color, x, y, w, h in apps_info:
        draw.rounded_rectangle([x, y, x+w, y+h], radius=16, fill='#1a1d42', outline=color, width=3)
        draw.text((x+w//2, y+30), name, fill=color, font=font_medium, anchor='mt')
        for i, line in enumerate(desc.split('\n')):
            draw.text((x+w//2, y+70 + i*28), line, fill='#b0b3d0', font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 18), anchor='mt')
    
    # Backend box
    draw.rounded_rectangle([400, 520, 1520, 650], radius=16, fill='#22264f', outline='#e8e8f0', width=2)
    draw.text((960, 565), "Python HTTP Server + PostgreSQL Database", fill='#e8e8f0', font=font_medium, anchor='mm')
    draw.text((960, 610), "Shared Backend with JWT Authentication & Real-time APIs", fill='#6c6f9a', font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 18), anchor='mm')
    
    # Integration flow
    draw.text((width//2, 700), "Integration Flow", fill='#ff6b35', font=font_title, anchor='mt')
    
    flow = [
        ("1. Customer places order", '#ff6b35'),
        ("2. Partner receives & accepts", '#1abc9c'),
        ("3. Courier auto-assigned (nearest)", '#5dade2'),
        ("4. Courier picks up & delivers", '#5dade2'),
        ("5. Support monitors & assists", '#f39c12'),
        ("6. Admin oversees everything", '#9b59b6'),
    ]
    
    for i, (step, color) in enumerate(flow):
        x = 200 + (i % 3) * 560
        y = 770 + (i // 3) * 100
        draw.rounded_rectangle([x, y, x+500, y+70], radius=12, fill='#1a1d42', outline=color, width=2)
        draw.text((x+250, y+35), step, fill=color, font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 20), anchor='mm')
    
    # Features
    draw.text((width//2, 990), "8 Themes | 3 Languages (EN/RU/RO) | 36 Restaurants | 547 Items | Loyalty Points | Voice Calls", fill='#6c6f9a', font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 18), anchor='mm')
    
    img.save(os.path.join(FRAMES_DIR, filename))
    return [filename] * hold

def create_video():
    """Main function to create the demo video."""
    from playwright.sync_api import sync_playwright
    
    ordered_frames = []
    
    # ═══ TITLE FRAMES ═══
    print("Creating title frames...")
    ordered_frames.extend(create_title_frame("ELYANIVERY", "Delivery Platform - Complete Demo", 
                                             sub2="5 Integrated Web Applications | Chisinau, Moldova", 
                                             filename='title_intro.png', hold=8))
    ordered_frames.extend(create_architecture_frame(hold=10))
    
    # ═══ CAPTURE SCREENSHOTS ═══
    print("Capturing app screenshots...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-gpu'])
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=1,
            color_scheme='dark'
        )
        
        # App configurations
        apps = [
            {
                'name': 'Customer App',
                'path': '/customer/',
                'color': '#ff6b35',
                'creds': ('customer1', '1234'),
                'section_desc': 'Browse restaurants, place orders,\ntrack deliveries, chat with courier',
            },
            {
                'name': 'Courier App', 
                'path': '/courier/',
                'color': '#5dade2',
                'creds': ('courier1', '1234'),
                'section_desc': 'Accept deliveries, navigate routes,\ntrack earnings, manage vehicle',
            },
            {
                'name': 'Admin Dashboard',
                'path': '/admin/', 
                'color': '#9b59b6',
                'creds': ('admin', 'admin'),
                'section_desc': 'Manage users, view statistics,\nbroadcast messages, approve couriers',
            },
            {
                'name': 'Support Dashboard',
                'path': '/support/',
                'color': '#f39c12',
                'creds': ('support1', '1234'),
                'section_desc': 'Handle tickets, process refunds,\nchat with customers, manage orders',
            },
            {
                'name': 'Partner Dashboard',
                'path': '/partner/',
                'color': '#1abc9c',
                'creds': ('andyspizza', '1234'),
                'section_desc': 'Manage menu items, accept orders,\ntrack stats, toggle availability',
            },
        ]
        
        for app in apps:
            name = app['name']
            path = app['path']
            color = app['color']
            desc = app['section_desc']
            username, password = app['creds']
            
            print(f"  Capturing {name}...")
            
            # Section title
            safe_name = name.lower().replace(' ', '_')
            ordered_frames.extend(create_title_frame(name, desc, color=color, 
                                                     filename=f'section_{safe_name}.png', hold=5))
            
            # Splash screen
            page = context.new_page()
            try:
                page.goto(f'{BASE_URL}{path}', wait_until='domcontentloaded', timeout=10000)
                time.sleep(1.5)
                fname = f'app_{safe_name}_splash.png'
                page.screenshot(path=os.path.join(FRAMES_DIR, fname))
                ordered_frames.extend([fname] * 3)
            except Exception as e:
                print(f"    Splash capture failed: {e}")
            
            # Login screen (after splash fades)
            try:
                time.sleep(2.5)
                fname = f'app_{safe_name}_login.png'
                page.screenshot(path=os.path.join(FRAMES_DIR, fname))
                ordered_frames.extend([fname] * 3)
                
                # Try to fill in login
                page.evaluate(f'''() => {{
                    const inputs = document.querySelectorAll('input');
                    if(inputs[0]) inputs[0].value = '{username}';
                    if(inputs[1]) inputs[1].value = '{password}';
                    const btn = document.querySelector('.login-btn, button[type="submit"], button');
                    if(btn) btn.click();
                }}''')
                time.sleep(2)
                
                # Dashboard view
                fname = f'app_{safe_name}_dashboard.png'
                page.screenshot(path=os.path.join(FRAMES_DIR, fname))
                ordered_frames.extend([fname] * 4)
                
                # Try to capture different tabs/views if available
                # Scroll down
                page.evaluate('window.scrollTo(0, 400)')
                time.sleep(0.5)
                fname = f'app_{safe_name}_view2.png'
                page.screenshot(path=os.path.join(FRAMES_DIR, fname))
                ordered_frames.extend([fname] * 2)
                
            except Exception as e:
                print(f"    Login capture failed: {e}")
            
            page.close()
        
        browser.close()
    
    # ═══ CLOSING FRAME ═══
    ordered_frames.extend(create_title_frame("ELYANIVERY", "Delivery Platform", 
                                             sub2="Built with Python + PostgreSQL | Deployed on Railway | 5 SPAs | 8 Themes | 3 Languages", 
                                             filename='closing.png', hold=8))
    
    # ═══ CREATE VIDEO WITH FFMPEG ═══
    print(f"Creating video with {len(ordered_frames)} frames...")
    
    list_file = os.path.join(FRAMES_DIR, 'framelist.txt')
    with open(list_file, 'w') as f:
        for i, frame in enumerate(ordered_frames):
            fpath = os.path.join(FRAMES_DIR, frame)
            if os.path.exists(fpath):
                f.write(f"file '{fpath}'\n")
                f.write(f"duration {1/FPS}\n")
        # Last frame
        if ordered_frames:
            last = os.path.join(FRAMES_DIR, ordered_frames[-1])
            if os.path.exists(last):
                f.write(f"file '{last}'\n")
    
    output_video = os.path.join(OUTPUT_DIR, 'elyanivery_demo.mp4')
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat', '-safe', '0',
        '-i', list_file,
        '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0f1128,format=yuv420p',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
        '-movflags', '+faststart',
        output_video
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"FFmpeg error: {result.stderr[-500:]}")
        return None
    
    # Get video info
    size_mb = os.path.getsize(output_video) / (1024*1024)
    print(f"Video created: {output_video} ({size_mb:.1f} MB)")
    return output_video

if __name__ == '__main__':
    video_path = create_video()
    if video_path:
        print(f"\nSuccess! Video saved to: {video_path}")
    else:
        print("\nFailed to create video!")
