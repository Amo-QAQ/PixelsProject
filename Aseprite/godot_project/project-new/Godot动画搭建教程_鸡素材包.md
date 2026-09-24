# 鸡素材包 · 从零搭建 Godot 状态机 + 时间线（教程）

> 这份文档是**准备工作交接 + 动手教程**：素材我已经帮你整理好，动画怎么做由你亲手完成。
> 项目：`E:\My_work\PixelsProject\Aseprite\godot_project\project-new` ｜ Godot 4.7.2

---

## 0. 准备工作清单（已完成，直接可用）

| 内容 | 位置 | 说明 |
|---|---|---|
| 大鸡 8 张精灵图 | `assets/chicken/chicken_*.png` | 已复制进项目，编辑器会自动导入 |
| 小鸡 8 张精灵图 | `assets/chicken/chick_*.png` | 同上 |
| 大鸡帧资源 | `assets/chicken/chicken_frames.tres` | SpriteFrames：8 状态 × 3 方向 = 24 个动画 |
| 小鸡帧资源 | `assets/chicken/chick_frames.tres` | 同上 |
| 重建脚本 | `tools/build_chicken_frames.gd` | 素材变更后重跑可重新生成 .tres |

**重建 .tres 的命令**（改了素材后执行）：

```bash
godot --headless --path project-new --script res://tools/build_chicken_frames.gd
```

**动画命名约定**（两个 .tres 内部一致）：`状态_方向`，例如 `idle_f`、`walk_b`、`eat_l`。

---

## 1. 素材结构（做动画前先记住这张表）

每张 combined 精灵图 = **3 行**，自上而下分别是 **b(背面) / f(正面) / l(左侧)**；每行内按 **32×32** 网格、**行优先**分帧：

| 状态 | 每方向帧数 | 建议 fps | 说明 |
|---|---|---|---|
| idle01 → `idle` | 4 | 4 | 待机 |
| idle02 → `idle2` | 9（3×3） | 4 | 待机·细节 |
| walk | 4 | 9 | 走路 |
| eat | 10（5×2） | 6 | 先站后低头啄 |
| sleep | 8（4×2） | 2 | 睡觉 |
| squat | 4 | 4 | 蹲下 |
| squat_idle | 8（4×2） | 4 | 蹲下待机 |
| like | 7（4×2，右下格为空） | 6 | 爱心 |

> 想改某个动画的播放速度：打开 .tres，选中对应动画，Inspector 里改 **Speed (FPS)**。

---

## 2. 第一步：新建预览场景

1. `FileSystem` 面板 → 在 `sences/` 下右键 → **New Folder**（如 `chicken_preview`）。
2. 右键该文件夹 → **New Scene** → 选 **Node2D**（根节点）→ 保存为 `chicken_preview.tscn`。
3. 选中根节点，点 **+** 加子节点：
   - `AnimatedSprite2D`（改名 `Chicken`，大鸡）
   - `AnimatedSprite2D`（改名 `Chick`，小鸡）
4. 分别选中它们，在 Inspector 的 **SpriteFrames** 属性点击空槽 → **Load** → 选 `chicken_frames.tres` / `chick_frames.tres`。
5. 每个精灵设 `Scale = (3, 3)`；`Offset = (16, 16)` 让脚底大致对齐（像素素材放大后中心在身体中部，偏移到脚底观感更好）。

> 顺手可以把背景设成一个纯色：加一个 `ColorRect` 子节点并拉到全屏（或直接不管）。

---

## 3. 第二步：AnimationPlayer —— 做"时间线片段"

这是你说的"实时间线"部分。一个片段（Animation）就是一条 2 秒的时间线，在第 0 秒放一个关键帧，告诉精灵播放哪个 SpriteFrames 动画。

1. 根节点加子节点 **AnimationPlayer**。
2. 选中它，底部出现 **Animation 面板**（窗口底部的底部栏，若没有则 `窗口 → 底部面板 → 动画`）。
3. 点面板上的 **Animation → New**，命名 `idle_f`，回车。
4. 在时间轴把片段长度改为 **2.0 秒**（默认会一直循环；把 `Loop Mode` 设为 `None`）。
5. 选中场景里的 `Chicken` 节点 → 点 Animation 面板上的 **加号（Add Track）→ 方法轨道（Method Track）**，目标选 `Chicken`。
6. 把播放头放到 **0.0s**，点轨道上的 **加号** 加一个关键帧，在右侧 `Method` 里填：方法名 `play`，参数 `idle_f`（注意：字符串要带引号）。
7. 同样的方法，再给 `Chick` 加一条方法轨道，关键帧调用 `play("idle_f")`。
8. 点 Animation 面板的**播放按钮**，两只鸡应该播放正面待机了。

> **为什么用"方法轨道"而不是"动画属性轨道"？**
> 如果你把 `SpriteFrames` 动画名（字符串）直接写成属性轨道，Godot 4.7 在多个片段间混合字符串会触发"experimental"警告甚至崩溃。方法轨道直接调用 `play()`，没有混合问题，是这类"片段=播放一个动画"场景最稳的写法。

按同样方法把 8 个正面片段建出来：`idle_f / idle2_f / walk_f / eat_f / sleep_f / squat_f / squat_idle_f / like_f`（每片段内两条方法轨道，分别调大鸡、小鸡）。方向 b/l 的片段（`idle_b`、`walk_b`…）可以之后再补，先用正面把流程跑通。

