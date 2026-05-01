# finding_metadata = "\[(.*?)\]"


# TODO make the default max_drones for starthub and endhub the same as nb_drones
# TODO find why coords are negtaives
# TODO find how to avoid the bs double brackets
# TODO valid the names 
# TODO find anomalies and the writing 
# TODO there might be bullshit of double ::::::: in the attributes
#  TODO maybe u can use split and index 0 instead of startswith 

# TODO there is also the bullshits about writing the comments inside the mandatory attributes
from pydantic import BaseModel, model_validator, ValidationError, Field
from typing import Optional, Literal
from enum import Enum


class State(Enum):
    START = 0
    NORMAL = 1
    END = 2


ZONE = Literal["normal", "blocked", "restricted", "priority"]

# TODO placeholder
COLOR = Literal["red", "green", "blue", "yellow"]

class H_Metadata(BaseModel):
    zone: ZONE = Field(default="normal")
    color: Optional[COLOR]
    max_drones: int = Field(default=1, ge=1)

class Hub(BaseModel):
    name: str
    x: int
    y: int
    metadata: Optional[H_Metadata]
    state: State

    @model_validator(mode="after")
    def validate(self):
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

        if self.nb_drones < 0:
            _, nb_drones = src.split()
            self.nb_drones = int(nb_drones)
            print(f"==> number of drones ({self.nb_drones})")
        else:
            print("==> nb_drones already exists")

    def validate_metadata(self, metadata: str):
        metadata = metadata.strip()
        config = {}
        if metadata[0] == '[' and metadata[-1] == ']':
            metadata = metadata[1:-1]
            options = metadata.split()
            for option in options:
                key, value = option.split("=")
                # if key in config:
                #     print("key already existed")
                config[key] = value
                print(f"* {config}")
            meta = H_Metadata(**config)
            print(f"####> {meta}")
            return meta
        else:
            print("metadatas should be in single brackets!!!")


    def validate_hub(self, hub_str: str, state: int):
        hub = hub_str.split(maxsplit=3)
        if len(hub) == 3:
            name, x, y = hub
            metadata = None
        elif len(hub) == 4:
            name, x, y, metadata = hub
        else:
            print("This hub have few or more than arguments required")
            return

        metadata = self.validate_metadata(metadata)

        hub = Hub(name=name,
                  x=x,
                  y=y,
                  metadata=metadata,
                  state=state)
        print(hub)


    def process_hub(self, src: str, state: int = State.NORMAL.value):
    
        hub = src.split(maxsplit=1)[1]

        if state == State.START.value:
            if not self.is_started:
                self.is_started = True
                self.start_hub = hub
                print(f"==> starting hub ({hub})")
            else:
                print("==> start_hub already exists")
        elif state == State.NORMAL.value:
            self.hubs.append(hub)
            print(f"==> regular hub ({hub})")
        else:
            if not self.is_ended:
                self.is_ended = True
                self.end_hub = hub
                print(f"==> ending hub ({hub})")
            else:
                print("==> end_hub already exists")

        self.validate_hub(hub, state)



    def process_connections(self, src: str):
        connection = src.split(maxsplit=1)[1]
        z1, z2 = connection.split("-")
        self.connections.append((z1, z2))
        print(f"==> connection ({z1} and {z2})")

    def parse(self):
        with open(self.filepath, "r") as file:
            for line in file:
                res = line.strip().split("#", maxsplit=1)[0]

                print(res)

                if not res:
                    print("==> skip")
                    continue
                    # TODO might be deleted
                if self.str_startswith(res, "#"):
                    print("==> must be skipped")
                    continue

                if self.str_startswith(res, "nb_drones:"):
                    self.process_nbdrones(res)
                    continue

                if self.nb_drones < 0:
                    print("==> ERROR: nb_drones missing")
                    break

                if self.str_startswith(res, "start_hub:"):
                    self.process_hub(res, state=State.START.value)

                elif self.str_startswith(res, "hub:"):
                    self.process_hub(res)

                elif self.str_startswith(res, "end_hub:"):
                    self.process_hub(res, state=State.END.value)

                elif self.str_startswith(res, "connection:"):
                    self.process_connections(res)

                else:
                    print("==> Error unknown attribute")
                print()

config = Fly_In_Config("01_linear_path.txt")
config.parse()