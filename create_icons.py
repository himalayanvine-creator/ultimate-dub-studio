import os
from PIL import Image, ImageDraw, ImageFont

icons_dir = "/Volumes/new/LocalDubWorkspace/frontend/icons"
os.makedirs(icons_dir, exist_ok=True)

def create_pwa_icon(size):
    # Create dark canvas
    img = Image.new("RGBA", (size, size), (17, 17, 27, 255)) # #11111b
    draw = ImageDraw.Draw(img)

    # Draw rounded squircle background
    padding = int(size * 0.08)
    radius = int(size * 0.22)
    draw.rounded_rectangle(
        [padding, padding, size - padding, size - padding],
        radius=radius,
        fill=(24, 24, 37, 255),  # #181825 card bg
        outline=(137, 180, 250, 255), # #89b4fa blue border
        width=max(2, int(size * 0.015))
    )

    # Draw sound wave bars in center
    center_y = size // 2
    center_x = size // 2
    bar_width = max(3, int(size * 0.04))
    spacing = max(2, int(size * 0.03))
    
    # Height ratios of 7 vertical waveform bars
    heights = [0.25, 0.45, 0.70, 0.90, 0.65, 0.40, 0.20]
    total_width = len(heights) * bar_width + (len(heights) - 1) * spacing
    start_x = center_x - (total_width // 2)

    for i, h_ratio in enumerate(heights):
        x = start_x + i * (bar_width + spacing)
        bar_h = int((size * 0.45) * h_ratio)
        y0 = center_y - (bar_h // 2)
        y1 = center_y + (bar_h // 2)

        # Alternate gradient colors (#89b4fa to #a6e3a1)
        if i % 2 == 0:
            color = (137, 180, 250, 255) # Blue
        else:
            color = (166, 227, 161, 255) # Green

        draw.rounded_rectangle(
            [x, y0, x + bar_width, y1],
            radius=bar_width // 2,
            fill=color
        )

    out_path = os.path.join(icons_dir, f"icon-{size}.png")
    img.save(out_path, "PNG")
    print(f"[✓] Generated PWA Icon: {out_path}")

create_pwa_icon(192)
create_pwa_icon(512)
