.PHONY: test install run docker-build docker-run

install:
	pip install -e .[dev]

test:
	pytest -v

run:
	uvicorn webhook_relay:app --reload

docker-build:
	docker build -t webhook-relay:latest .

docker-run:
	docker run -p 8000:8000 webhook-relay:latest
