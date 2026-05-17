import heapq

from painting import Painting
from parser import Config_Hub, Fly_In_Config


class Drone:
    _id_counter = 0

    def __init__(
        self,
        start_hub: Config_Hub,
        end_hub: Config_Hub,
        path: list[str],
    ) -> None:
        Drone._id_counter += 1

        self.id = Drone._id_counter
        self.curr_hub = start_hub
        self.end_hub = end_hub

        self.steps = 1
        self.path = path

        self.is_standby = False
        self.turn_allowed = 0
        self.delivered = False

        self.prev_hub: str | None = None

    def check_deliverance(self) -> None:
        self.delivered = (
            self.path[self.steps - 1] == self.end_hub.name
        )


class Graph:
    def __init__(self, config: Fly_In_Config) -> None:
        self.config = config

        self.start_hub = config.start_hub
        self.end_hub = config.end_hub

        self.hubs = config.hubs
        self.connections = config.connections

        self.adjacency = self.connection_to_adjacency()

        self.paths = sorted(
            self.get_k_paths(10),
            key=self.path_cost,
        )

        self.drones: list[Drone] = [
            Drone(
                config.start_hub,
                config.end_hub,
                self.paths[0],
            )
            for _ in range(config.nb_drones)
        ]

    def path_cost(self, path: list[str]) -> int:
        return sum(
            2 if self.hubs[hub].metadata.zone == "restricted" else 1
            for hub in path[1:]
        )

    def connection_to_adjacency(
        self,
    ) -> dict[str, dict[str, int]]:

        adjacency: dict[str, dict[str, int]] = {}

        for hub in self.hubs.values():

            if hub.metadata.zone == "blocked":
                continue

            adjacency[hub.name] = {}

            for connection in self.connections:

                if (
                    hub.name == connection.hub1.name
                    and connection.hub2.metadata.zone != "blocked"
                ):
                    adjacency[hub.name][
                        connection.hub2.name
                    ] = connection.max_link_capacity

                if (
                    hub.name == connection.hub2.name
                    and connection.hub1.metadata.zone != "blocked"
                ):
                    adjacency[hub.name][
                        connection.hub1.name
                    ] = connection.max_link_capacity

        return adjacency

    def dijkstra(
        self,
        penalty_nodes: dict[str, float] | None = None,
        penalty_edges: dict[tuple[str, str], float] | None = None,
    ) -> list[str] | None:

        penalty_nodes = penalty_nodes or {}
        penalty_edges = penalty_edges or {}

        start = self.config.start_hub.name
        end = self.config.end_hub.name

        cost_so_far: dict[str, float] = {
            start: 0,
        }

        came_from: dict[str, str | None] = {
            start: None,
        }

        heap: list[tuple[float, str]] = [
            (0, start),
        ]

        while heap:

            current_cost, current = heapq.heappop(heap)

            if current == end:

                path: list[str] = []

                while current is not None:
                    path.append(current)
                    current = came_from[current]

                return list(reversed(path))

            if current_cost > cost_so_far[current]:
                continue

            for neighbor_name in self.adjacency[current]:

                neighbor = self.hubs[neighbor_name]

                if neighbor.metadata.zone == "restricted":
                    base_cost = 2
                elif neighbor.metadata.zone == "priority":
                    base_cost = 0.5
                else:
                    base_cost = 1

                node_penalty = penalty_nodes.get(neighbor_name, 0)

                edge_key = tuple(
                    sorted((current, neighbor_name))
                )

                edge_penalty = penalty_edges.get(edge_key, 0)

                new_cost = (
                    current_cost
                    + base_cost
                    + node_penalty
                    + edge_penalty
                )

                if new_cost < cost_so_far.get(neighbor_name, float("inf")):
                    cost_so_far[neighbor_name] = new_cost

                    came_from[neighbor_name] = current

                    heapq.heappush(heap, (new_cost, neighbor_name))

        return None

    def get_k_paths(self, k: int) -> list[list[str]]:
        penalty_nodes: dict[str, float] = {}

        retries = 0
        min_cost = -1

        paths: list[list[str]] = []

        while retries < k:

            path = self.dijkstra(
                penalty_nodes=penalty_nodes,
            )

            if path is None:
                break

            if path not in paths:

                if not paths:
                    min_cost = self.path_cost(path)

                if abs(self.path_cost(path) - min_cost) < 5:
                    paths.append(path)
                    retries = 0

            retries += 1

            for node in path:
                penalty_nodes[node] = (
                    penalty_nodes.get(node, 0) + 2
                )

        return paths


