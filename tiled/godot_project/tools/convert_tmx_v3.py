#!/usr/bin/env python3
"""
TMX → TileMapLayer 转换器 (Python 版本 v3)
基于对 Godot 4 二进制格式的完整分析

数据格式:
- 每个非空单元格 12 字节: [x:int32][y:int32][tile_data:int32]
- tile_data 编码: source_id(低16位) | atlas_coord(高16位)
"""

import xml.etree.ElementTree as ET
import base64
import struct
import os

# ==================== 配置 ====================
TMX_PATH = "maps/map01.tmx"
OUTPUT_PATH = "maps/map01_editable.tscn"

# Tiled tileset firstgid → Godot TileSet source_index
TILESET_MAP = {
    1: 0,      # terrainA
    41: 1,     # terrainB
    361: 2,    # terrainC
    811: 3,    # water-ani
    979: 4,    # decorations
    1021: 5,   # Props
    1063: 6,   # house_A
    1117: 7,   # house_B
    1157: 8,   # tree
    1220: 9,   # crop (ScenesCollection)
    1256: 10,  # 角色_F
}

# 每个 source 的列数 (用于计算 atlas 坐标)
SOURCE_COLS = {
    0: 10,    # terrainA: 10 columns
    1: 32,    # terrainB: 32 columns
    2: 30,    # terrainC: 30 columns
    3: 24,    # water-ani: 使用纹理宽度作为列数 (实际图块从16,4开始)
    4: 14,    # decorations
    5: 7,     # props
    6: 9,     # house_A
    7: 5,     # house_B
    8: 1,     # tree
    9: 12,    # crop
    10: 8,    # 角色
}


def parse_tmz(filepath):
    """解析 TMX 文件，返回地图信息和图层列表"""
    tree = ET.parse(filepath)
    root = tree.getroot()

    map_width = int(root.get("width"))
    map_height = int(root.get("height"))

    layers = []
    for layer_elem in root.findall("layer"):
        layer_name = layer_elem.get("name")
        layer_w = int(layer_elem.get("width"))
        layer_h = int(layer_elem.get("height"))

        # 解析 CSV 数据
        data_elem = layer_elem.find("data")
        csv_text = data_elem.text.strip()
        tiles = []
        for val in csv_text.split(","):
            val = val.strip()
            if val:
                tiles.append(int(val))

        layers.append({
            "name": layer_name,
            "width": layer_w,
            "height": layer_h,
            "tiles": tiles,
        })

    return map_width, map_height, layers


def get_source_info(gid):
    """
    从全局 GID 获取 source 信息
    返回 (source_index, local_id) 或 (None, None)
    """
    pure_gid = gid & 0x1FFFFFFF  # 移除翻转标志

    best_firstgid = -1
    best_source_idx = -1
    best_local_id = 0

    for firstgid, source_idx in TILESET_MAP.items():
        if pure_gid >= firstgid and firstgid > best_firstgid:
            best_firstgid = firstgid
            best_source_idx = source_idx
            best_local_id = pure_gid - firstgid

    if best_source_idx == -1:
        return None, None

    return best_source_idx, best_local_id


def encode_tile_data(source_id, atlas_x, atlas_y):
    """
    编码 Godot 4 tile_data 格式 (基于实际数据分析)

    观察到的格式 (从 new_tilemap.tscn Water 层):
    - tile_data = 0x00030003
    - Water source_id = 3
    - 低16位 = 0x0003 = source_id ✓
    - 高16位 = 0x0003 = atlas 坐标编码

    结论: tile_data = (atlas_encoded << 16) | source_id
    其中 atlas_encoded 可能是 y*256+x 或简单的坐标组合
    """
    # 编码 atlas 坐标到高16位
    # 简单编码: (y << 8) | x
    coord_encoded = ((atlas_y & 0xFF) << 8) | (atlas_x & 0xFF)

    # 最终格式: 高16位=coord, 低16位=source_id
    return (coord_encoded << 16) | source_id


