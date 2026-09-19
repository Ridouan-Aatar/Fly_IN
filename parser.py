from pydantic import (
    BaseModel,
    model_validator,
    ValidationError,
    Field,
    ConfigDict,
    field_validator,
)
from typing import Optional, Literal, Any
from enum import Enum
from painting import Painting


class ParseError(Exception):
    """Custom exception raised when the map file fails validation.

    Attributes:
        line_num: The line number where the error occurred, or -1 if unknown.
    """
    def __init__(self, message: str, line_num: int = -1) -> None:
        self.line_num = line_num
        if line_num >= 0:
            super().__init__(f"Line {line_num}: {message}")
        else:
            super().__init__(message)


class State(Enum):
    """Enum representing the role of a hub in the map.

    Attributes:
        START: The starting hub where all drones begin.
        NORMAL: A regular intermediate hub.
        END: The destination hub all drones must reach.
    """
    START = 0
    NORMAL = 1
    END = 2


ZONE = Literal["normal", "blocked", "restricted", "priority"]


class H_Metadata(BaseModel):
    """Pydantic model for hub metadata parsed from the map file.

    Attributes:
        zone: The zone type of the hub. Defaults to "normal".
        color: Optional display color for visual output.
        max_drones: Maximum number of drones allowed simultaneously.
            Defaults to -1 as a sentinel (resolved during hub validation).
    """
    model_config = ConfigDict(extra="forbid")

    zone: ZONE = Field(default="normal")
    color: Optional[str] = Field(default=None)
    max_drones: int = Field(default=-1, ge=1)

    @field_validator("zone", mode="before")
    @classmethod
    def tolower(cls, value: str) -> str:
        """Normalises the zone value to lowercase before validation.

        Args:
            value: Raw zone string from the map file.

        Returns:
            Lowercased zone string.
        """
        return value.lower()

    @field_validator("color", mode="before")
    @classmethod
    def validate_color(cls, value: str) -> str:
        """Validates and normalises the color value.

        Args:
            value: Raw color string from the map file.

        Returns:
            Lowercased color string.

        Raises:
            ValueError: If the color is not a recognised named color.
        """
        value = value.lower()
        if not Painting.validate_color(value):
            raise ValueError(f"Invalid named color '{value}'")
        return value


class Config_Hub(BaseModel):
    """Pydantic model representing a parsed hub.

    Attributes:
        name: Unique hub name. Dashes are not allowed.
        x: X coordinate of the hub.
        y: Y coordinate of the hub.
        metadata: Associated metadata for the hub.
        state: Role of the hub (START, NORMAL, or END).
    """
    model_config = ConfigDict(extra="forbid")

    name: str
    x: int
    y: int
    metadata: H_Metadata
    state: State

    @model_validator(mode="after")
    def validate_hub_rules(self) -> "Config_Hub":
        """Applies post-construction validation rules to the hub.

        - Disallows dashes in hub names.
        - Disallows blocked zones for start/end hubs.
        - Sets max_drones to 0 for blocked zones.
        - Sets max_drones to 1 for all other zones if not explicitly set.

        Returns:
            The validated Config_Hub instance.

        Raises:
            ValueError: If any rule is violated.
        """
        if "-" in self.name:
            raise ValueError("'-' is not allowed in hub names!!")

        if self.state in (State.START, State.END):
            if self.metadata.zone == "blocked":
                raise ValueError("Start/End Hubs cannot be blocked zones")

        if self.metadata.zone == "blocked":
            self.metadata.max_drones = 0
        else:
            if self.metadata.max_drones == -1:
                self.metadata.max_drones = 1

        return self


class Config_Connection(BaseModel):
    """Pydantic model representing a parsed connection between two hubs.

    Attributes:
        hub1: First hub in the connection.
        hub2: Second hub in the connection.
        max_link_capacity: Maximum number of drones allowed to traverse
            this connection simultaneously. Defaults to 1.
    """
    model_config = ConfigDict(extra="forbid")

    hub1: Config_Hub
    hub2: Config_Hub
    max_link_capacity: int = Field(default=1, ge=1)


