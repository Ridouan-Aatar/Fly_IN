from main import Fly_In_Config, Config_Hub, Config_Connection, State
import heapq


class Drone():
    _id_counter = 0  # class-level counter (your version mutates shared state oddly)

    def __init__(self, start_hub: Config_Hub, end_hub: Config_Hub, path: list) -> None:

        Drone._id_counter += 1
        self.id: int = Drone._id_counter
        self.curr_hub: Config_Hub = start_hub
        self.end_hub: Config_Hub = end_hub
        self.steps = 1
        self.path: list[Config_Hub] = path
        self.isstandby: bool = False
        self.turn_allowed: int = 0 # 0 no movement allowed  1 normal move  2 restricted moves
        self.delivered: bool = False
        self.skip_turn: bool = False

    def check_deliverance(self):
        # print(f"{self.curr_hub.name} === {self.end_hub.name}")
        # self.delivered = self.curr_hub.name == self.end_hub.name
        self.delivered = self.path[self.steps - 1] == self.end_hub.name



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
        self.paths = sorted(self.get_k_paths(4), key=self.path_cost)[:1] # TODO this is hardcoded K
        for path in self.paths:
            print(len(path))
        self.drones: list[Drone] = [
            Drone(config.start_hub, config.end_hub, self.paths[0])
            for _ in range(config.nb_drones)
        ]
    def path_cost(self, path: list[str]) -> int:
        return sum(
            2 if self.hubs[h].metadata.zone == "restricted" else 1
            for h in path[1:]  # skip start hub
        )
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
        self.curr_num_drones[self.graph.start_hub.name] = self.graph.config.nb_drones
        # self.curr_num_drones[self.graph.end_hub.name] = self.graph.config.nb_drones
        self.paths = self.graph.paths

    def all_delivered(self):
        return all(drone.delivered for drone in self.drones)

    def change_path(self, id):
        drone = self.drones[id]
        old_path = drone.path
        step = drone.steps
        old_hub_name = old_path[step - 1]

        for path in self.paths:
            if drone.path != path:
                if old_hub_name in path:
                    step = path.index(old_hub_name)
                    drone.steps = step + 1
                    drone.path = path
                    return True

        return False

    # def check_num_connectivity(self, id):

    def add_connection(self, id):
        drone = self.drones[id]
        step = drone.steps
        old_hub_name = drone.path[step - 1]
        new_hub_name = drone.path[step]
        key = tuple(sorted((old_hub_name, new_hub_name)))
        # print(f"D{id + 1} add connection {key}")
        self.conn_occupancy[key] += 1
    
    def release_connection(self, id):
        drone = self.drones[id]
        step = drone.steps
        old_hub_name = drone.path[step - 1]
        new_hub_name = drone.path[step]
        key = tuple(sorted((old_hub_name, new_hub_name)))
        # print(f"D{id + 1} release connection {key}")
        self.conn_occupancy[key] -= 1
        if self.conn_occupancy[key] < 0:
            raise ValueError("conn_occupancy reaches negativity")

    def modify_connectivity(self, id, mode: bool = True):
        hubs = self.graph.hubs
        drone = self.drones[id]
        step = drone.steps
        oldest_hub_name = None if step < 2 else drone.path[step - 2]
        old_hub_name = drone.path[step - 1]
        new_hub_name = drone.path[step]

        if mode:
            key = tuple(sorted((old_hub_name, new_hub_name)))
            self.conn_occupancy[key] += 1 if new_hub_name != self.graph.end_hub.name else 0
        
        if oldest_hub_name:
            key = tuple(sorted((old_hub_name, oldest_hub_name)))
            self.conn_occupancy[key] -= 1

    def check_availability(self, id):
        drone = self.drones[id]
        hubs = self.graph.hubs
        step = drone.steps
        old_hub_name = drone.path[step - 1]
        new_hub_name = drone.path[step]

        key = tuple(sorted((old_hub_name, new_hub_name)))
        
        # print(self.conn_occupancy, key)

        conn_capacity = self.conn_occupancy.get(key)
        if conn_capacity is None:
            raise KeyError(f"This {key} doesnt exist !!")

        hard_conn_capacity = self.graph.adjacency[old_hub_name][new_hub_name] # maybe i should do the same as above

        # print(conn_capacity, hard_conn_capacity)


        if not drone.isstandby:
            # print(id,"hello")
            if conn_capacity >= hard_conn_capacity:
                return False
            # print(id,"helloXXXXXX")
            # print(id,"hello")
            # if hubs[new_hub_name].metadata.zone == "restricted":
            #     # print("i can go")
            #     return True

            # print(id, self.curr_num_drones[new_hub_name],hubs[new_hub_name].metadata.max_drones )
            if self.curr_num_drones[new_hub_name] >= hubs[new_hub_name].metadata.max_drones:
                return hubs[new_hub_name].metadata.zone == "restricted"

        return True

    def give_turns(self, id):
        hubs = self.graph.hubs
        drone = self.drones[id]
        step = drone.steps
        new_hub_name = drone.path[step]

        if drone.turn_allowed == 0:
            drone.turn_allowed = (2 if hubs[new_hub_name].metadata.zone == "restricted" else 1)

    def traverse(self, id):
        hubs = self.graph.hubs
        drone = self.drones[id]
        step = drone.steps
        old_hub_name = drone.path[step - 1]
        new_hub_name = drone.path[step]

        self.give_turns(id)

        if drone.turn_allowed > 0 and not drone.isstandby:
            self.curr_num_drones[old_hub_name] -= 1
            self.add_connection(id)
            drone.isstandby = drone.turn_allowed == 2
        
        drone.turn_allowed -= 1
        
        if drone.turn_allowed == 0:

            self.curr_num_drones[new_hub_name] += 1
            # self.modify_connectivity(id)
            self.release_connection(id)

            drone.isstandby = False

        
        if drone.turn_allowed:
            return (f"D{id+1}-{old_hub_name}-{new_hub_name}")
        else:
            drone.steps += 1
            return (f"D{id+1}-{new_hub_name}")



    def simulate(self):
        # self.drones[0].path = self.paths[0]
        # step = 1

        turn = 0

        while not all(drone.delivered for drone in self.drones[:]):
            turn += 1
            d_paths = []
            for i, drone in enumerate(self.drones[:]):
                
                if drone.delivered:
                    continue
                if not self.check_availability(i):
                    # print(f"D{i+ 1} not moving yet")
                    # continue
                    if not self.change_path(i):
                        continue
                    else:
                        if not self.check_availability(i):
                            continue
                    
                
                # if :
                #     print("there is restrictions")
                # else:
                #     print("no restrictions")
                
                d_path = self.traverse(i)
                d_paths.append(d_path)
                # print(self.conn_occupancy)

                self.drones[i].check_deliverance()
                
            print(f"Turn {turn}: {" ".join(d_paths)}")

            # print([drone.delivered for drone in self.drones[:2]])
            # print(self.drones[1].path[self.drones[1].steps])
            # print(self.curr_num_drones)
            # break

        # while not self.all_delivered():
            # for drone in self.drones:
            #     pass


import sys
if __name__ == "__main__":

    config = Fly_In_Config(sys.argv[1])
    config.parse()

    graph = Graph(config)
    # print(f"{graph.connection_to_adjacency()}")
    # path = graph.dijkstra()

    # print(" -> ".join(path))    
    for path in graph.paths:
        print(f"{path} ====> {len(path)}")

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
