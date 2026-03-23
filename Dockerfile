FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY evals_101 ./evals_101
COPY datasets ./datasets

RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

CMD ["python", "-m", "evals_101.api"]
