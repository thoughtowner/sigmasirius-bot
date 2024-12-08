#!/usr/bin/env bash

exec python3 -m uvicorn src.app:create_app --factory --host 0.0.0.0

# без exec
# 1 - startup.sh
# 2 - python3
#
# c exec
# 1 - python3