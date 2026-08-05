"""Deterministic color-object counting and controlled-scene comparison."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from math import hypot
from typing import Sequence


@dataclass(frozen=True)
class Component:
    area: int
    x_min: int
    y_min: int
    x_max: int
    y_max: int

    @property
    def width(self) -> int:
        return self.x_max - self.x_min + 1

    @property
    def height(self) -> int:
        return self.y_max - self.y_min + 1

    def to_dict(self) -> dict[str, int]:
        return asdict(self) | {"width": self.width, "height": self.height}


@dataclass(frozen=True)
class Peak:
    x: int
    y: int
    radius: float

    def to_dict(self) -> dict[str, float | int]:
        return {"x": self.x, "y": self.y, "radius": self.radius}


def connected_components(
    mask: Sequence[bool], width: int, height: int, *, minimum_area: int = 1
) -> list[Component]:
    """Return four-connected foreground components in deterministic reading order."""
    if width <= 0 or height <= 0 or len(mask) != width * height:
        raise ValueError("mask dimensions are inconsistent")
    if minimum_area <= 0:
        raise ValueError("minimum_area must be positive")
    visited = bytearray(width * height)
    components = []
    for start, foreground in enumerate(mask):
        if not foreground or visited[start]:
            continue
        queue = deque([start])
        visited[start] = 1
        area = 0
        x_min = x_max = start % width
        y_min = y_max = start // width
        while queue:
            index = queue.popleft()
            x, y = index % width, index // width
            area += 1
            x_min, x_max = min(x_min, x), max(x_max, x)
            y_min, y_max = min(y_min, y), max(y_max, y)
            if x and mask[index - 1] and not visited[index - 1]:
                visited[index - 1] = 1
                queue.append(index - 1)
            if x + 1 < width and mask[index + 1] and not visited[index + 1]:
                visited[index + 1] = 1
                queue.append(index + 1)
            if y and mask[index - width] and not visited[index - width]:
                visited[index - width] = 1
                queue.append(index - width)
            if y + 1 < height and mask[index + width] and not visited[index + width]:
                visited[index + width] = 1
                queue.append(index + width)
        if area >= minimum_area:
            components.append(Component(area, x_min, y_min, x_max, y_max))
    return sorted(components, key=lambda item: (item.y_min, item.x_min))


def red_mask(
    image,
    *,
    hue_edge: int = 14,
    minimum_saturation: int = 145,
    minimum_value: int = 80,
) -> list[bool]:
    """Select strongly red pixels using Pillow's 0..255 HSV representation."""
    hsv = image.convert("RGB").convert("HSV")
    return [
        (hue <= hue_edge or hue >= 256 - hue_edge)
        and saturation >= minimum_saturation
        and value >= minimum_value
        for hue, saturation, value in hsv.getdata()
    ]


def count_red_objects(
    image,
    *,
    minimum_area: int = 180,
    minimum_width: int = 8,
    minimum_height: int = 8,
) -> tuple[int, list[Component], list[Peak], list[bool]]:
    """Count red round objects, separating touching regions by distance peaks."""
    width, height = image.size
    mask = red_mask(image)
    components = [
        component
        for component in connected_components(mask, width, height, minimum_area=minimum_area)
        if component.width >= minimum_width and component.height >= minimum_height
    ]
    component_mask = [False] * len(mask)
    for component in components:
        for y in range(component.y_min, component.y_max + 1):
            row = y * width
            for x in range(component.x_min, component.x_max + 1):
                index = row + x
                component_mask[index] = component_mask[index] or mask[index]
    raw_peaks = distance_peaks(component_mask, width, height)
    peaks = []
    for component in components:
        members = [
            peak
            for peak in raw_peaks
            if component.x_min <= peak.x <= component.x_max
            and component.y_min <= peak.y <= component.y_max
            and component_mask[peak.y * width + peak.x]
        ]
        substantial = [peak for peak in members if peak.radius >= 10.0]
        peaks.extend(substantial if substantial else sorted(members, key=lambda peak: -peak.radius)[:1])
    peaks.sort(key=lambda peak: (peak.y, peak.x))
    return len(peaks), components, peaks, mask


