#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 map01.tmx 渲染为高清地图图。
- 静态图: 6 倍放大 (4800x4800), 最近邻无模糊
- 动态 GIF: 水面动画循环 (原尺寸 800x800)
"""
import os
import base64
import struct
import xml.etree.ElementTree as ET
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPS = os.path.join(ROOT, "maps")
TMX = os.path.join(MAPS, "map01.tmx")
OUT_PNG = os.path.join(MAPS, "map01_preview_6x.png")
OUT_GIF = os.path.join(MAPS, "map01_water_anim.gif")

SCALE = 6  # 静态图放大倍数


def load_tilesets(tmx_root):
    """读取所有外部 tileset (.tsx) 配置，返回 firstgid -> 信息"""
    tilesets = {}
    for ts in tmx_root.findall("tileset"):
        firstgid = int(ts.get("firstgid"))
        source = ts.get("source")
        if source:
            # 外部 tsx
            tsx_path = os.path.normpath(os.path.join(MAPS, source))
            t = ET.parse(tsx_path).getroot()
        else:
            t = ts
        tw = int(t.get("tilewidth", "16"))
        th = int(t.get("tileheight", "16"))
        columns = int(t.get("columns", "1"))
        tilecount = int(t.get("tilecount", "1"))
        img_el = t.find("image")
        img_src = img_el.get("source")
        img_path = os.path.normpath(os.path.join(MAPS, img_src))
        tilesets[firstgid] = {
            "image": img_path,
            "tw": tw, "th": th,
            "columns": columns,
            "tilecount": tilecount,
        }
    return tilesets


def get_tile_image(tilesets, gid, pil_cache):
    """根据 GID 返回 (PIL Image of the tile, flip flags)"""
    # 解析翻转位
    flipped_h = bool(gid & 0x80000000)
    flipped_v = bool(gid & 0x40000000)
    flipped_d = bool(gid & 0x20000000)
    pure = gid & 0x1FFFFFFF

    # 找到对应 tileset
    best_fg = -1
    for fg in tilesets:
        if pure >= fg and fg > best_fg:
            best_fg = fg
    if best_fg == -1:
        return None, False, False, False
    info = tilesets[best_fg]
    local = pure - best_fg
    if local >= info["tilecount"]:
        return None, flipped_h, flipped_v, flipped_d

    if info["image"] not in pil_cache:
        pil_cache[info["image"]] = Image.open(info["image"]).convert("RGBA")
    sheet = pil_cache[info["image"]]

    col = local % info["columns"]
    row = local // info["columns"]
    x = col * info["tw"]
    y = row * info["th"]
    tile = sheet.crop((x, y, x + info["tw"], y + info["th"]))

    if flipped_h:
        tile = tile.transpose(Image.FLIP_LEFT_RIGHT)
    if flipped_v:
        tile = tile.transpose(Image.FLIP_TOP_BOTTOM)
    if flipped_d:
        tile = tile.transpose(Image.TRANSPOSE)
    return tile, flipped_h, flipped_v, flipped_d


def parse_layers(tmx_root):
    """返回 [(name, [[gid,...],...]), ...] 按 TMX 顺序"""
    layers = []
    for layer in tmx_root.findall("layer"):
        name = layer.get("name")
        w = int(layer.get("width"))
        h = int(layer.get("height"))
        data_el = layer.find("data")
        encoding = data_el.get("encoding")
        if encoding == "csv":
            text = data_el.text.strip()
            flat = [int(v) for v in text.replace("\n", ",").split(",") if v.strip() != ""]
        elif encoding == "base64":
            raw = base64.b64decode(data_el.text.strip())
            flat = list(struct.unpack("<%di" % (len(raw) // 4), raw))
        else:
            flat = []
        grid = [flat[i * w:(i + 1) * w] for i in range(h)]
        layers.append((name, grid, w, h))
    return layers


def render_static(layers, tilesets, pil_cache, map_w, map_h):
    tw = 16
    th = 16
    W = map_w * tw * SCALE
    H = map_h * th * SCALE
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    for (name, grid, w, h) in layers:
        if name == "角色":  # 角色是动态节点，不画在地图上
            continue
        print("  渲染图层:", name)
        for y in range(h):
            for x in range(w):
                gid = grid[y][x]
                if gid == 0:
                    continue
                tile, _, _, _ = get_tile_image(tilesets, gid, pil_cache)
                if tile is None:
                    continue
                big = tile.resize((tw * SCALE, th * SCALE), Image.NEAREST)
                canvas.alpha_composite(big, (x * tw * SCALE, y * th * SCALE))
    return canvas


def render_water_gif(layers, tilesets, pil_cache, map_w, map_h):
    """为水面图层做动画 GIF: 用 water-ani 贴图连续帧循环"""
    # 找到 water-ani tileset (firstgid=811)
    water_fg = 811
    info = tilesets.get(water_fg)
    if info is None:
        print("  未找到 water-ani tileset, 跳过 GIF")
        return
    # 找水面图层
    water_grid = None
    for (name, grid, w, h) in layers:
        if name == "水":
            water_grid = grid
            break
    if water_grid is None:
        print("  未找到 水 图层, 跳过 GIF")
        return

    tw, th = info["tw"], info["th"]
    columns = info["columns"]
    tilecount = info["tilecount"]
    sheet = Image.open(info["image"]).convert("RGBA")

    frames = min(7, tilecount)  # 取前7帧做循环
    base_tiles = []
    for f in range(frames):
        col = f % columns
        row = f // columns
        x = col * tw
        y = row * th
        base_tiles.append(sheet.crop((x, y, x + tw, y + th)))

    W = map_w * tw
    H = map_h * th
    gif_frames = []
    for f in range(frames):
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for y in range(map_h):
            for x in range(map_w):
                gid = water_grid[y][x]
                if gid == 0:
                    continue
                # 水面格用动画帧替换
                big = base_tiles[f].resize((tw, th), Image.NEAREST)
                canvas.alpha_composite(big, (x * tw, y * th))
        # 转 RGB 以兼容 GIF
        rgb = Image.new("RGB", (W, H), (30, 40, 60))
        rgb.paste(canvas, mask=canvas.split()[3])
        gif_frames.append(rgb)

    gif_frames[0].save(
        OUT_GIF,
        save_all=True,
        append_images=gif_frames[1:],
        duration=120,
        loop=0,
        disposal=2,
    )
    print("  GIF 已保存:", OUT_GIF, "帧数:", frames)


def main():
    print("解析 TMX:", TMX)
    tmx = ET.parse(TMX).getroot()
    map_w = int(tmx.get("width"))
    map_h = int(tmx.get("height"))
    print("地图尺寸: %dx%d 格, 每格 16px" % (map_w, map_h))

    tilesets = load_tilesets(tmx)
    print("tileset 数量:", len(tilesets))
    pil_cache = {}

    layers = parse_layers(tmx)
    print("图层数量:", len(layers))

    print("\n[1/2] 渲染静态 6x 高清图 ...")
    canvas = render_static(layers, tilesets, pil_cache, map_w, map_h)
    canvas.save(OUT_PNG)
    print("  已保存:", OUT_PNG, "尺寸:", canvas.size)

    print("\n[2/2] 渲染水面动画 GIF ...")
    render_water_gif(layers, tilesets, pil_cache, map_w, map_h)

    print("\n完成!")


if __name__ == "__main__":
    main()
