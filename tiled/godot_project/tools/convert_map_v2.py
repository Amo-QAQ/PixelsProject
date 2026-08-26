#!/usr/bin/env python3
"""
TMX 到 Godot 4 TileMapLayer 转换器
基于 map01.tmx 源文件生成可编辑的 .tscn 格式
"""

import xml.etree.ElementTree as ET
import base64
import struct
import re

# TMX tileset 的 firstgid 到 world_tileset.tres source_id 的映射
TILESET_MAPPING = [
    {"firstgid": 1, "source": "terrainA.tsx", "source_id": 0},      # terrain_a
    {"firstgid": 41, "source": "terrainB.tsx", "source_id": 1},     # terrain_b
    {"firstgid": 361, "source": "terrainC.tsx", "source_id": 2},    # terrain_c
    {"firstgid": 811, "source": "water-ani.tsx", "source_id": 3},   # water
    {"firstgid": 979, "source": "decorations_tilemap.tsx", "source_id": 4},  # decorations
    {"firstgid": 1021, "source": "Props.tsx", "source_id": 5},      # props
    {"firstgid": 1063, "source": "house_A.tsx", "source_id": 6},    # house_a
    {"firstgid": 1117, "source": "house_B.tsx", "source_id": 7},    # house_b
    {"firstgid": 1157, "source": "tree.tsx", "source_id": 8},       # tree
    {"firstgid": 1220, "source": "crop.tsx", "source_id": 9},       # crop
    {"firstgid": 1256, "source": "角色_F.tsx", "source_id": 10},    # 角色
]

# 各 tileset 的列数（用于计算 atlas coords）
TILESET_COLUMNS = {
    0: 10,   # terrainA: 10 columns
    1: 32,   # terrainB: 32 columns
    2: 30,   # terrainC: 30 columns
    3: 24,   # water: 24 columns
    4: 14,   # decorations: 14 columns
    5: 7,    # props: 7 columns
    6: 9,    # house_A: 9 columns
    7: 5,    # house_B: 5 columns
    8: 18,   # tree: 18 columns
    9: 12,   # crop: 12 columns
    10: 8,   # 角色: 8 columns
}


def get_source_id(gid):
    """根据 GID 获取 source_id 和本地 tile ID"""
    if gid == 0:
        return None, 0
    
    for ts in reversed(TILESET_MAPPING):
        if gid >= ts["firstgid"]:
            return ts["source_id"], gid - ts["firstgid"]
    
    return None, 0


def get_atlas_coords(local_id, source_id):
    """根据本地 tile ID 计算 atlas 坐标 (atlas_x, atlas_y)"""
    cols = TILESET_COLUMNS.get(source_id, 10)
    atlas_x = local_id % cols
    atlas_y = local_id // cols
    return atlas_x, atlas_y


def encode_tilemap_layer_data(cells):
    """
    将 cell 数据编码为 Godot 4 TileMapLayer 的 PackedByteArray 格式
    Godot 4 使用变长编码格式存储 tile 数据
    """
    if not cells:
        return ""
    
    # 按 coordinates 排序确保一致性
    cells.sort(key=lambda c: (c[1], c[0]))  # 先按 y，再按 x
    
    data = bytearray()
    prev_x, prev_y = 0, 0
    
    for x, y, source_id, alt_id in cells:
        # 计算相对坐标差值
        dx = x - prev_x
        dy = y - prev_y
        
        # Godot 4 TileMapLayer 使用特定的变长编码
        # 格式：coord_delta + tile_info
        # 这里我们使用简化的编码方式
        
        # 写入坐标差值（使用 zigzag 编码和变长 int）
        coord_val = (dx << 16) | (dy & 0xFFFF)
        data.extend(encode_varint(coord_val))
        
        # 写入 tile 信息
        tile_info = (source_id & 0xF) | ((alt_id & 0xF) << 4)
        data.append(tile_info)
        
        prev_x, prev_y = x, y
    
    return base64.b64encode(bytes(data)).decode('ascii')


def encode_varint(value):
    """编码变长整数（简化版）"""
    result = bytearray()
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value & 0x7F)
    return bytes(result)


def parse_csv_layer_data(csv_text):
    """解析 CSV 格式的图层数据"""
    values = []
    for line in csv_text.strip().split('\n'):
        line = line.strip()
        if line:
            values.extend([int(x) for x in line.split(',') if x.strip()])
    return values


