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

.PHONY: reverse demo-reverse

reverse:
	$(PYTHON) -B -m src.reverse --config examples/reverse_diamond.xml

demo-reverse:
	$(PYTHON) -B -m tools.demo_reverse

.PHONY: demo-visuals compare-npm

demo-visuals:
	mkdir -p output
	$(PYTHON) -B -m src.main --config examples/visual_is_number.xml
	$(PYTHON) -B -m src.main --config examples/visual_is_odd.xml
	$(PYTHON) -B -m src.main --config examples/visual_types_node.xml

compare-npm:
	$(PYTHON) -B -m tools.compare_npm

.PHONY: audit

audit:
	$(PYTHON) -B -m tools.check_repository
