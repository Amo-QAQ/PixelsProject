-- ============================================================
-- export_sprite_sheets.lua
-- 功能：一键按 切片(Slice) × 标签(Tag) 导出精灵图(Sprite Sheet)
--
-- 原理：
--   遍历所有 Slice 和 Tag 的组合
--   对每个组合：收集该 Tag 下所有帧 → 按 Slice 区域裁剪 → 拼接成 Sprite Sheet
--
-- 使用方法：
--   1. File -> Scripts -> Open Script Folder
--   2. 把此脚本放进去
--   3. File -> Scripts -> Reload Scripts and Plugins
--   4. 打开 .ase/.aseprite 文件
--   5. File -> Scripts -> export_sprite_sheets -> Run Script
-- ============================================================

local dlg = Dialog("🎮 精灵图批量导出工具")

-- 全局配置
local config = {
  outputDir = "",
  direction = "horizontal",  -- horizontal / vertical
  padding = 0,
  maxPerRow = 0,              -- 0 = 无限
  bgTransparent = true,
  bgColor = app.pixelColor.rgba(0, 0, 0, 0),
  generateJson = true,
}

-- ============================================================
-- 工具函数
-- ============================================================

--- 安全化文件名（去除非法字符）
local function safeFileName(name)
  return string.gsub(name, "[^%w_%-]", "_")
end

--- 创建目录（递归）
local function ensureDir(path)
  os.execute('mkdir "' .. path .. '" 2>nul')
end

--- 获取切片在某帧的实际边界
local function getSliceBounds(slice, frameNum)
  if not slice then return nil end
  
  -- 检查是否有逐帧定义的边界
  local bounds = slice.bounds
  if not bounds then return nil end
  
  return {
    x = bounds.x,
    y = bounds.y,
    width = bounds.width,
    height = bounds.height
  }
end

--- 从图像中裁剪指定区域
local function cropImage(srcImg, x, y, w, h)
  if w <= 0 or h <= 0 then return nil end
  
  local cropped = Image(w, h)
  
  -- 复制像素
  for dy = 0, h - 1 do
    for dx = 0, w - 1 do
      local sx = x + dx
      local sy = y + dy
      if sx >= 0 and sx < srcImg.width and sy >= 0 and sy < srcImg.height then
        local pixel = srcImg:getPixel(sx, sy)
        cropped:drawPixel(dx, dy, pixel)
      else
        cropped:drawPixel(dx, dy, app.pixelColor.rgba(0, 0, 0, 0))
      end
    end
  end
  
  return cropped
end

--- 合并某一帧的所有可见图层为一个图像
local function flattenFrame(spr, frame)
  if not spr or not frame then return nil end
  
  -- 获取 Sprite 尺寸
  local sw = spr.width
  local sh = spr.height
  
  -- 创建透明图像
  local flat = Image(sw, sh)
  flat:clear(app.pixelColor.rgba(0, 0, 0, 0))
  
  -- 从后往前遍历图层（底层先画）
  local layers = {}
  for i = 0, #spr.layers - 1 do
    layers[i + 1] = spr.layers[i]
  end
  
  -- 按层级排序（从底到顶）
  table.sort(layers, function(a, b)
    return a.stackIndex < b.stackIndex
  end)
  
  for _, layer in ipairs(layers) do
    -- 跳过隐藏层
    if layer.isVisible then
      local cel = layer:cel(frame)
      if cel and cel.image then
        local img = cel.image
        local pos = cel.position
        
        -- 绘制该层图像到合并图像
        for y = 0, img.height - 1 do
          for x = 0, img.width - 1 do
            local px = pos.x + x
            local py = pos.y + y
            if px >= 0 and px < sw and py >= 0 and py < sh then
              local pixel = img:getPixel(x, y)
              local alpha = app.pixelColor.rgbaA(pixel)
              if alpha > 0 then
                flat:drawPixel(px, py, pixel)
              end
            end
          end
        end
      end
    end
  end
  
  return flat
end

--- 创建精灵图（将多帧拼接成一张图）
local function createSpriteSheet(frames, direction, padding, maxPerRow, bgColor)
  if not frames or #frames == 0 then return nil end
  
  local fw = frames[1].width
  local fh = frames[1].height
  local count = #frames
  
  -- 计算布局
  local cols, rows
  if direction == "horizontal" then
    cols = (maxPerRow > 0 and math.min(maxPerRow, count)) or count
    rows = math.ceil(count / cols)
  else
    rows = (maxPerRow > 0 and math.min(maxPerRow, count)) or count
    cols = math.ceil(count / rows)
  end
  
  local sheetW = fw * cols + padding * math.max(0, cols - 1)
  local sheetH = fh * rows + padding * math.max(0, rows - 1)
  
  -- 创建 Sheet
  local sheet = Image(sheetW, sheetH)
  sheet:clear(bgColor)
  
  -- 粘贴每帧
  local framesData = {}
  for i, frame in ipairs(frames) do
    local col, row
    if direction == "horizontal" then
      col = (i - 1) % cols
      row = math.floor((i - 1) / cols)
    else
      row = (i - 1) % rows
      col = math.floor((i - 1) / rows)
    end
    
    local x = col * (fw + padding)
    local y = row * (fh + padding)
    
    if frame.image then
      sheet:drawImage(frame.image, x, y)
    end
    
    table.insert(framesData, {
      frame = i,
      x = x,
      y = y,
      width = fw,
      height = fh
    })
  end
  
  return sheet, framesData, { width = sheetW, height = sheetH }
