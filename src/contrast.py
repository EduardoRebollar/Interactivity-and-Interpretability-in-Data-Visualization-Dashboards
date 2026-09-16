"""WCAG 2.1 contrast math.

Lives in `src/` rather than `scripts/` so that both the reporting script and the test suite import
the same implementation — the accessibility floor is enforced by tests, not by a script someone
remembers to run.

Reference: WCAG 2.1, "relative luminance" and "contrast ratio" definitions.
"""

from __future__ import annotations

# WCAG 2.1 AA floors.
TEXT_MIN = 4.5  # normal-size text
GRAPHIC_MIN = 3.0  # graphical objects and UI components


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    """Parse "#RRGGBB" (or "RRGGBB") into 0-255 components."""
    value = color.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Expected a 6-digit hex color, got {color!r}")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def relative_luminance(color: str) -> float:
    """WCAG relative luminance, 0.0 (black) to 1.0 (white)."""
    channels = []
    for component in hex_to_rgb(color):
        srgb = component / 255
        channels.append(srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: str, background: str) -> float:
    """Contrast ratio between two colors, from 1.0 (identical) to 21.0 (black on white)."""
    a = relative_luminance(foreground)
    b = relative_luminance(background)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def passes(foreground: str, background: str, minimum: float = GRAPHIC_MIN) -> bool:
    return contrast_ratio(foreground, background) >= minimum


def darken_to_ratio(color: str, background: str, target: float = GRAPHIC_MIN) -> str:
    """Scale a color toward black until it meets `target` against `background`.

    Multiplying all three channels by the same factor holds the hue roughly constant while dropping
    luminance, so a palette keeps its hue separation after correction. Returns the original color
    unchanged if it already passes.
    """
    if passes(color, background, target):
        return color

    red, green, blue = hex_to_rgb(color)
    # 256 steps is finer than 8-bit color can express, so this finds the lightest passing shade.
    for step in range(256):
        factor = 1 - step / 255
        scaled = (round(red * factor), round(green * factor), round(blue * factor))
        candidate = "#{:02X}{:02X}{:02X}".format(*scaled)
        if passes(candidate, background, target):
            return candidate
    return "#000000"
