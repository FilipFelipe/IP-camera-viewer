#!/bin/bash
cd "$(dirname "$0")"

if [ ! -f ".venv/bin/activate" ]; then
  echo ".venv not found. Create it first with: python3 -m venv .venv"
  exit 1
fi

source .venv/bin/activate
exec python main.py
