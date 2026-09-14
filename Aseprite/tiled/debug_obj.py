import json, os, xml.etree.ElementTree as ET
from PIL import Image

TILED_DIR = r"D:\CodeProject\PixelsProject\Aseprite\tiled"
TMX_PATH = os.path.join(TILED_DIR, "预览01.tmx")

tree = ET.parse(TMX_PATH)
root = tree.getroot()

# Load tilesets (simplified - just for gid lookup)
tilesets = []
for ts_elem in root.findall("tileset"):
    firstgid = int(ts_elem.get("firstgid"))
    tsj_file = ts_elem.get("source")
    tsj_path = os.path.join(TILED_DIR, tsj_file)
    with open(tsj_path, "r", encoding="utf-8") as f:
        tsj = json.load(f)
    tilecount = tsj.get("tilecount", 0)
    name = tsj.get("name", "")
    tilesets.append((firstgid, tilecount, name, tsj))
    print("TS: %s firstgid=%d tilecount=%d" % (name, firstgid, tilecount))

# Find object groups
for child in root:
    if child.tag == "objectgroup":
        name = child.get("name")
        objs = child.findall("object")
        print("\nObjectGroup: %s (%d objects)" % (name, len(objs)))
        for obj in objs[:5]:
            gid = int(obj.get("gid", 0))
            x = float(obj.get("x", 0))
            y = float(obj.get("y", 0))
            w = float(obj.get("width", 0))
            h = float(obj.get("height", 0))
            # Find which tileset
            ts_name = "UNKNOWN"
            local = -1
            for firstgid, tilecount, tsn, tsj in tilesets:
                if firstgid <= gid < firstgid + tilecount:
                    ts_name = tsn
                    local = gid - firstgid
                    break
                # Also check if gid falls in range by actual tile IDs
            print("  gid=%d -> local=%d ts=%s pos=(%.1f,%.1f) size=%.0fx%.0f" % (gid, local, ts_name, x, y, w, h))