---

## 4. 第三步：AnimationTree —— 做"状态机"

1. 根节点加子节点 **AnimationTree**。
2. 选中它，Inspector 里把 **Anim Player** 指向 `../AnimationPlayer`。
3. 点 `Tree Root` 右侧的 **新建**，选 **AnimationNodeStateMachine**。
4. 底部出现状态机图。**右键空白 → 添加节点 → 动画**，依次加 8 个节点，命名为 `idle / idle2 / walk / eat / sleep / squat / squat_idle / like`。
5. 选中每个状态节点，右侧 `Animation` 填对应的片段名：`idle` 节点填 `idle_f`、`walk` 节点填 `walk_f`……
6. **连线**（拖节点间的圆点）：
   - 从 `Start`（初始节点）分别连到每个状态；
   - 8 个状态之间互相连满（或按你的需求连，比如 `idle ↔ walk ↔ eat`…）。
7. 选中每条连线（转换），右侧属性设置：
   - `Switch Mode` = `Immediate`
   - `Advance Mode` = `Enabled`
   - `Advance Condition` 留空，然后点 `+` 添加条件：属性填 `conditions/force`、状态填 **true**
8. 运行前脚本要激活它：`tree.active = true`。

> **为什么所有转换都要挂 `force` 条件？**
> 如果不加条件，状态机在片段结束时会按连线自动跳转（你片段设的是 2 秒不循环，播完就乱跑）。挂上默认关闭的 `force`，状态机就"没人喊就不动"，切换完全由你的代码说了算。

---

## 5. 第四步：控制脚本 —— 让状态机动起来

给根节点挂一个 GDScript（新建脚本，或先挂个空脚本再编辑）。这是**最小骨架**，关键部分有注释，你按自己需求补：

```gdscript
extends Node2D

@onready var tree: AnimationTree = $AnimationTree
var playback: AnimationNodeStateMachinePlayback
var state := "idle"

func _ready() -> void:
    tree.active = true
    playback = tree.get("parameters/playback")

func travel(target: String) -> void:
    state = target
    tree.set("parameters/conditions/force", true)  # 放行 force 条件
    playback.travel(target)                        # 状态机沿连线切到目标状态
    await get_tree().process_frame                 # 等一帧
    tree.set("parameters/conditions/force", false) # 立刻收回，防止乱跳
```

然后你可以在 `_unhandled_input()` 或 `_process()` 里写按键/逻辑调用 `travel("walk")` 之类。注意：**`travel()` 只会沿着状态机的连线走**，所以想让任意状态都能切到任意状态，就把图连满。

---

## 6. 方向 b / f / l 怎么处理（两个方案，自己选）

**方案 A：每状态 3 个片段（推荐，清晰）**
- 每个状态建 3 个片段：`walk_f / walk_b / walk_l`…（共 24 个）。
- 状态机里仍只有 8 个状态节点；切换方向时，把状态节点的 `Animation` 属性改成对应片段，并立刻对两个精灵 `play()` 一次让当前画面立即生效，同时更新 8 个节点的动画名（这样下次进入任何状态都是新方向）。
- 优点：状态机简单，方向是"片段选择"而不是"状态"。

**方案 B：方向也做成状态**
- 状态机里建 24 个节点（`walk_f / walk_b / walk_l`…）。
- 优点：连线的转场（X Fade）能作用于方向切换；缺点：图很乱，改起来费劲。

> 右侧方向不需要新素材：游戏里朝右时给 `AnimatedSprite2D` 设 `flip_h = true` 并播 `_l` 方向动画即可。

---

## 7. 常见坑（都是我实际踩过的，帮你避雷）

1. **不要用属性轨道写动画名**（字符串混合会警告/崩溃）→ 用方法轨道 `play("动画名")`。
2. **片段别设太短**（如 0.001s）→ 用 2 秒左右、不循环，播放由 SpriteFrames 自己循环。
3. **force 条件用完要收回**（下一帧设回 false），否则状态机可能在你没注意时自己跳。
4. **Start 节点必须显式连到所有状态**，否则初始 travel 无路径可用。
5. **改了状态节点的 Animation 属性后画面不会立刻变**，需要再手动 `play()` 一次。
6. **无头跑脚本时**，如果自定义脚本继承 `SceneTree`，`_process()` 必须返回 `false`（返回 `true` 会退出主循环）。
7. **AnimationPlayer 添加片段**：Godot 4.7 没有 `add_animation()`，只有 `AnimationLibrary.add_animation()` + `add_animation_library()`（编辑器里操作不受影响，这条是写脚本生成时才遇到）。

---

## 8. 素材包其他可用内容

- 鸡的素材还有 `egg`（蛋）等其它文件在源目录 `...\project_end\Cozy Lands - Asset Pack\Animals\Chicken\`，需要的话按同样的"3 行方向 + 32×32 网格"方式加进 `build_chicken_frames.gd` 的 `SPECS` 表重建即可。
- 其他动物素材包结构大概率一致，可以复用这套准备工作流程。

**做完想让我帮你无头验证状态机是否正常切换，随时把场景路径发我。**
