# Tiled Map01 → Godot 4

打开 `project.godot` 即可运行地图。主场景是 `main.tscn`，其中实例化了 `maps/map01.tscn` 并添加了摄像机。窗口与地图均为 800×800 像素，贴图默认使用最近邻过滤。

运行后，鼠标滚轮向上拉近、向下拉远；按住鼠标中键拖动可以平移视野。缩放范围默认为 0.5× 到 4×。摄像机位于地图中心，相关参数可以在 `main.tscn` 的 `Camera2D` 节点上调整。

场景中的人物已从 Tiled 角色图块拆分为独立的 `CharacterBody2D`，并分别使用 `角色_F / B / L / R.png` 播放前、后、左、右四向动画。移动时播放贴图第 2 行的 8 帧行走动画，停止时回到第 1 行待机帧。使用 `W/A/S/D` 上、左、下、右移动；斜向移动会自动归一化，因此速度不会变快。移动速度与动画速度可以在 `main.tscn` 的 `Player` 节点上调整。

水面动画由 `WaterAnimator` 在原 TileMap 的“水”图层内换帧。它按照 `water-ani.tsx` 中的 12 组非连续序列播放，每组 7 帧、默认 100 ms/帧，并支持间隔 3 格或 2 格取帧。当前地图中的 27 个动态水面格会自动被识别。

## 像素渲染设置

- 2D 纹理使用最近邻过滤，不做平滑插值。
- 窗口保持宽高比并采用整数倍缩放。
- 启用 2D 变换像素对齐，避免半像素边缘。
- 关闭 MSAA 2D 和屏幕空间抗锯齿。
- PNG 贴图使用无损压缩，并且不生成 mipmap。

## 新建地图模板

`maps/new_tilemap.tscn` 是根据现有环境素材生成的空白地图模板，包含水面、地面、建筑和装饰四个 `TileMapLayer`，以及独立的 `PlantEntities` 实体容器。地图图层共用 `tilesets/world_tileset.tres`，其中只保留 8 个环境图集。作物与树木分别使用 `scenes/plants/crop_entity.tscn` 和 `scenes/plants/tree_entity.tscn`，应作为实体实例放在 `PlantEntities` 下，而不是绘制到 TileMap 中。

## 重新从 Tiled 导出

1. 在 `maps/map01.tmx` 中修改地图。
2. 在 Tiled 选择“文件 → 导出为”，格式选择 **Godot 4 Scene (`.tscn`)**。
3. 覆盖 `maps/map01.tscn`。

命令行等价操作：

```powershell
& 'C:\Program Files\Tiled\tiled.exe' --export-map tscn '.\maps\map01.tmx' '.\maps\map01.tscn'
```

## 水面动画说明

原始 `water-ani.tsx` 的动画使用隔格帧（例如 3、6、9……）。Tiled 的 Godot 4 导出器只支持图集中连续排列、且不与其他图块共用的动画帧，因此地图场景本身仍按静态首帧导出，再由 `WaterAnimator` 在运行时补回原动画。原目录中的 Tiled 源文件和动画数据未被修改。
