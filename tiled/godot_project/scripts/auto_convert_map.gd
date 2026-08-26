extends Node2D
"""
地图转换器 - 在游戏启动时自动将 TMX 转换为可编辑的 TileMapLayer 格式
运行一次后自动禁用自己
"""

const TMX_PATH := "res://maps/map01.tmx"
const OUTPUT_PATH := "res://maps/map01_editable.tscn"
const TILESET_PATH := "res://tilesets/world_tileset.tres"

# Tiled firstgid → world_tileset source index
var _tileset_map := {
	1: 0,      # terrainA
	41: 1,     # terrainB
	361: 2,    # terrainC
	811: 3,    # water-ani
	979: 4,    # decorations
	1021: 5,   # Props
	1063: 6,   # house_A
	1117: 7,   # house_B
	1157: 8,   # tree
	1220: 9,   # crop
	1256: 10,  # 角色_F
}

# 每个 source 的列数
var _source_cols := {
	0: 10, 1: 32, 2: 30, 3: 8, 4: 14,
	5: 7, 6: 9, 7: 5, 8: 1, 9: 12, 10: 8
}


func _ready() -> void:
	print("\n" + "=" .repeat(50))
	print("  🗺️  地图转换器启动")
	print("=" .repeat(50))
	
	# 等待一帧确保资源系统就绪
	await get_tree().process_frame
	
	_convert_map()
	
	print("\n✅ 转换完成！请打开 maps/map01_editable.tscn")
	print("   此脚本将在下次运行时自动禁用")
	
	# 标记已完成（通过修改自身）
	_disable_self()


func _disable_self() -> void:
	# 将此节点从场景中移除
	queue_free()


func _convert_map() -> void:
	# 检查文件
	if not FileAccess.file_exists(TMX_PATH):
		push_error("❌ 找不到 TMX: " + TMX_PATH)
		return
	
	if not FileAccess.file_exists(TILESET_PATH):
		push_error("❌ 找不到 TileSet: " + TILESET_PATH)
		return
	
	# 解析 XML
	var xml_content := FileAccess.get_file_as_string(TMX_PATH)
	var xml := XMLParser.new()
	var err := xml.open_buffer(xml_content.to_utf8_buffer())
	if err != OK:
		push_error("❌ 无法解析 XML: " + str(err))
		return
	
	# 解析 TMX 结构
	var map_width := 0
	var map_height := 0
	var layers := []  # [{name, tiles: int[]}]
	
	while xml.read() == OK:
		if xml.get_node_type() == XMLParser.NODE_ELEMENT:
			if xml.get_node_name() == "map":
				map_width = xml.get_attribute_value("width").to_int()
				map_height = xml.get_attribute_value("height").to_int()
			
			elif xml.get_node_name() == "layer":
				var layer_name := xml.get_attribute_value("name")
				var layer_w := xml.get_attribute_value("width").to_int()
				var layer_h := xml.get_attribute_value("height").to_int()
				
				var tiles := []
				while xml.read() == OK:
					if xml.get_node_type() == XMLParser.NODE_TEXT:
						var csv := xml.get_node_data().strip_edges()
						for val in csv.split(","):
							val = val.strip_edges()
							if val != "":
								tiles.append(val.to_int())
					elif xml.get_node_type() == XMLParser.NODE_ELEMENT_END and xml.get_node_name() == "data":
						break
				
				layers.append({
					"name": layer_name,
					"width": layer_w,
					"height": layer_h,
					"tiles": tiles,
				})
	
	print("\n📐 地图尺寸: %d x %d" % [map_width, map_height])
	print("📑 图层数量: %d" % layers.size())
	
	# 创建场景根节点
	var root := Node2D.new()
	root.name = "map01"
	
	# 加载 TileSet
	var tileset := load(TILESET_PATH) as TileSet
	if tileset == null:
		push_error("❌ 无法加载 TileSet")
		return
	
	print("✅ TileSet 已加载")
	
	var z_index := 0
	var total_tiles := 0
	
	for layer_data in layers:
		var layer_name: String = layer_data["name"]
		
		if layer_name == "角色":
			print("⏭️  跳过 '%s'" % layer_name)
			continue
		
		# 创建 TileMapLayer
		var tile_layer := TileMapLayer.new()
		tile_layer.name = layer_name
		tile_layer.tile_set = tileset
		tile_layer.z_index = z_index
		
		# 使用 Godot API 设置每个单元格
		var tiles: Array = layer_data["tiles"]
		var count := 0
		
		for y in range(layer_data["height"]):
			for x in range(layer_data["width"]):
				var idx := y * layer_data["width"] + x
				if idx >= tiles.size():
					break
				
				var gid: int = tiles[idx]
				if gid == 0:
					continue
				
				# 解析 GID
				var flipped_h: bool = bool((gid >> 31) & 1)
				var flipped_v: bool = bool((gid >> 30) & 1)
				var pure_gid: int = gid & 0x1FFFFFFF
				
				# 找到 source
				var source_idx := -1
				var local_id := 0
				var best_firstgid := -1
				
				for firstgid_key in _tileset_map.keys():
					var firstgid := int(firstgid_key)
					if pure_gid >= firstgid and firstgid > best_firstgid:
						best_firstgid = firstgid
						source_idx = _tileset_map[firstgid]
						local_id = pure_gid - firstgid
				
				if source_idx == -1 or not _source_cols.has(source_idx):
					continue
				
				# 计算 atlas 坐标
				var cols: int = _source_cols[source_idx]
				var atlas_x := local_id % cols
				var atlas_y := local_id / cols
				
				# 使用 set_cell API（这是最可靠的方式！）
				var coord := Vector2i(x, y)
				var atlas := Vector2i(atlas_x, atlas_y)
				var source_id := source_idx
				
				tile_layer.set_cell(coord, source_id, atlas, 0)
				
				# 处理翻转
				if flipped_h or flipped_v:
					var alt := tile_layer.get_cell_alternative_tile(coord)
					tile_layer.set_cell(coord, source_id, atlas, alt, flipped_h, flipped_v, false)
				
				count += 1
		
		root.add_child(tile_layer)
		tile_layer.owner = root  # 重要！设为 owner 才能保存
		
		total_tiles += count
		z_index += 1
		print("  ✓ %s: %d 个图块" % [layer_name, count])
	
	# 保存为 PackedScene
	var packed_scene := PackedScene.new()
	packed_scene.pack(root)
	
	var save_err := ResourceSaver.save(packed_scene, OUTPUT_PATH)
	if save_err != OK:
		push_error("❌ 保存失败: " + str(save_err))
		return
	
	print("\n" + "=" .repeat(50))
	print("🎉 成功!")
	print("   输出: %s" % OUTPUT_PATH)
	print("   图层: %d" % z_index)
	print("   总图块: %d" % total_tiles)
	print("=" .repeat(50))
