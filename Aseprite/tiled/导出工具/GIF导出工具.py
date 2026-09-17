# -*- coding: utf-8 -*-
"""
GIF 导出工具（本地网页版）
==========================
把 tmxrasterizer / 自研渲染的参数变成可视化界面：
    - 选择地图 -> 自动读取动画信息、自动计算循环帧数
    - 图层勾选显示/隐藏
    - 导出单帧 PNG 或动画 GIF（透明底，无默认底色）
    - 页面直接预览结果

启动方式：
    双击「启动GIF工具.bat」，或命令行运行 python GIF导出工具.py
    会自动打开浏览器 http://127.0.0.1:8765

依赖：Python + Pillow（本机已有）
"""
import json
import math
import os
import io
import subprocess
import sys
import tempfile
import webbrowser
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))      # 导出工具文件夹
TILED_DIR = os.path.dirname(BASE_DIR)                      # tiled 文件夹
GIF_DIR = os.path.join(TILED_DIR, "GIF")                   # 交付产物
TEMP_DIR = os.path.join(TILED_DIR, "_临时")                # 临时文件
PORT = 8765
DEFAULT_FRAME_MS = 100
SCALES = [1, 2, 3, 4, 5, 6, 8]
# 背景色：默认浅蓝（与商店展示规格一致）；white=纯白；transparent=透明
BG_MAP = {
    "lightblue": (135, 205, 225, 255),
    "white": (255, 255, 255, 255),
    "transparent": (0, 0, 0, 0),
}
DEFAULT_BG = "lightblue"

# ---------- 地图 / 瓦片集解析（与已验证的 export_preview.py 一致） ----------

def list_maps():
    names = []
    for f in os.listdir(TILED_DIR):
        if f.endswith(".tmx"):
            names.append(f[:-4])
    return sorted(names)


def load_tilesets(root, tile_w, tile_h):
    tilesets = []
    for ts_elem in root.findall("tileset"):
        firstgid = int(ts_elem.get("firstgid"))
        tsj_path = os.path.join(TILED_DIR, ts_elem.get("source"))
        tsj_dir = os.path.dirname(tsj_path)
        with open(tsj_path, "r", encoding="utf-8") as f:
            tsj = json.load(f)
        columns = tsj.get("columns", 0)
        tilecount = tsj.get("tilecount", 0)
        ts_w = tsj.get("tilewidth", tile_w)
        ts_h = tsj.get("tileheight", tile_h)
        spritesheet = None
        tile_images = {}
        if "image" in tsj:
            img_path = os.path.normpath(os.path.join(tsj_dir, tsj["image"]))
            if os.path.exists(img_path):
                spritesheet = Image.open(img_path).convert("RGBA")
            else:
                print(f"  [警告] 图片缺失: {img_path}")
        else:
            for tile_info in tsj.get("tiles", []):
                if "image" in tile_info:
                    img_path = os.path.normpath(os.path.join(tsj_dir, tile_info["image"]))
                    if os.path.exists(img_path):
                        im = Image.open(img_path).convert("RGBA")
                        iw = tile_info.get("imagewidth", im.width)
                        ih = tile_info.get("imageheight", im.height)
                        tile_images[tile_info["id"]] = (im, 0, 0, iw, ih)
        animations = {}
        for tile_info in tsj.get("tiles", []):
            if "animation" in tile_info:
                animations[tile_info["id"]] = tile_info["animation"]
        tilesets.append({
            "firstgid": firstgid, "name": tsj.get("name", ""),
            "spritesheet": spritesheet, "tile_images": tile_images,
            "columns": columns, "tilecount": tilecount,
            "tile_w": ts_w, "tile_h": ts_h, "animations": animations,
        })
    for i, ts in enumerate(tilesets):
        start = ts["firstgid"]
        end = tilesets[i + 1]["firstgid"] if i + 1 < len(tilesets) else start + ts["tilecount"]
        ts["gid_start"], ts["gid_end"] = start, end
    return tilesets


