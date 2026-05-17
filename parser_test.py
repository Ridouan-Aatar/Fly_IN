# finding_metadata = "\[(.*?)\]"


# TODO make the default max_drones for starthub and endhub the same as nb_drones
# TODO find why coords are negtaives
# TODO find how to avoid the bs double brackets
# TODO valid the names 
# TODO find anomalies and the writing 
# TODO there might be bullshit of double ::::::: in the attributes
#  TODO maybe u can use split and index 0 instead of startswith 


# TODO start_hub should exist also end_hub (use flags)

# TODO find out why the fuck other metadata atribs are accepted (ignored)

# TODO the zone blocked must have max_drones = 0

# TODO there is also the full duplicated connections find something about it 

# TODO there is also the bullshits about writing the comments inside the mandatory attributes

# TODO delete the restricted requirement for start/hub

# TODO start_hub and end_hub cannot be isolated

# TODO ensure that there is at least connectivity from start to end (excluding the blocked zones)

# TODO dont forget to turn colors into matplotlib or some shit like that



# TODO WARNING maybe they are not sequential load everything at once 
# TODO keyboard BS
# TODO Warning they should give the line with error
# TODO give warning for maxdrones being little in start/end hub

from pydantic import (
    BaseModel,
    model_validator,
    ValidationError,
    Field,
    ConfigDict,
    field_validator,
)
from typing import Optional, Literal
from enum import Enum
from painting import Painting


class ParseError(Exception):
    def __init__(self, message: str, line_num: int = -1) -> None:
        self.line_num = line_num
        if line_num >= 0:
            super().__init__(f"Line {line_num}: {message}")
        else:
            super().__init__(message)


class State(Enum):
    START = 0
    NORMAL = 1
    END = 2


ZONE = Literal["normal", "blocked", "restricted", "priority"]


class H_Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone: ZONE = Field(default="normal")
    color: Optional[str] = Field(default=None)
    max_drones: int = Field(default=-1, ge=1)

    @field_validator("zone", mode="before")
    @classmethod
    def tolower(cls, value: str) -> str:
        return value.lower()

    @field_validator("color", mode="before")
    @classmethod
    def validate_color(cls, value: str) -> str:
        value = value.lower()
        if not Painting.validate_color(value):
            raise ValueError(f"Invalid named color '{value}'")
        return value


