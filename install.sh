#!/bin/bash
# install.sh - A setup script for the Discord VPS creator bot.

set -e

echo "--- Installing essential packages and Python dependencies ---"
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install python3 python3-pip python3-venv tmux -y
python3 -m venv venv
source venv/bin/activate
pip install discord.py python-dotenv firebase-admin

echo "--- Installing Docker ---"
sudo apt-get install ca-certificates curl gnupg lsb-release -y
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io -y

echo "--- Adding user to docker group (Log out and back in to apply!) ---"
sudo usermod -aG docker $USER

echo "--- Building Docker images ---"
docker build -t ubuntu-tmate -f Dockerfile1 .
docker build -t debian-tmate -f Dockerfile2 .

echo "--- Setup complete. Please log out and back in to finalize Docker permissions. ---"
echo "Then, run the bot using 'source venv/bin/activate && python3 v2.py' in a tmux session."
