"""
Splits test.jpg (equirectangular 720x360) into 3 depth layers via vertical
banding with feathered alpha transitions, plus a sphere-brightness boost so
the white spheres stay opaque on near/mid layers across their full height.

Output:
  depth_far.png   - sky + upper atmosphere (outermost concentric sphere)
  depth_mid.png   - horizon band, midground spheres        (middle sphere)
  depth_near.png  - reflective floor + foreground spheres  (innermost sphere)
"""
from PIL import Image, ImageFilter
import numpy as np

SRC = "/Users/t1m/github/sphere-world/test.jpg"
OUT_FAR  = "/Users/t1m/github/sphere-world/depth_far.png"
OUT_MID  = "/Users/t1m/github/sphere-world/depth_mid.png"
OUT_NEAR = "/Users/t1m/github/sphere-world/depth_near.png"

img = Image.open(SRC).convert("RGB")
W, H = img.size
rgb = np.asarray(img, dtype=np.float32) / 255.0

# Brightness mask — emphasises the white spheres so they stay visible
# even when they sit in the alpha-fade zone of a depth band.
luma = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
sphere_mask = np.clip((luma - 0.55) / 0.4, 0.0, 1.0)  # bright pixels -> 1

y = np.linspace(0.0, 1.0, H, dtype=np.float32)[:, None]  # 0=top, 1=bottom

def smoothstep(edge0, edge1, x):
    t = np.clip((x - edge0) / (edge1 - edge0 + 1e-9), 0.0, 1.0)
    return t * t * (3 - 2 * t)

# Far / sky: fully opaque on top, fades out before the horizon.
far_alpha = 1.0 - smoothstep(0.30, 0.55, y)
far_alpha = np.broadcast_to(far_alpha, (H, W)).copy()

# Mid / horizon band: centred around the horizon (~y=0.5).
mid_alpha = smoothstep(0.30, 0.45, y) * (1.0 - smoothstep(0.55, 0.70, y))
mid_alpha = np.broadcast_to(mid_alpha, (H, W)).copy()
# Push the bright spheres up toward fully opaque on the mid layer.
mid_alpha = np.maximum(mid_alpha, sphere_mask * 0.85)
# But cut the sky out of the mid layer.
mid_alpha *= smoothstep(0.10, 0.35, np.broadcast_to(y, (H, W)))

# Near / floor + foreground spheres: opaque at the bottom, fades up.
near_alpha = smoothstep(0.45, 0.70, y)
near_alpha = np.broadcast_to(near_alpha, (H, W)).copy()
# Keep the big foreground spheres fully opaque even where they extend upward.
# (They're the brightest objects above the horizon line in their columns.)
near_alpha = np.maximum(near_alpha, sphere_mask * smoothstep(0.20, 0.45, np.broadcast_to(y, (H, W))))

def save_layer(alpha, path):
    a = (np.clip(alpha, 0.0, 1.0) * 255.0).astype(np.uint8)
    rgba = np.dstack([(rgb * 255.0).astype(np.uint8), a])
    out = Image.fromarray(rgba, mode="RGBA")
    # Slight blur on the alpha channel to soften band edges.
    r, g, b, a_ch = out.split()
    a_ch = a_ch.filter(ImageFilter.GaussianBlur(radius=1.2))
    out = Image.merge("RGBA", (r, g, b, a_ch))
    out.save(path, optimize=True)
    print(f"wrote {path} ({out.size}, mode={out.mode})")

save_layer(far_alpha,  OUT_FAR)
save_layer(mid_alpha,  OUT_MID)
save_layer(near_alpha, OUT_NEAR)
