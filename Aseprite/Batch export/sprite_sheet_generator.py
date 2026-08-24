#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
序列帧合成精灵图工具 (Sprite Sheet Generator)
=============================================
功能：
  1. 批量扫描输入目录中的序列帧 PNG
  2. 自动按动画 / 动作分组
  3. 自动优化列数，最大程度减少空白（优先 0 空白）
  4. 帧数超过每行上限时自动换行
  5. 生成精灵图 PNG + JSON 元数据
  6. 网页界面（浏览器操作，无需安装额外依赖）/ 命令行双模式

用法：
  网页版 :  双击「启动精灵图工具.bat」或运行 python sprite_sheet_generator.py
  命令行 :  python sprite_sheet_generator.py --input <dir> --output <dir> [--max-cols 5] [--mode animation]
"""

import os
import sys
import math
import json
import re
import glob
import argparse
import io
import base64
import threading
import webbrowser
import http.server
import urllib.parse
from collections import defaultdict

# === 依赖检查 ===
try:
    from PIL import Image
except ImportError:
    print("缺少 Pillow，正在安装...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image


# ============================================================
#  核心逻辑
# ============================================================

def find_optimal_columns(n, max_cols=5):
    """
    为 n 个帧找到最优列数 (<= max_cols)，使空白单元格最少。

    策略：
      1. n <= max_cols → 直接 n 列一行 (0 空白)
      2. 优先找 [2, max_cols] 内能整除 n 的最大列数 (0 空白，最紧凑)
      3. 若无，找空白最少的列数，优先较大的列数 (更紧凑)

    示例：
      n=8,  max=5 → 4  (4x2=8,  0 空白)
      n=12, max=5 → 4  (4x3=12, 0 空白)
      n=16, max=5 → 4  (4x4=16, 0 空白)
      n=7,  max=5 → 4  (4x2=8,  1 空白 — 7 是质数，无法整除，1 空白为数学最小值)
    """
    if n <= 0:
        return 1
    if n <= max_cols:
        return n

    # 优先：[2, max_cols] 范围内能整除的最大列数
    for c in range(max_cols, 1, -1):
        if n % c == 0:
            return c

    # 其次：空白最少，优先列数大
    best_c = max_cols
    best_blanks = float('inf')
    for c in range(max_cols, 1, -1):
        blanks = c * math.ceil(n / c) - n
        if blanks < best_blanks:
            best_blanks = blanks
            best_c = c

    return best_c


def parse_filename(filename):
    """
    解析文件名，提取动作名、方向、帧号。

    支持模式：
      action_direction_number.png  -> (action, direction, number)
      action_number.png            -> (action, None,   number)

    示例：
      walk_girl_B_0.png -> ('walk_girl', 'B', 0)
      walk_girl_0.png   -> ('walk_girl', None, 0)
    """
    name = os.path.splitext(filename)[0]

    # 模式1: prefix_DIRECTION_number (方向 = 单个大写字母)
    m = re.match(r'^(.+)_([A-Z])_(\d+)$', name)
    if m:
        return m.group(1), m.group(2), int(m.group(3))

    # 模式2: prefix_number
    m = re.match(r'^(.+)_(\d+)$', name)
    if m:
        return m.group(1), None, int(m.group(2))

    return name, None, 0


def scan_and_group(input_dir, mode='animation'):
    """
    扫描输入目录，按指定模式分组 PNG 序列帧。

    mode:
      'animation' - 按动画分组 (action_direction 各一张 sheet)
      'action'    - 按动作分组 (同 action 所有方向合到一张 sheet，每方向独立行块)
      'all'       - 全部合并为一张 sheet

    返回: dict {group_name: [(frame_num, filepath, direction), ...]}
    """
    files = sorted(glob.glob(os.path.join(input_dir, '*.png')))
    if not files:
        return {}

    groups = defaultdict(list)

    for f in files:
        basename = os.path.basename(f)
        action, direction, frame_num = parse_filename(basename)

        if mode == 'animation':
            key = f"{action}_{direction}" if direction else action
        elif mode == 'action':
            key = action
        else:
            key = 'sprite_sheet'

        groups[key].append((frame_num, f, direction))

    # 按帧号排序
    for key in groups:
        groups[key].sort(key=lambda x: x[0])

    return dict(groups)


def create_sprite_sheet(frames, output_path, max_cols=5, optimize=True, padding=0):
    """
    将帧序列合成为精灵图 (单个动画组)。

    参数:
      frames       - [(frame_num, filepath, direction), ...]
      output_path  - 输出 PNG 路径
      max_cols     - 每行最大帧数
      optimize     - 是否自动优化列数
      padding      - 帧间距 (像素)

    返回: dict (sheet 信息)
    """
    n = len(frames)
    if n == 0:
        return None

    # 加载图片
    images = []
    max_w = 0
    max_h = 0

    for _, fpath, _ in frames:
        img = Image.open(fpath).convert('RGBA')
        images.append(img)
        max_w = max(max_w, img.width)
        max_h = max(max_h, img.height)

    # 计算列数
    if optimize:
        cols = find_optimal_columns(n, max_cols)
    else:
        cols = min(n, max_cols)

    rows = math.ceil(n / cols)

    # 画布大小
    cell_w = max_w + padding
    cell_h = max_h + padding
    sheet_w = cols * cell_w - padding
    sheet_h = rows * cell_h - padding

    # 创建画布 (透明背景)
    sheet = Image.new('RGBA', (sheet_w, sheet_h), (0, 0, 0, 0))

    # 粘贴每一帧
    frame_data = []
    for i, (img, (frame_num, fpath, direction)) in enumerate(zip(images, frames)):
        col = i % cols
        row = i // cols
        x = col * cell_w
        y = row * cell_h

        # 居中 (帧大小不一致时)
        ox = x + (max_w - img.width) // 2
        oy = y + (max_h - img.height) // 2
        sheet.paste(img, (ox, oy))

        frame_data.append({
            'index': i,
            'frame': frame_num,
            'x': x,
            'y': y,
            'w': max_w,
            'h': max_h,
            'direction': direction,
        })

    # 保存
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    sheet.save(output_path, 'PNG')

    blanks = cols * rows - n

    return {
        'image': os.path.basename(output_path),
        'cols': cols,
        'rows': rows,
        'frameWidth': max_w,
        'frameHeight': max_h,
        'sheetWidth': sheet_w,
        'sheetHeight': sheet_h,
        'frameCount': n,
        'blankCells': blanks,
        'padding': padding,
        'frames': frame_data,
    }


def create_action_sprite_sheet(direction_frames, output_path, max_cols=5, optimize=True, padding=0):
    """
    按动作创建精灵图 (多个方向合到一张图，每个方向占独立的行块)。

    direction_frames: {direction: [(frame_num, filepath, direction), ...]}

    布局示例 (walk_girl, 4方向 x 8帧, cols=4):
      Row 0-1: direction B  [0][1][2][3] / [4][5][6][7]
      Row 2-3: direction F  [0][1][2][3] / [4][5][6][7]
      Row 4-5: direction L  [0][1][2][3] / [4][5][6][7]
      Row 6-7: direction R  [0][1][2][3] / [4][5][6][7]
    """
    directions = sorted(direction_frames.keys())
    if not directions:
        return None

    # 加载所有图片
    all_images = {}
    max_w = 0
    max_h = 0
    max_frames = 0

    for d in directions:
        imgs = []
        for _, fpath, _ in direction_frames[d]:
            img = Image.open(fpath).convert('RGBA')
            imgs.append(img)
            max_w = max(max_w, img.width)
            max_h = max(max_h, img.height)
        all_images[d] = imgs
        max_frames = max(max_frames, len(imgs))

    # 计算列数 (基于最大帧数)
    if optimize:
        cols = find_optimal_columns(max_frames, max_cols)
    else:
        cols = min(max_frames, max_cols)

    # 每个方向的行数 & 总行数
    dir_rows = {}
    total_rows = 0
    for d in directions:
        n = len(all_images[d])
        r = math.ceil(n / cols)
        dir_rows[d] = r
        total_rows += r

    # 画布大小
    cell_w = max_w + padding
    cell_h = max_h + padding
    sheet_w = cols * cell_w - padding
    sheet_h = total_rows * cell_h - padding

    sheet = Image.new('RGBA', (sheet_w, sheet_h), (0, 0, 0, 0))

    # 粘贴帧
    frame_data = []
    animations = {}
    current_row = 0

    for d in directions:
        imgs = all_images[d]
        n = len(imgs)
        start_index = len(frame_data)

        for i, img in enumerate(imgs):
            col = i % cols
            row = current_row + i // cols
            x = col * cell_w
            y = row * cell_h

            ox = x + (max_w - img.width) // 2
            oy = y + (max_h - img.height) // 2
            sheet.paste(img, (ox, oy))

            frame_data.append({
                'index': len(frame_data),
                'frame': direction_frames[d][i][0],
                'x': x,
                'y': y,
                'w': max_w,
                'h': max_h,
                'direction': d,
            })

        animations[d] = {
            'startFrame': start_index,
            'frameCount': n,
            'rowStart': current_row,
            'rowCount': dir_rows[d],
        }

        current_row += dir_rows[d]

    # 保存
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    sheet.save(output_path, 'PNG')

    total_cells = cols * total_rows
    total_frames = sum(len(v) for v in direction_frames.values())
    blanks = total_cells - total_frames

    return {
        'image': os.path.basename(output_path),
        'cols': cols,
        'rows': total_rows,
        'frameWidth': max_w,
        'frameHeight': max_h,
        'sheetWidth': sheet_w,
        'sheetHeight': sheet_h,
        'frameCount': total_frames,
        'blankCells': blanks,
        'padding': padding,
        'animations': animations,
        'frames': frame_data,
    }


def preview_layout(input_dir, mode='animation', max_cols=5, optimize=True):
    """
    布局预览（不生成文件）。

    返回: list of dict
    """
    groups = scan_and_group(input_dir, mode)
    result = []

    for group_name, frames in sorted(groups.items()):
        n = len(frames)
        item = {'name': group_name, 'frames': n}

        if mode == 'action':
            dir_counts = defaultdict(int)
            for _, _, d in frames:
                dir_counts[d or 'default'] += 1
            max_n = max(dir_counts.values())
            c = find_optimal_columns(max_n, max_cols) if optimize else min(max_n, max_cols)
            dirs = []
            for d, cnt in sorted(dir_counts.items()):
                dirs.append({'dir': d, 'count': cnt, 'cols': c, 'rows': math.ceil(cnt / c)})
            total_rows = sum(d['rows'] for d in dirs)
            blanks = c * total_rows - n
            item.update({'kind': 'action', 'cols': c, 'rows': total_rows,
                         'blankCells': blanks, 'dirs': dirs})
        else:
            c = find_optimal_columns(n, max_cols) if optimize else min(n, max_cols)
            r = math.ceil(n / c)
            blanks = c * r - n
            grid = [[1 if ri * c + ci < n else 0 for ci in range(c)] for ri in range(r)]
            item.update({'kind': 'grid', 'cols': c, 'rows': r,
                         'blankCells': blanks, 'grid': grid})

        result.append(item)

    return result


def generate_all(input_dir, output_dir, max_cols=5, mode='animation',
                 optimize=True, padding=0, generate_json=True, log_func=None):
    """
    批量生成精灵图。

    返回: list of (group_name, info_dict)
    """
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(msg)

    log(f"扫描输入目录: {input_dir}")
    groups = scan_and_group(input_dir, mode)

    if not groups:
        log("未找到任何 PNG 文件!")
        return []

    log(f"发现 {len(groups)} 个分组\n")

    os.makedirs(output_dir, exist_ok=True)
    results = []

    for group_name, frames in sorted(groups.items()):
        output_png = os.path.join(output_dir, f'{group_name}.png')

        if mode == 'action':
            # 按 direction 分组
            dir_frames = defaultdict(list)
            for item in frames:
                dir_frames[item[2] or 'default'].append(item)
            dir_frames = dict(dir_frames)

            info = create_action_sprite_sheet(
                dir_frames, output_png, max_cols, optimize, padding
            )
        else:
            info = create_sprite_sheet(
                frames, output_png, max_cols, optimize, padding
            )

        if info is None:
            continue

        results.append((group_name, info))

        # 日志输出
        blanks = info['blankCells']
        status = "0 空白" if blanks == 0 else f"{blanks} 空白格"
        log(f"  {group_name}: {info['frameCount']}帧 -> "
            f"{info['cols']}列x{info['rows']}行, "
            f"{info['sheetWidth']}x{info['sheetHeight']}px, {status}")

        # 保存 JSON
        if generate_json:
            json_path = os.path.join(output_dir, f'{group_name}.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(info, f, ensure_ascii=False, indent=2)

    log(f"\n完成! 共生成 {len(results)} 张精灵图")
    log(f"输出目录: {output_dir}")

    return results


# ============================================================
#  网页界面 (Web GUI)
# ============================================================

WEB_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>序列帧合成精灵图工具</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "Segoe UI", "Microsoft YaHei", sans-serif; background: #f5f6f8; color: #1f2328; }
header { background: #fff; border-bottom: 1px solid #e2e4e9; padding: 14px 24px; }
header h1 { font-size: 19px; font-weight: 600; }
header p { color: #6a737d; font-size: 12px; margin-top: 3px; }
.wrap { display: grid; grid-template-columns: 430px 1fr; gap: 16px; padding: 16px 24px; align-items: start; }
@media (max-width: 960px) { .wrap { grid-template-columns: 1fr; } }
.card { background: #fff; border: 1px solid #e2e4e9; border-radius: 10px; padding: 16px; }
.card h2 { font-size: 13px; font-weight: 600; margin-bottom: 12px; color: #444c56; }
.field { margin-bottom: 12px; }
.field label { display: block; font-size: 12px; color: #6a737d; margin-bottom: 4px; }
.path-row { display: flex; gap: 6px; }
.path-row input { flex: 1; padding: 7px 10px; border: 1px solid #d8dbe0; border-radius: 6px; font-size: 12px; min-width: 0; }
button { cursor: pointer; border: none; border-radius: 6px; padding: 7px 14px; font-size: 12px; }
.b2 { background: #f0f1f4; color: #1f2328; }
.b2:hover { background: #e2e5ea; }
.b1 { background: #2f6fed; color: #fff; }
.b1:hover { background: #2459c2; }
.b1:disabled { background: #9db8ee; cursor: wait; }
.options { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 12px 0; }
.options label { font-size: 12px; color: #444c56; }
.options select, .options input[type=number] { padding: 6px 8px; border: 1px solid #d8dbe0; border-radius: 6px; font-size: 12px; }
.checks { display: flex; gap: 16px; margin: 10px 0; font-size: 12px; }
.checks label { display: flex; align-items: center; gap: 5px; cursor: pointer; }
.actions { display: flex; gap: 8px; }
#log { font-family: Consolas, "Courier New", monospace; font-size: 12px; background: #1e1e1e; color: #d4d4d4; border-radius: 8px; padding: 12px; height: 260px; overflow: auto; white-space: pre-wrap; word-break: break-all; }
#results { margin-top: 12px; }
.res-title { font-size: 13px; font-weight: 600; margin-bottom: 8px; color: #444c56; }
.sheet-card { display: flex; gap: 12px; align-items: flex-start; border: 1px solid #e2e4e9; border-radius: 8px; padding: 10px; margin-bottom: 10px; background: #fafbfc; }
.sheet-card img { border: 1px solid #e2e4e9; max-width: 180px; max-height: 140px; }
.checker { background: conic-gradient(#e8e9ec 25%, #fff 0 50%, #e8e9ec 0 75%, #fff 0) 0 0 / 16px 16px; border-radius: 4px; }
.sheet-info { min-width: 0; }
.sheet-title { font-size: 13px; font-weight: 600; word-break: break-all; }
.sheet-meta { font-size: 12px; color: #6a737d; margin-top: 3px; }
.badge { display: inline-block; font-size: 11px; padding: 1px 8px; border-radius: 10px; margin-left: 6px; vertical-align: 1px; }
.badge.ok { background: #dafbe1; color: #116329; }
.badge.warn { background: #fff8c5; color: #7d4e00; }
.mini-grid { display: inline-grid; gap: 2px; margin-top: 6px; }
.cell-fill { width: 13px; height: 13px; background: #2f6fed; border-radius: 2px; }
.cell-empty { width: 13px; height: 13px; background: #f0f1f4; border: 1px dashed #c9ccd2; border-radius: 2px; }
.dir-line { font-size: 12px; color: #57606a; margin-top: 3px; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.35); display: none; align-items: center; justify-content: center; z-index: 100; }
.modal { background: #fff; border-radius: 12px; width: 580px; max-width: 94vw; max-height: 74vh; display: flex; flex-direction: column; overflow: hidden; }
.modal-head { padding: 12px 16px; border-bottom: 1px solid #e2e4e9; display: flex; justify-content: space-between; align-items: center; }
.modal-head b { font-size: 14px; }
.modal-path { font-size: 12px; color: #6a737d; padding: 8px 16px 0; word-break: break-all; }
.modal-body { padding: 6px 16px 12px; flex: 1; overflow-y: auto; min-height: 200px; }
.modal-foot { padding: 10px 16px; border-top: 1px solid #e2e4e9; display: flex; justify-content: flex-end; gap: 8px; }
.dir-item { display: flex; align-items: center; gap: 8px; padding: 7px 10px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.dir-item:hover { background: #f0f1f4; }
.dir-item svg { flex: 0 0 auto; }
.dir-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.up-row { display: flex; justify-content: space-between; align-items: center; padding: 4px 0 8px; }
.hint { font-size: 11px; color: #9aa1ab; margin-top: 6px; }
</style>
</head>
<body>
<header>
  <h1>序列帧合成精灵图工具</h1>
  <p>批量将序列帧 PNG 合成为精灵图，自动优化列数减少空白 · 本工具仅在本机运行</p>
</header>
<div class="wrap">
  <div class="card">
    <h2>参数设置</h2>
    <div class="field">
      <label>输入路径（序列帧所在文件夹）</label>
      <div class="path-row">
        <input id="input_path" placeholder="选择或直接粘贴路径">
        <button class="b2" onclick="openBrowser('input')">浏览...</button>
      </div>
    </div>
    <div class="field">
      <label>输出路径（精灵图保存位置）</label>
      <div class="path-row">
        <input id="output_path" placeholder="默认: 输入目录/sprite_sheets">
        <button class="b2" onclick="openBrowser('output')">浏览...</button>
        <button class="b2" onclick="openOutput()" title="在资源管理器中打开">打开</button>
      </div>
    </div>
    <div class="options">
      <label>每行最大帧数 <input id="max_cols" type="number" min="1" max="32" value="5" style="width:60px"></label>
      <label>分组模式
        <select id="mode">
          <option value="animation">按动画分组</option>
          <option value="action">按动作分组(多方向合一)</option>
          <option value="all">全部合并</option>
        </select>
      </label>
      <label>帧间距 <input id="padding" type="number" min="0" max="32" value="0" style="width:60px"></label>
    </div>
    <div class="checks">
      <label><input id="optimize" type="checkbox" checked>自动优化列数(减少空白)</label>
      <label><input id="gen_json" type="checkbox" checked>生成JSON元数据</label>
    </div>
    <div class="actions">
      <button id="btn-prev" class="b2" onclick="doAction('preview')">预览布局</button>
      <button id="btn-gen" class="b1" onclick="doAction('generate')">生成精灵图</button>
    </div>
    <div class="hint">提示：先点「预览布局」查看排版与空白数量，确认后再生成。</div>
  </div>
  <div>
    <div class="card">
      <h2>日志</h2>
      <div id="log">就绪。选择输入/输出路径后，先预览布局，再生成精灵图。</div>
    </div>
    <div id="results"></div>
  </div>
</div>

<div class="modal-overlay" id="modal">
  <div class="modal">
    <div class="modal-head">
      <b id="modal-title">选择文件夹</b>
      <button class="b2" onclick="closeBrowser()">x</button>
    </div>
    <div class="modal-path" id="browse-path"></div>
    <div class="up-row" style="padding: 8px 16px 0;">
      <button class="b2" id="browse-up" onclick="goUp()" style="visibility:hidden">上一级</button>
      <span class="hint" id="drive-hint" style="display:none">请选择磁盘</span>
    </div>
    <div class="modal-body" id="dir-list"></div>
    <div class="modal-foot">
      <button class="b2" onclick="closeBrowser()">取消</button>
      <button class="b1" onclick="pickDir()">选择此文件夹</button>
    </div>
  </div>
</div>

<script>
var $ = function (id) { return document.getElementById(id); };
var browse = { kind: null, path: '', parent: null };
var FOLDER_SVG = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M1.5 3.5h4l1.5 2h7.5v7a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 1 12.5v-9a1 1 0 0 1 1-1h1.5v1H2.2a.7.7 0 0 0-.7.7v.3z" fill="#8db4e8"/></svg>';

function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function postJSON(url, data) {
  return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
    .then(function (r) { return r.json(); });
}

function openBrowser(kind) {
  browse.kind = kind; browse.path = ''; browse.parent = null;
  $('modal-title').textContent = kind === 'input' ? '选择输入文件夹' : '选择输出文件夹';
  $('modal').style.display = 'flex';
  loadDirs('');
}
function closeBrowser() { $('modal').style.display = 'none'; }

function loadDirs(path) {
  fetch('/api/list?path=' + encodeURIComponent(path)).then(function (r) { return r.json(); }).then(function (data) {
    browse.path = data.path; browse.parent = data.parent;
    $('browse-path').textContent = data.path || '请选择磁盘';
    $('browse-up').style.visibility = data.parent ? 'visible' : 'hidden';
    $('drive-hint').style.display = data.path ? 'none' : 'inline';
    var list = $('dir-list');
    list.innerHTML = '';
    (data.items || []).forEach(function (it) {
      var row = document.createElement('div');
      row.className = 'dir-item';
      row.innerHTML = FOLDER_SVG + '<span class="dir-name">' + escapeHtml(it.name) + '</span>';
      row.title = it.path;
      row.onclick = function () { loadDirs(it.path); };
      list.appendChild(row);
    });
  });
}
function goUp() { if (browse.parent) loadDirs(browse.parent); }

function pickDir() {
  var inp = browse.kind === 'input' ? $('input_path') : $('output_path');
  if (!browse.path) { alert('请先进入一个文件夹'); return; }
  inp.value = browse.path;
  if (browse.kind === 'input' && !$('output_path').value) {
    $('output_path').value = browse.path.replace(/[\\\\/]+$/, '') + '\\\\sprite_sheets';
  }
  closeBrowser();
}

function collect() {
  return {
    input_dir: $('input_path').value.trim(),
    output_dir: $('output_path').value.trim(),
    max_cols: parseInt($('max_cols').value, 10) || 5,
    mode: $('mode').value,
    optimize: $('optimize').checked,
    padding: parseInt($('padding').value, 10) || 0,
    generate_json: $('gen_json').checked
  };
}

function renderLog(lines) {
  $('log').textContent = (lines || []).join('\\n');
  $('log').scrollTop = $('log').scrollHeight;
}

function gridHtml(grid, cols) {
  var html = '<div class="mini-grid" style="grid-template-columns:repeat(' + cols + ',13px)">';
  grid.forEach(function (rowArr) {
    rowArr.forEach(function (cell) {
      html += cell ? '<div class="cell-fill"></div>' : '<div class="cell-empty"></div>';
    });
  });
  return html + '</div>';
}

function renderPreview(items) {
  var box = $('results');
  var html = '<div class="res-title">布局预览</div>';
  items.forEach(function (it) {
    var badge = it.blankCells === 0
      ? '<span class="badge ok">0 空白</span>'
      : '<span class="badge warn">' + it.blankCells + ' 空白</span>';
    html += '<div class="sheet-card"><div class="sheet-info">';
    html += '<div class="sheet-title">' + escapeHtml(it.name) + ' (' + it.frames + '帧) ' + badge + '</div>';
    html += '<div class="sheet-meta">' + it.cols + '列 x ' + it.rows + '行</div>';
    if (it.kind === 'grid') {
      html += gridHtml(it.grid, it.cols);
    } else {
      it.dirs.forEach(function (d) {
        html += '<div class="dir-line">方向 ' + escapeHtml(d.dir) + ': ' + d.count + '帧 -> ' + d.cols + '列x' + d.rows + '行</div>';
      });
    }
    html += '</div></div>';
  });
  box.innerHTML = html;
}

function renderSheets(sheets) {
  var box = $('results');
  var html = '<div class="res-title">生成结果 (' + sheets.length + ' 张)</div>';
  sheets.forEach(function (s) {
    var badge = s.blanks === 0
      ? '<span class="badge ok">0 空白</span>'
      : '<span class="badge warn">' + s.blanks + ' 空白</span>';
    html += '<div class="sheet-card"><div class="checker"><img src="' + s.dataUrl + '" alt="' + escapeHtml(s.name) + '"></div>';
    html += '<div class="sheet-info"><div class="sheet-title">' + escapeHtml(s.name) + '.png ' + badge + '</div>';
    html += '<div class="sheet-meta">' + s.frameCount + '帧 · ' + s.cols + '列x' + s.rows + '行 · ' +
            s.sheetWidth + 'x' + s.sheetHeight + 'px' + (s.jsonWritten ? ' · 含JSON' : '') + '</div></div></div>';
  });
  box.innerHTML = html;
}

function doAction(action) {
  var body = collect();
  var btn = action === 'generate' ? $('btn-gen') : $('btn-prev');
  btn.disabled = true;
  var old = btn.textContent;
  btn.textContent = '处理中...';
  postJSON('/api/' + action, body).then(function (res) {
    if (res.error) { renderLog((res.log || []).concat(['错误: ' + res.error])); }
    else {
      renderLog(res.log || []);
      if (res.preview) renderPreview(res.preview);
      if (res.sheets) renderSheets(res.sheets);
    }
  }).catch(function (e) {
    renderLog(['请求失败: ' + e]);
  }).then(function () {
    btn.disabled = false; btn.textContent = old;
  });
}

function openOutput() {
  var p = $('output_path').value.trim();
  if (p) fetch('/api/open?path=' + encodeURIComponent(p));
}
</script>
</body>
</html>
"""


