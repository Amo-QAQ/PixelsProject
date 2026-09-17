# -*- coding: utf-8 -*-
"""更新手册：对象层 topdown 规则"""
import io

p = r"E:\My_work\PixelsProject\Aseprite\tiled\导出工具\Tiled导出_需求与排障手册.md"
c = io.open(p, encoding="utf-8").read()

old = "3. **位置四舍五入用 half-up**：`int(x + 0.5)`，不能用 Python `round()`（银行家舍入，round(172.5)=172 与官方 173 不符）\n\n**验证记录**（预览01 第 0 帧 vs 官方 tmxrasterizer）：\n- 修复前（无对象层解析）：植物/角色完全缺失\n- 左上对齐 + 原尺寸：差异 20479 点（全部对象偏 16px）\n- 底部对齐修复：差异 3384 → 四舍五入修复后 **621 点（全部为半透明 ±1 舍入差，正常）**"

new = "3. **位置四舍五入用 half-up**：`int(x + 0.5)`，不能用 Python `round()`（银行家舍入，round(172.5)=172 与官方 173 不符）\n4. **对象层内绘制顺序 = topdown（关键！2026-09-17 新修）**：Tiled 对象层默认 `draworder=topdown`，即**按对象 y 坐标升序绘制**（y 小的先画、y 大的盖在上面）——不是 XML 列表顺序！此前 stone_06/stone_05 重叠区「前后层反了」（官方 stone_06 盖 stone_05，工具相反），根因就是没按 y 排序。对象层 XML 有 `draworder=\"index\"` 属性时才按列表顺序。修复后**强差异归零**（模板匹配 stone_06/stone_05 官方与工具均 0 差异）\n\n**验证记录**（预览01 第 0 帧 vs 官方 tmxrasterizer）：\n- 修复前（无对象层解析）：植物/角色完全缺失\n- 左上对齐 + 原尺寸：差异 20479 点（全部对象偏 16px）\n- 底部对齐修复：差异 3384 → 四舍五入修复后 621 点\n- **topdown 排序修复（v4.1）：强差异 = 0，仅 477 点半透明 ±1 舍入弱差（正常基线）**"

if old in c:
    c = c.replace(old, new)
    io.open(p, "w", encoding="utf-8", newline="").write(c)
    print("手册已更新：新增对象层 topdown 规则 4")
else:
    print("未找到目标文本")
    # 打印实际内容便于核对
    idx = c.find("half-up")
    print(repr(c[idx-100:idx+400]))
