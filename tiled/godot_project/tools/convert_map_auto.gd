@tool
extends SceneTree
## 独立运行的转换工具
## 在 Godot 命令行运行: godot --script tools/convert_map_auto.gd

const TMX_PATH := "res://maps/map01.tmx"
const OUTPUT_PATH := "res://maps/map01_editable.tscn"
const TILESET_PATH := "res://tilesets/world_tileset.tres"

const TILESET_MAP := {
	1: 0, 41: 1, 361: 2, 811: 3, 979: 4,
	1021: 5, 1063: 6, 1117: 7, 1157: 8, 1220: 9, 1256: 10,
}

const SOURCE_COLS := {
	0: 10, 1: 32, 2: 30, 3: 24, 4: 14,
	5: 7, 6: 9, 7: 5, 8: 18, 9: 12, 10: 8,
}

func _init() -> void:
	print("\n🗺️ TMX → TileMapLayer 转换器\n")
	
	var xml_content := FileAccess.get_file_as_string(TMX_PATH)
	if xml_content == "":
		print("❌ 无法读取 TMX 文件!")
		quit(1)
		return
	
	var xml := XMLParser.new()
	if xml.open_buffer(xml_content.to_utf8_buffer()) != OK:
		print("❌ XML 解析失败!")
		quit(1)
		return
	
	var map_w := 0
	var map_h := 0
	var layers := []
	
	while xml.read() == OK:
		if xml.get_node_type() == XMLParser.NODE_ELEMENT:
			if xml.get_node_name() == "map":
				map_w = int(xml.get_attribute_value("width", "0"))
				map_h = int(xml.get_attribute_value("height", "0"))
			
			elif xml.get_node_name() == "layer":
				var lname := xml.get_attribute_value("name", "")
				if lname == "角色":
					_skip(xml)
					continue
				
				var data := _read_layer(xml, map_w)
				if not data.is_empty():
					layers.append({"name": lname, "cells": data})
					print(f"  ✓ {lname}: {data.size()} tiles")
	
	if layers.is_empty():
		print("❌ 无有效图层!")
		quit(1)
		return
	
	# 构建场景
	var root := Node2D.new()
	root.name = "map01"
	
	var tileset := load(TILESET_PATH) as TileSet
	
	for i in range(layers.size()):
		var l := layers[i]
		var node := TileMapLayer.new()
		node.name = l.name
		node.tile_set = tileset
		node.z_index = i
		
		for c in l.cells:
			node.set_cell(Vector2i(c.x, c.y), c.src, Vector2i(c.ax, c.ay))
		
		root.add_child(node)
	
	var scene := PackedScene.new()
	scene.pack(root)
	var err := ResourceSaver.save(scene, OUTPUT_PATH)
	
	if err == OK:
		print(f"\n✅ 成功! 输出: {OUTPUT_PATH}")
	else:
		print(f"\n❌ 保存失败! (err={err})")
	
	quit(0)


func _read_layer(xml: XMLParser, w: int) -> Array:
	var cells := []
	var name := ""
	
	while xml.read() == OK:
		if xml.get_node_type() == XMLParser.NODE_ELEMENT:
			if xml.get_node_name() == "layer":
				name = xml.get_attribute_value("name")
			elif xml.get_node_name() == "data" and xml.get_attribute_value("encoding") == "csv":
				xml.read()
				var csv := xml.get_node_data().strip_edges()
				var vals := csv.split(",")
				for idx in range(vals.size()):
					var gid_str := vals[idx].strip_edges()
					if gid_str.empty():
						continue
					var gid := int(gid_str)
					if gid == 0:
						continue
					
					var src := -1
					var lid := 0
					for k in TILESET_MAP.keys():
						if gid >= k and k > (lid * 0):  # 找到最大的匹配 firstgid
							src = TILESET_MAP[k]
							lid = gid - k
							break
					
					# 重新正确查找 source_id
					src = -1
					var keys := TILESET_MAP.keys()
					keys.sort_custom(func(a, b): return a > b)
					for k in keys:
						if gid >= k:
							src = TILESET_MAP[k]
							lid = gid - k
							break
					
					if src < 0:
						continue
					
					var cols := SOURCE_COLS.get(src, 10)
					cells.append({
						"x": idx % w,
						"y": idx / w,
						"src": src,
						"ax": lid % cols,
						"ay": lid / cols,
					})
				break
		elif xml.get_node_type() == XMLParser.NODE_ELEMENT_END:
			if xml.get_node_name() == "layer":
				break
	return cells


func _skip(xml: XMLParser) -> void:
	var d := 1
	while d > 0 and xml.read() == OK:
		if xml.get_node_type() == XMLParser.NODE_ELEMENT:
			d += 1
		elif xml.get_node_type() == XMLParser.NODE_ELEMENT_END:
			d -= 1
