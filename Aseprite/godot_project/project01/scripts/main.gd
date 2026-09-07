extends Node2D

@export var tiled_character_layer := "角色"


func _ready() -> void:
	var tile_map := get_node_or_null("Map01/TileMap")
	if tile_map == null:
		return

	for layer_index in tile_map.get_layers_count():
		if tile_map.get_layer_name(layer_index) == tiled_character_layer:
			tile_map.set_layer_enabled(layer_index, false)
			break

