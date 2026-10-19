# BlockProbe developer tasks (PRD section 11).
# Only setup and test do real work in this plan; the other targets call
# blockprobe subcommands that later plans add.

.PHONY: setup quick full matrix test demo

OPENMINION_VERSIONS ?= 0.1.3,0.1.4

setup:
	python -m pip install -e ".[dev,probe]"

quick:
	blockprobe run --profile quick

full:
	blockprobe run --profile full

matrix:
	blockprobe matrix --versions $(OPENMINION_VERSIONS)

test:
	python -m pytest tests -v

demo:
	blockprobe run --profile quick --analyze
