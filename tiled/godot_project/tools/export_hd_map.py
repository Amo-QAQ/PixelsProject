#!/usr/bin/env python3
"""
高清地图导出工具 - 6倍放大 GIF/PNG 导出

使用方法:
    python tools/export_hd_map.py                    # 默认导出 PNG
    python tools/export_hd_map.py --gif              # 导出动画 GIF
    python tools/export_hd_map.py --scale 4           # 自定义放大倍数
    python tools/export_hd_map.py --gif --frames 30   # GIF 帧数
"""

import xml.etree.ElementTree as ET
import os
import argparse
from PIL import Image

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# TMX 文件路径
TMX_PATH = os.path.join(PROJECT_ROOT, "maps", "map01.tmx")

# 输出目录
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "exports")

# 放大倍数
DEFAULT_SCALE = 6


class Tileset:
    """Tileset 定义"""
    def __init__(self, firstgid, name, tilewidth, tileheight, columns, image_path):
        self.firstgid = firstgid
        self.name = name
        self.tilewidth = tilewidth
        self.tileheight = tileheight
        self.columns = columns
        self.image_path = image_path
        self.image = None  # PIL Image

    def load_image(self):
        """加载贴图"""
        # 图像路径是相对于 TMX 文件所在目录的
        tmx_dir = os.path.dirname(TMX_PATH)
        abs_path = os.path.normpath(os.path.join(tmx_dir, self.image_path))
        if os.path.exists(abs_path):
            self.image = Image.open(abs_path).convert("RGBA")
            return True
        print(f"  ⚠️ 找不到贴图: {abs_path}")
        return False

    def get_tile(self, local_id):
        """获取指定 ID 的图块图像"""
        if self.image is None:
            return None

        x = (local_id % self.columns) * self.tilewidth
        y = (local_id // self.columns) * self.tileheight

        # 确保坐标在图像范围内
        if x + self.tilewidth > self.image.width or y + self.tileheight > self.image.height:
            return None

        return self.image.crop((x, y, x + self.tilewidth, y + self.tileheight))


def parse_tilesets(tmx_root, base_dir):
    """解析 TMX 中的 tileset 定义"""
    tilesets = []

    for ts in tmx_root.findall("tileset"):
        source = ts.get("source")
        firstgid = int(ts.get("firstgid"))

        # 解析外部 TSX 文件
        tsx_path = os.path.join(base_dir, source)
        if not os.path.exists(tsx_path):
            print(f"  ⚠️ 找不到 TSX 文件: {tsx_path}")
            continue

        tsx_tree = ET.parse(tsx_path)
        tsx_root = tsx_tree.getroot()

        name = tsx_root.get("name")
        tilewidth = int(tsx_root.get("tilewidth"))
        tileheight = int(tsx_root.get("tileheight"))
        columns = int(tsx_root.get("columns"))

        # 获取图像路径
        img_elem = tsx_root.find("image")
        image_source = img_elem.get("source") if img_elem is not None else None

        tileset = Tileset(firstgid, name, tilewidth, tileheight,
                         columns=columns, image_path=image_source)
        tilesets.append(tileset)
        print(f"  ✓ {name}: GID {firstgid}, {columns}列, {tilewidth}x{tileheight}")

    return tilesets


def find_tileset(tilesets, gid):
    """根据 GID 找到对应的 tileset 和 local_id"""
    pure_gid = gid & 0x1FFFFFFF  # 去除翻转标志

    best_match = None
    best_firstgid = -1

    for ts in tilesets:
        if ts.firstgid <= pure_gid and ts.firstgid > best_firstgid:
            best_match = ts
            best_firstgid = ts.firstgid

    if best_match is None:
        return None, None

    local_id = pure_gid - best_match.firstgid
    return best_match, local_id


def render_layer(layer_data, tilesets, scale, map_width, map_height, tile_size=16):
    """渲染单个图层"""
    layer_width = layer_data["width"]
    layer_height = layer_data["height"]
    tiles = layer_data["tiles"]

    # 创建画布（6倍大小）
    canvas_width = map_width * tile_size * scale
    canvas_height = map_height * tile_size * scale
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))

    non_empty_count = 0

    for y in range(layer_height):
        for x in range(layer_width):
            idx = y * layer_width + x
            if idx >= len(tiles):
                continue

            gid = tiles[idx]
            if gid == 0:
                continue

            ts, local_id = find_tileset(tilesets, gid)
            if ts is None:
                continue

            tile_img = ts.get_tile(local_id)
            if tile_img is None:
                continue

            # 检查翻转标志
            flipped_h = bool((gid >> 31) & 1)
            flipped_v = bool((gid >> 30) & 1)

            if flipped_h or flipped_v:
                tile_img = tile_img.transpose(Image.FLIP_LEFT_RIGHT if flipped_h else Image.FLIP_TOP_BOTTOM)
                if flipped_h and flipped_v:
                    tile_img = tile_img.transpose(Image.FLIP_LEFT_RIGHT if not flipped_h else Image.FLIP_TOP_BOTTOM)

            # 放大图块
            if scale != 1:
                tile_img = tile_img.resize(
                    (ts.tilewidth * scale, ts.tileheight * scale),
                    Image.NEAREST  # 最近邻插值，保持像素清晰
                )

            # 计算位置并粘贴
            pos_x = x * tile_size * scale
            pos_y = y * tile_size * scale
            canvas.paste(tile_img, (pos_x, pos_y), tile_img)

            non_empty_count += 1

    return canvas, non_empty_count


