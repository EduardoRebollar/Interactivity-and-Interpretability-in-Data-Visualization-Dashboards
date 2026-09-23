"""WCAG 2.1 contrast math, and colour difference under simulated colour-vision deficiency.

Lives in `src/` rather than `scripts/` so that both the reporting script and the test suite import
the same implementation — the accessibility floor is enforced by tests, not by a script someone
remembers to run.

References: WCAG 2.1, "relative luminance" and "contrast ratio" definitions. Colour-vision
deficiency is simulated with Machado, Oliveira and Fernandes (2009), severity 1.0, on linear RGB.
Colour difference is CIEDE2000 (Sharma, Wu and Dalal, 2005) in CIELAB under D65.
"""

from __future__ import annotations

import math
from itertools import combinations

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


# --- Colour-vision deficiency ---------------------------------------------------------------------
#
# WCAG contrast says a colour stands out from the background. It says nothing about whether two
# series colours can be told apart, and the palette's first defect was exactly that: Okabe-Ito
# orange, darkened to pass contrast, came within 1.1 dE of vermillion under protanopia. These
# functions measure it, so tests/test_palette.py can hold a floor.

# Machado et al. (2009), severity 1.0: dichromacy, the most severe form of each. Applied to LINEAR
# RGB. Normal vision is the identity.
CVD_MATRICES: dict[str, tuple[tuple[float, float, float], ...] | None] = {
    "normal": None,
    "protan": (
        (0.152286, 1.052583, -0.204868),
        (0.114503, 0.786281, 0.099216),
        (-0.003882, -0.048116, 1.051998),
    ),
    "deutan": (
        (0.367322, 0.860646, -0.227968),
        (0.280085, 0.672501, 0.047413),
        (-0.011820, 0.042940, 0.968881),
    ),
    "tritan": (
        (1.255528, -0.076749, -0.178779),
        (-0.078411, 0.930809, 0.147602),
        (0.004733, 0.691367, 0.303900),
    ),
}
# The palette is held apart under these: red-green deficiency affects about 1 in 12 men, and these
# are its most severe forms. Tritanopia, about 1 in 10,000 people, is reported, not held to it.
PRIMARY_VISION = ("normal", "deutan", "protan")


def _linear(color: str) -> tuple[float, float, float]:
    channels = []
    for component in hex_to_rgb(color):
        srgb = component / 255
        channels.append(srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4)
    return channels[0], channels[1], channels[2]


def simulate(color: str, vision: str) -> tuple[float, float, float]:
    """Linear RGB of `color` as seen with `vision` ("normal", "protan", "deutan" or "tritan")."""
    rgb = _linear(color)
    matrix = CVD_MATRICES[vision]
    if matrix is None:
        return rgb
    red, green, blue = (
        min(1.0, max(0.0, row[0] * rgb[0] + row[1] * rgb[1] + row[2] * rgb[2])) for row in matrix
    )
    return red, green, blue


def to_lab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    """CIELAB (D65) of a linear RGB triple."""
    red, green, blue = rgb
    x = (0.4124564 * red + 0.3575761 * green + 0.1804375 * blue) / 0.95047
    y = 0.2126729 * red + 0.7151522 * green + 0.0721750 * blue
    z = (0.0193339 * red + 0.1191920 * green + 0.9503041 * blue) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e2000(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    """CIEDE2000 colour difference between two CIELAB colours (Sharma, Wu and Dalal, 2005)."""
    l1, a1, b1 = first
    l2, a2, b2 = second
    c_bar = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2
    g = 0.5 * (1 - math.sqrt(c_bar**7 / (c_bar**7 + 25**7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360

    delta_l, delta_c = l2 - l1, c2p - c1p
    if c1p * c2p == 0:
        delta_h = 0.0
    elif abs(h2p - h1p) <= 180:
        delta_h = h2p - h1p
    elif h2p - h1p > 180:
        delta_h = h2p - h1p - 360
    else:
        delta_h = h2p - h1p + 360
    delta_big_h = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(delta_h / 2))

    l_bar, c_bar_p = (l1 + l2) / 2, (c1p + c2p) / 2
    if c1p * c2p == 0:
        h_bar = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        h_bar = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        h_bar = (h1p + h2p + 360) / 2
    else:
        h_bar = (h1p + h2p - 360) / 2
    t = (
        1
        - 0.17 * math.cos(math.radians(h_bar - 30))
        + 0.24 * math.cos(math.radians(2 * h_bar))
        + 0.32 * math.cos(math.radians(3 * h_bar + 6))
        - 0.20 * math.cos(math.radians(4 * h_bar - 63))
    )
    delta_theta = 30 * math.exp(-(((h_bar - 275) / 25) ** 2))
    r_c = 2 * math.sqrt(c_bar_p**7 / (c_bar_p**7 + 25**7))
    s_l = 1 + 0.015 * (l_bar - 50) ** 2 / math.sqrt(20 + (l_bar - 50) ** 2)
    s_c = 1 + 0.045 * c_bar_p
    s_h = 1 + 0.015 * c_bar_p * t
    r_t = -math.sin(math.radians(2 * delta_theta)) * r_c
    return math.sqrt(
        (delta_l / s_l) ** 2
        + (delta_c / s_c) ** 2
        + (delta_big_h / s_h) ** 2
        + r_t * (delta_c / s_c) * (delta_big_h / s_h)
    )


def cvd_distance(first: str, second: str, visions: tuple[str, ...] = PRIMARY_VISION) -> float:
    """The smallest CIEDE2000 difference between two colours across `visions`."""
    return min(
        delta_e2000(to_lab(simulate(first, vision)), to_lab(simulate(second, vision)))
        for vision in visions
    )


def weakest_pair(
    colors: list[str], visions: tuple[str, ...] = PRIMARY_VISION
) -> tuple[float, str, str]:
    """The least separable pair in `colors`: (distance, first, second)."""
    return min((cvd_distance(a, b, visions), a, b) for a, b in combinations(colors, 2))