def parse_layers(root):
    """解析瓦片层(layer) 与图块对象层(objectgroup)；对象层只保留带 gid 的图块对象"""
    layers = []
    for child in root:
        if child.tag == "layer":
            visible = child.get("visible", "1") != "0"
            csv_data = child.find("data").text.strip()
            tiles = []
            for row in csv_data.split("\n"):
                row = row.strip().rstrip(",")
                if row:
                    tiles.append([int(x.strip()) for x in row.split(",")])
            layers.append({"type": "tile", "name": child.get("name"),
                           "visible": visible, "tiles": tiles})
        elif child.tag == "objectgroup":
            visible = child.get("visible", "1") != "0"
            draworder = child.get("draworder", "topdown")  # Tiled 默认 topdown(y升序)
            objs = []
            for o in child:
                if o.get("gid") is None:
                    continue  # 纯矩形/碰撞对象不渲染
                objs.append({"gid": int(o.get("gid")),
                             "x": float(o.get("x", 0)),
                             "y": float(o.get("y", 0)),
                             "width": float(o.get("width", 0)) or None,
                             "height": float(o.get("height", 0)) or None})
            if draworder == "topdown":
                objs.sort(key=lambda o: o["y"])  # y 小的先画，y 大的盖上面(官方行为)
            layers.append({"type": "object", "name": child.get("name"),
                           "visible": visible, "draworder": draworder, "objects": objs})
    return layers


def compute_cycle(tilesets, frame_ms=DEFAULT_FRAME_MS):
    """各动画帧数集合 -> 循环帧数（LCM）。时长统一按 frame_ms 推进。"""
    anim_lengths = set()
    for ts in tilesets:
        for _, frames in ts["animations"].items():
            anim_lengths.add(len(frames))
    total = 1
    for n in anim_lengths:
        total = total * n // math.gcd(total, n)
    return total


