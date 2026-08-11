#!/bin/bash

set -e

echo "Initializing SentinelOps Kubernetes SRE Agent setup"

############################################
# 1. Verify Docker
############################################

echo "Checking Docker..."

if ! docker info > /dev/null 2>&1; then
  echo "Docker is not running. Please start Docker Desktop."
  exit 1
fi

############################################
# 2. Start Infrastructure Services
############################################

echo "Starting Postgres and Redis containers..."

docker compose up -d postgres redis

############################################
# 3. Wait for Postgres
############################################

echo "Waiting for Postgres to be ready..."

timeout=60
counter=0

until docker compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; do

  counter=$((counter + 1))

  if [ $counter -gt $timeout ]; then
    echo "Postgres failed to start within ${timeout} seconds"
    docker compose logs postgres
    exit 1
  fi

  echo "Postgres not ready (${counter}/${timeout})"
  sleep 1

done

echo "Postgres is ready"

############################################
# 4. Create Database and Role (Idempotent)
############################################

echo "Creating database and role if not present..."

docker compose exec -T postgres psql -U postgres -d postgres << EOF

DO \$\$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_roles WHERE rolname = 'k8s-agent'
   ) THEN
      CREATE ROLE "k8s-agent"
      WITH LOGIN PASSWORD 'password'
      SUPERUSER CREATEDB;
   END IF;
END
\$\$;

SELECT 'CREATE DATABASE sre_agent OWNER "k8s-agent"'
WHERE NOT EXISTS (
   SELECT FROM pg_database WHERE datname = 'sre_agent'
)\gexec

EOF

echo "Database configuration complete"

############################################
# 5. Verify Database Authentication
############################################

echo "Validating database access..."

timeout_role=30
counter_role=0

until docker compose exec -T postgres \
psql -U "k8s-agent" -d "sre_agent" -c "SELECT 1" > /dev/null 2>&1; do

  counter_role=$((counter_role + 1))

  if [ $counter_role -gt $timeout_role ]; then
    echo "Database authentication failed"
    docker compose logs postgres
    exit 1
  fi

  echo "Waiting for database authentication (${counter_role}/${timeout_role})"
  sleep 1

done

echo "Database authentication successful"

############################################
# 6. Wait for Redis
############################################

echo "Waiting for Redis..."

redis_timeout=30
redis_counter=0

until docker compose exec -T redis redis-cli ping | grep -q PONG; do

  redis_counter=$((redis_counter + 1))

  if [ $redis_counter -gt $redis_timeout ]; then
    echo "Redis failed to start"
    docker compose logs redis
    exit 1
  fi

  echo "Redis not ready (${redis_counter}/${redis_timeout})"
  sleep 1

done

echo "Redis is ready"

############################################
# 7. Setup Python Environment
############################################

echo "Setting up Python virtual environment..."

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

############################################
# 8. Upgrade Python Tools
############################################

echo "Upgrading Python tooling..."

pip install --upgrade pip setuptools wheel

############################################
# 9. Install Dependencies
############################################

echo "Installing project dependencies..."

pip install -r requirements.txt

############################################
# 10. Run Database Migrations
############################################

echo "Running database migrations..."

alembic upgrade head

echo "Database migrations completed"

############################################
# 11. Verify Ollama Installation
############################################

echo "Checking Ollama installation..."

if ! command -v ollama &> /dev/null
then
  echo "Ollama is not installed. Install it from https://ollama.com"
  exit 1
fi

############################################
# 12. Verify Ollama Server
############################################

echo "Checking Ollama server..."

if ! curl -s --connect-timeout 2 http://localhost:11434/api/tags > /dev/null; then
  echo "Ollama server is not running."
  echo "Start it using:"
  echo ""
  echo "    ollama serve"
  echo ""
fi

############################################
# 13. Verify SentinelOps AI Model
############################################

echo "Checking SentinelOps AI model..."

if ollama list | grep -q "sre-agent:latest"; then
  echo "SentinelOps model is installed"
else
  echo "SentinelOps model not found"
  echo ""
  echo "Create the model using:"
  echo ""
  echo "    ollama create sre-agent -f Modelfile"
  echo ""
fi

############################################
# 14. Verify Kubernetes Access
############################################

echo "Checking Kubernetes access..."

if command -v kubectl &> /dev/null; then
  if kubectl cluster-info > /dev/null 2>&1; then
    echo "Kubernetes cluster is reachable"
  else
    echo "kubectl installed but cluster is not configured"
  fi
else
  echo "kubectl is not installed"
fi

############################################
# 15. Prepare Logs Directory
############################################

mkdir -p logs

############################################
# 16. Final System Check
############################################

echo "Infrastructure status"

docker compose ps

############################################
# Setup Complete
############################################

echo ""
echo "SentinelOps setup completed successfully"
echo ""
echo "Next steps:"
echo ""
echo "1. Ensure Ollama server is running:"
echo "   ollama serve"
echo ""
echo "2. Activate environment:"
echo "   source .venv/bin/activate"
echo ""
echo "3. Start the SRE agent:"
echo "   ./run_agent.sh"
echo ""