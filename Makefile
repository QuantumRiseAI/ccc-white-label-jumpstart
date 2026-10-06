# Serif jumpstarts. Python 3.9+, stdlib only; the tests need Node and Playwright.
PERIOD ?= aug2026

.PHONY: package build test clean

package:  ## the two Claude Project upload folders, in out/dist/
	python3 tools/package.py

build:    ## a close month from inputs/$(PERIOD)/, run as the Projects run it
	bash tools/build.sh $(PERIOD)

test:     ## the console tests, on consoles/
	node tests/test_console.js

clean:
	rm -rf out/dist