def _list_drives():
    """返回本机可用盘符列表。"""
    import string
    drives = []
    for c in string.ascii_uppercase:
        p = f'{c}:\\'
        if os.path.exists(p):
            drives.append(p)
    return drives


def list_dirs(path):
    """返回目录列表，用于网页端文件夹浏览。"""
    if not path:
        items = [{'name': p, 'path': p} for p in _list_drives()]
        return {'path': '', 'parent': None, 'items': items}

    path = os.path.abspath(path)
    parent = os.path.dirname(path) if os.path.dirname(path) != path else None
    try:
        entries = sorted(os.listdir(path), key=str.lower)
    except Exception:
        entries = []
    items = []
    for e in entries:
        full = os.path.join(path, e)
        try:
            if os.path.isdir(full):
                items.append({'name': e, 'path': full})
        except Exception:
            pass
    return {'path': path, 'parent': parent, 'items': items}


def _sheet_preview(png_path, max_size=400):
    """生成精灵图的 base64 缩略图 (data URL)，避免网页传输大图。"""
    try:
        img = Image.open(png_path).convert('RGBA')
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size))
        buf = io.BytesIO()
        img.save(buf, 'PNG', optimize=True)
        return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception:
        return ''


class _WebHandler(http.server.BaseHTTPRequestHandler):
    """本地 HTTP 服务，处理页面与 API 请求。"""

    def log_message(self, *args):
        pass

    def _send(self, code, content_type, body):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj):
        data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self._send(200, 'application/json; charset=utf-8', data)

    def _send_html(self, html):
        data = html.encode('utf-8')
        self._send(200, 'text/html; charset=utf-8', data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path in ('/', '/index.html'):
            self._send_html(WEB_HTML)
        elif parsed.path == '/api/list':
            q = urllib.parse.parse_qs(parsed.query)
            path = q.get('path', [''])[0]
            self._send_json(list_dirs(path))
        elif parsed.path == '/api/open':
            q = urllib.parse.parse_qs(parsed.query)
            path = q.get('path', [''])[0]
            try:
                os.startfile(path)
                self._send_json({'ok': True})
            except Exception:
                self._send_json({'ok': False})
        else:
            self._send(404, 'text/plain', b'Not Found')

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0) or 0)
        try:
            body = json.loads(self.rfile.read(length).decode('utf-8') or '{}')
        except Exception:
            body = {}

        if self.path == '/api/preview':
            try:
                pv = preview_layout(
                    input_dir=body.get('input_dir', ''),
                    mode=body.get('mode', 'animation'),
                    max_cols=int(body.get('max_cols', 5)),
                    optimize=bool(body.get('optimize', True)),
                )
                self._send_json({'preview': pv, 'log': [f"预览 {len(pv)} 个分组完成"]})
            except Exception as e:
                self._send_json({'error': str(e), 'log': []})

        elif self.path == '/api/generate':
            logs = []
            try:
                results = generate_all(
                    input_dir=body.get('input_dir', ''),
                    output_dir=body.get('output_dir', ''),
                    max_cols=int(body.get('max_cols', 5)),
                    mode=body.get('mode', 'animation'),
                    optimize=bool(body.get('optimize', True)),
                    padding=int(body.get('padding', 0)),
                    generate_json=bool(body.get('generate_json', True)),
                    log_func=logs.append,
                )
                sheets = []
                for name, info in results:
                    png_path = os.path.join(body.get('output_dir', ''), info['image'])
                    sheets.append({
                        'name': name,
                        'cols': info['cols'],
                        'rows': info['rows'],
                        'frameCount': info['frameCount'],
                        'blankCells': info['blankCells'],
                        'sheetWidth': info['sheetWidth'],
                        'sheetHeight': info['sheetHeight'],
                        'jsonWritten': bool(body.get('generate_json', True)),
                        'dataUrl': _sheet_preview(png_path),
                    })
                self._send_json({'log': logs, 'sheets': sheets})
            except Exception as e:
                logs.append(f'错误: {e}')
                self._send_json({'error': str(e), 'log': logs})
        else:
            self._send(404, 'text/plain', b'Not Found')


