# Example build context: skill root. Pin the base image digest and apt snapshot in production.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY scripts/ /app/scripts/
USER 10001:10001
ENTRYPOINT ["python3", "/app/scripts/audio_qc.py"]
