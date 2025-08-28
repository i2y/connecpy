format:
    uv run ruff check --fix .
    uv run ruff format .

lint:
    uv run ruff format --check .
    uv run ruff check .

typecheck:
    uv run pyright

[working-directory: 'noextras']
test-noextras *args:
    uv run --exact pytest {{args}}

test *args: (test-noextras args)
    uv run pytest {{args}}

check: lint typecheck test

[working-directory: 'conformance']
conformance *args:
    uv run pytest {{args}}

docs:
    uv run mkdocs build

[working-directory: 'site']
docs-serve: docs
    uv run python -m http.server 8000
