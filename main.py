# finding_metadata = "\[(.*?)\]"


# TODO make the default max_drones for starthub and endhub the same as nb_drones
# TODO find why coords are negtaives
# TODO find how to avoid the bs double brackets
# TODO valid the names 
# TODO find anomalies and the writing 
# TODO there might be bullshit of double ::::::: in the attributes
#  TODO maybe u can use split and index 0 instead of startswith 


# TODO the zone blocked must have max_drones = 0

# TODO there is also the bullshits about writing the comments inside the mandatory attributes
from pydantic import BaseModel, model_validator, ValidationError, Field, field_validator
from typing import Optional, Literal
from enum import Enum
import math


class State(Enum):
    START = 0
    NORMAL = 1
    END = 2


ZONE = Literal["normal", "blocked", "restricted", "priority"]
COLOR = Literal["red", "green", "blue", "yellow"]


class H_Metadata(BaseModel):
    zone: ZONE = Field(default="normal")
    color: Optional[COLOR]
    max_drones: int = Field(default=-1, ge=0)


class Hub(BaseModel):
    name: str
    x: int
    y: int
    metadata: Optional[H_Metadata]
    state: State

    @model_validator(mode="after")
    def validate(self):
        if "-" in self.name:
            raise ValueError("'-' is not allowed in hub names!!")

        if self.state == State.START or self.state == State.END:
            if self.metadata.max_drones == -1:
                self.metadata.max_drones = math.inf
            if self.metadata.zone in ("blocked", "restricted"):
                raise ValueError("Start/End Hubs cannot be "
                                 "blocked/restricted zones")

        if self.metadata.zone == "blocked":
            if self.metadata.max_drones != -1:
                print("Warning: setting max_drones "
                      "has no effect on blocked zones")
            self.metadata.max_drones = 0
        else:
            if self.metadata.max_drones == -1:
                self.metadata.max_drones = 1
        return self


class Fly_In_Config:
    def __init__(self, filepath):
        self.filepath = filepath

        self.nb_drones = -1
        self.start_hub = None
        self.end_hub = None
        self.hubs = []
        self.connections = []

        self.is_started = False
        self.is_ended = False

    def str_startswith(self, line: str, target: str) -> bool:
        try:
            first, _ = line.split(maxsplit=1)
            return first == target
        except Exception:
            return False

    def process_nbdrones(self, src: str):
        if self.nb_drones >= 0:
            raise ValueError("nb_drones already defined")

        try:
            _, nb_drones = src.split()
            self.nb_drones = int(nb_drones)
        except Exception:
            raise ValueError("Invalid nb_drones format")

    def validate_metadata(self, metadata: str):
        if not metadata:
            return H_Metadata()

        metadata = metadata.strip()
        config = {}

        if not (metadata.startswith("[") and metadata.endswith("]")):
            raise ValueError("Metadata must be enclosed in []")

        metadata = metadata[1:-1]

        for option in metadata.split():
            if "=" not in option:
                raise ValueError(f"Invalid metadata entry: {option}")

            key, value = option.split("=")

            if key in config:
                raise ValueError(f"Duplicate metadata key: {key}")

            config[key] = value

        try:
            return H_Metadata(**config)
        except ValidationError as e:
            raise ValueError(f"Invalid metadata values: {e}")

    def validate_hub(self, hub_str: str, state: int):
        parts = hub_str.split(maxsplit=3)

        if len(parts) not in (3, 4):
            raise ValueError("Hub must have 3 or 4 fields")

        name, x, y = parts[:3]
        metadata = parts[3] if len(parts) == 4 else None

        try:
            x = int(x)
            y = int(y)
        except ValueError:
            raise ValueError("Hub coordinates must be integers")

        metadata = self.validate_metadata(metadata)

        try:
            hub = Hub(
                name=name,
                x=x,
                y=y,
                metadata=metadata,
                state=State(state),
            )
        except ValidationError as e:
            raise ValueError(f"Invalid hub: {e}")

        return hub

    def process_hub(self, src: str, state: int = State.NORMAL.value):
        try:
            _, hub_str = src.split(maxsplit=1)
        except ValueError:
            raise ValueError("Invalid hub line format")

        hub = self.validate_hub(hub_str, state)

        if state == State.START.value:
            if self.is_started:
                raise ValueError("start_hub already defined")
            self.is_started = True
            self.start_hub = hub

        # elif state == State.NORMAL.value:
        elif state == State.END.value:
            if self.is_ended:
                raise ValueError("end_hub already defined")
            self.is_ended = True
            self.end_hub = hub

        self.hubs.append(hub)
    def process_connections(self, src: str):
        try:
            _, connection = src.split(maxsplit=1)
            z1, z2 = connection.split("-")
        except ValueError:
            raise ValueError("Invalid connection format")

        self.connections.append((z1, z2))

    def validate_all_hubs(self):
        set_names = set()
        set_coords = set()

        for hub in self.hubs:
            if hub.name in set_names:
                raise ValueError("Invalid Duplicate Hub detected !!")
            set_names.add(hub.name)

            if (hub.x, hub.y) in set_coords:
                raise ValueError("Invalid Duplicate Hub coordinates detected !")
            set_coords.add((hub.x, hub.y))

            max_drones = hub.metadata.max_drones
            state = hub.state
            if (max_drones < self.nb_drones and state in (State.START, State.END)):
                raise ValueError("Start or end hubs cannot have less"
                                 " max_drones than number of drones")

    def parse(self):
        with open(self.filepath, "r") as file:
            for line_num, line in enumerate(file, start=1):
                res = line.strip().split("#", maxsplit=1)[0]

                if not res:
                    continue

                if self.str_startswith(res, "nb_drones:"):
                    self.process_nbdrones(res)
                    continue

                if self.nb_drones < 0:
                    raise ValueError(f"Line {line_num}: nb_drones must be defined first")

                if self.str_startswith(res, "start_hub:"):
                    self.process_hub(res, state=State.START.value)

                elif self.str_startswith(res, "hub:"):
                    self.process_hub(res)

                elif self.str_startswith(res, "end_hub:"):
                    self.process_hub(res, state=State.END.value)

                elif self.str_startswith(res, "connection:"):
                    self.process_connections(res)

                else:
                    raise ValueError(f"Line {line_num}: Unknown attribute")

        self.validate_all_hubs()

    def to_dict(self):
        return {
            "nb_drones": self.nb_drones,
            "start_hub": self.start_hub,
            "end_hub": self.end_hub,
            "hubs": [h for h in self.hubs],
            "connections": self.connections,
        }

    def summary(self):
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
            print(f"  - {c[0]} -> {c[1]}")


config = Fly_In_Config("01_linear_path.txt")
config.parse()
config.summary()