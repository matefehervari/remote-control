#!/bin/env bash

if [ ! -d .venv ]; then
    echo "Creating .venv..."
    python3 -m venv .venv
fi

echo "Installing dependencies..."
set -e
source .venv/bin/activate && \
pip install -r requirements.txt
deactivate

echo "Configuring remote-control server..."
PS3='Please select a network: '
ips=($(hostname -I))
ips=("${ips[@]}" 'Quit')
select ip in "${ips[@]}"; do
  case $ip in
    *[0-9]*)
      HOST=$ip
      break
      ;;
    Quit) echo quit
      exit;;
    *) echo Invalid option >&2;;
  esac
done

echo ""
echo "Host set to $REPLY) $ip"

read -p "Server host PORT (Default: 1234): " PORT

if [ -z $PORT ]; then
    PORT=1234
fi

echo "RC_HOST=$HOST
RC_PORT=$PORT" > .env

RC_PATH=$(pwd)
echo "cd $RC_PATH && source ./.venv/bin/activate && ./remote_control.py" > run.sh && \
chmod +x run.sh
