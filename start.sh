#!/bin/bash
# start.sh - Quick start script (after initial setup)
# Use this to start services after running setup.sh once

echo "🚀 Starting CppUTest Generator"
echo "==============================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if already set up
if [ ! -f ".env" ]; then
    echo -e "${RED}✗ Not set up yet${NC}"
    echo -e "${YELLOW}Run ./setup.sh first${NC}"
    exit 1
fi

# Start services
echo -e "${YELLOW}Starting services...${NC}"
docker-compose up -d

# Wait for health
echo -e "${YELLOW}Waiting for services...${NC}"
sleep 5

MAX_ATTEMPTS=20
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "\n${GREEN}✅ Services ready!${NC}"
        
        # Show status
        HEALTH=$(curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null)
        echo "$HEALTH"
        
        echo -e "\n${GREEN}Open: http://localhost:8000${NC}"
        exit 0
    fi
    ATTEMPT=$((ATTEMPT + 1))
    echo -n "."
    sleep 2
done

echo -e "\n${RED}✗ Services failed to start${NC}"
echo -e "${YELLOW}Check logs: docker-compose logs -f${NC}"
exit 1