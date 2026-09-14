import json, os

tsj_path = r"D:\CodeProject\PixelsProject\Aseprite\tiled\stone_01.tsj"
with open(tsj_path, "r", encoding="utf-8") as f:
    tsj = json.load(f)

print("tilecount:", tsj.get("tilecount"))
print("tiles defined:", len(tsj.get("tiles", [])))
tsj_dir = os.path.dirname(tsj_path)

for t in tsj.get("tiles", []):
    tid = t["id"]
    img_rel = t.get("image", "NONE")
    img_path = os.path.normpath(os.path.join(tsj_dir, img_rel))
    exists = os.path.exists(img_path)
    print("  tile %d: %s exists=%s" % (tid, os.path.basename(img_rel), exists))
