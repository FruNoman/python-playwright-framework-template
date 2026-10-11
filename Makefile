# The commands a person and CI run. Everything else: uv run pytest … (see README).
.PHONY: test check format browsers
test:  ## all tests, parallel
	uv run pytest -n $${TESTS_THREADS:-4}
check: ## style and types — what CI checks
	uv run ruff check . && uv run ruff format --check . && uv run pyright
format:
	uv run ruff format . && uv run ruff check --fix .
browsers: ## the browsers for local runs (once per Playwright version)
	uv run playwright install chromium
