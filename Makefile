PY ?= python

all: data run

data:
	$(PY) -m qa.generate_data

run:
	$(PY) -m qa.pipeline

test:
	$(PY) -m pytest -q

.PHONY: all data run test
