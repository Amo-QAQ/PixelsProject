#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sprite Sheet Combiner v2.0
Combines individual PNG frames into sprite sheets by filename prefix.

Usage: Double-click to run, follow the prompts.
"""

import os
import sys
import re
from collections import defaultdict

try:
    from PIL import Image
except ImportError:
    print("=" * 50)
    print("Pillow not found, installing...")
    os.system(f'"{sys.executable}" -m pip install Pillow -q')
    from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def group_files_by_prefix(folder):
    """Group files by name prefix (everything before the last _-number)."""
    groups = defaultdict(list)

    if not os.path.isdir(folder):
        return groups

    for f in os.listdir(folder):
        if not f.lower().endswith(('.png', '.bmp', '.jpg', '.jpeg')):
            continue

        base = os.path.splitext(f)[0]
        match = re.match(r'^(.*?)[_-](\d+)$', base)
        if match:
            group_name = match.group(1)
            frame_num = int(match.group(2))
            full_path = os.path.join(folder, f)
            groups[group_name].append((frame_num, full_path))

    for name in groups:
        groups[name].sort(key=lambda x: x[0])

    return groups


def make_sprite_sheet(frame_paths, direction='horizontal', padding=0):
    """Combine multiple images into a single sprite sheet."""
    if not frame_paths:
        return None

    frames = []
    max_w, max_h = 0, 0

    for path in frame_paths:
        try:
            img = Image.open(path).convert('RGBA')
            frames.append(img)
            max_w = max(max_w, img.width)
            max_h = max(max_h, img.height)
        except Exception:
            pass

    if not frames:
        return None

    count = len(frames)

    if direction == 'horizontal':
        sheet_w = max_w * count + padding * (count - 1)
        sheet_h = max_h
    else:
        sheet_w = max_w
        sheet_h = max_h * count + padding * (count - 1)

    sheet = Image.new('RGBA', (sheet_w, sheet_h), (0, 0, 0, 0))

    for i, frame in enumerate(frames):
        if direction == 'horizontal':
            x = i * (max_w + padding)
            y = 0
        else:
            x = 0
            y = i * (max_h + padding)

        offset_x = x + (max_w - frame.width) // 2
        offset_y = y + (max_h - frame.height) // 2

        sheet.paste(frame, (offset_x, offset_y), frame.convert('RGBA'))

    return sheet, max_w, max_h


def main():
    print("")
    print("+" + "-" * 56 + "+")
    print("|" + "  Sprite Sheet Combiner v2.0".center(50) + "|")
    print("|" + "  Merge individual PNG frames into sprite sheets".center(42) + "|")
    print("+" + "-" * 56 + "+")
    print("")

    # Step 1: Input folder
    print("--- Step 1/3: Input Folder ---")
    print("Enter the folder containing your PNG frame files.")
    print("You can paste the path or drag & drop a folder here.")

    default_input = os.path.join(SCRIPT_DIR, "export")
    input_dir = input(f"Input folder [Enter for default: {default_input}]: ").strip()

    if not input_dir:
        input_dir = default_input

    input_dir = input_dir.strip('"').strip("'")

    if not os.path.isdir(input_dir):
        print(f"\n[ERROR] Folder not found: {input_dir}")
        input("Press Enter to exit...")
        return

    print(f"[OK] Input folder: {input_dir}")

    # Step 2: Output folder
    print("")
    print("--- Step 2/3: Output Folder ---")
    default_output = os.path.join(input_dir, "sprite_sheets")
    output_dir = input(f"Output folder [Enter for default: {default_output}]: ").strip()

    if not output_dir:
        output_dir = default_output

    output_dir = output_dir.strip('"').strip("'")

    print(f"[OK] Output folder: {output_dir}")

    # Step 3: Scan and preview
    print("")
    print("--- Step 3/3: Scan & Preview ---")

    groups_data = group_files_by_prefix(input_dir)

    if not groups_data:
        print("\n[ERROR] No image files found!")
        print("   Make sure the folder contains files like: name_0.png, name_1.png")
        input("Press Enter to exit...")
        return

    total_frames = 0
    print("")
    print(f"{'#':<5}{'Group Name':<38}{'Frames':<8}{'Size (horizontal)':<18}")
    print("-" * 69)

    for idx, name in enumerate(sorted(groups_data.keys()), 1):
        frames = groups_data[name]
        count = len(frames)
        total_frames += count

        try:
            img = Image.open(frames[0][1])
            w, h = img.size
            size_str = f"{w * count} x {h}"
        except:
            size_str = "unknown"

        print(f"{idx:<5}{name:<38}{count:<8}{size_str:<18}")

    print("-" * 69)
    print(f"Total: {len(groups_data)} animation group(s), {total_frames} frame(s)")

    # Options
    print("")
    print("--- Settings ---")
    dir_choice = input("Direction [Enter=horizontal(h), v=vertical]: ").strip().lower()
    direction = "vertical" if dir_choice == 'v' else "horizontal"
    dir_label = "vertical" if direction == "vertical" else "horizontal"

    pad_choice = input("Frame padding in pixels [Enter=0]: ").strip()
    try:
        padding = int(pad_choice) if pad_choice else 0
    except:
        padding = 0

    print("")
    print(f"Settings: direction={dir_label}, padding={padding}px")

    # Confirm
    confirm = input(f"\nProceed? [Enter=yes, n=cancel]: ").strip().lower()

    if confirm == 'n':
        print("Cancelled.")
        input("Press Enter to exit...")
        return

    # Start combining
    print("")
    print("=" * 50)
    print("Processing...")

    os.makedirs(output_dir, exist_ok=True)

    success = 0
    fail = 0
    output_files = []

    for group_name in sorted(groups_data.keys()):
        frame_list = groups_data[group_name]
        paths = [p[1] for p in frame_list]

        result = make_sprite_sheet(paths, direction=direction, padding=padding)

        if result is None:
            fail += 1
            continue

        sheet, fw, fh = result

        out_png = os.path.join(output_dir, group_name.rstrip('_-') + ".png")
        sheet.save(out_png, 'PNG')

        output_files.append((group_name.rstrip('_-'), sheet.width, sheet.height))
        success += 1

    # Summary
    print("")
    print("[DONE] Sprite sheets generated!")
    print("-" * 45)
    print(f"Success: {success}  |  Failed: {fail}")
    print("")
    print("Output files:")
    for fname, w, h in output_files:
        print(f"  -> {fname}.png  ({w} x {h})")
    print("")
    print(f"Output location: {output_dir}")
    print("=" * 50)

    # Open folder
    open_it = input("\nOpen output folder? [Enter=yes, n=no]: ").strip().lower()
    if open_it != 'n':
        os.startfile(output_dir)

    input("\nPress Enter to exit...")


if __name__ == '__main__':
    main()