end

--- 导出单个 Sprite Sheet
local function exportOne(spr, slice, tag, outputDir, cfg)
  local sliceName = safeFileName(slice.name or ("slice_" .. tostring(slice)))
  local tagName = safeFileName(tag.name or ("tag_" .. tostring(tag)))
  
  local baseName = sliceName .. "_" .. tagName
  
  -- 收集该 Tag 范围内的所有帧
  local frames = {}
  local fromFrame = tag.from or 1
  local toFrame = tag.to or (#spr.frames)
  
  for frameNum = fromFrame, toFrame do
    local frame = spr.frames[frameNum]
    if not frame then goto continue end
    
    -- 获取切片边界
    local bounds = getSliceBounds(slice, frameNum)
    if not bounds then goto continue end
    
    -- 展平该帧
    local flatImg = flattenFrame(spr, frame)
    if not flatImg then goto continue end
    
    -- 裁剪切片区域
    local cropped = cropImage(flatImg, bounds.x, bounds.y, bounds.width, bounds.height)
    
    if cropped then
      table.insert(frames, {
        image = cropped,
        width = bounds.width,
        height = bounds.height,
        frameNumber = frameNum
      })
    end
    
    flatImg:free()
    
    ::continue::
  end
  
  if #frames == 0 then
    return false, "没有可用的帧"
  end
  
  -- 创建 Sprite Sheet
  local bgColor = cfg.bgTransparent and app.pixelColor.rgba(0, 0, 0, 0) or cfg.bgColor
  local sheet, framesData, sheetSize = createSpriteSheet(
    frames, cfg.direction, cfg.padding, cfg.maxPerRow, bgColor
  )
  
  if not sheet then
    return false, "创建精灵图失败"
  end
  
  -- 保存 PNG
  ensureDir(outputDir)
  local pngPath = outputDir .. "\\" .. baseName .. ".png"
  sheet:saveAs(pngPath)
  sheet:free()
  
  -- 释放裁剪后的帧图像
  for _, f in ipairs(frames) do
    if f.image then f.image:free() end
  end
  
  -- 可选：生成 JSON
  local jsonPath = nil
  if cfg.generateJson then
    local jsonData = {
      name = baseName,
      slice = sliceName,
      tag = tagName,
      frameSize = { frames[1].width, frames[1].height },
      frameCount = #frames,
      sheetSize = { sheetSize.width, sheetSize.height },
      direction = cfg.direction,
      frames = framesData
    }
    
    jsonPath = outputDir .. "\\" .. baseName .. ".json"
    local file = io.open(jsonPath, "w")
    if file then
      -- 简单 JSON 序列化
      local function serialize(obj, indent)
        indent = indent or ""
        local t = type(obj)
        if t == "nil" then return "nil"
        elseif t == "boolean" then return obj and "true" or "false"
        elseif t == "number" then return tostring(obj)
        elseif t == "string" then return '"' .. obj:gsub('"', '\\"') .. '"'
        elseif t == "table" then
          local isArray = true
          local k = 1
          for _ in pairs(obj) do
            if obj[k] == nil then isArray = false; break end
            k = k + 1
          end
          
          local result = ""
          if isArray then
            result = result .. "[\n"
            for i, v in ipairs(obj) do
              result = result .. indent .. "  " .. serialize(v, indent .. "  ")
              if i < #obj then result = result .. "," end
              result = result .. "\n"
            end
            result = result .. indent .. "]"
          else
            result = result .. "{\n"
            local keys = {}
            for k in pairs(obj) do table.insert(keys, k) end
            table.sort(keys)
            for i, k in ipairs(keys) do
              result = result .. indent .. '  "' .. k .. '": ' .. serialize(obj[k], indent .. "  ")
              if i < #keys then result = result .. "," end
              result = result .. "\n"
            end
            result = result .. indent .. "}"
          end
          return result
        end
        return '"???"'
      end
      
      file:write(serialize(jsonData))
      file:close()
    end
  end
  
  return true, pngPath, #frames, sheetSize
end

-- ============================================================
-- 主流程
-- ============================================================

local spr = app.activeSprite
if not spr then
  return alert("❌ 请先打开一个 Aseprite 工程文件！\n\nFile -> Open -> 选择你的 .ase/.aseprite 文件")
end

-- 设置默认输出目录
local filePath = spr.fileName
if filePath and filePath ~= "" then
  config.outputDir = app.fs.filePath(filePath) .. "\\sprite_sheets_export"
else
  config.outputDir = app.fs.homePath .. "\\Desktop\\sprite_sheets_export"
end

-- 收集切片
local slices = {}
for i = 0, #spr.slices - 1 do
  table.insert(slices, spr.slices[i])
end

-- 收集标签
local tags = {}
for i = 0, #spr.tags - 1 do
  table.insert(tags, spr.tags[i])
end

-- 如果没有标签，添加一个虚拟标签覆盖全部帧
if #tags == 0 then
  tags = {{ name = "all_frames", from = 1, to = #spr.frames }}
end

-- 如果没有切片，提示用户
if #slices == 0 then
  return alert([[
❌ 没有找到任何切片(Slice)！

请先创建切片：
  方法1：菜单 Sprite -> New Slice
  方法2：快捷键 Shift+R（矩形选区后）
  方法3：右键图层面板 -> New Slice

创建切片后再运行此脚本。
]])
end

-- ============================================================
-- 构建对话框
-- ============================================================

dlg:label{
  label="工程文件",
  text=app.fs.fileTitle(filePath) or "(未保存)"
}

dlg:label{
  label="检测到",
  text=string.format("%d 个切片 × %d 个标签 = %d 张精灵图", 
    #slices, #tags, #slices * #tags)
}

-- 显示切片列表
local sliceNames = {}
for _, s in ipairs(slices) do
  table.insert(sliceNames, s.name or ("未命名#"..tostring(s)))
end
dlg:combobox{ label="切片列表", options=sliceNames, readonly=true }

-- 显示标签列表
local tagNames = {}
for _, t in ipairs(tags) do
  local info = t.name .. " (帧 " .. tostring(t.from) .. "-" .. tostring(t.to) .. ")"
  table.insert(tagNames, info)
end
dlg:combobox{ label="标签列表", options=tagNames, readonly=true }

dlg:separator{}

-- 导出设置
dlg:entry{ id="outputDir", label="输出目录", text=config.outputDir }
dlg:combobox{ id="direction", label="排列方向", options={"horizontal(横排)", "vertical(纵排)"}, default="horizontal(横排)" }
dlg:number{ id="padding", label="帧间距", value=0, min=0, max=20 }
dlg:check{ id="transparent", label="透明背景", value=true }
dlg:check{ id="genJson", label="生成JSON数据", value=true }

dlg:separator{}
dlg:button{ id="ok", text="✅ 开始导出", onclick=function()
  dlg:close{ ok=true }
end}
dlg:button{ id="cancel", text="取消", onclick=function()
  dlg:close{ cancel=true }
end}

-- 显示对话框
local result = dlg:show{ wait=true }

if not result.ok then
  return -- 用户取消
end

-- 读取用户设置
config.outputDir = result.outputDir or config.outputDir
config.direction = string.match(result.direction, "^(%w+)") or "horizontal"
config.padding = result.padding or 0
config.bgTransparent = result.transparent ~= false
config.generateJson = result.genJson == true

-- ============================================================
-- 执行导出
-- ============================================================

ensureDir(config.outputDir)

local successCount = 0
local failCount = 0
local results = {}

app.refresh()

for si, slice in ipairs(slices) do
  for ti, tag in ipairs(tags) do
    local sliceName = slice.name or ("slice_" .. tostring(si))
    local tagName = tag.name or ("tag_" .. tostring(ti))
    
    app.log(string.format("正在导出: %s × %s ...", sliceName, tagName))
    
    local ok, ret1, ret2, ret3 = exportOne(spr, slice, tag, config.outputDir, config)
    
    if ok then
      local path, count, size = ret1, ret2, ret3
      successCount = successCount + 1
      table.insert(results, {
        status = "✅",
        slice = sliceName,
        tag = tagName,
        frames = count,
        size = tostring(size.width) .. "x" .. tostring(size.height),
        path = path
      })
      app.log(string.format("  ✅ 成功: %s (%d帧, %s)", path, count, tostring(size.width).."x"..tostring(size.height)))
    else
      failCount = failCount + 1
      local reason = ret1 or "未知错误"
      table.insert(results, {
        status = "❌",
        slice = sliceName,
        tag = tagName,
        error = reason
      })
      app.log(string.format("  ❌ 失败: %s", reason))
    end
  end
end

-- ============================================================
-- 结果报告
-- ============================================================

local report = "🎮 导出完成！\n\n"
report = report .. string.format("成功: %d 张 | 失败: %d 张\n", successCount, failCount)
report = report .. "输出位置: " .. config.outputDir .. "\n\n"

if #results <= 10 then
  -- 详细显示每条结果
  for _, r in ipairs(results) do
    if r.status == "✅" then
      report = report .. string.format("%s [%s×%s] %d帧 %s\n", 
        r.status, r.slice, r.tag, r.frames, r.size)
    else
      report = report .. string.format("%s [%s×%s] %s\n", 
        r.status, r.slice, r.tag, r.error or "")
    end
  end
else
  report = report .. "(结果较多，已省略详情)\n"
end

alert(report)

-- 打开输出文件夹
os.execute('explorer "' .. config.outputDir .. '"')

app.log("全部导出任务完成!")