class Fly_In_Config:
    """Parses and validates a Fly-in map file.

    Reads the map file line by line, builds hub and connection objects,
    and runs a series of validation checks before the simulation can start.

    Attributes:
        filepath: Path to the map file.
        nb_drones: Number of drones to simulate.
        start_hub: The parsed start hub.
        end_hub: The parsed end hub.
        hubs: Dict mapping hub names to Config_Hub objects.
        connections: List of all parsed Config_Connection objects.
        is_started: True once a start_hub has been parsed.
        is_ended: True once an end_hub has been parsed.
    """
    def __init__(self, filepath: str) -> None:
        """Initialises the config with default empty state.

        Args:
            filepath: Path to the map file to parse.
        """
        self.filepath = filepath

        self.nb_drones: int = -1
        self.start_hub: Optional[Config_Hub] = None
        self.end_hub: Optional[Config_Hub] = None

        self.hubs: dict[str, Config_Hub] = {}

        self.connections: list[Config_Connection] = []

        self.is_started: bool = False
        self.is_ended: bool = False

    def str_startswith(self, line: str, target: str) -> bool:
        """Checks whether the first token of a line matches the target.

        Args:
            line: A stripped line from the map file.
            target: The keyword to match (e.g. "hub:", "connection:").

        Returns:
            True if the first whitespace-delimited token equals target.
        """
        try:
            first, _ = line.split(maxsplit=1)
            return first == target
        except Exception:
            return False

    def process_nbdrones(self, src: str, line_num: int) -> None:
        """Parses and validates the nb_drones line.

        Args:
            src: The full line string.
            line_num: Line number for error reporting.

        Raises:
            ParseError: If nb_drones is already defined, not an integer,
                or not greater than 0.
        """
        if self.nb_drones >= 0:
            raise ParseError("nb_drones already defined", line_num)

        parts = src.split()
        if len(parts) != 2:
            raise ParseError("Invalid nb_drones format", line_num)

        try:
            self.nb_drones = int(parts[1])
        except ValueError:
            raise ParseError("nb_drones must be an integer", line_num)

        if self.nb_drones <= 0:
            raise ParseError("nb_drones must be > 0", line_num)

    def _parse_metadata_str(
        self,
        metadata: str,
        line_num: int,
    ) -> dict[str, str]:
        """Parses a raw metadata string into a key-value dict.

        Expects the format: [key=value key=value ...]

        Args:
            metadata: Raw metadata string including brackets.
            line_num: Line number for error reporting.

        Returns:
            Dict of string key-value pairs.

        Raises:
            ParseError: If brackets are missing, an entry has no '=',
                or a key appears more than once.
        """
        metadata = metadata.strip()

        if not (metadata.startswith("[") and metadata.endswith("]")):
            raise ParseError("Metadata must be enclosed in []", line_num)

        metadata = metadata[1:-1]
        config: dict[str, str] = {}

        for option in metadata.split():
            if "=" not in option:
                raise ParseError(f"Invalid metadata entry: {option}", line_num)

            key, value = option.split("=", 1)

            if key in config:
                raise ParseError(f"Duplicate metadata key: {key}", line_num)

            config[key] = value

        return config

    def validate_hub_metadata(
        self,
        metadata: Optional[str],
        line_num: int = -1,
    ) -> H_Metadata:
        """Parses and validates hub metadata into an H_Metadata instance.

        Returns a default H_Metadata if no metadata string is provided.

        Args:
            metadata: Raw metadata string or None.
            line_num: Line number for error reporting.

        Returns:
            A validated H_Metadata instance.

        Raises:
            ParseError: If the metadata string is invalid or fails Pydantic
                        validation.
        """
        if not metadata:
            return H_Metadata()

        config = self._parse_metadata_str(metadata, line_num)

        try:
            return H_Metadata.model_validate(config)
        except ValidationError as e:
            msgs = [err["msg"] for err in e.errors()]
            raise ParseError(", ".join(msgs), line_num)

    def validate_conn_metadata(
        self,
        metadata: Optional[str],
        line_num: int = -1,
    ) -> dict[str, str]:
        """Parses connection metadata into a raw key-value dict.

        Returns an empty dict if no metadata string is provided.

        Args:
            metadata: Raw metadata string or None.
            line_num: Line number for error reporting.

        Returns:
            Dict of string key-value pairs.

        Raises:
            ParseError: If the metadata string is malformed.
        """
        if not metadata:
            return {}

        return self._parse_metadata_str(metadata, line_num)

    def validate_hub(
        self,
        hub_str: str,
        state: int,
        line_num: int,
    ) -> Config_Hub:
        """Parses and validates a hub definition string into a Config_Hub.

        Args:
            hub_str: The hub portion of the line (after the keyword).
            state: Integer value of the hub's State enum.
            line_num: Line number for error reporting.

        Returns:
            A validated Config_Hub instance.

        Raises:
            ParseError: If the format is wrong, coordinates are not integers,
                or Pydantic validation fails.
        """
        parts = hub_str.split(maxsplit=3)

        if len(parts) not in (3, 4):
            raise ParseError("Hub must have 3 or 4 fields", line_num)

        name, x_str, y_str = parts[:3]
        metadata_str = parts[3] if len(parts) == 4 else None

        try:
            x = int(x_str)
            y = int(y_str)
        except ValueError:
            raise ParseError("Hub coordinates must be integers", line_num)

        metadata = self.validate_hub_metadata(metadata_str, line_num)

        try:
            return Config_Hub(
                name=name,
                x=x,
                y=y,
                metadata=metadata,
                state=State(state),
            )
        except ValidationError as e:
            msgs = [err["msg"] for err in e.errors()]
            raise ParseError(", ".join(msgs), line_num)

    def process_hub(
        self,
        src: str,
        line_num: int,
        state: int = State.NORMAL.value,
    ) -> None:
        """Parses a hub line and adds it to the internal hub registry.

        Also registers start/end hubs when the appropriate state is given.

        Args:
            src: The full line string including the keyword.
            line_num: Line number for error reporting.
            state: Integer value of the hub's State enum. Defaults to NORMAL.

        Raises:
            ParseError: If the format is invalid, the hub name
                is duplicated, or start/end hubs are defined more than once.
        """
        try:
            _, hub_str = src.split(maxsplit=1)
        except ValueError:
            raise ParseError("Invalid hub line format", line_num)

        hub = self.validate_hub(hub_str, state, line_num)

        if hub.name in self.hubs:
            raise ParseError(f"Hub '{hub.name}' already defined", line_num)

        self.hubs[hub.name] = hub

        if state == State.START.value:
            if self.is_started:
                raise ParseError("start_hub already defined", line_num)
            self.is_started = True
            self.start_hub = hub

        elif state == State.END.value:
            if self.is_ended:
                raise ParseError("end_hub already defined", line_num)
            self.is_ended = True
            self.end_hub = hub

    def validate_connections(
        self,
        conn_hubs: tuple[str, str],
        metadata: Optional[str],
        line_num: int,
    ) -> Config_Connection:
        """Validates and constructs a Config_Connection from two hub names.

        Args:
            conn_hubs: Tuple of (hub1_name, hub2_name).
            metadata: Optional raw metadata string for the connection.
            line_num: Line number for error reporting.

        Returns:
            A validated Config_Connection instance.

        Raises:
            ParseError: If either hub does not exist, the connection is a
                self-loop, the connection already exists, or Pydantic
                validation fails.
        """
        z1_name, z2_name = conn_hubs

        if z1_name not in self.hubs:
            raise ParseError(f"Hub '{z1_name}' does not exist", line_num)
        if z2_name not in self.hubs:
            raise ParseError(f"Hub '{z2_name}' does not exist", line_num)

        if z1_name == z2_name:
            raise ParseError("Self connection not allowed", line_num)

        if any(
            (c.hub1.name, c.hub2.name) in [(z1_name, z2_name),
                                           (z2_name, z1_name)]
            for c in self.connections
        ):
            raise ParseError(
                f"Connection ({z1_name}-{z2_name}) already exists",
                line_num,
            )

        z1 = self.hubs[z1_name]
        z2 = self.hubs[z2_name]

        meta = self.validate_conn_metadata(metadata, line_num)
        data: dict[str, Any] = {"hub1": z1, "hub2": z2}

        if meta:
            data.update(meta)

        try:
            # fix: type: ignore needed since mypy can't infer **dict[str, Any]
            # into Pydantic model fields
            return Config_Connection(**data)
        except ValidationError as e:
            msgs = [err["msg"] for err in e.errors()]
            raise ParseError(", ".join(msgs), line_num)

    def process_connections(self, src: str, line_num: int) -> None:
        """Parses a connection line and appends it to the connections list.

        Args:
            src: The full line string including the keyword.
            line_num: Line number for error reporting.

        Raises:
            ParseError: If the connection format is invalid.
        """
        try:
            _, connection = src.split(maxsplit=1)
            parts = connection.split()

            if len(parts) == 1:
                z1, z2 = connection.split("-")
                metadata = None
            else:
                conn_hubs, metadata = parts
                z1, z2 = conn_hubs.split("-")

        except ValueError:
            raise ParseError("Invalid connection format", line_num)

        conn = self.validate_connections((z1, z2), metadata, line_num)
        self.connections.append(conn)

    def validate_all_hubs(self) -> None:
        """Runs post-parse hub validation checks.

        Detects duplicate names and coordinates across all hubs.
        Sets max_drones on start/end hubs to match nb_drones.

        Raises:
            ParseError: If duplicate names or coordinates are found.
        """
        seen_names: set[str] = set()

        for hub in self.hubs.values():

            if hub.name in seen_names:
                raise ParseError("Duplicate hub name")

            seen_names.add(hub.name)

            if hub.state in (State.START, State.END):
                hub.metadata.max_drones = self.nb_drones

    def validate_parse_state(self) -> None:
        """Checks that the minimum required fields were parsed.

        Raises:
            ParseError: If nb_drones was never set or start/end hubs are
                        missing.
        """
        if self.nb_drones < 0:
            raise ParseError("Empty file")
        if not self.start_hub or not self.end_hub:
            raise ParseError("Missing start or end hub")

    def validate_connectivity(self) -> None:
        """Verifies that a path exists from start to end hub.

        Also prints a warning for any hubs unreachable from the start hub.

        Raises:
            ParseError: If the end hub cannot be reached from the start hub.
        """
        assert self.start_hub is not None
        assert self.end_hub is not None

        hubs = set(self.hubs.keys())
        frontier: set[str] = {self.start_hub.name}
        visited: set[str] = set()

        while frontier:
            curr = frontier.pop()

            if self.hubs[curr].metadata.zone:
                visited.add(curr)
                for conn in self.connections:
                    if (
                        conn.hub1.name == curr
                        and conn.hub2.name not in visited
                    ):
                        frontier.add(conn.hub2.name)

                    if (
                        conn.hub2.name == curr
                        and conn.hub1.name not in visited
                    ):
                        frontier.add(conn.hub1.name)

        if self.end_hub.name not in visited:
            raise ParseError(
                f"No path from '{self.start_hub.name}' "
                f"to '{self.end_hub.name}'. "
                f"Reachable hubs: {visited}"
            )

        diff = hubs.difference(visited)
        if diff:
            print(f"Warning isolated hubs: {diff}")

    def parse(self) -> None:
        """Reads and parses the map file line by line.

        Strips comments, skips blank lines, and dispatches each line to
        the appropriate handler. Runs full validation after all lines
        are processed.

        Raises:
            ParseError: On any syntax, format, or validation error,
                with the offending line number included in the message.
        """
        with open(self.filepath, "r") as file:
            for line_num, line in enumerate(file, start=1):
                res = line.split("#", 1)[0].strip()

                if not res:
                    continue

                if self.str_startswith(res, "nb_drones:"):
                    self.process_nbdrones(res, line_num)
                    continue

                if self.nb_drones < 0:
                    raise ParseError(
                        "nb_drones must be defined first", line_num
                    )

                if self.str_startswith(res, "start_hub:"):
                    self.process_hub(res, line_num, State.START.value)
                elif self.str_startswith(res, "hub:"):
                    self.process_hub(res, line_num)
                elif self.str_startswith(res, "end_hub:"):
                    self.process_hub(res, line_num, State.END.value)
                elif self.str_startswith(res, "connection:"):
                    self.process_connections(res, line_num)
                else:
                    raise ParseError(f"Unknown attribute '{res}'", line_num)

        self.validate_parse_state()
        self.validate_all_hubs()
        self.validate_connectivity()
