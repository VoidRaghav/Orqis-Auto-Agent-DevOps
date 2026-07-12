.PHONY: ci unit integration frontend preflight tier-a tier-b test-agent up

ci: unit integration frontend

up:
	docker compose up --build

unit:
	pytest tests/unit/ tests/test_tenancy.py tests/test_scan_keys.py -v

integration:
	pytest tests/ -m integration -v

frontend:
	cd frontend && npm ci && npm run build

test-agent: preflight tier-a tier-b

preflight:
	python scripts/preflight.py

tier-a:
	pytest tests/test_pipeline_runaway.py -v

tier-b:
	@if [ -n "$$CURSOR_API_KEY" ]; then \
		pytest tests/test_agent_ide_flow.py -v; \
	else \
		echo "SKIP Tier B: CURSOR_API_KEY not set"; \
	fi