def convert_tmx_to_tilemaplayer(tmx_path, output_path):
    """转换 TMX 文件为 Godot 4 可编辑格式"""
    
    print(f"正在解析 {tmx_path}...")
    tree = ET.parse(tmx_path)
    root = tree.getroot()
    
    width = int(root.get('width'))
    height = int(root.get('height'))
    
    print(f"地图尺寸: {width}x{height}")
    
    # 收集所有图层
    layers = []
    skip_layers = ['角色']  # 要跳过的图层名称
    
    for layer in root.findall('layer'):
        name = layer.get('name')
        
        if name in skip_layers:
            print(f"  跳过图层: {name}")
            continue
        
        data_elem = layer.find('data')
        if data_elem is None:
            continue
        
        encoding = data_elem.get('encoding', 'csv')
        csv_text = data_elem.text.strip() if data_elem.text else ""
        
        if encoding == 'csv':
            gids = parse_csv_layer_data(csv_text)
        else:
            print(f"  跳过图层 {name}: 不支持的编码格式 {encoding}")
            continue
        
        # 转换 GID 为 cell 数据
        cells = []
        for idx, gid in enumerate(gids):
            if gid == 0:
                continue
            
            x = idx % width
            y = idx // width
            
            source_id, local_id = get_source_id(gid)
            if source_id is None:
                continue
            
            atlas_x, atlas_y = get_atlas_coords(local_id, source_id)
            
            cells.append((x, y, source_id, (atlas_y << 8) | atlas_x))
        
        layers.append({
            'name': name,
            'cells': cells,
            'count': len(cells)
        })
        
        print(f"  图层 '{name}': {len(cells)} 个图块")
    
    # 生成 .tscn 文件
    generate_tscn(output_path, layers, width, height)
    
    print(f"\n✅ 转换完成! 输出文件: {output_path}")
    print(f"   共转换 {len(layers)} 个图层")


def generate_tscn(output_path, layers, width, height):
    """生成 Godot 4 格式的 .tscn 文件"""
    
    lines = []
    lines.append('[gd_scene format=4 uid="uid://bxm editable"]')
    lines.append('')
    lines.append('[ext_resource type="TileSet" uid="uid://c2fogefrc0p6f" path="res://tilesets/world_tileset.tres" id="1_tileset"]')
    lines.append('')
    lines.append(f'[node name="map01_editable" type="Node2D"]')
    lines.append('')
    
    for i, layer in enumerate(layers):
        z_index = i
        
        # 生成 tile_map_data
        if layer['cells']:
            # 使用更简单的编码方式 - 直接按 Godot 格式手动构建
            tile_data = encode_tile_data_v2(layer['cells'])
        else:
            tile_data = ''
        
        lines.append(f'[node name="{layer["name"]}" type="TileMapLayer" parent="."]')
        if z_index > 0:
            lines.append(f'z_index = {z_index}')
        if tile_data:
            lines.append(f'tile_map_data = PackedByteArray("{tile_data}")')
        lines.append(f'tile_set = ExtResource("1_tileset")')
        lines.append('')
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def encode_tile_data_v2(cells):
    """
    使用 Godot 4 兼容的格式编码 tile 数据
    基于 new_tilemap.tscn 中观察到的格式
    """
    if not cells:
        return ""
    
    # 创建坐标到 tile 的映射
    tile_map = {}
    for x, y, source_id, alt_id in cells:
        tile_map[(x, y)] = (source_id, alt_id)
    
    # Godot 4 TileMapLayer 的 PackedByteArray 格式分析：
    # 从 new_tilemap.tscn 的数据来看，它使用一种紧凑的二进制格式
    # 我们尝试模拟这种格式
    
    data = bytearray()
    
    # 按照 Godot 的内部格式编码
    # 参考: https://github.com/godotengine/godot/blob/master/scene/resources/tile_map_layer.cpp
    
    # 简化版本：逐行编码
    cells_sorted = sorted(cells, key=lambda c: (c[1], c[0]))
    
    prev_coord = (-1, -1)
    
    for x, y, source_id, alternative_id in cells_sorted:
        # 计算坐标增量
        if prev_coord == (-1, -1):
            # 第一个 cell
            dx = x + 1  # Godot 使用 1-based 或特殊偏移
            dy = y + 1
        else:
            dx = x - prev_coord[0]
            dy = y - prev_coord[1]
        
        # 编码坐标（Godot 使用变长编码）
        data.extend(_encode_signed_varint(dx))
        data.extend(_encode_signed_varint(dy))
        
        # 编码 tile 信息
        # source_id 在低 4 位，alternative_id 在高 4 位（或其他位）
        data.append(source_id | (alternative_id << 4))
        
        prev_coord = (x, y)
    
    return base64.b64encode(bytes(data)).decode('ascii')


def _encode_signed_varint(value):
    """编码有符号变长整数"""
    # Zigzag 编码
    if value >= 0:
        zigzag = value * 2
    else:
        zigzag = (-value) * 2 - 1
    
    return _encode_unsigned_varint(zigzag)


def _encode_unsigned_varint(value):
    """编码无符号变长整数"""
    result = bytearray()
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value & 0x7F)
    return bytes(result)


if __name__ == '__main__':
    tmx_file = 'maps/map01.tmx'
    output_file = 'maps/map01_editable.tscn'
    
    convert_tmx_to_tilemaplayer(tmx_file, output_file)
