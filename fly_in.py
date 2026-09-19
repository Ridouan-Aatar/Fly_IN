import heapq

from painting import Painting
from parser import Config_Hub, Fly_In_Config


class Drone:
    """Represents a single drone in the simulation.

    Attributes:
        _id_counter: Class-level counter to assign unique IDs.
        id: Unique drone identifier.
        end_hub: The destination hub for this drone.
        steps: Current index in the drone's path.
        path: Ordered list of hub names from start to goal.
        is_standby: True when the drone is mid-transit on a restricted zone.
        turn_allowed: Remaining turns for the current move
                      (2 for restricted, 1 for normal).
        delivered: True when the drone has reached the end hub.
        prev_hub: Name of the hub the drone was at before its last move.
    """
    _id_counter = 0

    def __init__(
        self,
        end_hub: Config_Hub,
        path: list[str],
    ) -> None:
        """Initialises a drone and assigns it a unique ID.

        Args:
            end_hub: The hub the drone must reach.
            path: Ordered list of hub names representing the drone's route.
        """
        Drone._id_counter += 1

        self.id = Drone._id_counter
        self.end_hub = end_hub

        self.steps = 1
        self.path = path

        self.is_standby = False
        self.turn_allowed = 0
        self.delivered = False

        self.prev_hub: str | None = None

    def check_deliverance(self) -> None:
        """Marks the drone as delivered if its last step was the end hub."""
        self.delivered = (
            self.path[self.steps - 1] == self.end_hub.name
        )


