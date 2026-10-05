#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier
printf '0' > /logs/verifier/reward.txt

cd /tests || exit 0
pytest test_output.py --ctrf=/logs/verifier/ctrf.json -q
status=$?

if [ "$status" -eq 0 ]; then
    printf '1' > /logs/verifier/reward.txt
fi

exit 0
