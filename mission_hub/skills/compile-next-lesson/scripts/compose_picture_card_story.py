#!/usr/bin/env python3
"""Compose a continuity-safe picture-card story from immutable reviewed card images."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from PIL import Image, ImageDraw


CANVAS = (1536, 1024)
CARD = (150, 200)
X0 = 63
X_STEP = 180
TOP_Y = 70
ACTIVE_Y = 412
BOTTOM_Y = 754


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dashed_round_rectangle(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    color: tuple[int, int, int],
) -> None:
    x0, y0, x1, y1 = box
    dash = 12
    gap = 8
    for x in range(x0 + 18, x1 - 18, dash + gap):
        draw.line((x, y0, min(x + dash, x1 - 18), y0), fill=color, width=3)
        draw.line((x, y1, min(x + dash, x1 - 18), y1), fill=color, width=3)
    for y in range(y0 + 18, y1 - 18, dash + gap):
        draw.line((x0, y, x0, min(y + dash, y1 - 18)), fill=color, width=3)
        draw.line((x1, y, x1, min(y + dash, y1 - 18)), fill=color, width=3)
    draw.arc((x0, y0, x0 + 36, y0 + 36), 180, 270, fill=color, width=3)
    draw.arc((x1 - 36, y0, x1, y0 + 36), 270, 360, fill=color, width=3)
    draw.arc((x0, y1 - 36, x0 + 36, y1), 90, 180, fill=color, width=3)
    draw.arc((x1 - 36, y1 - 36, x1, y1), 0, 90, fill=color, width=3)


def prepare_card(path: Path) -> Image.Image:
    source = Image.open(path).convert("RGB")
    source.thumbnail((CARD[0] - 16, CARD[1] - 16), Image.Resampling.LANCZOS)
    card = Image.new("RGB", CARD, (255, 255, 255))
    x = (CARD[0] - source.width) // 2
    y = (CARD[1] - source.height) // 2
    card.paste(source, (x, y))
    return card


def place_card(canvas: Image.Image, card: Image.Image, x: int, y: int, active: bool = False) -> None:
    draw = ImageDraw.Draw(canvas)
    shadow = (x + 5, y + 7, x + CARD[0] + 5, y + CARD[1] + 7)
    draw.rounded_rectangle(shadow, radius=18, fill=(178, 188, 198))
    border = (25, 116, 190) if active else (93, 103, 114)
    width = 7 if active else 3
    draw.rounded_rectangle((x, y, x + CARD[0], y + CARD[1]), radius=18, fill=(255, 255, 255), outline=border, width=width)
    mask = Image.new("L", CARD, 0)
    ImageDraw.Draw(mask).rounded_rectangle((4, 4, CARD[0] - 4, CARD[1] - 4), radius=15, fill=255)
    canvas.paste(card, (x, y), mask)
    ImageDraw.Draw(canvas).rounded_rectangle((x, y, x + CARD[0], y + CARD[1]), radius=18, outline=border, width=width)


def compose(cards: list[Image.Image], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    slot_color = (139, 151, 164)
    for page_index in range(10):
        active_index = page_index - 1 if 1 <= page_index <= 8 else None
        completed_count = 0 if page_index == 0 else min(page_index - 1, 8)
        if page_index == 9:
            completed_count = 8
        canvas = Image.new("RGB", CANVAS, (238, 244, 248))
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle((28, 34, CANVAS[0] - 28, 312), radius=28, fill=(226, 238, 246), outline=(172, 194, 209), width=3)
        draw.rounded_rectangle((28, 712, CANVAS[0] - 28, 990), radius=28, fill=(248, 240, 226), outline=(210, 190, 160), width=3)
        for index in range(8):
            x = X0 + index * X_STEP
            dashed_round_rectangle(draw, (x, TOP_Y, x + CARD[0], TOP_Y + CARD[1]), color=slot_color)
            dashed_round_rectangle(draw, (x, BOTTOM_Y, x + CARD[0], BOTTOM_Y + CARD[1]), color=slot_color)
        if active_index is not None:
            center_x = X0 + active_index * X_STEP + CARD[0] // 2
            draw.line((center_x, BOTTOM_Y - 8, center_x, TOP_Y + CARD[1] + 8), fill=(79, 147, 191), width=12)
            draw.ellipse((center_x - 14, TOP_Y + CARD[1] - 6, center_x + 14, TOP_Y + CARD[1] + 22), fill=(79, 147, 191))
        for index, card in enumerate(cards):
            x = X0 + index * X_STEP
            if active_index == index:
                y = ACTIVE_Y
                place_card(canvas, card, x, y, active=True)
            elif index < completed_count or page_index == 9:
                place_card(canvas, card, x, TOP_Y)
            else:
                place_card(canvas, card, x, BOTTOM_Y)
        output = output_dir / f"page-{page_index + 1:02d}.png"
        canvas.save(output, format="PNG", optimize=False)
        print(f"{output}\t{digest(output)}")


def draw_helper(draw: ImageDraw.ImageDraw, *, celebrating: bool = False) -> None:
    """Draw one stable waist-up helper; no identity or language is scored."""
    skin = (191, 132, 96)
    shirt = (72, 112, 154)
    hair = (69, 48, 39)
    draw.ellipse((1170, 135, 1370, 335), fill=skin, outline=(72, 62, 57), width=4)
    draw.pieslice((1155, 105, 1385, 300), 180, 360, fill=hair)
    draw.ellipse((1217, 218, 1231, 232), fill=(35, 35, 35))
    draw.ellipse((1309, 218, 1323, 232), fill=(35, 35, 35))
    draw.arc((1242, 244, 1298, 280), 10, 170, fill=(95, 49, 45), width=4)
    draw.rounded_rectangle((1115, 325, 1425, 760), radius=70, fill=shirt, outline=(45, 70, 98), width=5)
    if celebrating:
        draw.line((1150, 430, 1045, 300), fill=skin, width=34)
        draw.ellipse((1022, 266, 1067, 314), fill=skin)
        draw.line((1388, 430, 1470, 285), fill=skin, width=34)
        draw.ellipse((1447, 250, 1492, 300), fill=skin)
        # A simple raised thumb makes the resolved state visibly positive.
        draw.rounded_rectangle((1460, 215, 1488, 270), radius=12, fill=skin)
    else:
        draw.line((1145, 445, 1028, 530), fill=skin, width=34)
        draw.ellipse((1004, 507, 1050, 553), fill=skin)


def compose_sorting_story(cards: list[Image.Image], output_dir: Path) -> None:
    """Compose a visible agent-goal-development-resolution card-sorting story."""
    output_dir.mkdir(parents=True, exist_ok=True)
    board_slots = [
        (92 + (index % 4) * 218, 92 + (index // 4) * 220)
        for index in range(8)
    ]
    source_slots = [
        (75, 705), (260, 760), (450, 690), (635, 770),
        (825, 700), (185, 555), (545, 565), (850, 545),
    ]
    card_size = CARD
    for page_index in range(10):
        active_index = page_index - 1 if 1 <= page_index <= 8 else None
        completed_count = 0 if page_index == 0 else min(page_index - 1, 8)
        if page_index == 9:
            completed_count = 8
        canvas = Image.new("RGB", CANVAS, (245, 239, 226))
        draw = ImageDraw.Draw(canvas)
        # Ordered display board is the stable visible goal.
        draw.rounded_rectangle((42, 42, 990, 520), radius=32, fill=(222, 236, 226), outline=(74, 111, 83), width=7)
        for x, y in board_slots:
            dashed_round_rectangle(draw, (x, y, x + card_size[0], y + card_size[1]), color=(112, 142, 119))
        # The messy source surface supplies the initial problem.
        draw.rounded_rectangle((28, 610, 1010, 990), radius=35, fill=(190, 142, 94), outline=(112, 76, 46), width=7)
        draw.line((28, 650, 1010, 650), fill=(230, 192, 145), width=8)
        draw_helper(draw, celebrating=page_index == 9)
        # Goal cue: a nonlinguistic arrow from the messy table to the orderly board.
        if page_index == 0:
            draw.line((1020, 720, 1015, 495), fill=(64, 126, 82), width=16)
            draw.polygon([(1015, 455), (985, 510), (1045, 510)], fill=(64, 126, 82))
        for index, card in enumerate(cards):
            if active_index == index:
                x, y = 1015, 390
                place_card(canvas, card, x, y, active=True)
            elif index < completed_count or page_index == 9:
                x, y = board_slots[index]
                place_card(canvas, card, x, y)
            else:
                x, y = source_slots[index]
                # Small fixed rotations make the source visibly disordered while identity stays intact.
                angle = (-8, 6, -5, 9, -7, 5, -9, 7)[index]
                rotated = card.rotate(angle, expand=True, fillcolor=(255, 255, 255))
                canvas.paste(rotated, (x, y))
                ImageDraw.Draw(canvas).rounded_rectangle((x, y, x + rotated.width, y + rotated.height), radius=12, outline=(93, 103, 114), width=3)
        if page_index == 9:
            for x, y in ((1060, 80), (1430, 110), (1080, 300), (1440, 380)):
                draw.regular_polygon((x, y, 18), n_sides=5, rotation=-18, fill=(235, 178, 45))
        output = output_dir / f"page-{page_index + 1:02d}.png"
        canvas.save(output, format="PNG", optimize=False)
        print(f"{output}\t{digest(output)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--card", action="append", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("slots", "sorting"), default="slots")
    args = parser.parse_args()
    if len(args.card) != 8:
        raise SystemExit("exactly eight --card arguments are required in story order")
    missing = [path for path in args.card if not path.is_file()]
    if missing:
        raise SystemExit(f"missing card files: {missing}")
    cards = [prepare_card(path) for path in args.card]
    if args.mode == "sorting":
        compose_sorting_story(cards, args.output_dir)
    else:
        compose(cards, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
