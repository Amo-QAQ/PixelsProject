extends Node2D
# ============================================================
#   一键地图转换器 - 打开此场景后按 F5 即可
# ============================================================

func _ready() -> void:
	print("\n" + "=".repeat(50))
	print("  🗺️  地图转换器启动")
	print("=".repeat(50))
	
	# 等待一帧确保场景加载完成
	await get_tree().process_frame
	
	# 执行转换
	var success := await _do_convert()
	
	if success:
		print("\n" + "✅".repeat(25))
		print("  转换完成！正在加载新地图...")
		print("✅".repeat(25))
		
		# 等待一下再切换
		await get_tree().create_timer(1.0).timeout
		
		# 切换到新地图
		var err := get_tree().change_scene_to_file("res://maps/map01_editable.tscn")
		if err != OK:
			push_error("无法加载新地图，请手动打开: maps/map01_editable.tscn")
	else:
		push_error("❌ 转换失败，请查看控制台错误信息")


func _do_convert() -> bool:
	const TMX_PATH = "res://maps/map01.tmx"
	const OUTPUT = "res://maps/map01_editable.tscn"
	const TILESET = "res://tilesets/world_tileset.tres"

	# GID 映射
	var GID_MAP := {
		1: 0, 41: 1, 361: 2, 811: 3,
		979: 4, 1021: 5, 1063: 6, 1117: 7,
		1157: 8, 1220: 9, 1256: 10,
	}

	# ====== 1. 检查文件 ======
	if not FileAccess.file_exists(TMX_PATH):
		push_error("找不到: " + TMX_PATH)
		return false
	if not FileAccess.file_exists(TILESET):
		push_error("找不到: " + TILESET)
		return false

	print("✓ 文件检查通过")

	# ====== 2. 解析 TMX XML ======
	print("\n📖 解析 TMX...")
	var xml_str := FileAccess.get_file_as_string(TMX_PATH)
	var xml := XMLParser.new()
	if xml.open_buffer(xml_str.to_utf8_buffer()) != OK:
		push_error("XML 解析失败")
		return false

	var layers := []  # [{name, w, h, tiles: Array}]

	while xml.read() == OK:
		if xml.get_node_type() == XMLParser.NODE_ELEMENT:
			if xml.get_node_name() == "layer":
				var lname := xml.get_attribute_value("name")
				var lw := xml.get_attribute_value("width").to_int()
				var lh := xml.get_attribute_value("height").to_int()
				var tiles := []
				
				while xml.read() == OK:
					if xml.get_node_type() == XMLParser.NODE_TEXT:
						for v in xml.get_node_data().strip_edges().split(","):
							v = v.strip_edges()
							if v != "":
								tiles.append(int(v))
					elif xml.get_node_type() == XMLParser.NODE_ELEMENT_END:
						if xml.get_node_name() == "data":
							break
				
				layers.append({name=lname, w=lw, h=h, tiles=tiles})
				print(f"  ✓ 图层 '{lname}': {tiles.size()} 数据")

	print(f"共 {layers.size()} 个图层")

	# ====== 3. 创建场景 ======
	print("\n🔨 构建场景...")
	var root := Node2D.new()
	root.name = "map01"

	var ts := load(TILESET) as TileSet
	if ts == null:
		push_error("TileSet 加载失败")
		return false

	var z_idx := 0
	var total_cells := 0

	for ld in layers:
		var lname: String = ld.name
		
		# 跳过角色层
		if lname == "角色":
			print(f"  ⏭️  跳过 '{lname}'")
			continue

		# 创建 TileMapLayer
		var tml := TileMapLayer.new()
		tml.name = lname
		tml.tile_set = ts
		tml.z_index = z_idx

		# 填充图块
		var count := 0
		var tiles: Array = ld.tiles

		for y in range(ld.h):
			for x in range(ld.w):
				var idx := y * ld.w + x
				if idx >= tiles.size():
					break
				
				var gid: int = tiles[idx]
				if gid == 0:
					continue

				# 解析 GID
				var pure := gid & 0x1FFFFFFF

				# 查找 source
				var src := -1
				var local := 0
				var best_fg := -1

				for fg in GID_MAP.keys():
					var fg_i := int(fg)
					if pure >= fg_i and fg_i > best_fg:
						best_fg = fg_i
						src = GID_MAP[fg]
						local = pure - fg_i

				if src < 0:
					continue

				# 设置单元格！
				tml.set_cell(Vector2i(x, y), src, Vector2i(local, 0))
				count += 1

		root.add_child(tml)
		tml.owner = root

		print(f"  ✓ {lname}: {count} 个图块")
		total_cells += count
		z_idx += 1

	# ====== 4. 保存 ======
	print(f"\n💾 保存到: {OUTPUT}")
	
	var ps := PackedScene.new()
	ps.pack(root)
	
	var err := ResourceSaver.save(ps, OUTPUT)
	if err != OK:
		push_error("保存失败: " + str(err))
		return false

	print(f"\n{'🎉'*25}")
	print(f"  成功! 共 {total_cells} 个图块, {z_idx} 个图层")
	print(f"  已保存: {OUTPUT}")
	print(f"{'🎉'*25}")

	return true
