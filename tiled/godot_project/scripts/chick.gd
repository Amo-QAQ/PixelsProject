extends CharacterBody2D

@onready var anim: AnimatedSprite2D = $AnimatedSprite2D

@export var speed: float = 40.0          # 移动速度
@export var change_dir_time: float = 2.0 # 每隔多少秒换一次方向

# 状态枚举
enum State { 
	WALK,           # 行走（站立状态）
	IDLE_1,         # 待机1（站立状态）
	IDLE_2,         # 待机2（站立状态）
	EAT,            # 吃食（站立状态）
	SLEEP,          # 睡觉（蹲下状态）
	SQUAT_IDLE,     # 蹲下待机（蹲下状态）
	SQUAT_DOWN,     # 蹲下过渡动画（站立→蹲）
	SQUAT_UP        # 起立过渡动画（蹲→站立）
}

# 是否为"蹲下类"状态（需要通过 squat 过渡到达）
const SQUATTING_STATES = [State.SLEEP, State.SQUAT_IDLE]
# 是否为"站立类"状态
const STANDING_STATES = [State.WALK, State.IDLE_1, State.IDLE_2, State.EAT]

var direction := Vector2.ZERO
var timer := 0.0
var current_state := State.WALK

# 随机状态切换相关
var state_timer := 0.0
var state_duration := 0.0

# 过渡动画相关
var state_after_transition: State = State.WALK    # 过渡完成后要进入的目标状态
var current_facing: String = "Z"                  # 当前朝向 (B/Z/L)

# 连续静止计数器（防止一直停下来）
var consecutive_idle_count := 0
const MAX_CONSECUTIVE_IDLE := 2   # 最多连续2个静止状态


func _ready():
	_change_direction()
	_update_facing_from_direction()
	_play_walk_anim()


func _physics_process(delta: float):
	state_timer += delta
	
	match current_state:
		State.WALK:
			_update_walking(delta)
		
		State.IDLE_1, State.IDLE_2, State.EAT:
			if state_timer >= state_duration:
				_pick_and_transition_to_new_state()
		
		State.SLEEP, State.SQUAT_IDLE:
			if state_timer >= state_duration:
				_pick_and_transition_to_new_state()
		
		State.SQUAT_DOWN:
			if not anim.is_playing():
				current_state = state_after_transition
				_play_state_anim(current_state)
				state_timer = 0.0
				state_duration = _get_state_duration(current_state)
		
		State.SQUAT_UP:
			if not anim.is_playing():
				current_state = state_after_transition
				if current_state == State.WALK:
					_change_direction()
					_update_facing_from_direction()
				_play_state_anim(current_state)
				state_timer = 0.0
				state_duration = _get_state_duration(current_state)


func _update_walking(delta: float):
	timer += delta
	if timer >= change_dir_time:
		timer = 0.0
		_change_direction()
		_update_facing_from_direction()
		_play_walk_anim()
	
	# 移动（已归一化，斜向不会更快）
	velocity = direction * speed
	move_and_slide()
	
	# 撞墙换方向
	if get_slide_collision_count() > 0:
		_change_direction()
		_update_facing_from_direction()
		_play_walk_anim()
	
	# 约每2秒有几率停下
	if randf() < 0.008:
		_pick_and_transition_to_new_state()


func _pick_and_transition_to_new_state():
	var states = [
		State.WALK,
		State.IDLE_1,
		State.IDLE_2,
		State.EAT,
		State.SLEEP,
		State.SQUAT_IDLE
	]
	
	var weights = [45, 20, 15, 12, 4, 4]
	
	# 防止连续静止
	if consecutive_idle_count >= MAX_CONSECUTIVE_IDLE:
		weights[0] = 80
		for i in range(1, weights.size()):
			weights[i] = weights[i] / 4
	
	var total_weight = 0
	for w in weights:
		total_weight += w
	
	var rand_val = randi() % total_weight
	var cumulative = 0
	var next_state = State.WALK
	
	for i in range(states.size()):
		cumulative += weights[i]
		if rand_val < cumulative:
			next_state = states[i]
			break
	
	# 判断是否需要过渡动画
	var current_is_standing = current_state in STANDING_STATES or current_state == State.SQUAT_UP
	var current_is_squatting = current_state in SQUATTING_STATES or current_state == State.SQUAT_DOWN
	var next_is_standing = next_state in STANDING_STATES
	var next_is_squatting = next_state in SQUATTING_STATES
	
	# 更新连续静止计数器
	if next_state == State.WALK:
		consecutive_idle_count = 0
	elif next_state in [State.IDLE_1, State.IDLE_2, State.EAT, State.SLEEP, State.SQUAT_IDLE]:
		consecutive_idle_count += 1
	
	if current_is_standing and next_is_squatting:
		current_state = State.SQUAT_DOWN
		state_after_transition = next_state
		state_timer = 0.0
		state_duration = 0.0
		
		_randomize_facing()
		_play_squat_animation(false)
		
	elif current_is_squatting and next_is_standing:
		current_state = State.SQUAT_UP
		state_after_transition = next_state
		state_timer = 0.0
		state_duration = 0.0
		
		_play_squat_animation(true)
		
	else:
		current_state = next_state
		
		if next_state == State.WALK:
			_change_direction()
			_update_facing_from_direction()
		
		_play_state_anim(next_state)
		state_timer = 0.0
		state_duration = _get_state_duration(next_state)


