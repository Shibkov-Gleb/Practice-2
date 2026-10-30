PYTHON ?= python3

.PHONY: run test build check lint demo-errors demo-graphs

run:
	$(PYTHON) -B -m src.main --config examples/config.xml

test:
	$(PYTHON) -B -m unittest discover -s tests -v

build:
	$(PYTHON) -m compileall -q -b src

check:
	$(PYTHON) -B -m tools.check_style

lint:
	$(PYTHON) -B -m flake8 src tests tools

demo-errors:
	$(PYTHON) -B -m tools.demo_errors

demo-graphs:
	$(PYTHON) -B -m tools.demo_graphs
