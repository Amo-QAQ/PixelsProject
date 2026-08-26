@tool
extends EditorScript
"""
TMX → TileMapLayer 转换器 (Godot 编辑器脚本)

使用方法：
1. 在 Godot 中打开项目
2. 点击菜单: 项目 → 工具 → 执行脚本
3. 选择此文件
4. 会自动生成 map01_editable.tscn
"""

const TMX_PATH = "res://maps/map01.tmx"
const OUTPUT_PATH = "res://maps/map01_editable.tscn"
const TILESET_PATH = "res://tilesets/world_tileset.tres"

# TMX tileset firstgid → world_tileset.tres source index
const TILESET_MAP = {
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

# 每个 source 的列数 (用于计算 atlas 坐标)
const SOURCE_COLS = {
	0: 10,   # terrainA
	1: 32,   # terrainB
	2: 30,   # terrainC
	3: 24,   # water-ani
	4: 14,   # decorations
	5: 7,    # props
	6: 9,    # house_A
	7: 5,    # house_B
	8: 18,   # tree
	9: 12,   # crop
	10: 8,   # 角色
}


func _run() -> void:
	print("\n" + "=" .repeat(50))
	print("TMX → TileMapLayer 转换器")
	print("=" .repeat(50))

	# 检查文件
	if not FileAccess.file_exists(TMX_PATH):
		push_error("找不到 TMX 文件: " + TMX_PATH)
		return

	var xml_content = FileAccess.get_file_as_string(TMX_PATH)
	var xml = XMLParser.new()
	xml.open_buffer(xml_content.to_utf8_buffer())

	# 解析 TMX
	var map_width := 0
	var map_height := 0
	var layers := []  # [{name, width, height, data: int[]}]

	while xml.read() == OK:
		if xml.get_node_type() == XMLParser.NODE_ELEMENT:
			if xml.get_node_name() == "map":
				map_width = xml.get_attribute_value("width").to_int()
				map_height = xml.get_attribute_value("height").to_int()

			elif xml.get_node_name() == "layer":
				var layer_name = xml.get_attribute_value("name")
				var layer_w = xml.get_attribute_value("width").to_int()
				var layer_h = xml.get_attribute_value("height").to_int()

				# 读取 data 元素
				var tiles := []
				while xml.read() == OK:
					if xml.get_node_type() == XMLParser.NODE_TEXT:
						var csv = xml.get_node_data().strip_edges()
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

	print(f"\n地图尺寸: {map_width} x {map_height}")
	print(f"图层数量: {layers.size()}")

	# 创建场景
	var root := Node2D.new()
	root.name = "map01"

	# 加载 TileSet
	var tileset = load(TILESET_PATH)
	if tileset == null:
		push_error("无法加载 TileSet: " + TILESET_PATH)
		return

	var z_index := 0
	var skipped_layers := []

	for layer_data in layers:
		var layer_name = layer_data["name"]

		# 跳过角色图层
		if layer_name == "角色":
			skipped_layers.append(layer_name)
			continue

		# 创建 TileMapLayer
		var tile_map_layer := TileMapLayer.new()
		tile_map_layer.name = layer_name
		tile_map_layer.tile_set = tileset
		tile_map_layer.z_index = z_index

		# 填充图块数据
		var tiles = layer_data["tiles"]
		var non_empty := 0

		for y in range(layer_data["height"]):
			for x in range(layer_data["width"]):
				var idx = y * layer_data["width"] + x
				var gid = tiles[idx]

				if gid == 0:
					continue

				# 解析 GID
				var flipped_h = bool((gid >> 31) & 1)
				var flipped_v = bool((gid >> 30) & 1)
				var flipped_d = bool((gid >> 29) & 1)
				var pure_gid = gid & 0x1FFFFFFF

				# 找到 source index
				var source_idx = -1
				var local_id = 0

				for firstgid in TILESET_MAP.keys():
					if pure_gid >= int(firstgid):
						source_idx = TILESET_MAP[firstgid]
						local_id = pure_gid - int(firstgid)

				if source_idx == -1 or not SOURCE_COLS.has(source_idx):
					continue

				# 计算 atlas 坐标
				var cols = SOURCE_COLS[source_idx]
				var atlas_x = local_id % cols
				var atlas_y = local_id / cols

				# 设置图块
				var coords := Vector2i(x, y)
				var tile_source := source_idx
				var atlas_origin := Vector2i(atlas_x, atlas_y)
				var alternative_tile := 0

				tile_map_layer.set_cell(coords, tile_source, atlas_origin, alternative_tile)

				non_empty += 1

		root.add_child(tile_map_layer)
		tile_map_layer.owner = root

		print(f"✓ 图层 '{layer_name}': {non_empty} 个图块")
		z_index += 1

	# 保存场景
	var packed_scene := PackedScene.new()
	packed_scene.pack(root)
	var err = ResourceSaver.save(packed_scene, OUTPUT_PATH)

	if err == OK:
		print(f"\n{'=' .repeat(50)}")
		print(f"✅ 成功! 输出文件: {OUTPUT_PATH}")
		print(f"跳过的图层: {skipped_layers}")
		print(f"现在可以在 Godot 中打开并编辑了!")
		print("=" .repeat(50))
	else:
		push_error("保存失败: " + str(err))
