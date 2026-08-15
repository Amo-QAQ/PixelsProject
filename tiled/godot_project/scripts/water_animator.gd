extends Node

@export var tile_map_path: NodePath
@export var water_layer_name := "水"
@export_range(0.02, 1.0, 0.01) var frame_duration := 0.1

const WATER_TEXTURE_PATH := "res://assets/Terrain/Tileset/water-ani.png"
const ATLAS_COLUMNS := 24
const ANIMATIONS := {
	3: [3, 6, 9, 12, 15, 18, 21],
	5: [5, 8, 11, 14, 17, 20, 23],
	51: [51, 54, 57, 60, 63, 66, 69],
	52: [52, 55, 58, 61, 64, 67, 70],
	53: [53, 56, 59, 62, 65, 68, 71],
	75: [75, 78, 81, 84, 87, 90, 93],
	76: [76, 79, 82, 85, 88, 91, 94],
	77: [77, 80, 83, 86, 89, 92, 95],
	98: [98, 100, 102, 104, 106, 108, 110],
	99: [99, 101, 103, 105, 107, 109, 111],
	146: [146, 148, 150, 152, 154, 156, 158],
	147: [147, 149, 151, 153, 155, 157, 159],
}

var _tile_map: TileMap
var _water_layer := -1
var _water_source := -1
var _animated_cells: Array[Dictionary] = []
var _elapsed := 0.0
var _frame_index := 0


func _ready() -> void:
	_tile_map = get_node_or_null(tile_map_path) as TileMap
	if _tile_map == null or _tile_map.tile_set == null:
		set_process(false)
		return

	_water_layer = _find_layer_index()
	_water_source = _find_water_source_id()
	if _water_layer < 0 or _water_source < 0:
		set_process(false)
		return

	_collect_animated_cells()
	set_process(not _animated_cells.is_empty())


func _process(delta: float) -> void:
	_elapsed += delta
	while _elapsed >= frame_duration:
		_elapsed -= frame_duration
		_frame_index = (_frame_index + 1) % 7
		_apply_current_frame()


func _find_layer_index() -> int:
	for layer_index in range(_tile_map.get_layers_count()):
		if _tile_map.get_layer_name(layer_index) == water_layer_name:
			return layer_index
	return -1


func _find_water_source_id() -> int:
	var tile_set := _tile_map.tile_set
	for source_index in range(tile_set.get_source_count()):
		var source_id := tile_set.get_source_id(source_index)
		var source := tile_set.get_source(source_id) as TileSetAtlasSource
		if source == null or source.texture == null:
			continue
		if source.texture.resource_path == WATER_TEXTURE_PATH:
			return source_id
	return -1


func _collect_animated_cells() -> void:
	for coords in _tile_map.get_used_cells(_water_layer):
		if _tile_map.get_cell_source_id(_water_layer, coords) != _water_source:
			continue

		var atlas_coords := _tile_map.get_cell_atlas_coords(_water_layer, coords)
		var tile_id := atlas_coords.y * ATLAS_COLUMNS + atlas_coords.x
		if not ANIMATIONS.has(tile_id):
			continue

		_animated_cells.append({
			"coords": coords,
			"sequence": ANIMATIONS[tile_id],
			"alternative": _tile_map.get_cell_alternative_tile(_water_layer, coords),
		})


func _apply_current_frame() -> void:
	for cell_data in _animated_cells:
		var sequence: Array = cell_data["sequence"]
		var tile_id: int = sequence[_frame_index % sequence.size()]
		var atlas_coords := Vector2i(tile_id % ATLAS_COLUMNS, tile_id / ATLAS_COLUMNS)
		_tile_map.set_cell(
			_water_layer,
			cell_data["coords"],
			_water_source,
			atlas_coords,
			cell_data["alternative"]
		)