class Graph:
    """Builds the graph representation from a parsed config and computes paths.

    Attributes:
        config: The parsed map configuration.
        start_hub: The starting hub.
        end_hub: The destination hub.
        hubs: Dict mapping hub names to Config_Hub objects.
        connections: List of all Config_Connection objects.
        adjacency: Adjacency list mapping hub names to their neighbours and
            connection capacities.
        paths: List of viable paths sorted by total cost.
        drones: List of Drone objects assigned to paths.
    """

    def __init__(self, config: Fly_In_Config) -> None:
        """Initialises the graph, builds adjacency, finds paths, and creates
            drones.

        Args:
            config: A fully parsed Fly_In_Config instance.
        """
        self.config = config

        assert config.start_hub is not None
        assert config.end_hub is not None

        self.start_hub: Config_Hub = config.start_hub
        self.end_hub: Config_Hub = config.end_hub

        self.hubs = config.hubs
        self.connections = config.connections

        self.adjacency = self.connection_to_adjacency()

        self.paths = sorted(
            self.get_k_paths(10),
            key=self.path_cost,
        )
        self.drones: list[Drone] = [
            Drone(
                self.end_hub,
                self.paths[0],
            )
            for _ in range(config.nb_drones)
        ]

    def path_cost(self, path: list[str]) -> int:
        """Computes the total movement cost of a path.

        Restricted zones cost 2 turns, all others cost 1.
        The start hub is excluded from the cost calculation.

        Args:
            path: Ordered list of hub names.

        Returns:
            Total integer cost of the path.
        """

        return sum(
            2 if self.hubs[hub].metadata.zone == "restricted" else 1
            for hub in path[1:]
        )

    def connection_to_adjacency(
        self,
    ) -> dict[str, dict[str, int]]:

        """Builds an adjacency list from the connection list.

        Blocked zones are excluded entirely. Each entry maps a hub name
        to a dict of neighbour hub names and their max link capacity.

        Returns:
            Adjacency dict of the form {hub_name: {neighbour_name: capacity}}.
        """

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
        """Finds the shortest path from start to end using
            Dijkstra's algorithm.

        Zone costs are applied as edge weights. Optional penalty dicts can
        increase the cost of specific nodes or edges to force path diversity.

        Args:
            penalty_nodes: Optional dict mapping hub names to extra cost.
            penalty_edges: Optional dict mapping sorted hub name tuples to
                           extra cost.

        Returns:
            Ordered list of hub names from start to end,
            or None if unreachable.
        """

        penalty_nodes = penalty_nodes or {}
        penalty_edges = penalty_edges or {}

        start = self.start_hub.name
        end = self.end_hub.name

        cost_so_far: dict[str, float] = {start: 0}
        came_from: dict[str, str | None] = {start: None}
        heap: list[tuple[float, str]] = [(0, start)]

        while heap:

            current_cost, current = heapq.heappop(heap)

            if current == end:
                path: list[str] = []
                current_node: str | None = current
                while current_node is not None:
                    path.append(current_node)
                    current_node = came_from.get(current_node, None)
                if not path:
                    raise TypeError("No Path were found leading to end_hub")
                return list(reversed(path))

            if current_cost > cost_so_far[current]:
                continue

            for neighbor_name in self.adjacency[current]:

                neighbor = self.hubs[neighbor_name]

                if neighbor.metadata.zone == "restricted":
                    base_cost: float = 2.0
                elif neighbor.metadata.zone == "priority":
                    base_cost = 0.5
                else:
                    base_cost = 1.0

                node_penalty = penalty_nodes.get(neighbor_name, 0)

                edge_key: tuple[str, str] = (
                    min(current, neighbor_name),
                    max(current, neighbor_name),
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
        """Finds up to k diverse paths using penalty-based Dijkstra reruns.

        After each path is found, penalties are added to its nodes to push
        subsequent runs toward alternative routes. Paths whose cost deviates
        more than 5 from the best are discarded.

        Args:
            k: Maximum number of retries before stopping.

        Returns:
            List of paths, each being an ordered list of hub names.
        """

        penalty_nodes: dict[str, float] = {}

        retries = 0
        min_cost: float = -1.0

        paths: list[list[str]] = []

        while retries < k:

            path = self.dijkstra(penalty_nodes=penalty_nodes)

            if path is None:
                break

            if path not in paths:

                if not paths:
                    min_cost = float(self.path_cost(path))

                if abs(self.path_cost(path) - min_cost) < 5:
                    paths.append(path)
                    retries = 0

            retries += 1

            for node in path:
                penalty_nodes[node] = (
                    penalty_nodes.get(node, 0) + 2
                )
        if not paths:
            raise TypeError("No Paths were found leading to end_hub !!")

        return paths


class Fly_In:
    """Manages the turn-by-turn drone simulation.

    Attributes:
        graph: The Graph instance containing hubs, paths, and drones.
        paint: Painting instance for colored terminal output.
        drones: Sorted list of all drones.
        curr_num_drones: Dict tracking current drone count per hub.
        conn_occupancy: Dict tracking current drone count per connection.
        paths: Available paths for path-switching.
    """
    def __init__(self, graph: Graph) -> None:
        """Initialises the simulation state.

        Sets up hub and connection occupancy trackers and places all
        drones at the start hub.

        Args:
            graph: A fully built Graph instance.
        """
        self.graph = graph

        self.paint = Painting(graph.config)

        self.drones = sorted(
            graph.drones,
            key=lambda drone: drone.id,
        )

        self.curr_num_drones: dict[str, int] = {
            hub.name: 0
            for hub in graph.hubs.values()
        }

        self.conn_occupancy: dict[tuple[str, str], int] = {
            (
                min(conn.hub1.name, conn.hub2.name),
                max(conn.hub1.name, conn.hub2.name),
            ): 0
            for conn in graph.connections
        }

        self.curr_num_drones[graph.start_hub.name] = graph.config.nb_drones

        self.paths = graph.paths

    def all_delivered(self) -> bool:
        """Checks whether all drones have reached the end hub.

        Returns:
            True if every drone is marked as delivered.
        """
        return all(drone.delivered for drone in self.drones)

    def change_path(self, drone_id: int) -> bool:
        """Attempts to switch a blocked drone to an alternative path.

        Finds a path that contains the drone's current hub and whose
        next step is available. Reverts changes if no valid path is found.

        Args:
            drone_id: Index of the drone in self.drones.

        Returns:
            True if the path was successfully changed, False otherwise.
        """
        drone = self.drones[drone_id]

        old_path = drone.path
        old_step = drone.steps

        current_hub = drone.path[drone.steps - 1]

        for path in self.paths:

            if drone.path != path and current_hub in path:
                drone.steps = path.index(current_hub) + 1
                drone.path = path
                if self.check_availability(drone_id):
                    return True
                drone.path = old_path

        drone.path = old_path
        drone.steps = old_step
        return False

    def _make_key(self, a: str, b: str) -> tuple[str, str]:
        """Creates a consistent sorted tuple key for a connection.

        Args:
            a: First hub name.
            b: Second hub name.

        Returns:
            Tuple of (min, max) hub names for consistent dict lookup.
        """
        return (min(a, b), max(a, b))

    def add_connection(self, drone_id: int) -> None:
        """Increments the occupancy counter for the drone's current connection.

        Args:
            drone_id: Index of the drone in self.drones.
        """
        drone = self.drones[drone_id]

        key = self._make_key(
            drone.path[drone.steps - 1],
            drone.path[drone.steps],
        )

        self.conn_occupancy[key] += 1

    def release_old_connection(self, drone_id: int) -> None:
        """Decrements the occupancy counter for the drone's previous
            connection.

        Does nothing if the drone has no previous hub (first move).

        Args:
            drone_id: Index of the drone in self.drones.

        Raises:
            ValueError: If connection occupancy would go negative.
        """
        drone = self.drones[drone_id]

        if drone.prev_hub is None:
            return

        current_hub = drone.path[drone.steps - 1]
        key = self._make_key(drone.prev_hub, current_hub)

        self.conn_occupancy[key] -= 1

        if self.conn_occupancy[key] < 0:
            raise ValueError(f"Negative occupancy for {key}")

    def check_availability(self, drone_id: int) -> bool:
        """Checks whether a drone can move to its next hub this turn.

        Validates both connection capacity and hub capacity. Restricted
        zones are allowed to be full since the drone will still enter
        transit (standby mode handles the 2-turn cost).

        Args:
            drone_id: Index of the drone in self.drones.

        Returns:
            True if the drone can move, False if it must wait.

        Raises:
            KeyError: If the connection key is not found in conn_occupancy.
        """
        drone = self.drones[drone_id]
        # print(f"D{drone_id} {drone.steps - 1} {drone.path}")
        old_hub = drone.path[drone.steps - 1]
        new_hub = drone.path[drone.steps]

        key = self._make_key(old_hub, new_hub)

        occupancy = self.conn_occupancy.get(key)

        if occupancy is None:
            raise KeyError(f"Connection {key} does not exist")

        max_capacity = self.graph.adjacency[old_hub][new_hub]

        if not drone.is_standby:

            if occupancy >= max_capacity:
                return False

            if (
                self.curr_num_drones[new_hub]
                >= self.graph.hubs[new_hub].metadata.max_drones
            ):
                return (
                    self.graph.hubs[new_hub].metadata.zone == "restricted"
                )

        return True

    def give_turns(self, drone_id: int) -> None:
        """Assigns turn_allowed to a drone if it has not started moving yet.

        Sets turn_allowed to 2 for restricted zones and 1 for all others.
        Also releases the drone's previous connection at this point.

        Args:
            drone_id: Index of the drone in self.drones.
        """
        drone = self.drones[drone_id]

        new_hub = drone.path[drone.steps]

        if drone.turn_allowed == 0:
            zone = self.graph.hubs[new_hub].metadata.zone
            drone.turn_allowed = 2 if zone == "restricted" else 1
            self.release_old_connection(drone_id)

    def traverse(self, drone_id: int) -> str:
        """Moves a drone one step along its path and returns the output string.

        Handles normal moves, restricted zone transit (2-turn standby),
        and hub/connection occupancy updates.

        Args:
            drone_id: Index of the drone in self.drones.

        Returns:
            Formatted movement string e.g. "D1-hub" or "D1-old-new" for
                transit.
        """
        drone = self.drones[drone_id]

        old_hub = drone.path[drone.steps - 1]
        new_hub = drone.path[drone.steps]

        self.give_turns(drone_id)

        if drone.turn_allowed > 0 and not drone.is_standby:
            self.curr_num_drones[old_hub] -= 1
            self.add_connection(drone_id)
            drone.is_standby = drone.turn_allowed == 2

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

        return f"D{drone_id + 1}-{self.paint(new_hub)}"

    def simulate(self) -> None:
        """Runs the full simulation until all drones are delivered.

        Each turn, every undelivered drone attempts to move. If blocked,
        it tries to switch paths. If still blocked, it waits. Delivered
        drones release their last connection and are skipped in future turns.

        Prints one line per turn in the format:
            Turn N: D1-hub D2-hub ...
        """
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
                    if (
                        not self.change_path(index)
                    ):
                        continue

                drone_paths.append(self.traverse(index))
                drone.check_deliverance()

            print(f"Turn {turn}: {' '.join(drone_paths)}")
