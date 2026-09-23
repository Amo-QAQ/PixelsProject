# 解包工具 — 星露谷 XNB 数据表解包器

把星露谷 `Content\Data\*.xnb` 解密成可读 JSON 的自制工具。

## 为什么需要它

星露谷 1.6 的 XNB 文件是**自定义变体**（LZX 压缩 + XNA 4.0 带索引格式），网上标准工具全部失效。
本工具绕过的关键点：
- 用**游戏自带的 `MonoGame.Framework.dll`**（而非 NuGet 版）——星露谷的打包格式只有它自己的运行时能读
- 反射调用 `ContentReader.ReadAsset<object>()` 完整流程，让游戏版运行时自己解析 reader 列表和条目索引

## 使用方法

需要环境：.NET 8 SDK（`dotnet --version` 检查）。

```bash
# 在工程目录（xnbprobe.csproj 所在处）执行：
dotnet run                  # 批量解包默认 18 张表
dotnet run Objects          # 只解包一张表（表名）
dotnet run Objects Crops    # 解包多张表
```

输出到 `..\解包数据\<表名>.json`（相对工程目录，可在 Program.cs 顶部改 `OutDir`）。

## 改表目标

编辑 `Program.cs` 中 `ContentRoot`（数据目录）和默认表清单即可。

## 已知限制

- 只支持 `Content\Data` 下的数据表；地图（`Content\Maps\*.xnb`）需要额外处理（xTile 格式），本工具暂未覆盖
- 老式字符串表（Fish/Quests/Bundles/mail/Monsters/NPCGiftTastes/CraftingRecipes/CookingRecipes）解包为紧凑字符串
- 1.6 结构化表（Objects/Crops/Weapons/Tools/Buildings/Machines/Shops/FruitTrees/FarmAnimals/Buffs）解包为完整对象 JSON
