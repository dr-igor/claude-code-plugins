local stringify = pandoc.utils.stringify

local PNG_SIGNATURE = "\137PNG\r\n\26\n"
local PLANTUML_SOURCE = "^plantuml%-images/"
local BASELINE_IN = 0.1667
local AVERAGE_CHAR_IN = 0.069
local GUTTER_IN = 0.167
local BOX_PAD_IN = 0.02

local config = {
  dpi = 260.0,
  max_width = 6.5,
  max_height = 6.0,
  wrap_max_width = 3.0,
  wrap_max_height = 3.5,
  wrap = false,
  latex = false,
}

local function meta_number(meta, key, fallback)
  local value = meta[key]
  if value == nil then
    return fallback
  end
  return tonumber(stringify(value)) or fallback
end

local function meta_flag(meta, key)
  local value = meta[key]
  return value ~= nil and stringify(value) == "1"
end

local function read_config(meta)
  config.dpi = meta_number(meta, "diagram-dpi", config.dpi)
  config.max_width = meta_number(meta, "diagram-max-width-in", config.max_width)
  config.max_height = meta_number(meta, "diagram-max-height-in", config.max_height)
  config.wrap_max_width = meta_number(meta, "diagram-wrap-max-width-in", config.wrap_max_width)
  config.wrap_max_height = meta_number(meta, "diagram-wrap-max-height-in", config.wrap_max_height)
  config.wrap = meta_flag(meta, "diagram-wrap")
  config.latex = meta_flag(meta, "diagram-latex")
end

local function png_size(path)
  local handle = io.open(path, "rb")
  if not handle then
    return nil
  end
  local header = handle:read(24)
  handle:close()
  if not header or #header < 24 or header:sub(1, 8) ~= PNG_SIGNATURE then
    return nil
  end
  local ok, width, height = pcall(string.unpack, ">I4I4", header, 17)
  if not ok or width == 0 or height == 0 then
    return nil
  end
  return width, height
end

local function diagram_image(block)
  if block.t ~= "Para" or #block.content ~= 1 then
    return nil
  end
  local inline = block.content[1]
  if inline.t ~= "Image" or not inline.src:match(PLANTUML_SOURCE) then
    return nil
  end
  return inline
end

local function placement(pixel_width, pixel_height)
  local width = pixel_width / config.dpi
  local height = pixel_height / config.dpi
  if width > config.max_width then
    height = height * config.max_width / width
    width = config.max_width
  end
  if height > config.max_height then
    width = width * config.max_height / height
    height = config.max_height
  end
  return width, height
end

local function prose_characters(blocks, index)
  local total = 0
  for cursor = index, #blocks do
    local block = blocks[cursor]
    if block.t ~= "Para" or diagram_image(block) then
      break
    end
    total = total + #stringify(block)
  end
  return total
end

local function fits_beside(width, height, characters)
  local lines = height / BASELINE_IN
  local per_line = (config.max_width - width - GUTTER_IN) / AVERAGE_CHAR_IN
  return per_line > 0 and characters >= lines * per_line
end

local function wraps(blocks, index, width, height)
  if not (config.wrap and config.latex) then
    return false
  end
  if width > config.wrap_max_width or height > config.wrap_max_height then
    return false
  end
  local following = blocks[index + 1]
  if not following or following.t ~= "Para" or diagram_image(following) then
    return false
  end
  return fits_beside(width, height, prose_characters(blocks, index + 1))
end

local function wrap_figure(image, width)
  return pandoc.RawInline(
    "latex",
    string.format(
      "\\begin{wrapfigure}{r}{%.3fin}\\centering\\includegraphics[width=%.3fin]{%s}\\end{wrapfigure}",
      width + BOX_PAD_IN,
      width,
      image.src
    )
  )
end

local function centred(image, width)
  image.attributes.width = string.format("%.3fin", width)
  local para = pandoc.Para({ image })
  if not config.latex then
    return { para }
  end
  return {
    pandoc.RawBlock("latex", "\\begin{center}"),
    para,
    pandoc.RawBlock("latex", "\\end{center}"),
  }
end

local function layout(blocks)
  local result = pandoc.Blocks({})
  local index = 1
  while index <= #blocks do
    local block = blocks[index]
    local image = diagram_image(block)
    local pixel_width, pixel_height
    if image then
      pixel_width, pixel_height = png_size(image.src)
    end
    if not pixel_width then
      result:insert(block)
      index = index + 1
    else
      local width, height = placement(pixel_width, pixel_height)
      if wraps(blocks, index, width, height) then
        local content = blocks[index + 1].content:clone()
        content:insert(1, wrap_figure(image, width))
        result:insert(pandoc.Para(content))
        index = index + 2
      else
        result:extend(centred(image, width))
        index = index + 1
      end
    end
  end
  return result
end

return {
  {
    Pandoc = function(doc)
      read_config(doc.meta)
      return doc:walk({ Blocks = layout })
    end,
  },
}
