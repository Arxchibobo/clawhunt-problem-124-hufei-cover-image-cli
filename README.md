# Cover Image Multi-Ratio Export Tool

**ClawHunt Problem #124** - CLI: 封面图多比例自动导出 + 安全区检测

A production-ready CLI tool for exporting cover images to multiple platform-specific aspect ratios with intelligent safe-zone detection.

---

## Features

- 📐 **Multi-ratio Export**: Automatically generates covers for Bilibili (16:9, 4:3), Xiaohongshu (3:4), and Douyin (9:16)
- 🎯 **Smart Cropping**: Center-based crop with saliency preservation
- 🛡️ **Safe-Zone Detection**: Analyzes each platform's UI overlay margins to detect content at risk
- 🎨 **Auto-Padding**: Expands canvas with blurred edges when cropping would cut important content
- 📊 **Risk Reporting**: Color-coded table showing safety status per platform
- ⚙️ **Configurable**: Edit `platforms.json` to customize ratios and safe margins

## Installation

```bash
pip install -r requirements.txt
```

**Requirements:**
- Python 3.7+
- Pillow >= 10.0
- rich >= 13.0 (optional, for colored output)

## Quick Start

```bash
# Create a test image
python cover_tool.py --create-test

# Export to all platforms
python cover_tool.py test_input.jpg

# Export to specific platforms only
python cover_tool.py my_cover.jpg --platforms bilibili xiaohongshu

# Disable auto-padding (strict crop only)
python cover_tool.py my_cover.jpg --no-expand

# Get JSON output
python cover_tool.py my_cover.jpg --json
```

## Usage

```
python cover_tool.py INPUT_IMAGE [OPTIONS]

Arguments:
  INPUT_IMAGE              Path to input cover image (jpg/png)

Options:
  --output, -o DIR         Output directory (default: output)
  --platforms, -p LIST     Specific platforms: bilibili xiaohongshu douyin
  --no-expand              Disable auto-padding with blurred edges
  --json                   Output results as JSON instead of table
  --create-test            Create a test image and exit
```

## Safe-Zone Concept

Each platform overlays UI elements (titles, buttons, progress bars) that can obscure parts of your cover image. The tool analyzes these "danger zones" and warns you if important content is at risk.

```
┌─────────────────────────────────────────┐
│ ▓▓▓▓▓▓▓▓▓▓ DANGER ZONE (Top) ▓▓▓▓▓▓▓▓▓▓ │  ← Platform UI overlays
│ ▓                                     ▓ │
│ ▓  ┌─────────────────────────────┐   ▓ │
│ ▓  │                             │   ▓ │
│ ▓  │      SAFE ZONE              │   ▓ │  ← Your content is
│ ▓  │  (Visible to users)         │   ▓ │     safe here
│ ▓  │                             │   ▓ │
│ ▓  └─────────────────────────────┘   ▓ │
│ ▓                                     ▓ │
│ ▓▓▓▓▓▓▓▓▓ DANGER ZONE (Bottom) ▓▓▓▓▓▓▓▓▓ │
└─────────────────────────────────────────┘
```

**Risk Levels:**
- ✅ **Safe**: No important content in danger zones
- ⚠️ **Warning**: Moderate contrast/brightness detected in margins
- ❌ **Danger**: High-contrast or bright content likely to be obscured

## Output Structure

```
output/
├── bilibili/
│   ├── 16x9_my_cover.jpg
│   └── 4x3_my_cover.jpg
├── xiaohongshu/
│   └── 3x4_my_cover.jpg
└── douyin/
    └── 9x16_my_cover.jpg
```

## Platform-Specific Safe Margins

Default margins (configurable in `platforms.json`):

| Platform | Ratio | Top | Bottom | Left | Right |
|----------|-------|-----|--------|------|-------|
| **Bilibili** (16:9) | 16:9 | 8% | 12% | 5% | 5% |
| **Bilibili** (4:3) | 4:3 | 8% | 10% | 5% | 5% |
| **Xiaohongshu** | 3:4 | 10% | 15% | 8% | 8% |
| **Douyin** | 9:16 | 12% | 20% | 6% | 6% |

These margins represent areas where platform UI (titles, buttons, creator info, etc.) may cover your image.

## Customization

Edit `platforms.json` to adjust ratios and safe margins for your needs:

```json
{
  "bilibili_16x9": {
    "ratio": [16, 9],
    "safe_margins": {
      "top": 0.08,
      "bottom": 0.12,
      "left": 0.05,
      "right": 0.05
    }
  }
}
```

## Smart Cropping Behavior

The tool intelligently handles different source image aspect ratios:

1. **Source wider than target**: Crops width, centers horizontally
2. **Source taller than target**: Crops height, centers vertically
3. **Expansion needed** (with `--no-expand` off): Creates blurred background and composites original image scaled down

## Examples

### Basic Export
```bash
python cover_tool.py my_video_cover.png
```

Output:
```
╭────────────────── Cover Image Export Results ──────────────────╮
│ Platform   │ Ratio │ Status     │ Margins at Risk │ Output File │
├────────────┼───────┼────────────┼─────────────────┼─────────────┤
│ Bilibili   │ 16:9  │ ✅ Safe    │ None            │ 16x9_my...  │
│ Bilibili   │ 4:3   │ ⚠️ Warning │ top             │ 4x3_my...   │
│ Xiaohongshu│ 3:4   │ ✅ Safe    │ None            │ 3x4_my...   │
│ Douyin     │ 9:16  │ ❌ Danger  │ bottom          │ 9x16_my...  │
╰─────────────────────────────────────────────────────────────────╯

✨ Exported 4 images to 'output/' directory
```

### Platform-Specific Export
```bash
python cover_tool.py cover.jpg --platforms bilibili --output bilibili_exports
```

Only exports Bilibili ratios (16:9 and 4:3) to `bilibili_exports/` directory.

### JSON Output for Automation
```bash
python cover_tool.py cover.jpg --json > results.json
```

Perfect for CI/CD pipelines or batch processing.

## Tips for Best Results

1. **Start with high resolution**: Use at least 1920px on the shortest dimension
2. **Keep key content centered**: Important elements (faces, text) should be in the center third
3. **Avoid edge details**: Don't place critical info within 15% of any edge
4. **Test with the tool**: Run exports early in your design process to catch issues
5. **Review warnings**: Even ⚠️ warnings can be problematic depending on platform UI updates

## Troubleshooting

**"Cannot open image" error:**
- Ensure file path is correct and file is a valid image format (JPG, PNG)

**Blurry output:**
- Increase source image resolution
- Use `--no-expand` to avoid padding (may crop content)

**Missing rich formatting:**
- Install with `pip install rich` for colored table output
- Or use `--json` for machine-readable output

---

## ClawHunt Problem Details

- **Problem ID**: #124
- **Submitter**: 胡斐 <umbragic@google.com>
- **Bounty**: $150 USD
- **Problem page**: https://clawhunt.store/problems/124

## License

MIT License - Free for personal and commercial use.