def _tile_image(ts, local_id, anim_frame):
    if local_id in ts["animations"]:
        frames = ts["animations"][local_id]
        actual = frames[anim_frame % len(frames)]["tileid"]
    else:
        actual = local_id
    if ts["spritesheet"] is None:
        if actual in ts["tile_images"]:
            return ts["tile_images"][actual][0].copy()
        return None
    cols = ts["columns"] or 1
    tx = (actual % cols) * ts["tile_w"]
    ty = (actual // cols) * ts["tile_h"]
    return ts["spritesheet"].crop((tx, ty, tx + ts["tile_w"], ty + ts["tile_h"]))


def render_frame(layers, tilesets, map_w, map_h, tile_w, tile_h, anim_frame=0,
                 hidden_layers=(), bg=(0, 0, 0, 0)):
    """瓦片层 + 图块对象层渲染；瓦片底边贴格底、对象按官方规则(缩放+底部对齐)；
    hidden_layers 为图层索引集合；局部混合结果与原全图 alpha_composite 等价"""
    canvas = Image.new("RGBA", (map_w * tile_w, map_h * tile_h), bg)
    for idx, layer in enumerate(layers):
        if not layer["visible"] or idx in hidden_layers:
            continue
        if layer["type"] == "object":
            # 图块对象层：官方行为 = 瓦片缩放到对象宽高 + 底部对齐（对象 y 是瓦片底边）
            for obj in layer["objects"]:
                gid = obj["gid"]
                ts_idx = local_id = None
                for i, ts in enumerate(tilesets):
                    if ts["gid_start"] <= gid < ts["gid_end"]:
                        ts_idx, local_id = i, gid - ts["gid_start"]
                        break
                if ts_idx is None:
                    continue
                tile_img = _tile_image(tilesets[ts_idx], local_id, anim_frame)
                if not tile_img:
                    continue
                ow = int(obj.get("width") or tile_img.width)
                oh = int(obj.get("height") or tile_img.height)
                if (ow, oh) != tile_img.size:
                    tile_img = tile_img.resize((ow, oh), Image.NEAREST)
                px = int(obj["x"] + 0.5)          # 四舍五入(官方行为，round 是银行家舍入)
                py = int(obj["y"] + 0.5) - oh   # bottom 对齐：顶边 = y - 高度
                w, h = tile_img.size
                x0, y0 = max(px, 0), max(py, 0)
                x1, y1 = min(px + w, canvas.width), min(py + h, canvas.height)
                if x1 <= x0 or y1 <= y0:
                    continue
                box = (x0, y0, x1, y1)
                tile_part = tile_img.crop((x0 - px, y0 - py, x1 - px, y1 - py))
                region = canvas.crop(box)
                blended = Image.alpha_composite(region, tile_part)
                canvas.paste(blended, box)
            continue
        for row_idx, row in enumerate(layer["tiles"]):
            for col_idx, gid in enumerate(row):
                if gid == 0:
                    continue
                ts_idx = local_id = None
                for i, ts in enumerate(tilesets):
                    if ts["gid_start"] <= gid < ts["gid_end"]:
                        ts_idx, local_id = i, gid - ts["gid_start"]
                        break
                if ts_idx is None:
                    continue
                tile_img = _tile_image(tilesets[ts_idx], local_id, anim_frame)
                if not tile_img:
                    continue
                px = col_idx * tile_w
                py = row_idx * tile_h + tile_h - tile_img.height  # 底边贴格底
                w, h = tile_img.size
                # 局部混合：只处理瓦片覆盖区域（越界部分与 paste 裁剪等价）
                x0, y0 = max(px, 0), max(py, 0)
                x1, y1 = min(px + w, canvas.width), min(py + h, canvas.height)
                if x1 <= x0 or y1 <= y0:
                    continue
                box = (x0, y0, x1, y1)
                tile_part = tile_img.crop((x0 - px, y0 - py, x1 - px, y1 - py))
                region = canvas.crop(box)
                blended = Image.alpha_composite(region, tile_part)
                canvas.paste(blended, box)
    return canvas


# ---------- 导出 ----------

def _to_transparent_palette(img, transparent_idx=255):
    """RGBA -> P 模式 GIF 帧：alpha<128 的像素统一映射到透明索引，避免 Pillow 丢透明"""
    img = img.convert("RGBA")
    alpha = img.getchannel("A")
    p = img.convert("P", palette=Image.ADAPTIVE, colors=255)  # 留 1 个索引给透明
    mask = alpha.point(lambda a: 255 if a < 128 else 0)       # 透明区域掩码
    p.paste(transparent_idx, mask=mask)                        # 透明区像素改为透明索引
    p.info["transparency"] = transparent_idx
    return p


def export(tmx_name, mode, frames, frame_ms, scale, hidden_layers, bg=DEFAULT_BG, out_stem=None):
    tmx_path = os.path.join(TILED_DIR, tmx_name + ".tmx")
    tree = ET.parse(tmx_path)
    root = tree.getroot()
    map_w, map_h = int(root.get("width")), int(root.get("height"))
    tile_w, tile_h = int(root.get("tilewidth")), int(root.get("tileheight"))
    tilesets = load_tilesets(root, tile_w, tile_h)
    layers = parse_layers(root)
    auto_frames = compute_cycle(tilesets, frame_ms)
    bg_rgba = BG_MAP.get(bg, BG_MAP[DEFAULT_BG])
    if mode == "png":
        frame = render_frame(layers, tilesets, map_w, map_h, tile_w, tile_h, 0, hidden_layers, bg_rgba)
        out_name = (f"{tmx_name}_{out_stem}" if out_stem else f"{tmx_name}_单帧") + ".png"
        out_path = os.path.join(GIF_DIR, out_name)
        if scale > 1:
            frame = frame.resize((frame.width * scale, frame.height * scale), Image.NEAREST)
        frame.save(out_path)
        return {"url": "/files/" + out_name, "path": out_path, "frames": 1,
                "auto_frames": auto_frames, "seconds": 0}
    # GIF 模式
    frame_count = frames if frames and frames > 0 else auto_frames
    out_name = (f"{tmx_name}_{out_stem}" if out_stem else f"{tmx_name}_动画") + ".gif"
    out_path = os.path.join(GIF_DIR, out_name)
    imgs = []
    for i in range(frame_count):
        f = render_frame(layers, tilesets, map_w, map_h, tile_w, tile_h, i, hidden_layers, bg_rgba)
        if scale > 1:
            f = f.resize((f.width * scale, f.height * scale), Image.NEAREST)
        imgs.append(f)
    if bg == "transparent":
        prepared = [_to_transparent_palette(f) for f in imgs]
    else:
        prepared = [f.convert("RGB") for f in imgs]
    prepared[0].save(out_path, save_all=True, append_images=prepared[1:],
                     duration=frame_ms, loop=0, disposal=2)
    return {"url": "/files/" + out_name, "path": out_path, "frames": frame_count,
            "auto_frames": auto_frames,
            "seconds": round(frame_count * frame_ms / 1000, 2)}


def map_info(tmx_name):
    tmx_path = os.path.join(TILED_DIR, tmx_name + ".tmx")
    if not os.path.exists(tmx_path):
        return None
    tree = ET.parse(tmx_path)
    root = tree.getroot()
    tile_w, tile_h = int(root.get("tilewidth")), int(root.get("tileheight"))
    tilesets = load_tilesets(root, tile_w, tile_h)
    layers = parse_layers(root)
    animations = []
    for ts in tilesets:
        for tid, frames in ts["animations"].items():
            animations.append({
                "tileset": ts["name"],
                "tile": tid,
                "frames": len(frames),
                "duration": frames[0].get("duration", DEFAULT_FRAME_MS),
            })
    return {
        "layers": [{"name": l["name"], "visible": l["visible"],
                    "type": l["type"], "index": i}
                   for i, l in enumerate(layers)],
        "animations": animations,
        "auto_frames": compute_cycle(tilesets),
        "map_w": int(root.get("width")), "map_h": int(root.get("height")),
        "tile_w": tile_w, "tile_h": tile_h,
    }


# ---------- HTTP 服务 ----------

def load_map(tmx_name):
    """解析地图，返回全部渲染所需数据"""
    tmx_path = os.path.join(TILED_DIR, tmx_name + ".tmx")
    root = ET.parse(tmx_path).getroot()
    map_w, map_h = int(root.get("width")), int(root.get("height"))
    tile_w, tile_h = int(root.get("tilewidth")), int(root.get("tileheight"))
    tilesets = load_tilesets(root, tile_w, tile_h)
    layers = parse_layers(root)
    return root, map_w, map_h, tile_w, tile_h, tilesets, layers


def render_preview(tmx_name, frame=0, scale=2, bg=DEFAULT_BG, hidden_layers=()):
    """渲染单帧预览（不落正式产物），返回 PIL Image；scale 支持小数"""
    _, map_w, map_h, tile_w, tile_h, tilesets, layers = load_map(tmx_name)
    bg_rgba = BG_MAP.get(bg, BG_MAP[DEFAULT_BG])
    img = render_frame(layers, tilesets, map_w, map_h, tile_w, tile_h, frame, hidden_layers, bg_rgba)
    if scale > 1:
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.NEAREST)
    return img


