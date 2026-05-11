.PHONY: api worker frontend redis dev

PYTHON := .venv/bin/python

redis:
	redis-server --daemonize yes

api:
	PYTHONPATH=src $(PYTHON) -m uvicorn giae_api.main:app --reload --port 8000

worker:
	PYTHONPATH=src $(PYTHON) -m celery -A giae_api.worker.celery_app worker --loglevel=info --pool=threads --concurrency=4

frontend:
	cd frontend && bun run dev

dev: redis
	@echo "Starting API, Celery worker, and Next.js frontend..."
	@trap 'kill 0' INT; \
	PYTHONPATH=src $(PYTHON) -m uvicorn giae_api.main:app --reload --port 8000 & \
	PYTHONPATH=src $(PYTHON) -m celery -A giae_api.worker.celery_app worker --loglevel=warning --pool=threads --concurrency=4 & \
	cd frontend && bun run dev & \
	wait
