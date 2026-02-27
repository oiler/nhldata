#!/bin/bash
# Wrapper for launchd — loads .env and runs the orchestrator.
set -e

cd /Users/jrf1039/files/projects/nhl

# Load API key from .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

exec /Users/jrf1039/.pyenv/versions/3.11.6/bin/python3 v2/orchestrator/runner.py "$@"
