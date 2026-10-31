FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml setup.py ./
COPY src/ src/

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "webhook_relay:app", "--host", "0.0.0.0", "--port", "8000"]
