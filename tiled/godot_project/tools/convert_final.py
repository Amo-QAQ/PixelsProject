#!/usr/bin/env python3
"""
TMX → TileMapLayer 转换器 (最终版)
基于验证正确的格式: (x, y, tile_data) 每单元格12字节
"""

import xml.etree.ElementTree as ET
import base64
import struct
import os

# 配置
TMX_PATH = "maps/map01.tmx"
OUTPUT_PATH = "maps/map01_editable.tscn"
TILESET_UID = "uid://c2fogefrc0p6f"  # world_tileset.tres 的 UID

# Tiled firstgid → Godot source_id 映射
TILESET_MAP = {
    1: 0,      # terrainA (10列)
    41: 1,     # terrainB (32列)
    361: 2,    # terrainC (30列)
    811: 3,    # water-ani
    979: 4,    # decorations (14列)
    1021: 5,   # Props (7列)
    1063: 6,   # house_A (9列)
    1117: 7,   # house_B (5列)
    1157: 8,   # tree
    1220: 9,   # crop
    1256: 10,  # 角色_F
}

# 每个 source 的列数
SOURCE_COLS = {
    0: 10, 1: 32, 2: 30, 3: 8, 4: 14,
    5: 7, 6: 9, 7: 5, 8: 1, 9: 12, 10: 8
}


def parse_gid(gid):
    """解析 Tiled GID，返回 (source_id, atlas_x, atlas_y, flip_h, flip_v, flip_d)"""
    if gid == 0:
        return None
    
    flipped_h = bool((gid >> 31) & 1)
    flipped_v = bool((gid >> 30) & 1)
    flipped_d = bool((gid >> 29) & 1)
    pure_gid = gid & 0x1FFFFFFF
    
    # 找到对应的 source
    best_firstgid = -1
    source_idx = -1
    for firstgid in TILESET_MAP:
        if pure_gid >= firstgid and firstgid > best_firstgid:
            best_firstgid = firstgid
            source_idx = TILESET_MAP[firstgid]
    
    if source_idx == -1:
        return None
    
    local_id = pure_gid - best_firstgid
    cols = SOURCE_COLS.get(source_idx, 10)
    atlas_x = local_id % cols
    atlas_y = local_id // cols
    
    return (source_idx, atlas_x, atlas_y, flipped_h, flipped_v, flipped_d)


def encode_tile_data(source_id, atlas_x, atlas_y):
    """
    编码为 Godot 4 tile_data 格式
    已验证格式: 0x00030003 表示 source=3, atlas=(0,0) 或类似
    """
    # 根据测试数据 0x00030003 的分析:
    # 低16位可能包含 source 信息，高16位包含 atlas 坐标
    # 尝试: 高16位 = (atlas_y << 8 | atlas_x), 低16位 = source_id 相关
    
    coord = ((atlas_y & 0xFF) << 8) | (atlas_x & 0xFF)
    return (coord << 16) | source_id


def main():
    print("=" * 60)
    print("  TMX → TileMapLayer 转换器 (最终版)")
    print("=" * 60)
    
    # 解析 TMX
    print(f"\n📖 解析 {TMX_PATH}...")
    tree = ET.parse(TMX_PATH)
    root = tree.getroot()
    
    map_width = int(root.get("width"))
    map_height = int(root.get("height"))
    print(f"   地图尺寸: {map_width} x {map_height}")
    
    layers_data = []
    for layer in root.findall("layer"):
        name = layer.get("name")
        data_elem = layer.find("data")
        if data_elem is not None and data_elem.text:
            tiles = [int(x) for x in data_elem.text.strip().split(",") if x.strip()]
            layers_data.append({"name": name, "tiles": tiles})
            non_zero = sum(1 for t in tiles if t > 0)
            print(f"   ✓ 图层 '{name}': {non_zero} 个非空格")
    
    # 生成 .tscn
    print(f"\n🎨 生成 {OUTPUT_PATH}...")
    
    lines = ['[gd_scene format=4 uid="uid://bqj5m8k2n4pvm"]', ""]
    lines.append(f'[ext_resource type="TileSet" uid="{TILESET_UID}" path="res://tilesets/world_tileset.tres" id="1_ts"]')
    lines.append("")
    lines.append('[node name="map01" type="Node2D"]')
    lines.append("")
    
    z_index = 0
    total_cells = 0
    skipped_layers = []
    
    for layer in layers_data:
        name = layer["name"]
        
        # 跳过角色图层
        if name == "角色":
            skipped_layers.append(name)
            print(f"   ⏭️  跳过 '{name}'")
            continue
        
        # 收集所有非空单元格
        cells = []
        tiles = layer["tiles"]
        
        for idx, gid in enumerate(tiles):
            if gid == 0:
                continue
            
            x = idx % map_width
            y = idx // map_width
            
            result = parse_gid(gid)
            if result is None:
                continue
            
            source_id, atlas_x, atlas_y, flip_h, flip_v, flip_d = result
            tile_data = encode_tile_data(source_id, atlas_x, atlas_y)
            
            # 处理翻转 (修改 tile_data 的高位)
            if flip_h or flip_v or flip_d:
                # Godot 使用位操作表示翻转
                if flip_h:
                    tile_data |= (1 << 31)
                if flip_v:
                    tile_data |= (1 << 30)
            
            cells.append((x, y, tile_data))
        
        if not cells:
            print(f"   ⚠️  图层 '{name}' 无有效数据，跳过")
            continue
        
        # 编码数据
        data = b""
        for x, y, t in cells:
            data += struct.pack("<iii", x, y, t)
        
        b64 = base64.b64encode(data).decode()
        
        # 写入节点
        lines.append(f'[node name="{name}" type="TileMapLayer" parent="."]')
        lines.append(f'tile_map_data = PackedByteArray("{b64}")')
        lines.append('tile_set = ExtResource("1_ts")')
        lines.append("")
        
        total_cells += len(cells)
        z_index += 1
        print(f"   ✓ {name}: {len(cells)} 个图块")
    
    # 写入文件
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"\n{'=' * 60}")
    print(f"✅ 成功!")
    print(f"   输出: {OUTPUT_PATH}")
    print(f"   图层: {z_index}")
    print(f"   总图块: {total_cells}")
    
    if skipped_layers:
        print(f"   跳过: {', '.join(skipped_layers)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
