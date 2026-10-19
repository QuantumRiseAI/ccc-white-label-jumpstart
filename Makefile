# Serif jumpstarts. Python 3.9+, stdlib only; the tests need Node and Playwright.
PERIOD ?= aug2026

.PHONY: package build test clean

package:  ## the two Claude Project upload folders: claude-projects/ (committed) and out/dist/ (with NetSuite's lists and a .zip)
	python3 tools/package.py

build:    ## a close month from inputs/$(PERIOD)/, run as the Projects run it
	bash tools/build.sh $(PERIOD)

test:     ## claude-projects/ up to date, the console tests, accepted exceptions, the export readers, the Income Statement tie, the prepaid and capital screens, every account number named, and no table scrolling sideways
	python3 tools/package.py --check
	node tests/test_console.js
	python3 tests/test_exceptions.py
	python3 tests/test_readers.py
	python3 tests/test_tie.py
	python3 tests/test_screens.py
	python3 tests/test_passthrough.py
	python3 tests/test_facts.py
	node tests/test_flux_coding.js
	node tests/audit_account_names.js
	node tests/audit_table_width.js 1280

clean:
	rm -rf out/dist
