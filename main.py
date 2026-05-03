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

from pydantic import BaseModel, model_validator, ValidationError, Field, ConfigDict
from typing import Optional, Literal
from enum import Enum
import math


class State(Enum):
    START = 0
    NORMAL = 1
    END = 2


ZONE = Literal["normal", "blocked", "restricted", "priority"]
COLOR = Literal["red", "green", "blue", "yellow", "rainbow", "orange",
                "cyan", "purple", "black", "brown", "maroon", "gold", "silver",
                "darkred", "violet"]


class H_Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    zone: ZONE = Field(default="normal")
    color: Optional[COLOR] = Field(default=None)
    max_drones: int = Field(default=-1, ge=1) # TODO find if i ignore this


class Config_Hub(BaseModel):
    model_config = ConfigDict(extra="forbid")
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
            if self.metadata.zone == "blocked":
                raise ValueError("Start/End Hubs cannot be "
                                 "blocked zones")

        if self.metadata.zone == "blocked":
            if self.metadata.max_drones != -1:
                print("Warning: setting max_drones "
                      "has no effect on blocked zones")
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
            if self.nb_drones <= 0:
                raise ValueError("nb_drones shouldnt be negative nor 0")
        except Exception:
            raise ValueError("Invalid nb_drones format")

    def find_hub_by_name(self, name):
        for hub in self.hubs:
            if name == hub.name:
                return hub
        raise ValueError(f"This {name} doesnt exist")

    def validate_metadata(self, metadata: str, for_hub=True):
        if not metadata:

            return H_Metadata() if for_hub else None

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
            return H_Metadata(**config) if for_hub else config
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
            hub = Config_Hub(
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

    def validate_connections(self, conn_hubs, metadata):
        z1, z2 = conn_hubs

        hub_names = [hub.name for hub in self.hubs]

        if z1 not in hub_names:
            raise ValueError(f"this hub {z1} doesnt exist!!")
        if z2 not in hub_names:
            raise ValueError(f"this hub {z2} doesnt exist!!")

        if z1 == z2:
            raise ValueError(f"this hub {z1} cannot establish a connection with itself !")
        conns = [(c.hub1.name, c.hub2.name) for c in self.connections]

        if (z1, z2) in conns or (z2, z1) in conns:
            raise ValueError(f"The connection ({z1}-{z2}) is already etablished")

        z1 = self.find_hub_by_name(z1)
        z2 = self.find_hub_by_name(z2)

        metadata = self.validate_metadata(metadata, for_hub=False)
        res = {}
        if metadata:
            res = {
                "hub1": z1,
                "hub2": z2,
                **metadata
            }
        else:
            res = {
                "hub1": z1,
                "hub2": z2,
            }
        try:
            connection = Config_Connection(**res)
        except ValidationError as e:
            raise ValueError(f"Invalid connection: {e}")
        return connection

    def process_connections(self, src: str):
        try:
            _, connection = src.split(maxsplit=1)
            if len(connection.split()) == 1:
                z1, z2 = connection.split("-")
                metadata = None
            else:
                conn_hubs, metadata = connection.split()
                z1, z2 = conn_hubs.split("-")
                
        except ValueError:
            raise ValueError("Invalid connection format")
        conn = self.validate_connections((z1, z2), metadata)
        self.connections.append(conn)

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

    def validate_parse_state(self):
        if self.nb_drones < 0:
            raise ValueError("The file is empty")

        if not self.start_hub or not self.end_hub:
            raise ValueError("The file should contain start_hub and end_hub")

    def validate_connectivity(self):
        hubs = {hub.name for hub in self.hubs}
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
                f"No path from '{self.start_hub.name}' to '{self.end_hub.name}'. "
                f"Reachable hubs: {edges}"
            )

        diff = hubs.difference(edges)
        if diff:
            print(f"Warning these hubs are isolated {diff} !!!")

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

        self.validate_parse_state()
        self.validate_all_hubs()
        self.validate_connectivity()

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
            print(f"  - {c.hub1.name} -> {c.hub2.name} [max_link_capacity={c.max_link_capacity}]")

    def deploy(self):
        return {
            "nb_drones": self.nb_drones,
            "hubs": self.hubs,
            "connections": self.connections,
        }


if __name__ == "__main__":
    config = Fly_In_Config("01_linear_path.txt")
    config.parse()
    config.summary()
