from typing import TYPE_CHECKING, Final

import matplotlib.colors as mcolors

if TYPE_CHECKING:
    from parser import Fly_In_Config

RAINBOW_COLORS: Final[list[str]] = [
    "red",
    "orange",
    "yellow",
    "green",
    "blue",
    "indigo",
    "violet",
]


RESET_COLOR: Final[str] = "\x1b[0m"


class Painting:
    def __init__(self, config: "Fly_In_Config") -> None:
        self.config = config
        self.hubs = config.hubs

    @staticmethod
    def _paint(color_name: str) -> str:
        rgb = mcolors.to_rgb(color_name)

        r, g, b = (int(channel * 255) for channel in rgb)

        return f"\x1b[38;2;{r};{g};{b}m"

    def __call__(self, hub_name: str) -> str:
        color_name = self.hubs[hub_name].metadata.color

        if color_name is None:
            return hub_name

        if color_name != "rainbow":
            color = self._paint(color_name)
            return f"{color}{hub_name}{RESET_COLOR}"

        painted_chars: list[str] = []

        for index, char in enumerate(hub_name):
            rainbow_color = RAINBOW_COLORS[index % len(RAINBOW_COLORS)]

            painted_chars.append(
                f"{self._paint(rainbow_color)}{char}{RESET_COLOR}"
            )

        return "".join(painted_chars)

    @staticmethod
    def validate_color(color_name: str) -> bool:
        return (
            color_name == "rainbow"
            or color_name in mcolors.get_named_colors_mapping()
        )
