#!/bin/bash

echo "⏳ Waiting for CppUTest Generator to be ready..."

MAX_ATTEMPTS=60
ATTEMPT=0
SUCCESS=false

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    ATTEMPT=$((ATTEMPT + 1))
    
    # Try to connect
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null)
    
    if [ "$RESPONSE" = "200" ]; then
        echo "✅ Service is ready!"
        SUCCESS=true
        break
    fi
    
    echo -n "."
    sleep 2
done

echo ""

if [ "$SUCCESS" = true ]; then
    echo ""
    echo "Service Details:"
    curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null
    exit 0
else
    echo "❌ Service did not become ready in time"
    echo ""
    echo "Checking logs:"
    docker-compose logs cpputest-generator --tail=20
    exit 1
fi