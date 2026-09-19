*This project has been created as part of the 42 curriculum by raatar.*

# Fly-in

## Description

Fly-in is a drone routing simulation system written in Python. The goal is to move
a fleet of drones from a central start hub to a target end hub across a network of
connected zones, in the fewest possible simulation turns.l

The system reads a custom map file format, validates it, builds a weighted graph,
finds optimal paths using Dijkstra's algorithm, and simulates turn-by-turn drone
movement while respecting zone capacity, connection capacity, and movement cost rules.

---

## Instructions

**Requirements**
- Python 3.10+
- `uv`, `flake8`, `mypy`

**Installation**
```bash
make install
```

**Running**
```bash
make run
```

Or with a custom map:
```bash
make run MAP=maps/easy/01_linear_path.txt
```

**Linting**
```bash
make lint
```

**Debug mode**
```bash
make debug
```

---

## Algorithm Choices and Implementation Strategy

### Parsing

The map file is parsed line by line. Each line is validated strictly — unknown
attributes, malformed metadata, duplicate hubs, or missing start/end hubs all
raise a `ParseError` with the exact line number and cause. Pydantic models
(`Config_Hub`, `Config_Connection`, `H_Metadata`) enforce type safety on all
parsed data.

### Graph Construction

An adjacency list is built from the parsed connections, storing `max_link_capacity`
per edge. Blocked zones are excluded from the adjacency list entirely.

### Pathfinding — Dijkstra with Penalty-Based Diversity

A standard Dijkstra finds the shortest path by weighted zone cost:
- `normal` / `priority` zones: cost 1
- `restricted` zones: cost 2
- `blocked` zones: skipped entirely

To find multiple diverse paths, a penalty system progressively increases the cost
of nodes used in previously found paths, forcing Dijkstra to explore alternative
routes. Paths whose total cost deviates more than 5 from the optimal are discarded.
The resulting paths are sorted by total cost.

### Simulation

Each turn, every drone attempts to move to its next hub. Movement is blocked if:
- The destination hub is at full capacity (`max_drones`)
- The connection is at full capacity (`max_link_capacity`)

Restricted zones require 2 turns to traverse. On the first turn the drone enters
the connection (standby). On the second turn it arrives at the destination.

If a drone is blocked, it attempts to switch to an alternative path. If no
alternative is available it waits in place.

Hub occupancy and connection occupancy are tracked per turn to enforce all
capacity constraints simultaneously.

---

## Visual Representation

The `Painting` class provides colored terminal output during the simulation.
Each hub name in the turn output is colored according to its `color` metadata
field, giving immediate visual feedback about which zones drones are passing
through.

Zone types are distinguishable at a glance:
- `restricted` zones typically appear in warning colors (orange, red)
- `priority` zones in positive colors (green, gold)
- `blocked` zones are excluded from output entirely

The turn-by-turn output follows the required format:
```
Turn 1: D1-waypoint1 D2-waypoint1
Turn 2: D1-waypoint2 D2-waypoint2
Turn 3: D1-goal D2-goal
```

Drones in transit across restricted zones display the connection they are crossing:
```
Turn 1: D1-start-restricted_zone
Turn 2: D1-restricted_zone
```

---

## Resources

**Graph theory and pathfinding**
- Dijkstra's algorithm — https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm


**AI usage**

AI was used during this project for the following tasks:
- Debugging mypy type errors in Pydantic model validators
- Getting initial ideas on simulation architecture (turn loop structure,
  occupancy tracking approach)
- Reviewing error message clarity in the parser

All generated suggestions were reviewed, understood, and adapted before use.
No code was copied without full comprehension of its behavior.