def web_gui_main(port=8765):
    """启动本地网页服务并打开浏览器。"""
    handler = _WebHandler
    server = None
    for p in range(port, port + 20):
        try:
            server = http.server.ThreadingHTTPServer(('127.0.0.1', p), handler)
            port = p
            break
        except OSError:
            continue

    if server is None:
        print("无法启动本地服务 (端口被占用)，请稍后重试。")
        return

    url = f'http://127.0.0.1:{port}/'
    print("=" * 50)
    print("序列帧合成精灵图工具 - 网页版已启动")
    print(f"请在浏览器中打开: {url}")
    print("关闭本窗口 (Ctrl+C) 即可退出工具")
    print("=" * 50)

    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


# ============================================================
#  命令行入口
# ============================================================

def cli_main():
    parser = argparse.ArgumentParser(description='序列帧合成精灵图工具')
    parser.add_argument('--input', '-i', required=True, help='输入目录')
    parser.add_argument('--output', '-o', required=True, help='输出目录')
    parser.add_argument('--max-cols', type=int, default=5, help='每行最大帧数 (默认 5)')
    parser.add_argument('--mode', choices=['animation', 'action', 'all'],
                        default='animation', help='分组模式 (默认 animation)')
    parser.add_argument('--no-optimize', action='store_true', help='关闭列数自动优化')
    parser.add_argument('--no-json', action='store_true', help='不生成 JSON 元数据')
    parser.add_argument('--padding', type=int, default=0, help='帧间距 (默认 0)')
    parser.add_argument('--gui', action='store_true', help='启动网页界面')

    args = parser.parse_args()

    if args.gui:
        web_gui_main()
        return

    generate_all(
        input_dir=args.input,
        output_dir=args.output,
        max_cols=args.max_cols,
        mode=args.mode,
        optimize=not args.no_optimize,
        padding=args.padding,
        generate_json=not args.no_json,
    )


if __name__ == '__main__':
    # 无参数 -> 网页版; 有参数 -> 命令行
    if len(sys.argv) > 1:
        cli_main()
    else:
        web_gui_main()
