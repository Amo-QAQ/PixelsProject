# -*- coding: utf-8 -*-
"""
一键导出预览 GIF 工具（手动操作版）
用法：
    python export_preview.py 预览01
    python export_preview.py 预览02
    python export_preview.py map01_预览

流程：
    1. 用 Tiled 官方 tmxrasterizer 渲染第 0 帧作为基准
    2. 自研渲染器渲染第 0 帧，逐像素对比（差异必须为 0）
    3. 通过后才生成三件套（4x GIF / 原尺寸 GIF / 静态 PNG）
    4. 验证不过则中止并给出差异位置（不覆盖已有产物）

依赖：Python + Pillow（本机已有），Tiled 安装目录的 tmxrasterizer.exe
"""
import json
import math
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from PIL import Image

TILED_DIR = r"E:\My_work\PixelsProject\Aseprite\tiled"
OUTPUT_DIR = os.path.join(TILED_DIR, "GIF")       # 交付产物统一放这里
TEMP_DIR = os.path.join(TILED_DIR, "_临时")        # 测试/诊断临时文件统一放这里
TMXRASTERIZER = r"C:\Program Files\Tiled\tmxrasterizer.exe"
BG_COLOR = (135, 205, 225, 255)  # 浅蓝底
SCALE = 4                         # 4x 最近邻放大
FRAME_DURATION_MS = 100           # 每帧时长
DIFF_THRESHOLD = (10, 10, 10, 30) # 通道差阈值 / alpha 差阈值


def pick_map(name):
    """地图名 -> tmx 绝对路径"""
    candidates = [name, name + ".tmx"]
    for c in candidates:
        p = os.path.join(TILED_DIR, c)
        if os.path.exists(p):
            return p
    print(f"[错误] 找不到地图：{name}（期望 {TILED_DIR}\\{name}.tmx）")
    print("可选地图：预览01 / 预览02 / map01_预览")
    sys.exit(1)


def load_tilesets(root, tile_w, tile_h):
    tilesets = []
    for ts_elem in root.findall("tileset"):
        firstgid = int(ts_elem.get("firstgid"))
        tsj_path = os.path.join(TILED_DIR, ts_elem.get("source"))
        tsj_dir = os.path.dirname(tsj_path)
        with open(tsj_path, "r", encoding="utf-8") as f:
            tsj = json.load(f)
        name = tsj.get("name", "")
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
                    else:
                        print(f"  [警告] 瓦片图片缺失: {img_path}")
        animations = {}
        for tile_info in tsj.get("tiles", []):
            if "animation" in tile_info:
                animations[tile_info["id"]] = tile_info["animation"]
        tilesets.append({
            "firstgid": firstgid, "name": name, "spritesheet": spritesheet,
            "tile_images": tile_images, "columns": columns,
            "tilecount": tilecount, "tile_w": ts_w, "tile_h": ts_h,
            "animations": animations,
        })
    for i, ts in enumerate(tilesets):
        start = ts["firstgid"]
        end = tilesets[i + 1]["firstgid"] if i + 1 < len(tilesets) else start + ts["tilecount"]
        ts["gid_start"] = start
        ts["gid_end"] = end
    return tilesets


def parse_layers(root):
    layers = []
    for child in root:
        if child.tag != "layer":
            continue
        visible = child.get("visible", "1") != "0"
        csv_data = child.find("data").text.strip()
        tiles = []
        for row in csv_data.split("\n"):
            row = row.strip().rstrip(",")
            if row:
                tiles.append([int(x.strip()) for x in row.split(",")])
        layers.append({"name": child.get("name"), "visible": visible, "tiles": tiles})
    return layers


def compute_cycle(tilesets):
    anim_lengths = set()
    frame_ms = FRAME_DURATION_MS
    for ts in tilesets:
        for _, frames in ts["animations"].items():
            anim_lengths.add(len(frames))
            if frames:
                frame_ms = frames[0].get("duration", frame_ms)
    total = 1
    for n in anim_lengths:
        total = total * n // math.gcd(total, n)
    return total, frame_ms


def render_frame(layers, tilesets, map_w, map_h, tile_w, tile_h, anim_frame=0):
    """按 Tiled 规则渲染：瓦片底边贴格底 + 逐瓦片 alpha 混合"""
    canvas = Image.new("RGBA", (map_w * tile_w, map_h * tile_h), (0, 0, 0, 0))
    for layer in layers:
        if not layer["visible"]:
            continue
        for row_idx, row in enumerate(layer["tiles"]):
            for col_idx, gid in enumerate(row):
                if gid == 0:
                    continue
                ts_idx = None
                local_id = None
                for i, ts in enumerate(tilesets):
                    if ts["gid_start"] <= gid < ts["gid_end"]:
                        ts_idx, local_id = i, gid - ts["gid_start"]
                        break
                if ts_idx is None:
                    continue
                ts = tilesets[ts_idx]
                tile_img = _tile_image(ts, local_id, anim_frame)
                if not tile_img:
                    continue
                px = col_idx * tile_w
                py = row_idx * tile_h + tile_h - tile_img.height  # 底边贴格底
                overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
                overlay.paste(tile_img, (px, py))
                canvas = Image.alpha_composite(canvas, overlay)
    return canvas


