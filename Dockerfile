FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN adduser --disabled-password --gecos "" --uid 1000 app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY --chown=app:app backend/ backend/
COPY --chown=app:app index.html config.json projects.json ./
COPY --chown=app:app fonts/ fonts/
COPY --chown=app:app images/ images/
COPY --chown=app:app completed_work/ completed_work/

USER app
EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
