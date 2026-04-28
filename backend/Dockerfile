# Stage 1: pull static FFmpeg binary (avoids apt-get failures on Railway)
FROM mwader/static-ffmpeg:6.1 AS ffmpeg

# Stage 2: runtime image
FROM python:3.11-slim

# Copy FFmpeg + FFprobe static binaries — no apt-get needed
COPY --from=ffmpeg /ffmpeg  /usr/local/bin/ffmpeg
COPY --from=ffmpeg /ffprobe /usr/local/bin/ffprobe

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
