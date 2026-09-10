#!/usr/bin/env python3
"""Quick video assembly from existing frames."""
import os

FRAMES_DIR = '/home/z/my-project/download/video_frames'
OUTPUT_DIR = '/home/z/my-project/download'
FPS = 1.5  # seconds per frame

# Build ordered frame sequence
ordered_frames = [
    # Intro
    ('title_intro.png', 4),
    ('architecture.png', 5),
    
    # Customer App
    ('section_customer_app.png', 3),
    ('app_customer_app_login.png', 3),
    ('app_customer_app_dashboard.png', 4),
    ('app_customer_app_view2.png', 3),
    
    # Courier App
    ('section_courier_app.png', 3),
    ('app_courier_app_login.png', 3),
    ('app_courier_app_dashboard.png', 4),
    ('app_courier_app_view2.png', 3),
    
    # Admin Dashboard
    ('section_admin_dashboard.png', 3),
    ('app_admin_dashboard_login.png', 3),
    ('app_admin_dashboard_dashboard.png', 4),
    ('app_admin_dashboard_view2.png', 3),
    
    # Support Dashboard
    ('section_support_dashboard.png', 3),
    ('app_support_dashboard_login.png', 3),
    ('app_support_dashboard_dashboard.png', 4),
    ('app_support_dashboard_view2.png', 3),
    
    # Partner Dashboard
    ('section_partner_dashboard.png', 3),
    ('app_partner_dashboard_login.png', 3),
    ('app_partner_dashboard_dashboard.png', 4),
    ('app_partner_dashboard_view2.png', 3),
    
    # Closing
    ('closing.png', 5),
]

# Write ffmpeg concat file
list_file = os.path.join(FRAMES_DIR, 'framelist.txt')
with open(list_file, 'w') as f:
    for frame_name, duration in ordered_frames:
        fpath = os.path.join(FRAMES_DIR, frame_name)
        if os.path.exists(fpath):
            f.write(f"file '{fpath}'\n")
            f.write(f"duration {duration}\n")
    # Last frame again
    last_frame = ordered_frames[-1][0]
    last_path = os.path.join(FRAMES_DIR, last_frame)
    if os.path.exists(last_path):
        f.write(f"file '{last_path}'\n")

print("Frame list created. Building video...")

# Create video
output_video = os.path.join(OUTPUT_DIR, 'elyanivery_demo.mp4')
import subprocess
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
    print(f"FFmpeg error: {result.stderr[-300:]}")
else:
    size_mb = os.path.getsize(output_video) / (1024*1024)
    print(f"Video created: {output_video} ({size_mb:.1f} MB)")
