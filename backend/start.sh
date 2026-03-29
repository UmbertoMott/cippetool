#!/bin/bash
cd "$(dirname "$0")"
# --loop asyncio: evita uvloop che causa PermissionError su macOS (SIP)
/Users/umbertomottola/Library/Python/3.9/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --loop asyncio
