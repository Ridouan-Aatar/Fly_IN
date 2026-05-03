from main import Fly_In_Config, Config_Hub, Config_Connection, State


class Drone:
    _id_counter = 0  # class-level counter (your version mutates shared state oddly)

    def __init__(self, start_hub: Config_Hub) -> None:
        Drone._id_counter += 1
        self.id: int = Drone._id_counter
        self.curr_hub: Config_Hub = start_hub
        self.path: list[Config_Hub] = []
        self.turns_in_transit: int = 0  # for restricted zones (2-turn moves)
        self.delivered: bool = False

    def __repr__(self) -> str:
        return f"D{self.id}@{self.curr_hub.name}"


if __name__ == "__main__":
    config = Fly_In_Config("01_linear_path.txt")
    config.parse()
    print(config.deploy())