def distance_peaks(
    mask: Sequence[bool],
    width: int,
    height: int,
    *,
    minimum_radius: float = 7.0,
    minimum_separation: float = 20.0,
) -> list[Peak]:
    """Find centers of touching round regions with a dependency-free chamfer transform."""
    if width <= 0 or height <= 0 or len(mask) != width * height:
        raise ValueError("mask dimensions are inconsistent")
    infinity = width * height * 4
    distance = [0 if not value else infinity for value in mask]
    for y in range(height):
        for x in range(width):
            index = y * width + x
            if not mask[index]:
                continue
            best = distance[index]
            if x == 0 or y == 0 or x + 1 == width or y + 1 == height:
                best = min(best, 3)
            if x:
                best = min(best, distance[index - 1] + 3)
            if y:
                best = min(best, distance[index - width] + 3)
            if x and y:
                best = min(best, distance[index - width - 1] + 4)
            if x + 1 < width and y:
                best = min(best, distance[index - width + 1] + 4)
            distance[index] = best
    for y in range(height - 1, -1, -1):
        for x in range(width - 1, -1, -1):
            index = y * width + x
            if not mask[index]:
                continue
            best = distance[index]
            if x + 1 < width:
                best = min(best, distance[index + 1] + 3)
            if y + 1 < height:
                best = min(best, distance[index + width] + 3)
            if x + 1 < width and y + 1 < height:
                best = min(best, distance[index + width + 1] + 4)
            if x and y + 1 < height:
                best = min(best, distance[index + width - 1] + 4)
            distance[index] = best

    candidates = []
    threshold = round(minimum_radius * 3)
    for y in range(height):
        for x in range(width):
            index = y * width + x
            value = distance[index]
            if value < threshold:
                continue
            neighbors = []
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if not dx and not dy:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        neighbors.append(distance[ny * width + nx])
            if not neighbors or value >= max(neighbors):
                candidates.append((value, x, y))

    selected: list[Peak] = []
    for value, x, y in sorted(candidates, key=lambda item: (-item[0], item[2], item[1])):
        radius = round(value / 3, 3)
        if any(hypot(x - peak.x, y - peak.y) < minimum_separation for peak in selected):
            continue
        selected.append(Peak(x=x, y=y, radius=radius))
    return sorted(selected, key=lambda peak: (peak.y, peak.x))


def scene_difference(reference, candidate, excluded_mask: Sequence[bool]) -> dict[str, float]:
    """Measure RGB change outside a caller-supplied target-object mask."""
    if reference.size != candidate.size:
        raise ValueError("scene comparison requires identical dimensions")
    width, height = reference.size
    if len(excluded_mask) != width * height:
        raise ValueError("excluded mask dimensions are inconsistent")
    reference_pixels = reference.convert("RGB").getdata()
    candidate_pixels = candidate.convert("RGB").getdata()
    total_error = 0
    compared = 0
    materially_changed = 0
    for excluded, left, right in zip(excluded_mask, reference_pixels, candidate_pixels):
        if excluded:
            continue
        error = sum(abs(a - b) for a, b in zip(left, right)) / 3
        total_error += error
        materially_changed += error >= 24
        compared += 1
    if not compared:
        raise ValueError("excluded mask covers the entire image")
    return {
        "mean_absolute_rgb_error": round(total_error / compared, 6),
        "normalized_mean_absolute_error": round(total_error / compared / 255, 6),
        "materially_changed_fraction": round(materially_changed / compared, 6),
        "compared_pixel_fraction": round(compared / (width * height), 6),
    }


def union_masks(*masks: Sequence[bool]) -> list[bool]:
    if not masks or any(len(mask) != len(masks[0]) for mask in masks):
        raise ValueError("masks must be non-empty and equally sized")
    return [any(values) for values in zip(*masks)]
