#!/bin/bash

echo "Starting fake web server on PORT=${PORT}..."
python3 web.py &

echo "Starting Telegram bot..."
python3 main.py &

# Keep container alive forever so Render doesn't stop the service
tail -f /dev/null
