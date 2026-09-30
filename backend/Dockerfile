FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml ./
COPY requirements.lock ./
COPY app ./app
RUN pip install -c requirements.lock .
COPY alembic.ini ./
COPY migrations ./migrations
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]

FROM base AS test
USER root
RUN pip install -c requirements.lock '.[dev]'
COPY tests ./tests
USER appuser
CMD ["pytest", "-q"]

FROM base AS runtime
