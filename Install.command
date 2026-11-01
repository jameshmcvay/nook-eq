#!/bin/sh
cd "$(dirname "$0")" || exit 1
printf 'AirPort hostname [airport-express.local]: '
read -r nook_host
python3 install.py --host "${nook_host:-airport-express.local}"
printf '\nPress Return to close.'
read -r nook_done
