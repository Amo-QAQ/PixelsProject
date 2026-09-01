@tool
extends Node2D
class_name PlantEntity

signal interacted(actor: Node)

@export_range(0, 35, 1) var variant: int = 0:
	set(value):
		variant = maxi(value, 0)
		_apply_visual()
@export var interaction_id: StringName = &"plant"

@onready var _sprite := get_node_or_null("Sprite2D") as Sprite2D


func _ready() -> void:
	_apply_visual()
	if not Engine.is_editor_hint():
		add_to_group("plant_entities")


func interact(actor: Node) -> void:
	interacted.emit(actor)


func _apply_visual() -> void:
	if not is_instance_valid(_sprite):
		return

	var frame_count := maxi(1, _sprite.hframes * _sprite.vframes)
	_sprite.frame = clampi(variant, 0, frame_count - 1)
