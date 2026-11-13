# GAIA: Emergent AI Civilization

## Overview

GAIA is a local-first civilization simulation where autonomous citizens live, work, trade, build homes, elect a mayor, and raise families. A **Hybrid Sampler AI** sends urgent cases and a rotating sample of citizens to a local Ollama model, while the rest use a fast rule-based fallback. The result is a living economy that stays responsive even on modest hardware. Grain and wood markets respond to supply and demand, taxes fund a central bank, and the Bank intervenes when housing or food shortages threaten the settlement.

## Prerequisites

- **Python 3.10 or newer**
- **Ollama** installed and running locally
- A modern web browser

Install the Python dependencies from the project folder:

```bash
pip install -r requirements.txt
```

## 🧠 How to Connect the AI (Ollama)

### What happens if I don't have Ollama?

The game will still run perfectly using the built-in deterministic fallback rules. The top-right corner will say AI: OFFLINE. However, to experience the full emergent AI civilization, you need Ollama.

### Step 1: Install Ollama

Go to ollama.com and download the installer for your operating system. Run the installer.

### Step 2: Download the Brain

Open a new terminal (Command Prompt or PowerShell) and run:

```bash
ollama pull qwen2.5-coder:7b
```

This will download the 4.7 GB model.

### Step 3: Launch the Game

Double-click Launch_GAIA.bat. The game will automatically detect Ollama running in the background and the top-right badge will change to AI: ONLINE.

> **Note:** The game communicates with Ollama via the local API at http://localhost:11434. No internet connection is required after the model is downloaded.

## Quick Start

1. Download the model:

   ```bash
   ollama pull qwen2.5-coder:7b
   ```

2. Double-click **`Launch_GAIA.bat`**.

The launcher starts the simulation server, opens the viewer, and warns you if Ollama is unavailable. GAIA still runs without Ollama by falling back to deterministic citizen behavior.

## Features

### Cyberpunk GAIA Assistant

GAIA watches the settlement for anomalies such as homelessness, starvation, unemployment, and empty markets. Citizens ask her practical questions, and she answers through the local language model with a wise, slightly sarcastic personality. The neon console keeps a running log of interventions, citizen questions, and Bank activity.

### Mayor System

Citizens elect a mayor from the living population. The mayor gives the settlement a leader and influences the town's ongoing social and economic life as the simulation develops.

### The Central Bank

- **Housing Stimulus** — When citizens are homeless and the reserve is healthy, the Bank pays 15 coins per citizen to assign a free bed or instantly fund a new house. Every subsidized bed is recorded in the Bank ledger.
- **Grain Buyback** — When the market shelf runs dangerously low, the Bank buys grain to stabilize supply and keep food available.
- **Taxes and Food Stamps** — Wealth taxes replenish the reserve, while food stamps help penniless, hungry citizens survive.

### Map Expansion

The settlement grows beyond its starting tile as the population rises. New land brings additional markets and building space, and the camera can zoom, pan, fit, or recenter so you can follow the civilization as it expands.

## Controls

- **Play / Pause / Step** — Run the simulation, freeze it, or advance one tick.
- **1x–10x speed** — Control how quickly the world evolves.
- **Click a citizen** — Inspect their job, home, hunger, and inventory; gift coins or remove them.
- **+ Spawn** — Add a new citizen at the edge of the map.
- **Data Console** — Open population, market, housing, and citizen charts.
- **Reset** — Start a fresh civilization.

## Project Files

| File | Purpose |
| --- | --- |
| `world.py` | Simulation rules, citizens, economy, housing, elections, and expansion |
| `server.py` | FastAPI server and autonomous tick loop |
| `llm_bridge.py` | Ollama client, GAIA Assistant prompt, and fallback behavior |
| `persistence.py` | SQLite snapshots and event storage |
| `observer.py` | World observation data for AI decisions |
| `config.json` | Model, simulation, and timing settings |
| `viewer_pixi.html` | PixiJS viewer and control console |
| `assets/` | Visual assets used by the viewer |
| `Launch_GAIA.bat` | One-click Windows launcher |
| `requirements.txt` | Python dependencies |
