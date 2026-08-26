#!/usr/bin/env python3
"""
Tiled TMX → Godot 4 TileMapLayer 格式转换器
将旧版 TileMap（单节点多图层）转换为可编辑的 TileMapLayer（多节点）
"""

import xml.etree.ElementTree as ET
import base64
import struct
import re
import sys
from pathlib import Path


# TileSet 源映射 (TMX firstgid → Godot TileSet source index)
TILESET_MAPPING = {
    1: 0,      # terrainA → Terrain A
    41: 1,     # terrainB → Terrain B
    361: 2,    # terrainC → Terrain C
    811: 3,    # water-ani → Water
    979: 4,    # decorations_tilemap → Decorations
    1021: 5,   # Props → Outdoor Props
    1063: 6,   # house_A → House A
    1117: 7,   # house_B → House B
    1157: 8,   # tree → Tree
    1220: 9,   # crop → Crop
    1256: 10,  # 角色_F → Character
}

# 每个 tileset 的图块尺寸和列数
TILESET_INFO = {
    0: {"cols": 10, "rows": 4},     # terrainA: 10x4
    1: {"cols": 32, "rows": 10},    # terrainB: 32x10
    2: {"cols": 30, "rows": 15},    # terrainC: 30x15
    3: {"cols": 24, "rows": 7},     # water-ani: 24x7
    4: {"cols": 14, "rows": 3},     # decorations: 14x3
    5: {"cols": 7, "rows": 6},      # props: 7x6
    6: {"cols": 9, "rows": 6},      # house_A: 9x6
    7: {"cols": 5, "rows": 8},      # house_B: 5x8
    8: {"cols": 18, "rows": 3},     # tree: 18x3
    9: {"cols": 12, "rows": 6},     # crop: 12x6
    10: {"cols": 8, "rows": 4},     # 角色: 8x4
}


def parse_tmx(filepath):
    """解析 TMX 文件，返回图层数据"""
    tree = ET.parse(filepath)
    root = tree.getroot()

    width = int(root.get("width"))
    height = int(root.get("height"))

    # 收集所有 tileset 的 firstgid
    tilesets = []
    for ts in root.findall("tileset"):
        firstgid = int(ts.get("firstgid"))
        source = ts.get("source")
        tilesets.append({"firstgid": firstgid, "source": source})

    # 解析每个图层
    layers = []
    for layer in root.findall("layer"):
        name = layer.get("name")
        layer_width = int(layer.get("width"))
        layer_height = int(layer.get("height"))

        data_elem = layer.find("data")
        encoding = data_elem.get("encoding") if data_elem is not None else None

        if encoding == "csv":
            # CSV 编码
            csv_text = data_elem.text.strip()
            tiles = [int(x) for x in csv_text.split(",") if x.strip()]
        else:
            print(f"警告: 图层 '{name}' 使用不支持的编码: {encoding}")
            continue

        layers.append({
            "name": name,
            "width": layer_width,
            "height": layer_height,
            "tiles": tiles
        })

    return {
        "width": width,
        "height": height,
        "tilesets": tilesets,
        "layers": layers
}


def gid_to_tile_coords(gid):
    """
    将全局 GID 转换为 Godot TileSet 坐标
    返回 (source_index, atlas_x, atlas_y) 或 None（如果是空格）
    """
    if gid == 0:
        return None

    # 检查翻转标志
    flipped_h = (gid >> 31) & 1
    flipped_v = (gid >> 30) & 1
    flipped_d = (gid >> 29) & 1
    pure_gid = gid & 0x1FFFFFFF

    # 找到对应的 tileset
    best_source = -1
    best_firstgid = 0

    for firstgid in sorted(TILESET_MAPPING.keys()):
        if pure_gid >= firstgid:
            best_firstgid = firstgid
            best_source = TILESET_MAPPING[firstgid]

    if best_source == -1:
        return None

    # 计算在 tileset 内部的 ID
    local_id = pure_gid - best_firstgid

    # 计算坐标
    info = TILESET_INFO[best_source]
    cols = info["cols"]

    atlas_x = local_id % cols
    atlas_y = local_id // cols

    return {
        "source": best_source,
        "x": atlas_x,
        "y": atlas_y,
        "flip_h": bool(flipped_h),
        "flip_v": bool(flipped_v),
        "flip_d": bool(flipped_d),
    }


def generate_tilemaplayer_data(tiles, width, height):
    """
    将图块数据转换为 Godot 4 TileMapLayer 的 PackedByteArray 格式
    """
    # Godot 4 TileMapLayer 数据格式：
    # 每个单元格用变长编码，格式为：
    # - cell_x (varint)
    # - cell_y (varint)
    # - tile_data (varint)

    # 由于手动编码 PackedByteArray 很复杂，我们使用简化的方法：
    # 直接输出坐标和图块信息

    result = []
    non_empty_count = 0

    for y in range(height):
        for x in range(width):
            idx = y * width + x
            gid = tiles[idx]

            coords = gid_to_tile_coords(gid)
            if coords is None:
                continue

            non_empty_count += 1
            result.append({
                "x": x,
                "y": y,
                "source": coords["source"],
                "atlas_x": coords["x"],
                "atlas_y": coords["y"],
                "flip_h": coords["flip_h"],
                "flip_v": coords["flip_v"],
                "flip_d": coords["flip_d"],
            })

    return result, non_empty_count


