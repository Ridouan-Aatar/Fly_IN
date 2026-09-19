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
    """Handles colored terminal output for hub names during simulation.

    Uses matplotlib's named color database to convert color names into
    ANSI escape codes for terminal rendering. Supports a special "rainbow"
    mode that cycles each character of the hub name through rainbow colors.

    Attributes:
        config: The parsed map configuration.
        hubs: Dict mapping hub names to Config_Hub objects.
    """

    def __init__(self, config: "Fly_In_Config") -> None:
        """Initialises the Painting instance with the parsed config.

        Args:
            config: A fully parsed Fly_In_Config instance.
        """

        self.config = config
        self.hubs = config.hubs

    @staticmethod
    def _paint(color_name: str) -> str:
        """Converts a named color to an ANSI 24-bit foreground escape code.

        Args:
            color_name: A matplotlib-recognised color name (e.g. "red", "blue")

        Returns:
            ANSI escape string that sets the terminal foreground to that color.
        """
        rgb = mcolors.to_rgb(color_name)

        r, g, b = (int(channel * 255) for channel in rgb)

        return f"\x1b[38;2;{r};{g};{b}m"

    def __call__(self, hub_name: str) -> str:
        """Returns the hub name wrapped in its assigned terminal color.

        If the hub has no color set, the name is returned as-is.
        If the color is "rainbow", each character is painted a different
        color cycling through the RAINBOW_COLORS list.
        Otherwise, the entire name is painted in the hub's color.

        Args:
            hub_name: The name of the hub to colorize.

        Returns:
            The hub name as a terminal-colored string, or plain if no color.
        """
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
        """Checks whether a color name (after lowercase) is valid for use
            in the simulation.

        Accepts "rainbow" as a special case, plus any color name recognised
        by matplotlib's named color database.

        Args:
            color_name: The color string to validate.

        Returns:
            True if the color is valid, False otherwise.
        """
        color_name = color_name.lower()
        return (
            color_name == "rainbow"
            or color_name in mcolors.get_named_colors_mapping()
        )
