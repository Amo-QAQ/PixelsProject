@tool
extends EditorScript
## TMX 到 TileMapLayer 转换工具
## 使用方法：在 Godot 中点击"项目 → 工具 → 执行脚本"，选择此文件

const TMX_PATH := "res://maps/map01.tmx"
const OUTPUT_PATH := "res://maps/map01_editable.tscn"
const TILESET_PATH := "res://tilesets/world_tileset.tres"

# TMX firstgid -> source_id 映射（对应 world_tileset.tres）
const TILESET_MAP := {
	1: 0,      # terrainA -> source 0
	41: 1,     # terrainB -> source 1
	361: 2,    # terrainC -> source 2
	811: 3,    # water-ani -> source 3
	979: 4,    # decorations -> source 4
	1021: 5,   # Props -> source 5
	1063: 6,   # house_A -> source 6
	1117: 7,   # house_B -> source 7
	1157: 8,   # tree -> source 8
	1220: 9,   # crop -> source 9
	1256: 10,  # 角色 -> source 10
}

# 各 source 的列数
const SOURCE_COLS := {
	0: 10, 1: 32, 2: 30, 3: 24, 4: 14,
	5: 7, 6: 9, 7: 5, 8: 18, 9: 12, 10: 8,
}

# 要跳过的图层
const SKIP_LAYERS := ["角色"]


func _run() -> void:
	print("\n=== TMX 转 TileMapLayer 工具 ===\n")
	
	var tmx_content := _load_file(TMX_PATH)
	if tmx_content.is_empty():
		print("❌ 无法加载 TMX 文件!")
		return
	
	var xml := XMLParser.new()
	if xml.open_buffer(tmx_content.to_utf8_buffer()) != OK:
		print("❌ 解析 XML 失败!")
		return
	
	# 解析 TMX
	var map_width := 0
	var map_height := 0
	var layers := []  # [{name, cells: [{x, y, source_id, atlas_x, atlas_y}]}
	
	while xml.read() == OK:
		if xml.get_node_type() == XMLParser.NODE_ELEMENT:
			if xml.get_node_name() == "map":
				map_width = int(xml.get_attribute_value("width", "0"))
				map_height = int(xml.get_attribute_value("height", "0"))
				print(f"📐 地图尺寸: {map_width} x {map_height}")
			
			elif xml.get_node_name() == "layer":
				var layer_name := xml.get_attribute_value("name", "")
				if layer_name in SKIP_LAYERS:
					print(f"⏭️ 跳过图层: {layer_name}")
					_skip_layer(xml)
					continue
				
				var layer_data := _parse_csv_layer(xml, map_width)
				if not layer_data.cells.is_empty():
					layers.append({
						"name": layer_name,
						"cells": layer_data.cells,
					})
					print(f"✅ 图层 '{layer_name}': {layer_data.cells.size()} 个图块")
	
	if layers.is_empty():
		print("❌ 没有可转换的图层!")
		return
	
	# 创建场景
	var scene := PackedScene.new()
	var root := Node2D.new()
	root.name = "map01"
	scene.pack(root)
	
	# 加载 TileSet
	var tileset := load(TILESET_PATH) as TileSet
	if tileset == null:
		print("❌ 无法加载 TileSet: ", TILESET_PATH)
		return
	
	# 创建图层节点
	for i in range(layers.size()):
		var layer_info := layers[i]
		var layer_node := TileMapLayer.new()
		layer_node.name = layer_info.name
		layer_node.tile_set = tileset
		layer_node.z_index = i
		
		# 设置图块数据
		for cell in layer_info.cells:
			var coords := Vector2i(cell.x, cell.y)
			var atlas_coords := Vector2i(cell.atlas_x, cell.atlas_y)
			var source_id := cell.source_id
			layer_node.set_cell(coords, source_id, atlas_coords)
		
		root.add_child(layer_node)
		layer_node.owner = root
	
	# 保存场景
	var err := ResourceSaver.save(scene, OUTPUT_PATH)
	if err == OK:
		print(f"\n🎉 成功! 已保存到: {OUTPUT_PATH}")
		print(f"   共 {layers.size()} 个图层")
	else:
		print(f"\n❌ 保存失败! 错误码: {err}")


func _parse_csv_layer(xml: XMLParser, width: int) -> Dictionary:
	var result := {"cells": []}
	var layer_name := ""
	
	# 找到 data 元素
	while xml.read() == OK:
		if xml.get_node_type() == XMLParser.NODE_ELEMENT:
			if xml.get_node_name() == "layer":
				layer_name = xml.get_attribute_value("name", "")
			
			elif xml.get_node_name() == "data":
				var encoding := xml.get_attribute_value("encoding", "")
				if encoding != "csv":
					push_warning("跳过非 CSV 编码的图层: " + layer_name)
					return result
				
				# 读取 CSV 内容
				xml.read()  # 进入 text
				var csv_text := xml.get_node_data().strip_edges()
				_parse_gids(csv_text, width, result.cells)
				break
		
		elif xml.get_node_type() == XMLParser.NODE_ELEMENT_END:
			if xml.get_node_name() == "layer":
				break
	
	return result


func _parse_gids(csv_text: String, width: int, cells: Array) -> void:
	var values := csv_text.split(",")
	var idx := 0
	
	for gid_str in values:
		gid_str = gid_str.strip_edges()
		if gid_str.empty():
			idx += 1
			continue
		
		var gid := int(gid_str)
		if gid == 0:
			idx += 1
			continue
		
		# 查找 source_id
		var source_id := -1
		var local_id := 0
		var firstgids := TILESET_MAP.keys()
		firstgids.sort_custom(func(a, b): return a > b)  # 降序
		
		for firstgid in firstgids:
			if gid >= firstgid:
				source_id = TILESET_MAP[firstgid]
				local_id = gid - firstgid
				break
		
		if source_id < 0:
			idx += 1
			continue
		
		# 计算 atlas 坐标
		var cols := SOURCE_COLS.get(source_id, 10)
		var atlas_x := local_id % cols
		var atlas_y := local_id / cols
		
		var x := idx % width
		var y := idx / width
		
		cells.append({
			"x": x,
			"y": y,
			"source_id": source_id,
			"atlas_x": atlas_x,
			"atlas_y": atlas_y,
		})
		
		idx += 1


func _skip_layer(xml: XMLParser) -> void:
	"""跳过当前图层的所有内容"""
	var depth := 1
	while depth > 0 and xml.read() == OK:
		if xml.get_node_type() == XMLParser.NODE_ELEMENT:
			depth += 1
		elif xml.get_node_type() == XMLParser.NODE_ELEMENT_END:
			depth -= 1


func _load_file(path: String) -> String:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return ""
	return file.get_as_text()
