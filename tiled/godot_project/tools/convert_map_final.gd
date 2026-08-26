@tool
extends EditorScript
"""
TMX → TileMapLayer 转换器 (Godot 编辑器内运行)

使用方法:
1. 在 Godot 中打开项目
2. 点击菜单: 项目 → 工具 → 执行脚本
3. 选择此文件
4. 等待控制台输出成功信息
5. 打开 maps/map01_editable.tscn
"""

const TMX_PATH = "res://maps/map01.tmx"
const OUTPUT_PATH = "res://maps/map01_editable.tscn"
const TILESET_PATH = "res://tilesets/world_tileset.tres"

# Tiled tileset firstgid → Godot TileSet source index
var TILESET_MAP := {
	1: 0,
	41: 1,
	361: 2,
	811: 3,
	979: 4,
	1021: 5,
	1063: 6,
	1117: 7,
	1157: 8,
	1220: 9,
	1256: 10,
}

func _run() -> void:
	print("\n" + "=" .repeat(60))
	print("  TMX → TileMapLayer 转换器")
	print("=" .repeat(60))

	# 检查文件
	if not FileAccess.file_exists(TMX_PATH):
		push_error("❌ 找不到 TMX 文件: " + TMX_PATH)
		return

	if not FileAccess.file_exists(TILESET_PATH):
		push_error("❌ 找不到 TileSet: " + TILESET_PATH)
		return

	# 解析 TMX
	var xml_content := FileAccess.get_file_as_string(TMX_PATH)
	var xml := XMLParser.new()
	var err := xml.open_buffer(xml_content.to_utf8_buffer())
	if err != OK:
		push_error("❌ 无法解析 XML")
		return

	var map_width := 0
	var map_height := 0
	var layers := []  # [{name, width, height, tiles: int[]}]

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
	print("📑 图层数量: %d" % [layers.size()])

	# 创建场景
	var root := Node2D.new()
	root.name = "map01"

	var tileset := load(TILESET_PATH) as TileSet
	if tileset == null:
		push_error("❌ 无法加载 TileSet")
		return

	print("\n✅ TileSet 已加载")

	var z_index := 0
	var total_tiles := 0

	for layer_data in layers:
		var layer_name: String = layer_data["name"]

		# 跳过角色图层
		if layer_name == "角色":
			print("⏭️  跳过 '%s'" % layer_name)
			continue

		# 创建 TileMapLayer
		var tile_map_layer := TileMapLayer.new()
		tile_map_layer.name = layer_name
		tile_map_layer.tile_set = tileset
		tile_map_layer.z_index = z_index

		# 填充图块
		var tiles: Array = layer_data["tiles"]
		var non_empty := 0

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
				var flipped_d: bool = bool((gid >> 29) & 1)
				var pure_gid: int = gid & 0x1FFFFFFF

				# 查找 source
				var source_idx := -1
				var local_id := 0
				var best_firstgid := -1

				for firstgid_key in TILESET_MAP.keys():
					var firstgid := int(firstgid_key)
					if pure_gid >= firstgid and firstgid > best_firstgid:
						best_firstgid = firstgid
						source_idx = TILESET_MAP[firstgid_key]
						local_id = pure_gid - firstgid

				if source_idx == -1:
					continue

				# 设置图块 (使用 Godot API!)
				var coord := Vector2i(x, y)
				tile_map_layer.set_cell(coord, source_idx, Vector2i(local_id, 0))
				non_empty += 1

		root.add_child(tile_map_layer)
		tile_map_layer.owner = root

		print("✅ %s: %d 个图块" % [layer_name, non_empty])
		total_tiles += non_empty
		z_index += 1

	# 保存场景
	var packed_scene := PackedScene.new()
	packed_scene.pack(root)

	var err_save := ResourceSaver.save(packed_scene, OUTPUT_PATH)
	if err_save != OK:
		push_error("❌ 保存失败: " + str(err_save))
		return

	print("\n" + "🎉".repeat(30))
	print("✅ 成功! 已保存到: " + OUTPUT_PATH)
	print("📊 共 %d 个图块, %d 个图层" % [total_tiles, z_index])
	print("🎉".repeat(30))
