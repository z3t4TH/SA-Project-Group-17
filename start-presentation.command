#!/bin/zsh
cd "${0:A:h}"
exec python3 app.py --mode presentation --port 8002