def encode_tile_data_as_bytes(tile_cells):
    """
    将图块数据编码为 Godot PackedByteArray 格式
    这是 Godot 内部使用的压缩格式
    """
    # 简化版本：使用 Godot 可以理解的格式
    # 实际上我们需要生成与 new_tilemap.tscn 相同的格式

    data = bytearray()

    prev_x = 0
    prev_y = 0

    for cell in tile_cells:
        x = cell["x"]
        y = cell["y"]

        # 计算相对坐标差值
        dx = x - prev_x
        dy = y - prev_y

        # 编码坐标（Godot 使用 varint）
        data.extend(encode_varint(dx))
        data.extend(encode_varint(dy))

        # 编码图块数据
        source = cell["source"]
        atlas_x = cell["atlas_x"]
        atlas_y = cell["atlas_y"]

        # 构建 tile data 值
        # 格式：source 在高位，atlas 坐标在中位，翻转标志在低位
        tile_val = (source << 20) | (atlas_y << 10) | atlas_x

        if cell["flip_h"]:
            tile_val |= (1 << 9)
        if cell["flip_v"]:
            tile_val |= (1 << 8)
        if cell["flip_d"]:
            tile_val |= (1 << 7)

        data.extend(encode_varint(tile_val))

        prev_x = x
        prev_y = y

    return bytes(data)


def encode_varint(value):
    """编码为类似 varint 的格式（简化版）"""
    result = bytearray()

    # 处理负数（使用补码）
    if value < 0:
        value = value & 0xFFFFFFFF

    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value & 0x7F)

    return bytes(result) if result else b'\x00'


def bytes_to_godot_format(data_bytes):
    """将字节数组转换为 Godot .tscn 文件中的字符串格式"""
    return base64.b64encode(data_bytes).decode('ascii')


def generate_tscn(tm_data, output_path, tileset_path="res://tilesets/world_tileset.tres"):
    """生成新的 .tscn 文件"""

    lines = []

    # 文件头
    lines.append('[gd_scene load_steps=2 format=3]')
    lines.append('')

    # 外部资源引用
    lines.append(f'[ext_resource type="TileSet" uid="uid://c2fogefrc0p6f" path="{tileset_path}" id="1_tileset"]')
    lines.append('')

    # 根节点
    lines.append(f'[node name="map01" type="Node2D"]')
    lines.append('')

    # 为每个图层生成 TileMapLayer 节点
    z_index = 0
    for layer in tm_data["layers"]:
        name = layer["name"]
        width = layer["width"]
        height = layer["height"]
        tiles = layer["tiles"]

        # 跳过"角色"图层（我们会用独立的 Player 节点）
        if name == "角色":
            continue

        # 生成图块数据
        tile_cells, count = generate_tilemaplayer_data(tiles, width, height)

        if count == 0:
            print(f"跳过空图层: {name}")
            continue

        # 编码数据
        try:
            data_bytes = encode_tile_data_as_bytes(tile_cells)
            data_str = bytes_to_godot_format(data_bytes)
        except Exception as e:
            print(f"编码图层 '{name}' 数据时出错: {e}")
            continue

        # 写入节点
        safe_name = name.replace("/", "_").replace("\\", "_")
        lines.append(f'[node name="{safe_name}" type="TileMapLayer" parent="."]')
        if z_index > 0:
            lines.append(f'z_index = {z_index}')
        lines.append(f'tile_map_data = PackedByteArray("{data_str}")')
        lines.append(f'tile_set = ExtResource("1_tileset")')
        lines.append('')

        print(f"✓ 转换图层 '{name}': {count} 个图块")

        z_index += 1

    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"\n✅ 转换完成！输出文件: {output_path}")
    print(f"共转换 {len([l for l in tm_data['layers'] if l['name'] != '角色'])} 个图层")


def main():
    # 输入/输出路径
    input_tmx = Path(r"D:\CodeProject\PixelsProject\tiled\godot_project\maps\map01.tmx")
    output_tscn = Path(r"D:\CodeProject\PixelsProject\tiled\godot_project\maps\map01_editable.tscn")

    if not input_tmx.exists():
        print(f"错误: 找不到输入文件 {input_tmx}")
        sys.exit(1)

    print(f"📖 解析 TMX 文件: {input_tmx}")
    tm_data = parse_tmx(input_tmx)

    print(f"📐 地图尺寸: {tm_data['width']}x{tm_data['height']}")
    print(f"📦 图层数量: {len(tm_data['layers'])}")

    print(f"\n🔧 开始转换...")
    generate_tscn(tm_data, output_tscn)


if __name__ == "__main__":
    main()
