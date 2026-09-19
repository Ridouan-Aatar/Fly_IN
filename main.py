from parser import Fly_In_Config, ParseError
from fly_in import Graph, Fly_In
import sys


def main() -> None:
    """Entry point for the Fly-in simulation.

    Expects exactly one command-line argument: the path to a map file.
    Parses the file, builds the graph, and runs the simulation.

    Usage:
        python3 main.py <file_path>
    """
    if len(sys.argv) != 2:
        raise Exception("Invalid execution format \n"
                        "run: python3 main.py <file_path>")

    config = Fly_In_Config(sys.argv[1])
    config.parse()
    graph = Graph(config)

    fly = Fly_In(graph)
    fly.simulate()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProgram interrupted")
        sys.exit(130)

    except ParseError as e:
        print(e)
        sys.exit(1)

    except FileNotFoundError as e:
        print(f"File '{e.filename}' not found")
        sys.exit(1)

    except PermissionError as e:
        print(f"Permission denied when opening '{e.filename}'")
        sys.exit(1)

    except OSError as e:
        print(e)
        sys.exit(1)

    # except Exception as e:
    #     print(f"Unexpected error: {e}")
    #     sys.exit(1)
