# 手部挂点（HandAnchor）在 Godot 里怎么做

> 对应星露谷机制：物品挂在手的锚点上，跟随角色移动/朝向；收获举起时手抬高，物品跟着走。
> 面向美术 + AI 辅助写码：挂点本身只是一个"空位置标记节点"，不用画任何东西。

---

## 一、挂点到底是什么

一个**不显示任何图案的空节点（Marker2D）**，摆在角色手上的位置。
物品（武器、萝卜、工具）作为它的**子节点**放进去，就会自动跟着这个点移动、转向。
你在编辑器里把十字标记拖到手上即可，不用在代码里写坐标。

---

## 二、场景树结构（Godot 4，推荐照搬）

```
Player (CharacterBody2D)
├─ Sprite2D          # 角色图，flip_h 控制朝向左右
│   └─ Hand (Marker2D)        # ← 手部挂点：拖到手上的位置
│       └─ HeldItem (Sprite2D) # ← 当前手持物，挂在 Hand 下面
└─ CollisionShape2D
```

- `Marker2D` = Godot 3 里的 `Position2D`，Godot 4 改名了，功能一样。
- 物品是 Hand 的子节点 → Hand 走到哪，物品跟到哪；Hand 转向，物品跟着转。
- 读取挂点世界坐标用 `Hand.global_position`，不要用写死的数字。

### 最小代码骨架（交给 AI 补全即可）

```gdscript
# player.gd
@onready var hand: Marker2D = $Sprite2D/Hand
@onready var held_item: Sprite2D = $Sprite2D/Hand/HeldItem

# 收获瞬间：把物品"交到手上"
func pick_up(item: Sprite2D) -> void:
    item.reparent(hand)                 # 挂到手部挂点
    item.global_position = hand.global_position  # 对齐到手位
    held_item = item

# 收获结束：收回背包（隐藏即可）
func put_away() -> void:
    held_item.visible = false
```

---

## 三、两种情况，两种做法

### 情况 1：手持走路，手位置基本不动 → 固定 Marker2D（最常用）
走路时手一直长在同一个位置，一个固定 Hand 挂点就够，物品自然跟随。

### 情况 2：收获举起，手随帧抬高/摆动 → 固定点会"飘"，需要帧偏移
固定 Marker 不会跟着每帧的手位走，举起时物品会留在原地、和手错开。两种解法：

- **帧偏移表（手动少量帧）**：建一张字典，记录每帧手相对身体的偏移，在切帧信号里更新 `Hand.position`：
  ```gdscript
  var hand_offsets = {0: Vector2(4, -6), 1: Vector2(4, -14), 2: Vector2(2, -22)}
  # 在 frame_changed 信号里：hand.position = hand_offsets[当前帧]
  ```
- **AnimationPlayer 位置关键帧**：如果你已经用 AnimationPlayer 切角色帧，直接在同一条时间轴给 Hand 的 position 打关键帧，举起时手位自动跟着时间线走（推荐，别再单独开个计时器同步）。

> 关键：偏移要按"当前动画帧"查，不要按独立的物理 tick 计数，否则切帧速度一变就错位。

---

## 四、翻转（面朝左右）的坑，提前知道

`Sprite2D.flip_h = true` **只翻角色图片，不会把子节点 Hand 一起镜像**，挂点位置不会自动换到另一只手。

- 面朝右：Hand 在右侧；
- 面朝左：需要手动把 `Hand.position.x` 取反，或者干脆放两个挂点 `HandL / HandR`，按朝向切换显隐。
- 物品挂在 Hand 下，朝向翻转时物品本身要不要镜像，单独设置它自己的 `flip_h`。

---

## 五、什么时候才用骨骼方案（BoneAttachment）

以上是像素 2D、无骨骼的做法。等以后做骨骼动画（Spine / 3D / Skeleton2D），挂点改用 **BoneAttachment** 节点绑到手上的骨头，手怎么转物品都贴得住。星露谷是像素无骨骼，用不到。

---

## 六、推荐教程（由浅入深）

1. **Marker2D 锚点跟随（固定挂点入门，最对口）** — UhiyamaLab《Using Marker2D as a Management Node》
   https://uhiyama-lab.com/en/notes/godot/marker2d-as-manager-node/
   讲把 Marker2D 放在身体部位做跟随锚点（枪口/手/脚），含 `global_position` 用法和 flip_h 陷阱。
2. **帧特定挂点诊断（手随帧移动怎么办，免费文章不用买工具）** — Sprite Socket Bench Devlog
   https://knysgwr.itch.io/sprite-socket-bench/devlog/1712370/godot-muzzle-flash-drifts-while-walking-diagnose-frame-specific-attachment-points
   讲固定点为什么会飘、帧偏移表 / 动画关键帧怎么选。
3. **Godot 官方 Marker2D 类文档（权威参考）**
   https://docs.godotengine.org/en/stable/classes/class_marker2d.html
4. **完整武器挂载项目示例（武器作为子节点挂到玩家）** — GameDev Academy《Godot Weapon System》
   https://gamedevacademy.org/godot-weapon-system-tutorial/
5. **骨骼方案（以后需要再看）**：Godot 官方 BoneAttachment 文档 / 骨骼导出 BoneAttachment 章节。

---

## 七、迁移回星露谷的对照

| 星露谷 | Godot |
|---|---|
| 手部固定偏移（代码写死） | Hand (Marker2D) 固定位置 |
| 收获帧手抬高，物品跟随 | 帧偏移表 / AnimationPlayer 位置关键帧 |
| 面朝左镜像 | 手动取反 Hand.position.x 或 HandL/HandR 切换 |
| 物品单帧挂手 | HeldItem 作为 Hand 的子节点 |
