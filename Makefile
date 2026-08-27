.PHONY: install lint

install:
	pip install -e .

lint:
	llmlang check .
