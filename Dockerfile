# RECAP — AI Meeting Assistant
FROM python:3.11-slim

# ffmpeg is required by pydub/yt-dlp for audio extraction & conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching on rebuilds)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

# Render (and most platforms) inject $PORT; default to 8000 for local runs
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend:app --host 0.0.0.0 --port ${PORT}"]
