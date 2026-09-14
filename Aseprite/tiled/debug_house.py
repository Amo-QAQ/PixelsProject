import json, os

TILED_DIR = r"D:\CodeProject\PixelsProject\Aseprite\tiled"

# Check house.tsj and other.tsj
for name in ["house.tsj", "other.tsj"]:
    path = os.path.join(TILED_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        tsj = json.load(f)
    print("=== %s ===" % name)
    print("  tilecount:", tsj.get("tilecount"))
    if "image" in tsj:
        print("  spritesheet:", tsj["image"], "cols:", tsj.get("columns"))
    for t in tsj.get("tiles", []):
        tid = t["id"]
        if "image" in t:
            img_path = os.path.normpath(os.path.join(TILED_DIR, t["image"]))
            exists = os.path.exists(img_path)
            iw = t.get("imagewidth", "?")
            ih = t.get("imageheight", "?")
            print("  tile %d: %s %sx%s exists=%s" % (tid, os.path.basename(t["image"]), iw, ih, exists))
    print()
