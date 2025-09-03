#!/usr/bin/env bash

project_dir="$(realpath $(dirname ${BASH_SOURCE[0]}))"
service_file="$HOME/.config/systemd/user/remote-control.service"

if ! type poetry; then
    echo "Installing poetry..."
    pip install poetry
fi

cd $project_dir
echo "Installing dependencies..."
/usr/bin/env poetry update

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
API_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))")

echo "RC_HOST=$HOST
RC_PORT=$PORT
API_KEY=$API_KEY" > .env

echo "cd $project_dir && poetry run python ./remote_control.py" > run.sh && \
chmod +x run.sh

echo "Creating service..."
cat > "$service_file" << EOF
[Unit]
Description=Remote Control
After=graphical-session.target

[Service]
WorkingDirectory=$project_dir
ExecStart=/usr/bin/env poetry run python -u remote_control.py
Restart=on-failure

[Install]
WantedBy=default.target
EOF

if [[ $? -ne 0 ]]; then
    echo "Failed to create service unit at $service_file"
    exit 1
fi

echo "Starting service..."
systemctl --user daemon-reload || { echo "Failed to reload systemctl user daemon"; exit 1; }
systemctl --user enable --now remote-control || { echo "Failed to enable remote-control service"; exit 1; }
systemctl --user start remote-control || { echo "Failed to start remote-contorl service"; exit 1; }

echo "Remote Control has been installed successfully!"
