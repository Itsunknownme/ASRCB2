FROM python:3.10-slim-bullseye

# Install required system-level packages
RUN apt update && apt install -y \
    git \
    curl \
    build-essential \
    pkg-config \
    ffmpeg \
    libgl1 \
    && apt clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r /requirements.txt

# Set bot directory
WORKDIR /fwdbot

# Copy all files
COPY . /fwdbot

# Render needs a web port
ENV PORT=10000
EXPOSE 10000

# Permission for start.sh
RUN chmod +x /fwdbot/start.sh

# Start script
CMD ["/bin/bash", "/fwdbot/start.sh"]
