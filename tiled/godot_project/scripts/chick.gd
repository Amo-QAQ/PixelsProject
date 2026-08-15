extends CharacterBody2D

@onready var anim: AnimatedSprite2D = $AnimatedSprite2D

@export var speed: float = 40.0          # 移动速度
@export var change_dir_time: float = 2.0 # 每隔多少秒换一次方向

var direction := Vector2.ZERO
var timer := 0.0

func _ready():
	# 随机选一个初始方向
	_change_direction()
	# 开始播放走路动画
	_play_walk_anim()

func _physics_process(delta: float):
	timer += delta
	if timer >= change_dir_time:
		timer = 0.0
		_change_direction()
		_play_walk_anim()
	
	# 移动
	velocity = direction * speed
	move_and_slide()
	
	# 如果撞到墙就立刻换方向（可选）
	if get_slide_collision_count() > 0:
		_change_direction()
		_play_walk_anim()

func _change_direction():
	# 随机四个方向（你也可以改成八方向）
	var dirs = [
		Vector2.UP,    # 上 / 后
		Vector2.DOWN,  # 下 / 前
		Vector2.LEFT,  # 左
		Vector2.RIGHT  # 右
	]
	direction = dirs[randi() % dirs.size()]

func _play_walk_anim():
	# 根据方向播放对应动画（请根据你实际动画名称修改）
	if direction == Vector2.UP:
		anim.play("walk_B")      # 假设 walk_B 是背对/向上
	elif direction == Vector2.DOWN:
		anim.play("walk_Z")      # 假设 walk_Z 是正面/向下
	elif direction == Vector2.LEFT:
		anim.play("walk_L")
		anim.flip_h = false      # 根据你的精灵朝向调整
	elif direction == Vector2.RIGHT:
		anim.play("walk_L")      # 如果没有 walk_R，就用 walk_L 并翻转
		anim.flip_h = true
