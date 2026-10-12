# Serif jumpstarts. Python 3.9+, stdlib only; the tests need Node and Playwright.
PERIOD ?= aug2026

.PHONY: package build test clean

package:  ## the two Claude Project upload folders, in out/dist/
	python3 tools/package.py

build:    ## a close month from inputs/$(PERIOD)/, run as the Projects run it
	bash tools/build.sh $(PERIOD)

test:     ## the console tests, every account number named, and no table scrolling sideways
	node tests/test_console.js
	node tests/test_flux_coding.js
	node tests/audit_account_names.js
	node tests/audit_table_width.js 1280

clean:
	rm -rf out/dist
