FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements.txt
COPY src ./src
RUN useradd --uid 10001 --no-create-home researcher
USER researcher
EXPOSE 8000
# Compose publishes this container port only on host loopback.
CMD ["python", "-m", "uvicorn", "src.local_app:app", "--host", "0.0.0.0", "--port", "8000"]
