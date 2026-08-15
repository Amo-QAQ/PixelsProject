# -*- coding: utf-8 -*-
"""
精灵图序列帧合成工具
功能：将单帧 PNG 图片拼接成 Sprite Sheet（精灵图）

使用方法：
  python sprite_sheet_maker.py

配置：
  - INPUT_DIR: 输入文件夹（包含 frame_001.png, frame_002.png ...）
  - OUTPUT_DIR: 输出文件夹
  - FRAME_SIZE: 单帧尺寸 (宽, 高)
  - DIRECTION: 'horizontal' 横排 / 'vertical' 纵排
  - COLUMNS: 每行最多几帧（仅横排时有效，0=自动）
"""

import os
import json
import re
from PIL import Image


# ==================== 配置区 ====================

# 输入文件夹（放单帧 PNG 的目录）
INPUT_DIR = r"D:\CodeProject\PixelsProject\Aseprite\mod_end\Animals\Chick"

# 输出文件夹
OUTPUT_DIR = r"D:\CodeProject\PixelsProject\Aseprite\mod_end\Animals\Chick\sprite_sheets"

# 输出的精灵图文件名
OUTPUT_FILENAME = "ji_sprite_sheet"

# 单帧尺寸 (宽, 高) - 如果是 0 则自动检测第一张图
FRAME_SIZE = (21, 20)

# 排列方向: "horizontal" 或 "vertical"
DIRECTION = "horizontal"

# 每行/列最多几帧 (0=全部排成一行/列)
MAX_PER_ROW = 0

# 帧之间的间距
PADDING = 0

# 背景色 (R, G, B, A) - 默认透明
BACKGROUND = (0, 0, 0, 0)

# 文件名匹配正则 (提取数字排序)
FILENAME_PATTERN = r"ji(\d+)\.png$"

# 是否生成 JSON 数据文件（记录每帧位置，供游戏引擎用）
GENERATE_JSON = True

# 是否忽略已有精灵图的子文件夹
IGNORE_SUBFOLDERS = True

# ================================================


def natural_sort_key(filename):
    """自然排序：ji1.png, ji2.png, ..., ji10.png"""
    match = re.search(FILENAME_PATTERN, filename)
    if match:
        return int(match.group(1))
    return filename


def create_sprite_sheet(frames, output_path, sheet_name, direction="horizontal",
                        max_per_row=0, padding=0, background=(0, 0, 0, 0)):
    """
    将多帧图片拼成一张精灵图
    
    Args:
        frames: [PIL.Image, ...] 帧图片列表
        output_path: 输出文件路径
        sheet_name: 名称（用于 JSON）
        direction: 'horizontal' 或 'vertical'
        max_per_row: 每行最大帧数
        padding: 帧间距
        background: 背景色
        
    Returns:
        (输出路径, 帧数据列表)
    """
    if not frames:
        print(f"  ⚠️ 没有可用的帧!")
        return None, []

    frame_count = len(frames)
    fw, fh = frames[0].size

    # 计算布局
    if direction == "horizontal":
        if max_per_row > 0:
            cols = min(max_per_row, frame_count)
        else:
            cols = frame_count
        rows = (frame_count + cols - 1) // cols
        sheet_w = fw * cols + padding * (cols - 1)
        sheet_h = fh * rows + padding * (rows - 1)
    else:
        if max_per_row > 0:
            rows = min(max_per_row, frame_count)
        else:
            rows = frame_count
        cols = (frame_count + rows - 1) // rows
        sheet_w = fw * cols + padding * (cols - 1)
        sheet_h = fh * rows + padding * (rows - 1)

    # 创建精灵图（支持透明背景）
    if len(background) == 4 and background[3] == 0:
        sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
    else:
        sheet = Image.new("RGBA", (sheet_w, sheet_h), background)

    # 帧数据（用于 JSON）
    frames_data = []

    # 粘贴每一帧
    for i, frame in enumerate(frames):
        if direction == "horizontal":
            col = i % cols
            row = i // cols
        else:
            row = i % rows
            col = i // rows

        x = col * (fw + padding)
        y = row * (fh + padding)

        # 处理不同模式的图像
        if frame.mode == "P":
            frame = frame.convert("RGBA")
        elif frame.mode != "RGBA":
            frame = frame.convert("RGBA")

        sheet.paste(frame, (x, y), frame if frame.mode == "RGBA" else None)

        # 记录帧数据
        frames_data.append({
            "frame": i + 1,
            "filename": f"frame_{i+1:04d}.png",
            "x": x,
            "y": y,
            "width": fw,
            "height": fh
        })

    # 保存
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    sheet.save(output_path, "PNG")

    return output_path, frames_data


