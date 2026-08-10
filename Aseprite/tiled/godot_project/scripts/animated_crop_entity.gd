@tool
extends Node2D
class_name AnimatedCropEntity

signal interacted(actor: Node)

@export_range(0.05, 60.0, 0.05, "suffix:s") var seconds_per_stage: float = 1.0:
	set(value):
		seconds_per_stage = maxf(value, 0.05)
		_apply_animation_settings()
@export var loop_animation: bool = true:
	set(value):
		loop_animation = value
		_apply_animation_settings()
@export var play_animation: bool = true:
	set(value):
		play_animation = value
		_apply_animation_settings()
@export var interaction_id: StringName = &"crop"


func _ready() -> void:
	_apply_animation_settings()
	if not Engine.is_editor_hint():
		add_to_group("plant_entities")


func interact(actor: Node) -> void:
	interacted.emit(actor)


func _apply_animation_settings() -> void:
	var animated_sprite := get_node_or_null("AnimatedSprite2D") as AnimatedSprite2D
	if animated_sprite == null or animated_sprite.sprite_frames == null:
		return

	var animation_name := &"growth"
	if not animated_sprite.sprite_frames.has_animation(animation_name):
		return

	animated_sprite.sprite_frames.set_animation_speed(animation_name, 1.0 / seconds_per_stage)
	animated_sprite.sprite_frames.set_animation_loop(animation_name, loop_animation)
	if play_animation:
		animated_sprite.play(animation_name)
	else:
		animated_sprite.stop()
