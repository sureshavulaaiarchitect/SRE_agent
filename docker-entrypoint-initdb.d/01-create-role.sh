#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER "k8s-agent" WITH SUPERUSER PASSWORD '${POSTGRES_PASSWORD}';
    CREATE DATABASE sre_agent OWNER "k8s-agent";
EOSQL
