#!/bin/bash

# Oracle Cloud Free Tier Setup Script for Discord Bot
# Run this after SSH into your Oracle instance

echo "🚀 Starting Oracle Cloud Discord Bot Setup..."

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python 3.10+ and required tools
echo "🐍 Installing Python and tools..."
sudo apt-get install -y python3-full python3-venv git screen htop

# Create bot directory
echo "📁 Creating bot directory..."
mkdir -p ~/discord-bot
cd ~/discord-bot

# Create virtual environment
echo "🔧 Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Clone or create bot files
echo "📝 Setting up bot files..."

# Create the main bot file
cat > main.py << 'EOL'
# Your main.py content goes here
# (Copy your main.py content)
EOL

# Create keep_alive.py (optional for Oracle - not really needed)
cat > keep_alive.py << 'EOL'
# Your keep_alive.py content
EOL

# Create requirements.txt
cat > requirements.txt << 'EOL'
discord.py==2.3.2
aiohttp==3.9.1
python-dotenv==1.0.0
EOL

# Create .env file template
cat > .env.example << 'EOL'
DISCORD_TOKEN=your_discord_bot_token_here
DEEPL_KEY=your_deepl_api_key_here
AZURE_KEY=your_azure_key_here
AZURE_REGION=your_azure_region_here
USE_KEEP_ALIVE=false
EOL

echo "⚠️  IMPORTANT: Copy .env.example to .env and add your tokens!"
cp .env.example .env

# Install Python packages
echo "📦 Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# Create systemd service for auto-start
echo "⚙️ Creating systemd service..."
sudo tee /etc/systemd/system/discord-bot.service > /dev/null << EOL
[Unit]
Description=Discord Translation Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER/discord-bot
Environment="PATH=/home/$USER/discord-bot/venv/bin"
ExecStart=/home/$USER/discord-bot/venv/bin/python /home/$USER/discord-bot/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOL

# Enable and start service
echo "🎯 Enabling bot service..."
sudo systemctl daemon-reload
sudo systemctl enable discord-bot.service

# Create start/stop scripts
echo "📜 Creating management scripts..."

cat > start_bot.sh << 'EOL'
#!/bin/bash
sudo systemctl start discord-bot
echo "✅ Bot started! Check status with: sudo systemctl status discord-bot"
EOL

cat > stop_bot.sh << 'EOL'
#!/bin/bash
sudo systemctl stop discord-bot
echo "🛑 Bot stopped!"
EOL

cat > restart_bot.sh << 'EOL'
#!/bin/bash
sudo systemctl restart discord-bot
echo "🔄 Bot restarted!"
EOL

cat > logs.sh << 'EOL'
#!/bin/bash
sudo journalctl -u discord-bot -f
EOL

cat > status.sh << 'EOL'
#!/bin/bash
sudo systemctl status discord-bot
EOL

# Make scripts executable
chmod +x *.sh

# Setup firewall (Oracle specific)
echo "🔥 Configuring firewall..."
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8080 -j ACCEPT
sudo netfilter-persistent save

# Create update script
cat > update_bot.sh << 'EOL'
#!/bin/bash
echo "📥 Updating bot..."
source venv/bin/activate
git pull  # If using git
pip install --upgrade -r requirements.txt
sudo systemctl restart discord-bot
echo "✅ Bot updated and restarted!"
EOL
chmod +x update_bot.sh

echo "✨ Setup complete!"
echo ""
echo "📋 NEXT STEPS:"
echo "1. Edit .env file with your tokens: nano .env"
echo "2. Start the bot: ./start_bot.sh"
echo "3. Check logs: ./logs.sh"
echo "4. Check status: ./status.sh"
echo ""
echo "🎮 Bot Management Commands:"
echo "  ./start_bot.sh   - Start the bot"
echo "  ./stop_bot.sh    - Stop the bot"
echo "  ./restart_bot.sh - Restart the bot"
echo "  ./logs.sh        - View live logs"
echo "  ./status.sh      - Check bot status"
echo "  ./update_bot.sh  - Update bot code"
