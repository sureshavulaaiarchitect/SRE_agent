#!/bin/bash
set -e

echo "Starting SentinelOps Kubernetes SRE Agent"

############################################
# Resolve Project Root
############################################

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

############################################
# Verify Virtual Environment
############################################

if [ ! -d ".venv" ]; then
  echo "Virtual environment not found. Run setup.sh first."
  exit 1
fi

echo "Activating virtual environment"
source .venv/bin/activate

############################################
# Verify Docker
############################################

if ! docker info > /dev/null 2>&1; then
  echo "Docker is not running"
  exit 1
fi

############################################
# Show Infrastructure Status
############################################

echo "Checking infrastructure services"
docker compose ps

############################################
# Stop Previous API Instance
############################################

PORT=8080

if lsof -i :$PORT > /dev/null 2>&1; then
  echo "Stopping previous SentinelOps server on port $PORT"
  PID=$(lsof -t -i:$PORT)
  kill $PID
  sleep 2
fi

############################################
# Verify Ollama Installation
############################################

if ! command -v ollama > /dev/null 2>&1; then
  echo "Ollama is not installed"
  exit 1
fi

############################################
# Ensure Ollama Server Running
############################################

echo "Checking Ollama server"

if ! curl -s --connect-timeout 2 http://localhost:11434/api/tags > /dev/null; then
  echo "Ollama server not running. Starting Ollama..."
  ollama serve > /dev/null 2>&1 &
  sleep 6
else
  echo "Ollama server already running"
fi

############################################
# Verify SentinelOps Model
############################################

if ollama list | grep -q "sre-agent:latest"; then
  echo "SentinelOps AI model detected"
else
  echo "SentinelOps model not found"
  echo "Create the model using:"
  echo "ollama create sre-agent -f Modelfile"
  exit 1
fi

############################################
# Verify Kubernetes Access
############################################

if command -v kubectl > /dev/null 2>&1; then
  if kubectl cluster-info > /dev/null 2>&1; then
    echo "Kubernetes cluster reachable"
  else
    echo "kubectl installed but cluster not configured"
  fi
else
  echo "kubectl not installed"
fi

############################################
# Start SentinelOps API
############################################

if [ ! -f "main.py" ]; then
  echo "main.py not found in project root"
  exit 1
fi

echo "Starting SentinelOps API"

python main.py