def _tile_image(ts, local_id, anim_frame):
    if local_id in ts["animations"]:
        frames = ts["animations"][local_id]
        actual = frames[anim_frame % len(frames)]["tileid"]
    else:
        actual = local_id
    if ts["spritesheet"] is None:
        if actual in ts["tile_images"]:
            im, _, _, _, _ = ts["tile_images"][actual]
            return im.copy()
        return None
    cols = ts["columns"] or 1
    tx = (actual % cols) * ts["tile_w"]
    ty = (actual // cols) * ts["tile_h"]
    return ts["spritesheet"].crop((tx, ty, tx + ts["tile_w"], ty + ts["tile_h"]))


def official_frame0(tmx_path):
    """用 tmxrasterizer 渲染官方第 0 帧"""
    os.makedirs(TEMP_DIR, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False, dir=TEMP_DIR)
    tmp.close()
    out_path = tmp.name
    result = subprocess.run(
        [TMXRASTERIZER, "--no-smoothing", tmx_path, out_path],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if not os.path.exists(out_path) or result.returncode != 0:
        print("[错误] tmxrasterizer 渲染失败：", result.stderr.strip()[:300])
        sys.exit(1)
    img = Image.open(out_path).convert("RGBA")
    os.unlink(out_path)
    return img


def pixel_diff(a, b, limit=20):
    """返回差异像素数与前 limit 个差异点"""
    pa, pb = a.load(), b.load()
    diff_count = 0
    samples = []
    for y in range(a.height):
        for x in range(a.width):
            t = pa[x, y]
            m = pb[x, y]
            if t[3] > 0 or m[3] > 0:
                if (abs(t[0] - m[0]) > DIFF_THRESHOLD[0] or abs(t[1] - m[1]) > DIFF_THRESHOLD[1]
                        or abs(t[2] - m[2]) > DIFF_THRESHOLD[2] or abs(t[3] - m[3]) > DIFF_THRESHOLD[3]):
                    diff_count += 1
                    if len(samples) < limit:
                        samples.append((x, y, t, m))
    return diff_count, samples


def compose_frames(frames, out_w, out_h):
    """浅蓝底 + 4x 最近邻"""
    result = []
    for canvas in frames:
        bg = Image.new("RGBA", canvas.size, BG_COLOR)
        bg.paste(canvas, (0, 0), canvas)
        result.append(bg.convert("RGB").resize((out_w, out_h), Image.NEAREST))
    return result


def main():
    if len(sys.argv) < 2:
        print("用法：python export_preview.py <地图名>  例：python export_preview.py 预览02")
        sys.exit(1)
    name = sys.argv[1]
    tmx_path = pick_map(name)
    print(f"地图：{os.path.basename(tmx_path)}")

    tree = ET.parse(tmx_path)
    root = tree.getroot()
    map_w = int(root.get("width")); map_h = int(root.get("height"))
    tile_w = int(root.get("tilewidth")); tile_h = int(root.get("tileheight"))

    tilesets = load_tilesets(root, tile_w, tile_h)
    layers = parse_layers(root)
    total_frames, frame_ms = compute_cycle(tilesets)
    print(f"循环：{total_frames} 帧 × {frame_ms}ms = {total_frames * frame_ms / 1000:.1f}s")

    # ---- 第 1 步：官方基准对比 ----
    print("[1/3] 官方基准对比（第 0 帧）...")
    official = official_frame0(tmx_path)
    my_frame0 = render_frame(layers, tilesets, map_w, map_h, tile_w, tile_h, 0)
    diff_count, samples = pixel_diff(official, my_frame0)
    if diff_count > 0:
        diff_img = os.path.join(TEMP_DIR, f"_diff_{name}.png")
        my_frame0.save(diff_img)
        print(f"[拦截] 第 0 帧与官方渲染差异 {diff_count} 像素，不导出！")
        for x, y, t, m in samples[:5]:
            print(f"  差异点 ({x},{y})：官方{t} vs 渲染{m}")
        print(f"  差异图已保存：{diff_img}")
        print("  请检查 tmx/tsj/资产后重试。")
        sys.exit(2)
    print("[1/3] 通过：与官方渲染完全一致")

    # ---- 第 2 步：渲染全部帧 ----
    print(f"[2/3] 渲染 {total_frames} 帧动画...")
    frames = [render_frame(layers, tilesets, map_w, map_h, tile_w, tile_h, fi)
              for fi in range(total_frames)]

    # ---- 第 3 步：出三件套 ----
    print("[3/3] 生成三件套...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_w, out_h = map_w * tile_w * SCALE, map_h * tile_h * SCALE
    big = compose_frames(frames, out_w, out_h)
    small = [f.resize((map_w * tile_w, map_h * tile_h), Image.NEAREST) for f in big]

    gif_big = os.path.join(OUTPUT_DIR, f"{name}.gif")
    gif_small = os.path.join(OUTPUT_DIR, f"{name}_小.gif")
    png_static = os.path.join(OUTPUT_DIR, f"{name}.png")

    big[0].save(gif_big, save_all=True, append_images=big[1:], duration=frame_ms, loop=0, optimize=True)
    small[0].save(gif_small, save_all=True, append_images=small[1:], duration=frame_ms, loop=0, optimize=True)
    big[0].save(png_static)

    print(f"完成：{gif_big}")
    print(f"     {gif_small}")
    print(f"     {png_static}")


if __name__ == "__main__":
    main()
