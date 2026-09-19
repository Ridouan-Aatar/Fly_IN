UV = python3 -m uv
PYTHON = $(UV) run python3

CACHE_DIR = .uv_cache
VENV = .venv
MAP ?= maps/easy/01_linear_path.txt

SOURCES = main.py fly_in.py parser.py painting.py

run:
	$(PYTHON) main.py $(MAP)

install:
	pip install uv --quiet
	$(UV) sync --cache-dir $(CACHE_DIR)


debug:
	$(PYTHON) -m pdb main.py $(MAP)

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -name "*.pyc" -delete

fclean: clean
	rm -rf $(CACHE_DIR)
	rm -rf $(VENV)

lint:
	$(PYTHON) -m flake8 $(SOURCES) --exclude=$(VENV)
	$(PYTHON) -m mypy $(SOURCES) --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

lint-strict:
	$(PYTHON) -m flake8 $(SOURCES)
	$(PYTHON) -m mypy $(SOURCES) --strict

.PHONY: install run debug clean fclean lint lint-strict