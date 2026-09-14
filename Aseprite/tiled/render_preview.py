import json
import os
import xml.etree.ElementTree as ET
from PIL import Image

TILED_DIR = r"D:\CodeProject\PixelsProject\Aseprite\tiled"
TMX_PATH = os.path.join(TILED_DIR, "预览01.tmx")
OUTPUT_GIF = os.path.join(TILED_DIR, "预览01.gif")
OUTPUT_GIF_SMALL = os.path.join(TILED_DIR, "预览01_小.gif")

tree = ET.parse(TMX_PATH)
root = tree.getroot()

MAP_W = int(root.get("width"))
MAP_H = int(root.get("height"))
TILE_W = int(root.get("tilewidth"))
TILE_H = int(root.get("tileheight"))
CANVAS_W = MAP_W * TILE_W
CANVAS_H = MAP_H * TILE_H

print(f"Map: {MAP_W}x{MAP_H} tiles, canvas: {CANVAS_W}x{CANVAS_H}px")

# Load all tilesets
tilesets = []

for ts_elem in root.findall("tileset"):
    firstgid = int(ts_elem.get("firstgid"))
    tsj_file = ts_elem.get("source")
    tsj_path = os.path.join(TILED_DIR, tsj_file)
    tsj_dir = os.path.dirname(tsj_path)

    with open(tsj_path, "r", encoding="utf-8") as f:
        tsj = json.load(f)

    name = tsj.get("name", "")
    columns = tsj.get("columns", 0)
    tilecount = tsj.get("tilecount", 0)
    tile_w = tsj.get("tilewidth", TILE_W)
    tile_h = tsj.get("tileheight", TILE_H)

    # Determine format: spritesheet or collection
    spritesheet = None
    tile_images = {}  # local_id -> (image, px, py, w, h)

    if "image" in tsj:
        # Single spritesheet
        img_path = os.path.normpath(os.path.join(tsj_dir, tsj["image"]))
        if os.path.exists(img_path):
            spritesheet = Image.open(img_path).convert("RGBA")
            print(f"  [spritesheet] {name} firstgid={firstgid} cols={columns} tiles={tilecount} img={os.path.basename(img_path)}")
        else:
            print(f"  WARNING: Image not found: {img_path}")
    else:
        # Collection of images - each tile has its own image
        for tile_info in tsj.get("tiles", []):
            tid = tile_info["id"]
            if "image" in tile_info:
                img_path = os.path.normpath(os.path.join(tsj_dir, tile_info["image"]))
                if os.path.exists(img_path):
                    im = Image.open(img_path).convert("RGBA")
                    iw = tile_info.get("imagewidth", im.width)
                    ih = tile_info.get("imageheight", im.height)
                    tile_images[tid] = (im, 0, 0, iw, ih)
                else:
                    print(f"  WARNING: Tile image not found: {img_path}")
        print(f"  [collection] {name} firstgid={firstgid} tiles={tilecount} loaded={len(tile_images)}")

    # Parse animations
    animations = {}
    for tile_info in tsj.get("tiles", []):
        if "animation" in tile_info:
            animations[tile_info["id"]] = tile_info["animation"]

    tilesets.append({
        "firstgid": firstgid,
        "name": name,
        "spritesheet": spritesheet,
        "tile_images": tile_images,
        "columns": columns,
        "tilecount": tilecount,
        "tile_w": tile_w,
        "tile_h": tile_h,
        "animations": animations,
    })

# Compute actual gid ranges based on adjacent tileset firstgids
# (tsj tilecount can be larger than the range actually assigned in this map)
for i, ts in enumerate(tilesets):
    start = ts["firstgid"]
    if i + 1 < len(tilesets):
        end = tilesets[i + 1]["firstgid"]
    else:
        end = start + ts["tilecount"]
    ts["gid_start"] = start
    ts["gid_end"] = end
    print(f"  Range: {start}-{end-1} ({end-start} tiles) for {ts['name']}")

def gid_to_tileset_and_local(gid):
    if gid == 0:
        return None, None
    for i, ts in enumerate(tilesets):
        if ts["gid_start"] <= gid < ts["gid_end"]:
            return i, gid - ts["gid_start"]
    return None, None

