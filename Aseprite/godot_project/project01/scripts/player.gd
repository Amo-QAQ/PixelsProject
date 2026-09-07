extends CharacterBody2D

@export_range(1.0, 500.0, 1.0) var move_speed: float = 80.0
@export_range(1.0, 30.0, 0.5) var animation_fps: float = 14.0

@export_group("Direction Textures")
@export var front_texture: Texture2D
@export var back_texture: Texture2D
@export var left_texture: Texture2D
@export var right_texture: Texture2D

@onready var sprite: Sprite2D = $Sprite2D

enum Facing { FRONT, BACK, LEFT, RIGHT }

const WALK_FRAME_COUNT := 8
const IDLE_ROW := 0
const WALK_ROW := 1

var _facing := Facing.FRONT
var _animation_time := 0.0


func _ready() -> void:
	_apply_facing_texture()


func _physics_process(delta: float) -> void:
	var input_direction := Vector2(
		float(Input.is_physical_key_pressed(KEY_D))
			- float(Input.is_physical_key_pressed(KEY_A)),
		float(Input.is_physical_key_pressed(KEY_S))
			- float(Input.is_physical_key_pressed(KEY_W))
	)

	if input_direction.is_zero_approx():
		velocity = Vector2.ZERO
		_animation_time = 0.0
		sprite.frame_coords = Vector2i(0, IDLE_ROW)
	else:
		input_direction = input_direction.normalized()
		velocity = input_direction * move_speed
		_update_facing_direction(input_direction)
		_animation_time += delta
		var frame := int(_animation_time * animation_fps) % WALK_FRAME_COUNT
		sprite.frame_coords = Vector2i(frame, WALK_ROW)

	move_and_slide()


func _update_facing_direction(direction: Vector2) -> void:
	var new_facing: Facing

	if absf(direction.x) > absf(direction.y):
		new_facing = Facing.RIGHT if direction.x > 0.0 else Facing.LEFT
	else:
		new_facing = Facing.FRONT if direction.y > 0.0 else Facing.BACK

	if new_facing == _facing:
		return

	_facing = new_facing
	_apply_facing_texture()


func _apply_facing_texture() -> void:
	match _facing:
		Facing.FRONT:
			sprite.texture = front_texture
		Facing.BACK:
			sprite.texture = back_texture
		Facing.LEFT:
			sprite.texture = left_texture
		Facing.RIGHT:
			sprite.texture = right_texture
