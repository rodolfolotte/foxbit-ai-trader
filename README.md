# Foxbit AI Trader

This repository contains the scripts and configurations for the automated trading system built on top of the [Foxbit](https://foxbit.com.br) exchange and the [Hummingbot](https://hummingbot.org) framework.

## 1. Setup Hummingbot (via Docker)

The recommended way to run Hummingbot is via Docker. This ensures a clean and isolated environment.

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) installed on your machine.
- [Docker Compose](https://docs.docker.com/compose/install/) (usually included with Docker Desktop).

### Installation Steps

1. **Pull the latest Hummingbot image:**
   ```bash
   docker pull hummingbot/hummingbot:latest
   ```

2. **Create the Hummingbot Docker Container:**
   Run the following command from the root of this project (`/home/rodolfo/git/private/foxbit-ai-trader`). This will map your local `scripts` folder into the Docker container.

   ```bash
   docker run -it --name hummingbot-foxbit \
     -v $(pwd)/hummingbot_data/conf:/home/hummingbot/conf \
     -v $(pwd)/hummingbot_data/conf/connectors:/home/hummingbot/conf/connectors \
     -v $(pwd)/hummingbot_data/conf/strategies:/home/hummingbot/conf/strategies \
     -v $(pwd)/hummingbot_data/logs:/home/hummingbot/logs \
     -v $(pwd)/hummingbot_data/data:/home/hummingbot/data \
     -v $(pwd)/scripts:/home/hummingbot/scripts \
     -e CONFIG_PASSWORD=your_secure_password \
     hummingbot/hummingbot:latest
   ```
   *Note: Set a secure `CONFIG_PASSWORD`. This password encrypts your API keys locally.*

## 2. Connect to Foxbit

Once you are inside the Hummingbot CLI:

1. Type `connect foxbit`.
2. Provide your **API Key** when prompted.
3. Provide your **API Secret** when prompted.
4. Hummingbot will verify the connection.

## 3. Running the Basic Script

To verify everything is working, we have provided a basic testing script.

1. In the Hummingbot CLI, type:
   ```bash
   start --script 1_basic_listing_script.py
   ```
2. The bot will initialize and output your current balances and the mid-prices for the pairs defined in the script (BTC-BRL, ETH-BRL, USDT-BRL).
3. To stop the script, type:
   ```bash
   stop
   ```

---
*More advanced day-trading and long-term strategies will be added to the `scripts/` directory as the project progresses.*
