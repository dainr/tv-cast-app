import os
from PIL import Image, ImageDraw

def create_client_icon():
    # 256x256 image with transparent background
    img = Image.new('RGBA', (256, 256), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw background circle (deep dark grey/blue)
    draw.ellipse([10, 10, 246, 246], fill=(31, 40, 51, 255), outline=(102, 252, 241, 255), width=6)
    
    # Draw a stylized remote control or gamepad shape
    # Rounded rectangle for remote
    draw.rounded_rectangle([90, 50, 166, 206], radius=20, fill=(11, 12, 16, 255), outline=(102, 252, 241, 255), width=4)
    
    # Draw buttons on the remote
    # Power button (cyan circle)
    draw.ellipse([118, 70, 138, 90], fill=(102, 252, 241, 255))
    
    # Play icon triangle inside remote control
    draw.polygon([(118, 120), (118, 150), (144, 135)], fill=(69, 162, 158, 255))
    
    # Volume/channel buttons
    draw.rounded_rectangle([105, 170, 125, 185], radius=2, fill=(197, 198, 199, 255))
    draw.rounded_rectangle([131, 170, 151, 185], radius=2, fill=(197, 198, 199, 255))
    
    # Save the icon
    img.save('/home/dain/tv-cast-app/tv_cast_client.png')
    print("Created tv_cast_client.png")

def create_server_icon():
    # 256x256 image with transparent background
    img = Image.new('RGBA', (256, 256), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw background circle (deep dark grey/blue)
    draw.ellipse([10, 10, 246, 246], fill=(31, 40, 51, 255), outline=(102, 252, 241, 255), width=6)
    
    # Draw TV/Monitor body
    draw.rounded_rectangle([50, 60, 206, 170], radius=15, fill=(11, 12, 16, 255), outline=(197, 198, 199, 255), width=5)
    
    # Draw Screen inside monitor (filled with slightly lighter blue/grey)
    draw.rounded_rectangle([60, 70, 196, 150], radius=8, fill=(11, 12, 16, 255))
    
    # Draw TV Stand
    draw.polygon([(110, 170), (146, 170), (156, 200), (100, 200)], fill=(197, 198, 199, 255))
    draw.rounded_rectangle([80, 200, 176, 212], radius=4, fill=(197, 198, 199, 255))
    
    # Draw signal/wifi broadcasting waves coming out from screen center
    # Center of screen is (128, 110)
    # Circle waves:
    draw.ellipse([113, 95, 143, 125], outline=(102, 252, 241, 255), width=3)
    
    # Draw partial arcs (we can draw complete ellipses with wider bounding boxes or arc segments)
    draw.arc([98, 80, 158, 140], start=210, end=330, fill=(69, 162, 158, 255), width=3)
    draw.arc([83, 65, 173, 155], start=210, end=330, fill=(102, 252, 241, 255), width=3)
    
    # Save the icon
    img.save('/home/dain/tv-cast-app/tv_cast_server.png')
    print("Created tv_cast_server.png")

if __name__ == '__main__':
    create_client_icon()
    create_server_icon()
