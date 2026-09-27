FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY apps/api/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock
COPY apps/api apps/api
COPY migrations migrations
COPY prompts prompts
COPY config config
COPY scripts scripts
RUN pip install --no-cache-dir --no-deps -e apps/api && useradd --uid 10001 --create-home genius && mkdir /app/data && chown genius:genius /app/data
USER genius
CMD ["python", "-m", "uvicorn", "margin.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
