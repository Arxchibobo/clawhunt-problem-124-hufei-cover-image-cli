#!/usr/bin/env python3
"""
Cover Image Multi-Ratio Export Tool
Exports cover images to multiple platform-specific ratios with safe-zone detection
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any

from PIL import Image, ImageFilter, ImageDraw, ImageFont

try:
    from rich.console import Console
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class SafeZoneAnalyzer:
    """Analyzes image content for safe-zone violations"""

    def __init__(self, image: Image.Image):
        self.image = image
        self.width, self.height = image.size
        # Convert to grayscale for brightness analysis
        self.gray = image.convert('L')

    def get_region_stats(self, box: Tuple[int, int, int, int]) -> Dict[str, float]:
        """Calculate brightness and contrast stats for a region"""
        region = self.gray.crop(box)
        pixels = list(region.getdata())

        if not pixels:
            return {'mean': 0, 'std': 0, 'max': 0}

        mean = sum(pixels) / len(pixels)
        variance = sum((p - mean) ** 2 for p in pixels) / len(pixels)
        std = variance ** 0.5

        return {
            'mean': mean,
            'std': std,
            'max': max(pixels)
        }

    def analyze_margins(self, margins: Dict[str, float]) -> Dict[str, str]:
        """Analyze each margin region for content risk"""
        w, h = self.width, self.height

        # Define margin boxes
        top_box = (0, 0, w, int(h * margins['top']))
        bottom_box = (0, int(h * (1 - margins['bottom'])), w, h)
        left_box = (0, 0, int(w * margins['left']), h)
        right_box = (int(w * (1 - margins['right'])), 0, w, h)

        # Get center reference (safe zone)
        center_x = int(w * (margins['left'] + (1 - margins['left'] - margins['right']) / 2))
        center_y = int(h * (margins['top'] + (1 - margins['top'] - margins['bottom']) / 2))
        center_size = min(w // 4, h // 4)
        center_box = (
            center_x - center_size // 2,
            center_y - center_size // 2,
            center_x + center_size // 2,
            center_y + center_size // 2
        )

        center_stats = self.get_region_stats(center_box)

        # Analyze each margin
        results = {}
        margin_boxes = {
            'top': top_box,
            'bottom': bottom_box,
            'left': left_box,
            'right': right_box
        }

        for name, box in margin_boxes.items():
            stats = self.get_region_stats(box)
            risk = self._assess_risk(stats, center_stats)
            results[name] = risk

        return results

    def _assess_risk(self, margin_stats: Dict[str, float], center_stats: Dict[str, float]) -> str:
        """Assess risk level based on margin content"""
        # High contrast in margin = potential important content
        if margin_stats['std'] > 60:  # High variance = high contrast
            if margin_stats['mean'] > 180 or margin_stats['max'] > 240:  # Bright content
                return 'danger'
            return 'warning'

        # Check if margin has significantly different brightness than center
        if abs(margin_stats['mean'] - center_stats['mean']) > 80:
            return 'warning'

        return 'safe'

    def get_overall_risk(self, margin_results: Dict[str, str]) -> str:
        """Get overall risk level for the image"""
        if 'danger' in margin_results.values():
            return 'danger'
        if 'warning' in margin_results.values():
            return 'warning'
        return 'safe'


class CoverImageProcessor:
    """Processes cover images for multiple platform ratios"""

    def __init__(self, config_path: str = 'platforms.json'):
        self.config = self._load_config(config_path)

    def _load_config(self, path: str) -> Dict[str, Any]:
        """Load platform configuration"""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: Config file '{path}' not found")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in config file: {e}")
            sys.exit(1)

    def calculate_crop_box(self, img_width: int, img_height: int,
                          target_ratio: Tuple[int, int]) -> Tuple[int, int, int, int]:
        """Calculate optimal crop box to maintain aspect ratio"""
        img_ratio = img_width / img_height
        target_ratio_value = target_ratio[0] / target_ratio[1]

        if img_ratio > target_ratio_value:
            # Image is wider, crop width
            new_width = int(img_height * target_ratio_value)
            new_height = img_height
            left = (img_width - new_width) // 2
            top = 0
        else:
            # Image is taller, crop height
            new_width = img_width
            new_height = int(img_width / target_ratio_value)
            left = 0
            top = (img_height - new_height) // 2

        return (left, top, left + new_width, top + new_height)

    def create_blurred_background(self, image: Image.Image,
                                 target_size: Tuple[int, int]) -> Image.Image:
        """Create blurred and darkened background for padding"""
        # Resize image to target size (will be stretched)
        bg = image.copy()
        bg = bg.resize(target_size, Image.Resampling.LANCZOS)

        # Apply strong blur
        bg = bg.filter(ImageFilter.GaussianBlur(radius=20))

        # Darken
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Brightness(bg)
        bg = enhancer.enhance(0.4)

        return bg

    def smart_crop_with_padding(self, image: Image.Image,
                               target_ratio: Tuple[int, int],
                               allow_expand: bool = True) -> Image.Image:
        """Smart crop with optional padding"""
        img_width, img_height = image.size
        img_ratio = img_width / img_height
        target_ratio_value = target_ratio[0] / target_ratio[1]

        # Calculate target dimensions maintaining aspect ratio
        if img_ratio > target_ratio_value:
            # Image is wider than target
            crop_width = int(img_height * target_ratio_value)
            crop_height = img_height
        else:
            # Image is taller than target
            crop_width = img_width
            crop_height = int(img_width / target_ratio_value)

        # Check if we need to expand
        if allow_expand and (crop_width > img_width or crop_height > img_height):
            # Need to expand - use padded approach
            target_width = max(crop_width, 1920)  # Reasonable default
            target_height = int(target_width / target_ratio_value)

            # Create blurred background
            bg = self.create_blurred_background(image, (target_width, target_height))

            # Calculate scaling to fit original image
            scale = min(target_width / img_width, target_height / img_height) * 0.9
            scaled_width = int(img_width * scale)
            scaled_height = int(img_height * scale)

            # Resize original image
            resized = image.resize((scaled_width, scaled_height), Image.Resampling.LANCZOS)

            # Paste on center
            x = (target_width - scaled_width) // 2
            y = (target_height - scaled_height) // 2
            bg.paste(resized, (x, y))

            return bg
        else:
            # Standard center crop
            crop_box = self.calculate_crop_box(img_width, img_height, target_ratio)
            return image.crop(crop_box)

    def process_image(self, input_path: str, output_dir: str,
                     platforms: List[str], allow_expand: bool,
                     target_size: int = 1920) -> Dict[str, Any]:
        """Process image for all specified platforms"""
        # Load image
        try:
            image = Image.open(input_path).convert('RGB')
        except Exception as e:
            print(f"Error: Cannot open image '{input_path}': {e}")
            sys.exit(1)

        input_filename = Path(input_path).stem
        results = {}

        # Process each platform configuration
        for config_name, config_data in self.config.items():
            # Extract platform name from config
            platform = config_name.split('_')[0]

            # Skip if platform not requested
            if platforms and platform not in platforms:
                continue

            ratio = tuple(config_data['ratio'])
            margins = config_data['safe_margins']

            # Process image
            processed = self.smart_crop_with_padding(image, ratio, allow_expand)

            # Resize to target size
            ratio_value = ratio[0] / ratio[1]
            final_width = target_size
            final_height = int(target_size / ratio_value)
            processed = processed.resize((final_width, final_height), Image.Resampling.LANCZOS)

            # Analyze safe zones
            analyzer = SafeZoneAnalyzer(processed)
            margin_risks = analyzer.analyze_margins(margins)
            overall_risk = analyzer.get_overall_risk(margin_risks)

            # Save output
            platform_dir = Path(output_dir) / platform
            platform_dir.mkdir(parents=True, exist_ok=True)

            ratio_str = f"{ratio[0]}x{ratio[1]}"
            output_filename = f"{ratio_str}_{input_filename}.jpg"
            output_path = platform_dir / output_filename

            processed.save(output_path, 'JPEG', quality=95)

            results[config_name] = {
                'path': str(output_path),
                'ratio': ratio,
                'risk': overall_risk,
                'margin_risks': margin_risks,
                'platform': platform
            }

        return results


def print_results_table(results: Dict[str, Any], use_rich: bool = True):
    """Print results in a formatted table"""
    risk_symbols = {
        'safe': '✅',
        'warning': '⚠️',
        'danger': '❌'
    }

    if use_rich and RICH_AVAILABLE:
        console = Console()
        table = Table(title="Cover Image Export Results", show_header=True, header_style="bold magenta")

        table.add_column("Platform", style="cyan", width=15)
        table.add_column("Ratio", style="yellow", width=10)
        table.add_column("Status", width=8)
        table.add_column("Margins at Risk", width=25)
        table.add_column("Output File", style="green")

        for config_name, data in results.items():
            platform = data['platform'].capitalize()
            ratio = f"{data['ratio'][0]}:{data['ratio'][1]}"
            risk = data['risk']
            symbol = risk_symbols[risk]

            # Find risky margins
            risky_margins = [k for k, v in data['margin_risks'].items()
                           if v in ['warning', 'danger']]
            margins_text = ', '.join(risky_margins) if risky_margins else 'None'

            filename = Path(data['path']).name

            # Color code the status
            if risk == 'safe':
                status_text = f"[green]{symbol} Safe[/green]"
            elif risk == 'warning':
                status_text = f"[yellow]{symbol} Warning[/yellow]"
            else:
                status_text = f"[red]{symbol} Danger[/red]"

            table.add_row(platform, ratio, status_text, margins_text, filename)

        console.print(table)
    else:
        # Plain text fallback
        print("\n" + "="*80)
        print("COVER IMAGE EXPORT RESULTS")
        print("="*80)
        print(f"{'Platform':<15} {'Ratio':<10} {'Status':<10} {'Margins at Risk':<25} {'File'}")
        print("-"*80)

        for config_name, data in results.items():
            platform = data['platform'].capitalize()
            ratio = f"{data['ratio'][0]}:{data['ratio'][1]}"
            risk = data['risk']
            symbol = risk_symbols[risk]

            risky_margins = [k for k, v in data['margin_risks'].items()
                           if v in ['warning', 'danger']]
            margins_text = ', '.join(risky_margins) if risky_margins else 'None'

            filename = Path(data['path']).name

            print(f"{platform:<15} {ratio:<10} {symbol} {risk:<8} {margins_text:<25} {filename}")

        print("="*80 + "\n")


def create_test_image(output_path: str):
    """Create a test image with gradients and text-like elements"""
    width, height = 1920, 1080
    image = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(image)

    # Create gradient background
    for y in range(height):
        ratio = y / height
        r = int(100 + 155 * ratio)
        g = int(150 - 50 * ratio)
        b = int(200 - 100 * ratio)
        draw.rectangle([(0, y), (width, y+1)], fill=(r, g, b))

    # Add "text-like" rectangles to simulate content
    # Center content (safe)
    center_x, center_y = width // 2, height // 2
    draw.rectangle([center_x - 300, center_y - 100, center_x + 300, center_y + 100],
                   fill=(255, 255, 255), outline=(0, 0, 0), width=3)

    # Add some content near edges (to trigger warnings)
    # Top edge
    draw.rectangle([width // 2 - 200, 50, width // 2 + 200, 120],
                   fill=(255, 220, 100), outline=(0, 0, 0), width=2)

    # Bottom edge
    draw.rectangle([width // 2 - 250, height - 120, width // 2 + 250, height - 50],
                   fill=(100, 220, 255), outline=(0, 0, 0), width=2)

    # Left edge
    draw.rectangle([50, height // 2 - 150, 180, height // 2 + 150],
                   fill=(255, 150, 150), outline=(0, 0, 0), width=2)

    # Right edge
    draw.rectangle([width - 180, height // 2 - 150, width - 50, height // 2 + 150],
                   fill=(150, 255, 150), outline=(0, 0, 0), width=2)

    image.save(output_path, 'JPEG', quality=95)
    print(f"Test image created: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Export cover images to multiple platform-specific ratios with safe-zone detection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.jpg
  %(prog)s input.jpg --output exports --platforms bilibili xiaohongshu
  %(prog)s input.jpg --no-expand --json
        """
    )

    parser.add_argument('input_image', nargs='?', help='Input cover image (jpg/png)')
    parser.add_argument('--output', '-o', default='output',
                       help='Output directory (default: output)')
    parser.add_argument('--platforms', '-p', nargs='+',
                       choices=['bilibili', 'xiaohongshu', 'douyin'],
                       help='Specific platforms to export (default: all)')
    parser.add_argument('--no-expand', action='store_true',
                       help='Disable auto-padding with blurred edges')
    parser.add_argument('--json', action='store_true',
                       help='Output results as JSON')
    parser.add_argument('--create-test', action='store_true',
                       help='Create a test image and exit')

    args = parser.parse_args()

    # Handle test image creation
    if args.create_test:
        create_test_image('test_input.jpg')
        return

    # Check if input was provided
    if not args.input_image:
        parser.error('input_image is required unless --create-test is used')

    # Check if input exists
    if not os.path.exists(args.input_image):
        print(f"Error: Input image '{args.input_image}' not found")
        sys.exit(1)

    # Process image
    processor = CoverImageProcessor()
    results = processor.process_image(
        args.input_image,
        args.output,
        args.platforms,
        not args.no_expand
    )

    # Output results
    if args.json:
        import json
        print(json.dumps(results, indent=2))
    else:
        print_results_table(results, use_rich=RICH_AVAILABLE and not args.json)
        print(f"\n✨ Exported {len(results)} images to '{args.output}/' directory")


if __name__ == '__main__':
    main()
