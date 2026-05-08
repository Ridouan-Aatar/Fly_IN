from main import Fly_In_Config, Config_Hub, Config_Connection, State
import heapq

class Drone:
    _id_counter = 0  # class-level counter (your version mutates shared state oddly)

    def __init__(self, start_hub: Config_Hub, end_hub: Config_Hub, path: list) -> None:
        Drone._id_counter += 1
        self.id: int = Drone._id_counter
        self.curr_hub: Config_Hub = start_hub
        self.end_hub: Config_Hub = end_hub
        self.steps = 0
        self.path: list[Config_Hub] = path
        self.isstandby: bool = False
        self.delivered: bool = False

    def check_deliverance(self):
        self.delivered = self.curr_hub == self.end_hub

    def __repr__(self) -> str: # TODO i might not need to do this
        return f"D{self.id}@{self.curr_hub.name}"


class Graph:
    def __init__(self, config: Fly_In_Config):
        self.config = config

        self.start_hub = self.config.start_hub
        self.end_hub = self.config.end_hub
        self.hubs = {hub.name: hub for hub in self.config.hubs}
        # self.curr_drones_hubs = {hub.name: 0 for hub in self.config.hubs}
        self.connections = self.config.connections
        self.adjacency = self.connection_to_adjacency()
        self.paths = self.get_k_paths(3) # TODO this is hardcoded K
        self.drones: list[Drone] = [
            Drone(config.start_hub, config.end_hub, self.paths[0])
            for _ in range(config.nb_drones)
        ]

    def connection_to_adjacency(self):
        res = {}
        for hub in self.config.hubs:
            if hub.metadata.zone == "blocked":
                continue
            res[hub.name] = {}
            for connection in self.config.connections:
                if (hub.name == connection.hub1.name and
                        connection.hub2.metadata.zone != "blocked"):
                    res[hub.name][connection.hub2.name] = connection.max_link_capacity
                if (hub.name == connection.hub2.name and
                        connection.hub1.metadata.zone != "blocked"):
                    res[hub.name][connection.hub1.name] = connection.max_link_capacity
        return res

    def dijkstra(self, penalty_nodes=None, penalty_edges=None) -> list[str] | None: # TODO definetly i will try it on  my own
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

            for neighbor_name, _ in self.adjacency[current].items():
                neighbor = self.hubs[neighbor_name]

                # 🔥 base cost

                if neighbor.metadata.zone == "restricted":
                    base_cost = 2
                elif neighbor.metadata.zone == "priority":
                    base_cost = 0
                else:
                    base_cost = 1

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
        self.conn_occupancy = {
            tuple(sorted((conn.hub1.name, conn.hub2.name))): 0
            for conn in self.graph.config.connections
        }
        print(self.conn_occupancy)
        self.curr_num_drones[self.graph.start_hub.name] = self.graph.config.nb_drones
        # self.curr_num_drones[self.graph.end_hub.name] = self.graph.config.nb_drones
        self.paths = self.graph.paths

    def all_delivered(self):
        return all(drone.delivered for drone in self.drones)

    def check_n_drone_for_connectivity(self, id, new_hub_name):
        if self.drones[id].curr_hub:
            old_hub_name = self.drones[id].curr_hub.name

            if old_hub_name != new_hub_name:

                max_capacity = self.graph.adjacency[old_hub_name][new_hub_name]
                connection = tuple(sorted((old_hub_name, new_hub_name)))
                print(f"{self.conn_occupancy[connection]}  <==>  {max_capacity}")


    def assign_drone_to_hub(self, id, hub_name):

        self.check_n_drone_for_connectivity(id, hub_name)
        new_hub = self.graph.hubs[hub_name]
        if self.curr_num_drones[hub_name] + 1 > new_hub.metadata.max_drones:
            return False
        if self.drones[id].curr_hub:
            old_hub_name = self.drones[id].curr_hub.name
            self.curr_num_drones[old_hub_name] -= 1
            if self.curr_num_drones[old_hub_name] < 0:
                raise ValueError(f"curr_num_drones of {old_hub_name} reaches negativity !!")
        self.drones[id].curr_hub = new_hub
        self.curr_num_drones[hub_name] += 1
        return True

    def traverse(self, id, new_hub):
        if self.drones[id].isstandby:
            old_hub = self.drones[id].curr_hub
            self.drones[id].curr_hub = None
            if old_hub:
                self.curr_num_drones[old_hub.name] -= 1 # TODO this might have problems
            # self.drones[id].isstandby = False
            return f"D{id}-({old_hub.name}-{new_hub.name})"
        # self.drones[id].curr_hub = new_hub
        if not self.assign_drone_to_hub(id, new_hub.name):
            if self.change_path(id, self.drones[id].steps):
                new_hub, self.drones[id].steps = self.change_path(id, self.drones[id].steps)
                self.assign_drone_to_hub(id, new_hub.name)
        self.drones[id].check_deliverance()
        self.drones[id].steps += 1
        return f"D{id}-{new_hub.name}"

    def change_path(self, id, step):
        old_path = self.drones[id].path

        for path in self.paths:
            if old_path != path:
                if old_path[step] in path:
                    self.drones[id].path = path
                    return (path, path.index(old_path[step]))
        return None

    def simulate(self):
        # self.drones[0].path = self.paths[0]
        # step = 1

        turn = 0

        while not all(drone.delivered for drone in self.drones[:2]):
            turn += 1
            d_paths = []
            for i, drone in enumerate(self.drones[:2]):
                step = drone.steps
                name_hub = drone.path[step]
                hub = self.graph.hubs[name_hub]

                # if hub.metadata.max_drones == self.curr_num_drones[0]:
                #     if self.change_path(0, step):
                #         hub = 

                if hub.metadata.zone == "restricted" and not drone.isstandby:
                    drone.isstandby = True
                elif drone.isstandby:
                    drone.isstandby = False

                d_path = self.traverse(i, hub)
                d_paths.append(d_path)
            print(f"Turn {turn}: {" ".join(d_paths)}")
            print(self.curr_num_drones)

        # while not self.all_delivered():
            # for drone in self.drones:
            #     pass



if __name__ == "__main__":
    config = Fly_In_Config("maps/medium/02_circular_loop.txt")
    config.parse()

    graph = Graph(config)
    print(f"{graph.connection_to_adjacency()}")
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
