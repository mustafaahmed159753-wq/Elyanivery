import os
import zlib
import struct

def make_fast_png(width, height, get_pixel_func, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    raw_rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            pixel = get_pixel_func(x, y, width, height)
            row.extend(pixel)
        raw_rows.append(bytes(row))
    
    raw_data = b''.join(raw_rows)
    compressed = zlib.compress(raw_data, level=6)
    
    png = bytearray(b'\x89PNG\r\n\x1a\n')
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    png.extend(struct.pack('>I', len(ihdr)))
    png.extend(b'IHDR')
    png.extend(ihdr)
    png.extend(struct.pack('>I', zlib.crc32(b'IHDR' + ihdr)))
    
    png.extend(struct.pack('>I', len(compressed)))
    png.extend(b'IDAT')
    png.extend(compressed)
    png.extend(struct.pack('>I', zlib.crc32(b'IDAT' + compressed)))
    
    png.extend(struct.pack('>I', 0))
    png.extend(b'IEND')
    png.extend(struct.pack('>I', zlib.crc32(b'IEND')))
    
    with open(output_path, 'wb') as f:
        f.write(png)

def icon_pixel(x, y, w, h, bg=(255, 107, 0), fg=(255, 255, 255), is_maskable=False):
    nx = (x / (w - 1)) * 2 - 1
    ny = (y / (h - 1)) * 2 - 1
    
    margin = 0.75 if is_maskable else 0.88
    if abs(nx) < margin and abs(ny) < margin:
        cx, cy = nx / margin, ny / margin
        # E glyph
        if (-0.5 <= cx <= -0.2 and -0.6 <= cy <= 0.6) or \
           (-0.5 <= cx <= 0.5 and -0.6 <= cy <= -0.35) or \
           (-0.5 <= cx <= 0.35 and -0.15 <= cy <= 0.1) or \
           (-0.5 <= cx <= 0.5 and 0.35 <= cy <= 0.6):
            return fg[0], fg[1], fg[2], 255
        return bg[0], bg[1], bg[2], 255
    else:
        if is_maskable:
            return bg[0], bg[1], bg[2], 255
        return 0, 0, 0, 0

def screenshot_pixel(x, y, w, h, theme_dark=True):
    # Top navbar
    if y < int(h * 0.08):
        return 255, 107, 0, 255 # Brand orange topbar
    # Bottom tab bar if mobile
    if h > w and y > int(h * 0.92):
        return 30, 41, 59, 255
    # Sidebar if wide
    if w > h and x < int(w * 0.18):
        return 15, 23, 42, 255
    # Grid pattern for mockup UI
    if (x % 40 == 0) or (y % 40 == 0):
        return (51, 65, 85, 255) if theme_dark else (226, 232, 240, 255)
    return (15, 23, 42, 255) if theme_dark else (248, 250, 252, 255)

def main():
    sizes = [72, 96, 128, 144, 152, 180, 192, 384, 512]
    
    print("Generating standard icons...")
    for s in sizes:
        make_fast_png(s, s, lambda x,y,w,h,s=s: icon_pixel(x, y, w, h, is_maskable=False), f"public/icons/icon-{s}x{s}.png")
        make_fast_png(s, s, lambda x,y,w,h,s=s: icon_pixel(x, y, w, h, is_maskable=True), f"public/icons/maskable-icon-{s}x{s}.png")
    
    # Specific shortcuts
    make_fast_png(96, 96, lambda x,y,w,h: icon_pixel(x,y,w,h, bg=(255,107,0), is_maskable=False), "public/icons/shortcut-order.png")
    make_fast_png(96, 96, lambda x,y,w,h: icon_pixel(x,y,w,h, bg=(16,185,129), is_maskable=False), "public/icons/shortcut-courier.png")
    make_fast_png(96, 96, lambda x,y,w,h: icon_pixel(x,y,w,h, bg=(59,130,246), is_maskable=False), "public/icons/shortcut-partner.png")
    make_fast_png(96, 96, lambda x,y,w,h: icon_pixel(x,y,w,h, bg=(168,85,247), is_maskable=False), "public/icons/shortcut-support.png")
    make_fast_png(96, 96, lambda x,y,w,h: icon_pixel(x,y,w,h, bg=(239,68,68), is_maskable=False), "public/icons/shortcut-admin.png")
    
    # Apple touch icons
    make_fast_png(180, 180, lambda x,y,w,h: icon_pixel(x,y,w,h, is_maskable=False), "public/apple-touch-icon.png")
    make_fast_png(180, 180, lambda x,y,w,h: icon_pixel(x,y,w,h, is_maskable=False), "public/icons/apple-touch-icon.png")
    
    # Screenshots
    print("Generating screenshots...")
    # Desktop 1280x720
    make_fast_png(1280, 720, lambda x,y,w,h: screenshot_pixel(x,y,w,h, theme_dark=True), "public/screenshots/desktop-home.png")
    make_fast_png(1280, 720, lambda x,y,w,h: screenshot_pixel(x,y,w,h, theme_dark=False), "public/screenshots/desktop-dashboard.png")
    # Mobile 750x1334
    make_fast_png(750, 1334, lambda x,y,w,h: screenshot_pixel(x,y,w,h, theme_dark=True), "public/screenshots/mobile-customer.png")
    make_fast_png(750, 1334, lambda x,y,w,h: screenshot_pixel(x,y,w,h, theme_dark=True), "public/screenshots/mobile-courier.png")
    make_fast_png(750, 1334, lambda x,y,w,h: screenshot_pixel(x,y,w,h, theme_dark=True), "public/screenshots/mobile-partner.png")
    
    # Widget preview 400x200
    make_fast_png(400, 200, lambda x,y,w,h: screenshot_pixel(x,y,w,h, theme_dark=True), "public/screenshots/widget-order.png")
    
    print("All PWA assets generated successfully!")

if __name__ == '__main__':
    main()
