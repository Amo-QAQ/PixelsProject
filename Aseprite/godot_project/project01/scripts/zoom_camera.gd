extends Camera2D

@export_range(0.1, 8.0, 0.05) var min_zoom: float = 0.5
@export_range(0.1, 8.0, 0.05) var max_zoom: float = 4.0
@export_range(1.01, 2.0, 0.01) var zoom_step: float = 1.15
@export_range(0.0, 1.0, 0.01) var zoom_duration: float = 0.12
@export_range(0.1, 4.0, 0.1) var pan_speed: float = 1.0

var _target_zoom: float
var _zoom_tween: Tween
var _is_panning := false


func _ready() -> void:
	_target_zoom = zoom.x


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and _is_panning:
		position -= event.relative / zoom * pan_speed
		get_viewport().set_input_as_handled()
		return

	if not event is InputEventMouseButton:
		return

	if event.button_index == MOUSE_BUTTON_MIDDLE:
		_is_panning = event.pressed
		Input.set_default_cursor_shape(
			Input.CURSOR_DRAG if _is_panning else Input.CURSOR_ARROW
		)
		get_viewport().set_input_as_handled()
		return

	if not event.pressed:
		return

	match event.button_index:
		MOUSE_BUTTON_WHEEL_UP:
			_change_zoom(_target_zoom * zoom_step)
		MOUSE_BUTTON_WHEEL_DOWN:
			_change_zoom(_target_zoom / zoom_step)
		_:
			return

	get_viewport().set_input_as_handled()


func _change_zoom(value: float) -> void:
	_target_zoom = clampf(value, min_zoom, max_zoom)

	if is_instance_valid(_zoom_tween):
		_zoom_tween.kill()

	if is_zero_approx(zoom_duration):
		zoom = Vector2.ONE * _target_zoom
		return

	_zoom_tween = create_tween()
	_zoom_tween.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	_zoom_tween.tween_property(self, "zoom", Vector2.ONE * _target_zoom, zoom_duration)