func _play_walk_anim():
	anim.play("walk_" + current_facing)
	_apply_flip()


func _play_state_anim(state: State):
	match state:
		State.WALK:
			_play_walk_anim()
		State.IDLE_1:
			if randf() < 0.3:
				_randomize_facing()
			anim.play("idle_1_" + current_facing)
			anim.flip_h = false
		State.IDLE_2:
			if randf() < 0.25:
				_randomize_facing()
			anim.play("idle_2_" + current_facing)
			anim.flip_h = false
		State.EAT:
			if randf() < 0.4:
				_randomize_facing()
			anim.play("eat_" + current_facing)
			anim.flip_h = false
		State.SLEEP:
			_randomize_facing()
			anim.play("sleep_" + current_facing)
			anim.flip_h = false
		State.SQUAT_IDLE:
			anim.play("squat_idle_" + current_facing)
			anim.flip_h = false


func _play_squat_animation(reversed: bool):
	anim.play("squat_" + current_facing)
	
	if reversed:
		anim.frame = anim.sprite_frames.get_frame_count(anim.animation) - 1
		anim.speed_scale = -1.0
	else:
		anim.speed_scale = 1.0
	
	anim.flip_h = false


func _change_direction():
	# 8方向随机（星露谷风格）
	# 基础4方向
	var cardinal_dirs = [
		Vector2.UP,
		Vector2.DOWN,
		Vector2.LEFT,
		Vector2.RIGHT
	]
	
	# 小角度斜向（约25-30度偏移，更自然）
	# tan(25°) ≈ 0.47, tan(30°) ≈ 0.58
	var diagonal_dirs = [
		Vector2(-0.85, -0.53).normalized(),   # 左上（偏左）
		Vector2(-0.85, 0.53).normalized(),    # 左下（偏左）
		Vector2(0.85, -0.53).normalized(),    # 右上（偏右）
		Vector2(0.85, 0.53).normalized()      # 右下（偏右）
	]
	
	# 60%概率走基本4方向，40%概率走小角度斜向
	if randf() < 0.6:
		direction = cardinal_dirs[randi() % cardinal_dirs.size()]
	else:
		direction = diagonal_dirs[randi() % diagonal_dirs.size()]


func _update_facing_from_direction():
	"""
	根据8方向移动向量确定4向动画朝向（星露谷逻辑）
	- 主要判断哪个轴的分量更大
	- 如果X轴更大 → 左/右
	- 如果Y轴更大 → 上/下
	"""
	var abs_x = absf(direction.x)
	var abs_y = absf(direction.y)
	
	if abs_x > abs_y:
		# 水平分量为主 → 左或右
		if direction.x > 0:
			current_facing = "L"  # 右（用L+flip_h）
		else:
			current_facing = "L"  # 左
	else:
		# 垂直分量为主 → 上或下
		if direction.y < 0:
			current_facing = "B"  # 上/后
		else:
			current_facing = "Z"  # 下/前


func _randomize_facing():
	var facings = ["B", "Z", "L"]
	current_facing = facings[randi() % facings.size()]


func _apply_flip():
	"""只有向右移动且使用左侧动画时才翻转"""
	if direction.x > 0 and current_facing == "L":
		anim.flip_h = true
	else:
		anim.flip_h = false


func _get_state_duration(state: State) -> float:
	match state:
		State.WALK:
			return _random_duration(1.5, 2.5)
		State.IDLE_1:
			return _random_duration(1.0, 2.0)
		State.IDLE_2:
			return _random_duration(1.5, 2.5)
		State.EAT:
			return _random_duration(1.5, 2.5)
		State.SLEEP:
			return _random_duration(3.0, 5.0)
		State.SQUAT_IDLE:
			return _random_duration(2.0, 3.5)
		_:
			return 2.0


func _random_duration(min_val: float, max_val: float) -> float:
	return randf_range(min_val, max_val)