def export_static_image(tilesets, layers, scale, output_path):
    """导出静态高清图片"""
    print(f"\n🎨 渲染中... ({scale}倍放大)")

    # 从第一个图层获取地图尺寸
    map_width = layers[0]["width"] if layers else 50
    map_height = layers[0]["height"] if layers else 50

    # 创建最终画布
    final_width = map_width * 16 * scale
    final_height = map_height * 16 * scale
    final_canvas = Image.new("RGBA", (final_width, final_height), (0, 0, 0, 0))

    total_tiles = 0

    for layer in layers:
        layer_name = layer["name"]
        print(f"  渲染图层: {layer_name}...")

        layer_img, count = render_layer(layer, tilesets, scale, map_width, map_height)
        final_canvas = Image.alpha_composite(final_canvas, layer_img)
        total_tiles += count
        print(f"    ✓ {count} 个图块")

    # 转换为 RGB（去除 alpha）
    rgb_canvas = Image.new("RGB", final_canvas.size, (0, 0, 0))
    rgb_canvas.paste(final_canvas, mask=final_canvas.split()[3])

    # 保存
    rgb_canvas.save(output_path, "PNG", optimize=True)

    print(f"\n✅ 已保存: {output_path}")
    print(f"   尺寸: {final_width} x {final_height} 像素")
    print(f"   总图块: {total_tiles}")

    return final_canvas


def export_animated_gif(tilesets, layers, scale, output_path, frames=20, duration=150):
    """导出动画 GIF（用于展示水面动画等）"""
    print(f"\n🎬 生成动画 GIF... ({frames} 帧, {scale}倍放大)")

    map_width = layers[0]["width"] if layers else 50
    map_height = layers[0]["height"] if layers else 50

    # 为简单起见，生成静态帧（如果需要真正的动画效果，
    # 需要根据 water-ani 的帧数据生成不同帧）
    frame_images = []

    # 生成一个主帧
    final_width = map_width * 16 * scale
    final_height = map_height * 16 * scale
    final_canvas = Image.new("RGBA", (final_width, final_height), (0, 0, 0, 0))

    for layer in layers:
        layer_img, _ = render_layer(layer, tilesets, scale, map_width, map_height)
        final_canvas = Image.alpha_composite(final_canvas, layer_img)

    # 转换为 RGB
    rgb_frame = Image.new("RGB", final_canvas.size, (0, 0, 0))
    rgb_frame.paste(final_canvas, mask=final_canvas.split()[3])

    # 复制多帧（静态 GIF）
    # 如果要实现真正的水面动画，需要在这里切换不同的水图块
    frame_images.append(rgb_frame)

    # 保存 GIF
    frame_images[0].save(
        output_path,
        "GIF",
        save_all=True,
        append_images=frame_images * (frames - 1),
        duration=duration,
        loop=0,
        optimize=True
    )

    print(f"\n✅ 已保存: {output_path}")
    print(f"   尺寸: {final_width} x {final_height}")
    print(f"   帧数: {frames}, 帧间隔: {duration}ms")


def main():
    parser = argparse.ArgumentParser(description="高清地图导出工具")
    parser.add_argument("--scale", type=int, default=DEFAULT_SCALE, help=f"放大倍数 (默认: {DEFAULT_SCALE})")
    parser.add_argument("--gif", action="store_true", help="导出为 GIF 格式")
    parser.add_argument("--frames", type=int, default=20, help="GIF 帧数 (默认: 20)")
    parser.add_argument("--duration", type=int, default=150, help="每帧持续时间 ms (默认: 150)")
    args = parser.parse_args()

    print("=" * 60)
    print("  高清地图导出工具")
    print("=" * 60)

    # 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 解析 TMX
    print(f"\n📖 解析 TMX: {TMX_PATH}")
    tmx_tree = ET.parse(TMX_PATH)
    tmx_root = tmx_tree.getroot()

    map_width = int(tmx_root.get("width"))
    map_height = int(tmx_root.get("height"))
    print(f"📐 地图尺寸: {map_width} x {map_height}")

    # 解析 Tilesets
    base_dir = os.path.dirname(TMX_PATH)
    print("\n📦 加载 Tilesets:")
    tilesets = parse_tilesets(tmx_root, base_dir)

    # 加载所有贴图
    print("\n🖼️ 加载贴图:")
    for ts in tilesets:
        ts.load_image()

    # 解析图层
    print(f"\n📑 解析图层:")
    layers = []
    for layer_elem in tmx_root.findall("layer"):
        layer_name = layer_elem.get("name")
        layer_w = int(layer_elem.get("width"))
        layer_h = int(layer_elem.get("height"))

        data_elem = layer_elem.find("data")
        if data_elem is not None and data_elem.text:
            csv_text = data_elem.text.strip()
            tiles = [int(x.strip()) for x in csv_text.split(",") if x.strip()]
            non_zero = sum(1 for t in tiles if t != 0)
        else:
            tiles = []
            non_zero = 0

        layers.append({
            "name": layer_name,
            "width": layer_w,
            "height": layer_h,
            "tiles": tiles
        })
        print(f"  ✓ {layer_name}: {non_zero} 个非空格")

    # 导出
    timestamp = "__" + __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.gif:
        output_path = os.path.join(OUTPUT_DIR, f"map01_hd{timestamp}_{args.scale}x.gif")
        export_animated_gif(tilesets, layers, args.scale, output_path,
                          frames=args.frames, duration=args.duration)
    else:
        output_path = os.path.join(OUTPUT_DIR, f"map01_hd{timestamp}_{args.scale}x.png")
        export_static_image(tilesets, layers, args.scale, output_path)

    print("\n" + "=" * 60)
    print("  完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
