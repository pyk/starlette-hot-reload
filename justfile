check:
    uv run ruff check
    uv run ty check

fmt:
    uv run ruff fmt --write .

test:
    uv run pytest
