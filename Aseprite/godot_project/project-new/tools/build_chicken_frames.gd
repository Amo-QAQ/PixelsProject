extends SceneTree
## 从 combined 精灵图生成 SpriteFrames 资源（大鸡 chicken / 小鸡 chick）
## 用法: godot --headless --path <project> --script res://tools/build_chicken_frames.gd
## 每张 combined 图布局: 3 行 = b(背)/f(前)/l(左) 方向, 每行内按 32x32 网格分帧, 行内行优先

const FRAME := 32
const DIRS := ["b", "f", "l"]

# sheet: combined 文件名(去掉前缀)  name: 状态名  cols/rows: 每个方向块内的网格  fps: 播放速度
const SPECS := [
	{"sheet": "idle01.png",      "name": "idle",       "cols": 4, "rows": 1, "fps": 8.0},
	{"sheet": "idle02.png",      "name": "idle2",      "cols": 3, "rows": 3, "fps": 8.0},
	{"sheet": "walk.png",        "name": "walk",       "cols": 4, "rows": 1, "fps": 8.0},
	{"sheet": "eat.png",         "name": "eat",        "cols": 5, "rows": 2, "fps": 8.0},
	{"sheet": "sleep.png",       "name": "sleep",      "cols": 4, "rows": 2, "fps": 8.0},
	{"sheet": "squat.png",       "name": "squat",      "cols": 4, "rows": 1, "fps": 8.0},
	{"sheet": "squat_idle.png",  "name": "squat_idle", "cols": 4, "rows": 2, "fps": 8.0},
	{"sheet": "like.png",        "name": "like",       "cols": 4, "rows": 2, "fps": 8.0},
]

func _init() -> void:
	for prefix in ["chicken", "chick"]:
		var frames := SpriteFrames.new()
		if frames.has_animation("default"):
			frames.remove_animation("default")
		for spec in SPECS:
			var path := "res://assets/chicken/%s_%s" % [prefix, spec.sheet]
			var tex: Texture2D = load(path)
			if tex == null:
				push_error("无法加载贴图: %s" % path)
				quit(1)
				return
			var dir_block_h: int = tex.get_height() / 3
			for di in range(3):
				var anim_name := "%s_%s" % [spec.name, DIRS[di]]
				frames.add_animation(anim_name)
				frames.set_animation_speed(anim_name, spec.fps)
				frames.set_animation_loop(anim_name, true)
				var total: int = spec.cols * spec.rows
				for fi in range(total):
					var fx: int = fi % spec.cols
					var fy: int = fi / spec.cols
					var region := Rect2(fx * FRAME, di * dir_block_h + fy * FRAME, FRAME, FRAME)
					var atex := AtlasTexture.new()
					atex.atlas = tex
					atex.region = region
					frames.add_frame(anim_name, atex)
		var out := "res://assets/chicken/%s_frames.tres" % prefix
		var err := ResourceSaver.save(frames, out)
		if err != OK:
			push_error("保存失败 %s, err=%d" % [out, err])
			quit(1)
			return
		print("OK 已生成 %s (%d 个动画)" % [out, frames.get_animation_names().size()])
	quit(0)