class Config_Hub(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    x: int
    y: int
    metadata: H_Metadata
    state: State

    @model_validator(mode="after")
    def validate(self) -> "Config_Hub":
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
    model_config = ConfigDict(extra="forbid")

    hub1: Config_Hub
    hub2: Config_Hub
    max_link_capacity: int = Field(default=1, ge=1)


class Fly_In_Config:
    def __init__(self, filepath: str) -> None:
        self.filepath = filepath

        self.nb_drones: int = -1
        self.start_hub: Optional[Config_Hub] = None
        self.end_hub: Optional[Config_Hub] = None

        # ✅ CHANGED: list -> dict
        self.hubs: dict[str, Config_Hub] = {}

        self.__seen_cords = set()
        self.connections: list[Config_Connection] = []

        self.is_started: bool = False
        self.is_ended: bool = False

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------

    def str_startswith(self, line: str, target: str) -> bool:
        try:
            first, _ = line.split(maxsplit=1)
            return first == target
        except Exception:
            return False

    # --------------------------------------------------
    # nb_drones
    # --------------------------------------------------

    def process_nbdrones(self, src: str, line_num: int) -> None:
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

    # --------------------------------------------------
    # Hub lookup
    # --------------------------------------------------

    def find_hub_by_name(self, name: str) -> Config_Hub:
        try:
            return self.hubs[name]
        except KeyError:
            raise ParseError(f"Hub '{name}' does not exist")

    # --------------------------------------------------
    # Metadata
    # --------------------------------------------------

    def validate_metadata(
        self,
        metadata: Optional[str],
        for_hub: bool = True,
        line_num: int = -1,
    ) -> Optional[H_Metadata] | dict:

        if not metadata:
            return H_Metadata() if for_hub else None

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

        try:
            return H_Metadata(**config) if for_hub else config
        except ValidationError as e:
            msgs = [err["msg"] for err in e.errors()]
            raise ParseError(", ".join(msgs), line_num)

    # --------------------------------------------------
    # Hub
    # --------------------------------------------------

    def validate_hub(self, hub_str: str,
                     state: int,
                     line_num: int) -> Config_Hub:
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

        metadata = self.validate_metadata(metadata_str, True, line_num)

        try:
            return Config_Hub(
                name=name,
                x=x,
                y=y,
                metadata=metadata,  # type: ignore
                state=State(state),
            )
        except ValidationError as e:
            msgs = [err["msg"] for err in e.errors()]
            raise ParseError(", ".join(msgs), line_num)

    def process_hub(self, src: str,
                    line_num: int,
                    state: int = State.NORMAL.value) -> None:
        try:
            _, hub_str = src.split(maxsplit=1)
        except ValueError:
            raise ParseError("Invalid hub line format", line_num)

        hub = self.validate_hub(hub_str, state, line_num)

        # ✅ FIXED dict usage
        if hub.name in self.hubs:
            raise ParseError(f"Hub '{hub.name}' already defined", line_num)

        if (hub.x, hub.y) in self.__seen_cords:
            raise ParseError(f"Hub '{hub.name}' had duplicated "
                             f"coordinations {(hub.x, hub.y)}", line_num)

        self.hubs[hub.name] = hub
        self.__seen_cords.add((hub.x, hub.y))

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

    # --------------------------------------------------
    # Connections
    # --------------------------------------------------

    def validate_connections(
        self,
        conn_hubs: tuple[str, str],
        metadata: Optional[str],
        line_num: int,
    ) -> Config_Connection:

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
            raise ParseError(f"Connection ({z1_name}-{z2_name}) "
                             "already exists", line_num)

        z1 = self.hubs[z1_name]
        z2 = self.hubs[z2_name]

        meta = self.validate_metadata(metadata, False, line_num)
        data = {"hub1": z1, "hub2": z2}

        if meta:
            data.update(meta)

        try:
            return Config_Connection(**data)
        except ValidationError as e:
            msgs = [err["msg"] for err in e.errors()]
            raise ParseError(", ".join(msgs), line_num)

    def process_connections(self, src: str, line_num: int) -> None:
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

    # --------------------------------------------------
    # Validation
    # --------------------------------------------------

    def validate_all_hubs(self) -> None:
        seen_names = set()
        seen_coords = set()

        for hub in self.hubs.values():  # ✅ FIXED

            if hub.name in seen_names:
                raise ParseError("Duplicate hub name")

            if (hub.x, hub.y) in seen_coords:
                raise ParseError("Duplicate hub coordinates")

            seen_names.add(hub.name)
            seen_coords.add((hub.x, hub.y))

            if hub.state in (State.START, State.END):
                hub.metadata.max_drones = self.nb_drones

    def validate_parse_state(self) -> None:
        if self.nb_drones < 0:
            raise ParseError("Empty file")
        if not self.start_hub or not self.end_hub:
            raise ParseError("Missing start or end hub")

    def validate_connectivity(self) -> None:
        hubs = {key for key in self.hubs.keys()}
        frontier = {self.start_hub.name}
        edges = set()

        while frontier:
            curr = frontier.pop()
            edges.add(curr)
            for conn in self.connections:
                if conn.hub1.name == curr and conn.hub2.name not in edges:
                    frontier.add(conn.hub2.name)
                if conn.hub2.name == curr and conn.hub1.name not in edges:
                    frontier.add(conn.hub1.name)

        if self.end_hub.name not in edges:
            raise ValueError(
                f"No path from '{self.start_hub.name}' "
                f"to '{self.end_hub.name}'. "
                f"Reachable hubs: {edges}"
            )

        diff = hubs.difference(edges)
        if diff:
            print(f"Warning isolated hubs: {diff}")

    # --------------------------------------------------
    # Parse
    # --------------------------------------------------

    def parse(self) -> None:
        with open(self.filepath, "r") as file:
            for line_num, line in enumerate(file, start=1):
                res = line.split("#", 1)[0].strip()

                if not res:
                    continue

                if self.str_startswith(res, "nb_drones:"):
                    self.process_nbdrones(res, line_num)
                    continue
                if self.nb_drones < 0:
                    raise ParseError(f"Line {line_num}: nb_drones must "
                                     "be defined first")

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

    def to_dict(self):
        return {
            "nb_drones": self.nb_drones,
            "start_hub": self.start_hub,
            "end_hub": self.end_hub,
            "hubs": [h for h in self.hubs.values()],
            "connections": self.connections,
        }

    def summary(self):  # TODO this must be deleted
        data = self.to_dict()

        print("\n=== CONFIG SUMMARY ===")
        print(f"nb_drones: {data['nb_drones']}")

        print("\nStart Hub:")
        print(data["start_hub"])

        print("\nEnd Hub:")
        print(data["end_hub"])

        print(f"\nHubs ({len(data['hubs'])}):")
        for h in data["hubs"]:
            print(f"  - {h}")

        print(f"\nConnections ({len(data['connections'])}):")
        for c in data["connections"]:
            print(f"  - {c.hub1.name} -> {c.hub2.name} "
                  f"[max_link_capacity={c.max_link_capacity}]")


if __name__ == "__main__":
    try:
        config = Fly_In_Config("map.txt")
        config.parse()
        config.summary()
    except ParseError as e:
        print(f"{e}")
    except KeyboardInterrupt:
        print("Exiting the program!!!")