class Fly_In:
    def __init__(self, graph: Graph) -> None:
        self.graph = graph

        self.paint = Painting(graph.config)

        self.drones = sorted(
            graph.drones,
            key=lambda drone: drone.id,
        )

        self.curr_num_drones = {
            hub.name: 0
            for hub in graph.hubs.values()
        }

        self.conn_occupancy = {
            tuple(sorted((conn.hub1.name, conn.hub2.name))): 0
            for conn in graph.connections
        }

        self.curr_num_drones[graph.start_hub.name] = graph.config.nb_drones

        self.paths = graph.paths

    def all_delivered(self) -> bool:
        return all(
            drone.delivered
            for drone in self.drones
        )

    def change_path(self, drone_id: int) -> bool:
        drone = self.drones[drone_id]

        current_hub = drone.path[drone.steps - 1]

        for path in self.paths:

            if (drone.path != path and current_hub in path):

                drone.steps = (path.index(current_hub) + 1)
                drone.path = path

                return True

        return False

    def add_connection(self, drone_id: int) -> None:
        drone = self.drones[drone_id]

        key = tuple(
            sorted(
                (drone.path[drone.steps - 1], drone.path[drone.steps])
            )
        )

        self.conn_occupancy[key] += 1

    def release_old_connection(
        self,
        drone_id: int,
    ) -> None:

        drone = self.drones[drone_id]

        if drone.prev_hub is None:
            return

        current_hub = drone.path[drone.steps - 1]

        key = tuple(
            sorted(
                (drone.prev_hub, current_hub)
            )
        )

        self.conn_occupancy[key] -= 1

        if self.conn_occupancy[key] < 0:
            raise ValueError(
                f"Negative occupancy for {key}"
            )

    def check_availability(
        self,
        drone_id: int,
    ) -> bool:

        drone = self.drones[drone_id]

        old_hub = drone.path[drone.steps - 1]
        new_hub = drone.path[drone.steps]

        key = tuple(
            sorted((old_hub, new_hub))
        )

        occupancy = self.conn_occupancy.get(key)

        if occupancy is None:
            raise KeyError(
                f"Connection {key} does not exist"
            )

        max_capacity = self.graph.adjacency[old_hub][new_hub]

        if not drone.is_standby:

            if occupancy >= max_capacity:
                return False

            if (
                self.curr_num_drones[new_hub]
                >= self.graph.hubs[
                    new_hub
                ].metadata.max_drones
            ):
                return (
                    self.graph.hubs[new_hub].metadata.zone == "restricted"
                )

        return True

    def give_turns(self, drone_id: int) -> None:
        drone = self.drones[drone_id]

        new_hub = drone.path[drone.steps]

        if drone.turn_allowed == 0:

            zone = self.graph.hubs[new_hub].metadata.zone

            drone.turn_allowed = (
                2 if zone == "restricted" else 1
            )

            self.release_old_connection(
                drone_id
            )

    def traverse(self, drone_id: int) -> str:
        drone = self.drones[drone_id]

        old_hub = drone.path[drone.steps - 1]
        new_hub = drone.path[drone.steps]

        self.give_turns(drone_id)

        if (
            drone.turn_allowed > 0
            and not drone.is_standby
        ):
            self.curr_num_drones[old_hub] -= 1

            self.add_connection(drone_id)

            drone.is_standby = (
                drone.turn_allowed == 2
            )

        drone.turn_allowed -= 1

        if drone.turn_allowed == 0:
            self.curr_num_drones[new_hub] += 1
            drone.is_standby = False

        if drone.turn_allowed:
            return (
                f"D{drone_id + 1}-"
                f"{self.paint(old_hub)}-"
                f"{self.paint(new_hub)}"
            )

        drone.prev_hub = old_hub
        drone.steps += 1

        return (
            f"D{drone_id + 1}-"
            f"{self.paint(new_hub)}"
        )

    def simulate(self) -> None:
        turn = 0

        while not self.all_delivered():
            turn += 1
            drone_paths: list[str] = []

            for index, drone in enumerate(self.drones):

                if drone.delivered:
                    self.release_old_connection(index)
                    drone.prev_hub = None
                    continue

                if not self.check_availability(index):
                    if (not self.change_path(index) or
                       not self.check_availability(index)):
                        continue

                drone_paths.append(self.traverse(index))
                drone.check_deliverance()

            print(
                f"Turn {turn}: "
                f"{' '.join(drone_paths)}"
            )