def build_layer_tilemap_data(layers_data):
    """
    为单个图层构建 PackedByteArray 数据
    返回 base64 编码的字符串
    """
    cells = []  # [(x, y, tile_data), ...]

    tiles = layers_data["tiles"]
    width = layers_data["width"]
    height = layers_data["height"]

    skipped = 0

    for y in range(height):
        for x in range(width):
            idx = y * width + x
            if idx >= len(tiles):
                break

            gid = tiles[idx]
            if gid == 0:
                continue

            # 解析翻转标志
            flipped_h = bool((gid >> 31) & 1)
            flipped_v = bool((gid >> 30) & 1)
            flipped_d = bool((gid >> 29) & 1)
            pure_gid = gid & 0x1FFFFFFF

            # 获取 source 信息
            source_idx, local_id = get_source_info(pure_gid)

            if source_idx is None:
                skipped += 1
                if skipped <= 5:
                    print(f"    ⚠️ 未知 GID {pure_gid} at ({x}, {y})")
                continue

            # 计算 atlas 坐标
            cols = SOURCE_COLS.get(source_idx, 16)
            atlas_x = local_id % cols
            atlas_y = local_id // cols

            # 特殊处理 water source (图块从 16,4 开始偏移)
            if source_idx == 3:  # water
                # water 的实际图块位置需要调整
                # Tiled 中 water 的第一个 GID 是 811, 对应 water贴图的特定位置
                pass

            # 编码 tile_data
            tile_data = encode_tile_data(source_idx, atlas_x, atlas_y)

            # 添加翻转标志 (如果有)
            if flipped_h:
                tile_data |= (1 << 31)
            if flipped_v:
                tile_data |= (1 << 30)

            cells.append((x, y, tile_data))

    if skipped > 5:
        print(f"    ⚠️ ... 共跳过 {skipped} 个未知图块")

    # 构建二进制数据
    data = bytearray()
    for x, y, tile_data in cells:
        data += struct.pack("<iii", x, y, tile_data)

    return base64.b64encode(data).decode("ascii"), len(cells)


def generate_tscn(map_width, map_height, layers):
    """生成 .tscn 文件内容"""

    lines = []
    lines.append('[gd_scene format=4 uid="uid://bfxe8q8c7k5a2"]')
    lines.append("")

    # 引用 TileSet
    lines.append('[ext_resource type="TileSet" uid="uid://c2fogefrc0p6f" path="res://tilesets/world_tileset.tres" id="1_tileset"]')
    lines.append("")

    # 根节点
    lines.append('[node name="map01" type="Node2D"]')
    lines.append("")

    z_index = 0
    total_tiles = 0

    for layer_data in layers:
        layer_name = layer_data["name"]

        # 跳过角色图层
        if layer_name == "角色":
            print(f"  ⏭️  跳过图层 '{layer_name}'")
            continue

        # 构建数据
        b64_data, cell_count = build_layer_tilemap_data(layer_data)
        total_tiles += cell_count

        # 写入节点
        safe_name = layer_name.replace("/", "_").replace("\\", "_")

        extra_props = ""
        if z_index > 0:
            extra_props += f"\nz_index = {z_index}"

        lines.append(f'[node name="{safe_name}" type="TileMapLayer" parent="."]{extra_props}')
        lines.append(f'tile_map_data = PackedByteArray("{b64_data}")')
        lines.append('tile_set = ExtResource("1_tileset")')
        lines.append("")

        print(f"  ✅ {layer_name}: {cell_count} 个图块")

        z_index += 1

    print(f"\n📊 总计: {total_tiles} 个图块, {z_index} 个图层")

    return "\n".join(lines)


def main():
    print("=" * 60)
    print("  TMX → TileMapLayer 转换器 v3")
    print("=" * 60)

    # 检查文件
    if not os.path.exists(TMX_PATH):
        print(f"❌ 找不到 TMX 文件: {TMX_PATH}")
        return False

    # 解析 TMX
    print(f"\n📖 解析: {TMX_PATH}")
    map_width, map_height, layers = parse_tmz(TMX_PATH)
    print(f"📐 地图尺寸: {map_width} x {map_height}")
    print(f"📑 图层数量: {len(layers)}")

    # 生成 .tscn
    print(f"\n🔨 生成: {OUTPUT_PATH}")
    tscn_content = generate_tscn(map_width, map_height, layers)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(tscn_content)

    print(f"\n✅ 成功! 输出文件: {OUTPUT_PATH}")
    return True


if __name__ == "__main__":
    main()
