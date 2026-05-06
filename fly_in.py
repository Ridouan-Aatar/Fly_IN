from main import Fly_In_Config, Config_Hub, Config_Connection, State
import heapq

class Drone:
    _id_counter = 0  # class-level counter (your version mutates shared state oddly)

    def __init__(self, start_hub: Config_Hub, end_hub: Config_Hub) -> None:
        Drone._id_counter += 1
        self.id: int = Drone._id_counter
        self.curr_hub: Config_Hub = start_hub
        self.end_hub: Config_Hub = end_hub
        self.steps = 0
        self.path: list[Config_Hub] = []
        self.isstandby: bool = False
        self.delivered: bool = False

    def check_deliverance(self):
        self.delivered = self.curr_hub == self.end_hub

    def __repr__(self) -> str:
        return f"D{self.id}@{self.curr_hub.name}"


class Graph:
    def __init__(self, config: Fly_In_Config):
        self.config = config
        self.drones: list[Drone] = [
            Drone(config.start_hub, config.end_hub)
            for _ in range(config.nb_drones)
        ]

        self.hubs = {hub.name: hub for hub in self.config.hubs}
        self.connections = self.config.connections
        self.adjacency = self.connection_to_adjacency()
        self.paths = self.get_k_paths(3) # TODO this is hardcoded K


    def connection_to_adjacency(self):
        res = {}
        for hub in self.config.hubs:
            if hub.metadata.zone == "blocked":
                continue
            res[hub.name] = []
            for connection in self.config.connections:
                if (hub.name == connection.hub1.name and
                        connection.hub2.metadata.zone != "blocked"):
                    res[hub.name].append((connection.hub2,
                                          connection.max_link_capacity))
                if (hub.name == connection.hub2.name and
                        connection.hub1.metadata.zone != "blocked"):
                    res[hub.name].append((connection.hub1,
                                          connection.max_link_capacity))
        return res

    def dijkstra(self, penalty_nodes=None, penalty_edges=None) -> list[str] | None: # TODO definetly i will change it
        penalty_nodes = penalty_nodes or {}
        penalty_edges = penalty_edges or {}

        start = self.config.start_hub.name
        end = self.config.end_hub.name

        cost_so_far: dict[str, float] = {start: 0}
        came_from: dict[str, str | None] = {start: None}
        heap: list[tuple[float, str]] = [(0, start)]

        while heap:
            current_cost, current = heapq.heappop(heap)

            if current == end:
                # reconstruct path
                path = []
                while current is not None:
                    path.append(current)
                    current = came_from[current]
                return list(reversed(path))

            if current_cost > cost_so_far[current]:
                continue

            for neighbor, conn in self.adjacency[current]:
                neighbor_name = neighbor.name

                # 🔥 base cost
                base_cost = 2 if neighbor.metadata.zone == "restricted" else 1

                # 🔥 penalties
                node_penalty = penalty_nodes.get(neighbor_name, 0)
                edge_key = tuple(sorted((current, neighbor_name)))
                edge_penalty = penalty_edges.get(edge_key, 0)

                # 🔥 final cost
                cost = base_cost + node_penalty + edge_penalty
                new_cost = current_cost + cost

                if new_cost < cost_so_far.get(neighbor_name, float("inf")):
                    cost_so_far[neighbor_name] = new_cost
                    came_from[neighbor_name] = current
                    heapq.heappush(heap, (new_cost, neighbor_name))

        return None

    def get_k_paths(self, k: int):
        penalty_nodes = {}

        # K = 3  # number of paths you want
        paths = []
        for _ in range(k):
            path = self.dijkstra(penalty_nodes=penalty_nodes)

            if not path:
                break

            paths.append(path)

            # 🔥 increase penalty to force diversity
            for node in path:
                penalty_nodes[node] = penalty_nodes.get(node, 0) + 2
        return paths

class Fly_In:
    def __init__(self, graph: Graph):
        self.graph = graph
        self.drones = sorted(self.graph.drones, key=(lambda x: x.id))
        self.curr_num_drones = {hub.name: 0 for hub in self.graph.hubs.values()}
        self.paths = self.graph.paths

    def all_delivered(self):
        return all(drone.delivered for drone in self.drones)

    def traverse(self, id, new_hub):
        old_hub = self.drones[id].curr_hub
        if self.drones[id].isstandby:
            # self.drones[id].isstandby = False
            return f"D{id}-({old_hub.name}-{new_hub.name})"
        self.drones[id].curr_hub = new_hub
        self.drones[id].check_deliverance()
        self.drones[id].steps += 1
        return f"D{id}-{new_hub.name}"

    def simulate(self):
        path = self.paths[0]
        # step = 1

        turn = 0

        while not self.drones[0].delivered:
            turn += 1
            d_paths = []
            step = self.drones[0].steps
            name_hub = path[step]
            hub = self.graph.hubs[name_hub]
            
            if hub.metadata.zone == "restricted" and not self.drones[0].isstandby:
                self.drones[0].isstandby = True
            elif self.drones[0].isstandby:
                self.drones[0].isstandby = False

            d_path = self.traverse(0, hub)
            d_paths.append(d_path)
            print(f"Turn {turn}: {" ".join(d_paths)}")

        # while not self.all_delivered():
            # for drone in self.drones:
            #     pass



if __name__ == "__main__":
    config = Fly_In_Config("maps/medium/02_circular_loop.txt")
    config.parse()

    graph = Graph(config)
    print(f"{graph.connection_to_adjacency()['start']}")
    # path = graph.dijkstra()

    # print(" -> ".join(path))    

    fly = Fly_In(graph)
    # print(fly.all_delivered())
    fly.simulate()
    # penalty_nodes = {}
    # paths = []

    # K = 3  # number of paths you want

    # for _ in range(K):
    #     path = graph.dijkstra(penalty_nodes=penalty_nodes)

    #     if not path:
    #         break

    #     paths.append(path)

    #     # 🔥 increase penalty to force diversity
    #     for node in path:
    #         penalty_nodes[node] = penalty_nodes.get(node, 0) + 2

    # for path in paths:
    #     print(path)
    #     print()