def process_folder(folder_path, output_dir):
    """处理单个文件夹中的所有帧"""
    
    # 收集 PNG 文件
    files = []
    for f in os.listdir(folder_path):
        if f.lower().endswith(".png") and re.search(FILENAME_PATTERN, f):
            files.append(f)
    
    if not files:
        return [], None, None
    
    # 排序
    files.sort(key=natural_sort_key)
    
    print(f"\n📂 处理文件夹: {os.path.basename(folder_path)}")
    print(f"   找到 {len(files)} 帧: {files[0]} ~ {files[-1]}")
    
    # 加载所有帧
    frames = []
    for f in files:
        img_path = os.path.join(folder_path, f)
        img = Image.open(img_path)
        
        # 如果指定了帧尺寸，进行缩放/裁剪
        if FRAME_SIZE[0] > 0 and FRAME_SIZE[1] > 0:
            if img.size != FRAME_SIZE:
                print(f"   ⚠️ {f} 尺寸 {img.size} 与指定尺寸 {FRAME_SIZE} 不一致")
        
        frames.append(img)
    
    # 自动检测帧尺寸
    actual_frame_size = frames[0].size if frames else (0, 0)
    fw, fh = FRAME_SIZE if FRAME_SIZE[0] > 0 else actual_frame_size
    
    # 构造输出文件名
    folder_name = os.path.basename(folder_path)
    safe_name = re.sub(r'[^\w\-]', '_', folder_name)
    
    png_path = os.path.join(output_dir, f"{safe_name}.png")
    json_path = os.path.join(output_dir, f"{safe_name}.json") if GENERATE_JSON else None
    
    # 创建精灵图
    result_path, frames_data = create_sprite_sheet(
        frames=frames,
        output_path=png_path,
        sheet_name=safe_name,
        direction=DIRECTION,
        max_per_row=MAX_PER_ROW,
        padding=PADDING,
        background=BACKGROUND
    )
    
    if result_path:
        print(f"   ✅ 已生成: {os.path.basename(result_path)} ({frames[0].size[0]}x{frames[0].size[1]} × {len(frames)}帧)")
        
        # 生成 JSON
        if GENERATE_JSON and json_path:
            data = {
                "name": safe_name,
                "frame_size": list(actual_frame_size),
                "direction": DIRECTION,
                "frame_count": len(frames),
                "sheet_size": [result_path and Image.open(result_path).size or (0, 0)][0] if result_path else (0, 0),
                "frames": frames_data
            }
            
            with open(json_path, "w", encoding="utf-8") as jf:
                json.dump(data, jf, indent=2, ensure_ascii=False)
            print(f"   ✅ 已生成: {os.path.basename(json_path)}")
    
    return frames, result_path, json_path


def main():
    """主函数"""
    
    print("=" * 60)
    print("🎮 精灵图序列帧合成工具")
    print("=" * 60)
    print(f"输入目录: {INPUT_DIR}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"帧尺寸: {FRAME_SIZE}")
    print(f"排列方向: {'横排' if DIRECTION == 'horizontal' else '纵排'}")
    print("=" * 60)
    
    # 检查输入目录
    if not os.path.exists(INPUT_DIR):
        print(f"❌ 输入目录不存在: {INPUT_DIR}")
        return
    
    # 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 判断输入目录是直接包含 PNG 还是包含子文件夹
    has_subfolders = False
    has_direct_pngs = False
    
    for item in os.listdir(INPUT_DIR):
        item_path = os.path.join(INPUT_DIR, item)
        if os.path.isdir(item_path):
            has_subfolders = True
        elif item.lower().endswith(".png"):
            has_direct_pngs = True
    
    all_results = []
    
    if has_direct_pngs:
        # 模式2：直接处理当前文件夹的所有 PNG
        print("\n🖼️ 直接处理当前文件夹的 PNG 文件\n")
        frames, png_path, json_path = process_folder(INPUT_DIR, OUTPUT_DIR)
        if frames:
            all_results.append({
                "tag": os.path.basename(INPUT_DIR),
                "frame_count": len(frames),
                "png": png_path,
                "json": json_path
            })
    elif has_subfolders and IGNORE_SUBFOLDERS:
        # 模式1：每个子文件夹是一个标签，各自生成精灵图
        print("\n📁 检测到多个子文件夹，将按文件夹分别生成精灵图\n")
        
        for subfolder in sorted(os.listdir(INPUT_DIR)):
            sub_path = os.path.join(INPUT_DIR, subfolder)
            if os.path.isdir(subfolder):
                frames, png_path, json_path = process_folder(sub_path, OUTPUT_DIR)
                if frames:
                    all_results.append({
                        "tag": subfolder,
                        "frame_count": len(frames),
                        "png": png_path,
                        "json": json_path
                    })
    elif has_direct_pngs:
        # 模式2：直接处理当前文件夹的所有 PNG
        print("\n🖼️ 直接处理当前文件夹的 PNG 文件\n")
        frames, png_path, json_path = process_folder(INPUT_DIR, OUTPUT_DIR)
        if frames:
            all_results.append({
                "tag": os.path.basename(INPUT_DIR),
                "frame_count": len(frames),
                "png": png_path,
                "json": json_path
            })
    else:
        print("❌ 没有找到任何 PNG 文件!")
        return
    
    # 输出总结
    print("\n" + "=" * 60)
    print("✅ 全部完成! 总结:")
    print("=" * 60)
    
    total_frames = 0
    for r in all_results:
        total_frames += r["frame_count"]
        print(f"  📦 {r['tag']}: {r['frame_count']}帧 → {os.path.basename(r['png']) if r['png'] else 'N/A'}")
    
    print(f"\n  总计: {len(all_results)} 张精灵图, {total_frames} 帧")
    print(f"  输出位置: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
