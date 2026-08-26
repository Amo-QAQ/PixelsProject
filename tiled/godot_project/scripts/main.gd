extends Node2D

@export var tiled_character_layer = "角色"


func _ready():
	var tile_map = get_node_or_null("Map01/TileMap")
	if tile_map == null:
		return
	
	for i in range(tile_map.get_layers_count()):
		if tile_map.get_layer_name(i) == tiled_character_layer:
			tile_map.set_layer_enabled(i, false)
			break
