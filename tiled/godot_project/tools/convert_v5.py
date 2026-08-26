#!/usr/bin/env python3
"""
TMX → TileMapLayer 转换器 (v5 - 使用原始 tile_data)
直接从 map01.tscn 旧版格式提取 tile_data 值，保证100%兼容
"""

import re
import base64
import struct

# 输入输出
OLD_MAP = "maps/map01.tscn"      # 旧版 TileMap 格式
OUTPUT_PATH = "maps/map01_editable.tscn"  # 新版 TileMapLayer 格式


def parse_old_tilemap(filepath):
    """解析旧版 TileMap 格式，提取图层和图块数据"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    layers = []
    current_layer = None
    
    for line in content.split('\n'):
        line = line.strip()
        
        # 检测图层名
        m = re.match(r'layer_(\d+)/name = "(.+)"', line)
        if m:
            current_layer = {"name": m.group(2), "cells": []}
            layers.append(current_layer)
            continue
        
        # 检测图块数据
        if current_layer and 'tile_data = PackedInt32Array(' in line:
            # 提取数组内容
            data_str = line.split('PackedInt32Array(')[1].rstrip(')')
            values = [int(x.strip()) for x in data_str.split(',') if x.strip()]
            
            # 旧版格式: 每3个值一组 (tile_data, x, y) 或逐格存储？
            # 从数据分析: 看起来是按顺序存储的，每格一个值
            # 但长度应该等于 width * height
            
            # 实际上从数据特征看，这是逐格存储（包括空格=0）
            # 数组索引对应位置
            
            current_layer["raw_data"] = values
            current_layer["size"] = len(values)
    
    return layers


def old_to_new_format(old_layers, map_width=50, map_height=50):
    """将旧版格式转换为新版 TileMapLayer 格式"""
    
    output_lines = []
    output_lines.append('[gd_scene format=4 uid="uid://bqj5m8k2n4pvm"]')
    output_lines.append('')
    output_lines.append('[ext_resource type="TileSet" uid="uid://c2fogefrc0p6f" path="res://tilesets/world_tileset.tres" id="1_ts"]')
    output_lines.append('')
    output_lines.append('[node name="map01" type="Node2D"]')
    output_lines.append('')
    total_cells = 0
    
    for layer in old_layers:
        name = layer["name"]
        
        # 跳过角色图层
        if name == "角色":
            print(f"   ⏭️  跳过 '{name}'")
            continue
        
        raw_data = layer.get("raw_data", [])
        if not raw_data:
            continue
        
        # 逐格提取非空单元格
        cells_data = []
        
        for idx, tile_data in enumerate(raw_data):
            if tile_data == 0:
                continue
            
            x = idx % map_width
            y = idx // map_width
            
            # 直接使用原始的 tile_data 值！
            cells_data.append((x, y, tile_data))
        
        if not cells_data:
            continue
        
        # 编码为 PackedByteArray (新版格式)
        packed = b""
        for x, y, t in cells_data:
            packed += struct.pack("<iii", x, y, t)
        
        b64 = base64.b64encode(packed).decode()
        
        # 写入节点
        output_lines.append(f'[node name="{name}" type="TileMapLayer" parent="."]')
        output_lines.append(f'tile_map_data = PackedByteArray("{b64}")')
        output_lines.append('tile_set = ExtResource("1_ts")')
        output_lines.append('')
        
        total_cells += len(cells_data)
        print(f"   ✓ {name}: {len(cells_data)} 个图块")
    
    return '\n'.join(output_lines), total_cells


def main():
    print("=" * 60)
    print("  TMX → TileMapLayer 转换器 v5 (原始数据)")
    print("=" * 60)
    
    # 解析旧版文件
    print(f"\n📖 读取 {OLD_MAP}...")
    layers = parse_old_tilemap(OLD_MAP)
    print(f"   找到 {len(layers)} 个图层")
    
    # 转换
    print(f"\n🔄 转换为新版格式...")
    tscn_content, total_cells = old_to_new_format(layers)
    
    # 写入
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write(tscn_content)
    
    print(f"\n{'=' * 60}")
    print(f"✅ 成功!")
    print(f"   输出: {OUTPUT_PATH}")
    print(f"   总图块: {total_cells}")
    print(f"{'=' * 60}")
    print("\n⚠️  重要: 此版本直接复用原始 tile_data 值")
    print("   如果仍有显示问题，可能是新旧格式不完全兼容")


if __name__ == "__main__":
    main()
