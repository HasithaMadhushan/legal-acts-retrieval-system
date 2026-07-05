FROM python:3.13-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

EXPOSE 8000
# The app also auto-migrates at startup (see app.db.migrate), but running the
# migration explicitly here first gives a clear, separate log step and fails
# fast before the server starts accepting traffic.
#
# Gunicorn supervises one or more uvicorn workers (async, so a slow PDF-processing
# background task in one request doesn't block others on the same worker). Override
# WEB_CONCURRENCY to size workers for the host (a common rule of thumb is 2 x CPU
# cores + 1); it defaults to 2 for small single-instance deployments.
CMD ["sh", "-c", "alembic upgrade head && gunicorn app.main:app --bind 0.0.0.0:8000 --worker-class uvicorn.workers.UvicornWorker --workers ${WEB_CONCURRENCY:-2} --timeout 120 --access-logfile - --error-logfile -"]
