#!/bin/bash
echo "🔄 Updating CppUTest Generator and Restarting Service"
# Copy the updated main.py
docker cp main.py cpputest-generator:/app/main.py

# Restart the container
docker-compose restart cpputest-generator

# Wait for it to be ready
./wait_for_service.sh