def get_tile_image(ts_idx, local_id, anim_frame=0):
    ts = tilesets[ts_idx]

    # Resolve animation frame
    if local_id in ts["animations"]:
        frames = ts["animations"][local_id]
        frame_idx = anim_frame % len(frames)
        actual_tile = frames[frame_idx]["tileid"]
    else:
        actual_tile = local_id

    # Collection of images
    if ts["spritesheet"] is None:
        if actual_tile in ts["tile_images"]:
            im, _, _, _, _ = ts["tile_images"][actual_tile]
            return im.copy()
        return None

    # Spritesheet
    cols = ts["columns"]
    tx = (actual_tile % cols) * ts["tile_w"]
    ty = (actual_tile // cols) * ts["tile_h"]
    return ts["spritesheet"].crop((tx, ty, tx + ts["tile_w"], ty + ts["tile_h"]))

# Parse layers in XML order
layers = []
for child in root:
    if child.tag == "layer":
        visible = child.get("visible", "1") != "0"
        data_elem = child.find("data")
        csv_data = data_elem.text.strip()
        tiles = []
        for row in csv_data.split("\n"):
            row = row.strip().rstrip(",")
            if row:
                tiles.append([int(x.strip()) for x in row.split(",")])
        layers.append({"type": "layer", "name": child.get("name"), "visible": visible, "tiles": tiles})
    elif child.tag == "objectgroup":
        objects = []
        for obj in child.findall("object"):
            gid = int(obj.get("gid", 0))
            x = float(obj.get("x", 0))
            y = float(obj.get("y", 0))
            w = float(obj.get("width", TILE_W))
            h = float(obj.get("height", TILE_H))
            objects.append({"gid": gid, "x": x, "y": y, "w": w, "h": h})
        # Sort objects by bottom y (painter's algorithm: lower objects render on top)
        objects.sort(key=lambda o: o["y"])
        layers.append({"type": "objectgroup", "name": child.get("name"), "objects": objects})

print(f"\nRendering {len(layers)} layers/groups...")

# Determine animation cycles - find LCM of all animation lengths for perfect loop
import math
anim_lengths = set()
frame_duration_ms = 100
for ts in tilesets:
    for local_id, frames in ts["animations"].items():
        n = len(frames)
        anim_lengths.add(n)
        frame_duration_ms = frames[0].get("duration", 100)

# Calculate LCM of all cycle lengths
total_frames = 1
for n in anim_lengths:
    total_frames = total_frames * n // math.gcd(total_frames, n)

print(f"Animation cycles found: {sorted(anim_lengths)} frames each")
print(f"LCM = {total_frames} frames (water cycles: {total_frames//7 if 7 in anim_lengths else 'N/A'}, char cycles: {total_frames//8 if 8 in anim_lengths else 'N/A'})")
print(f"Frame duration: {frame_duration_ms}ms, total loop: {total_frames * frame_duration_ms / 1000:.1f}s")

def render_frame(anim_frame=0):
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    for layer in layers:
        if layer["type"] == "layer":
            if not layer["visible"]:
                continue
            for row_idx, row in enumerate(layer["tiles"]):
                for col_idx, gid in enumerate(row):
                    if gid == 0:
                        continue
                    ts_idx, local_id = gid_to_tileset_and_local(gid)
                    if ts_idx is None:
                        continue
                    tile_img = get_tile_image(ts_idx, local_id, anim_frame)
                    if tile_img:
                        px = col_idx * TILE_W
                        # Bottom-align: tile image bottom sits at the grid cell bottom
                        py = row_idx * TILE_H + TILE_H - tile_img.height
                        canvas.paste(tile_img, (px, py), tile_img)
        elif layer["type"] == "objectgroup":
            for obj in layer["objects"]:
                gid = obj["gid"]
                if gid == 0:
                    continue
                ts_idx, local_id = gid_to_tileset_and_local(gid)
                if ts_idx is None:
                    continue
                tile_img = get_tile_image(ts_idx, local_id, anim_frame)
                if tile_img:
                    px = int(round(obj["x"]))
                    py = int(round(obj["y"] - tile_img.height))
                    canvas.paste(tile_img, (px, py), tile_img)
    return canvas

# Scale factor
SCALE = 4
OUT_W = CANVAS_W * SCALE
OUT_H = CANVAS_H * SCALE

# Render all frames (at native resolution, then upscale)
frames = []
for fi in range(total_frames):
    canvas = render_frame(fi)
    # Composite over a sky-blue background
    bg = Image.new("RGBA", (CANVAS_W, CANVAS_H), (135, 205, 225, 255))
    bg.paste(canvas, (0, 0), canvas)
    # Upscale 4x with nearest-neighbor for pixel art
    upscaled = bg.convert("RGB").resize((OUT_W, OUT_H), Image.NEAREST)
    frames.append(upscaled)

print(f"Rendered {len(frames)} frames, {OUT_W}x{OUT_H} (4x scale)")

# Save full GIF (4x)
frames[0].save(
    OUTPUT_GIF,
    save_all=True,
    append_images=frames[1:],
    duration=frame_duration_ms,
    loop=0,
    optimize=True,
)
print(f"Saved: {OUTPUT_GIF}")

# Save small version (original resolution)
small_frames = [f.resize((CANVAS_W, CANVAS_H), Image.NEAREST) for f in frames]
small_frames[0].save(
    OUTPUT_GIF_SMALL,
    save_all=True,
    append_images=small_frames[1:],
    duration=frame_duration_ms,
    loop=0,
    optimize=True,
)
print(f"Saved: {OUTPUT_GIF_SMALL}")

# Save static PNG (4x)
static_png = os.path.join(TILED_DIR, "预览01.png")
frames[0].save(static_png)
print(f"Saved: {static_png}")
print("Done!")
