setup:
	python -m venv .venv
	. .venv/bin/activate && pip install -e .
	. .venv/bin/activate && python -m playwright install --with-deps chromium
	. .venv/bin/activate && crawl4ai-setup

test:
	pytest -q

crawl:
	python -m src.main --limit 100

crawl-no-discovery:
	python -m src.main --limit 100

legacy-reports:
	python -m src.legacy_reports --config config/settings.yaml --sources config/sources.yaml
