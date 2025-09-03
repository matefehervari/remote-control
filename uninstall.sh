#!/usr/bin/env bash

project_dir="$(realpath $(dirname ${BASH_SOURCE[0]}))"
env_file=".env"
run_file="run.sh"
service_file="$HOME/.config/systemd/user/remote-control.service"

cd $project_dir

echo "Uninstalling remote control..."
echo "Stopping remote-control.service..."

systemctl --user stop remote-control
systemctl --user disable remote-control

echo "Removing service..."
rm $service_file
systemctl --user daemon-reload
systemctl --user reset-failed

echo "Removing generated files..."

rm $env_file
rm $run_file