def export_batch(tmx_name, tasks):
    """批量导出多个任务，互不干扰，返回逐个结果"""
    results = []
    for t in tasks:
        try:
            r = export(
                tmx_name, t.get("mode", "gif"),
                int(t.get("frames", 0)), int(t.get("frame_ms", DEFAULT_FRAME_MS)),
                int(t.get("scale", 1)), t.get("hidden_layers", []),
                t.get("bg", DEFAULT_BG), t.get("out_stem"))
            results.append({"ok": True, **r})
        except Exception as e:
            results.append({"ok": False, "error": str(e)})
    return results

HTML_PATH = os.path.join(BASE_DIR, "GIF导出工具.html")

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/" or u.path == "/index.html":
            if os.path.exists(HTML_PATH):
                with open(HTML_PATH, "r", encoding="utf-8") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            else:
                self._send(404, "界面文件缺失: GIF导出工具.html")
            return
        if u.path == "/api/maps":
            self._send(200, json.dumps({"maps": list_maps()}, ensure_ascii=False))
            return
        if u.path == "/api/info":
            qs = parse_qs(u.query)
            name = (qs.get("map") or [""])[0]
            info = map_info(name)
            if info is None:
                self._send(404, json.dumps({"error": "地图不存在"}))
            else:
                self._send(200, json.dumps(info, ensure_ascii=False))
            return
        if u.path == "/api/preview":
            qs = parse_qs(u.query)
            name = (qs.get("map") or [""])[0]
            frame = int((qs.get("frame") or ["0"])[0])
            scale = min(int((qs.get("scale") or ["2"])[0]), 8)
            bg = (qs.get("bg") or [DEFAULT_BG])[0]
            hidden = [int(x) for x in (qs.get("hidden") or [""])[0].split(",") if x]
            try:
                info = map_info(name)
                # 预览自动限尺寸：最大边 512px
                base_side = max(info["map_w"] * info["tile_w"], info["map_h"] * info["tile_h"])
                if base_side * scale > 512:
                    scale = 512 / base_side
                img = render_preview(name, frame, scale, bg, hidden)
                buf = io.BytesIO()
                img.save(buf, "PNG")
                self._send(200, buf.getvalue(), "image/png")
            except Exception as e:
                self._send(500, json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
            return
        if u.path == "/api/preview-gif":
            qs = parse_qs(u.query)
            name = (qs.get("map") or [""])[0]
            scale = min(int((qs.get("scale") or ["2"])[0]), 8)
            bg = (qs.get("bg") or [DEFAULT_BG])[0]
            hidden = [int(x) for x in (qs.get("hidden") or [""])[0].split(",") if x]
            try:
                info = map_info(name)
                auto = info["auto_frames"]
                # 预览自动限尺寸：最大边 512px（大地图自动降缩放，加速渲染）
                base_side = max(info["map_w"] * info["tile_w"], info["map_h"] * info["tile_h"])
                if base_side * scale > 512:
                    scale = 512 / base_side
                imgs = [render_preview(name, i, scale, bg, hidden) for i in range(auto)]
                out = os.path.join(TEMP_DIR, f"_preview_{name}.gif")
                if bg == "transparent":
                    prepared = [_to_transparent_palette(f) for f in imgs]
                else:
                    prepared = [f.convert("RGB") for f in imgs]
                prepared[0].save(out, save_all=True, append_images=prepared[1:],
                                 duration=DEFAULT_FRAME_MS, loop=0, disposal=2)
                self._send(200, json.dumps(
                    {"ok": True, "url": "/files/_preview_" + name + ".gif",
                     "frames": auto, "size": prepared[0].size}, ensure_ascii=False))
            except Exception as e:
                self._send(500, json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
            return
        if u.path.startswith("/files/"):
            rel = u.path[len("/files/"):]
            for d in (GIF_DIR, TEMP_DIR):
                p = os.path.join(d, os.path.basename(rel))
                if os.path.exists(p):
                    ext = os.path.splitext(p)[1].lower()
                    ctype = {"png": "image/png", "gif": "image/gif"}.get(ext, "application/octet-stream")
                    with open(p, "rb") as f:
                        self._send(200, f.read(), ctype)
                    return
            self._send(404, "文件不存在")
            return
        self._send(404, "Not Found", "text/plain")

    def do_POST(self):
        u = urlparse(self.path)
        if u.path not in ("/api/export", "/api/export-batch"):
            self._send(404, "Not Found", "text/plain")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            os.makedirs(GIF_DIR, exist_ok=True)
            os.makedirs(TEMP_DIR, exist_ok=True)
            if u.path == "/api/export-batch":
                results = export_batch(body["map"], body.get("tasks", []))
                self._send(200, json.dumps({"ok": True, "results": results}, ensure_ascii=False))
                return
            result = export(
                body["map"],
                body.get("mode", "gif"),
                int(body.get("frames", 0)),
                int(body.get("frame_ms", DEFAULT_FRAME_MS)),
                int(body.get("scale", 1)),
                body.get("hidden_layers", []),
                body.get("bg", DEFAULT_BG),
            )
            self._send(200, json.dumps({"ok": True, **result}, ensure_ascii=False))
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send(500, json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))


def main():
    os.makedirs(GIF_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("GIF 导出工具已启动：http://127.0.0.1:%d" % PORT)
    print("按 Ctrl+C 停止")
    webbrowser.open("http://127.0.0.1:%d" % PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
