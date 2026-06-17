# SlitherMind 🐍

A reinforcement learning bot that teaches itself to play [slither.io](http://slither.io) using PPO and computer vision. The bot controls a real browser via Selenium, observes the game through grayscale screenshots and learns to survive and grow over time – without any hardcoded rules or handcrafted strategies.

> ⚠️ **Work in progress** – the bot is functional but not yet fully polished. Some edge cases around spawning and crash recovery may still occur.

---

## How it works

SlitherMind treats slither.io as a standard reinforcement learning problem. Every step, it takes a screenshot of the browser, converts it to a 160×160 grayscale image, and feeds it into a CNN policy. The policy outputs one of 16 actions, which get translated into a direction and boost command sent to the browser via JavaScript. Over thousands of episodes the model learns purely from the reward signal what keeps it alive and what gets it killed.

### Observation space
- 160×160 grayscale screenshot, 4 frames stacked → shape `(160, 160, 4)`
- Frame stacking lets the model perceive movement and direction of other snakes

### Action space
- 16 discrete actions: 8 compass directions × (no boost / boost)
- Direction is set by injecting `window.xm` / `window.ym` directly into the game's JS
- Boost is triggered via a simulated Space keydown/keyup event

### Reward shaping
| Situation | Reward |
|---|---|
| Score increases, new peak reached | `+peak_diff × 4` (or `×8` with boost) |
| Score increases, below peak | `+score_diff × 0.5` |
| Score stays the same | `+0.1` (or `-0.2` with boost, to discourage idle boosting) |
| Score drops slightly | `-0.1` (or `-0.5` with boost) |
| Large sudden score drop (>20) | `-100`, treated as death |
| Death | `-50` base penalty |
| Death too fast after big score | up to `-130` (discourages suicidal behavior) |

### Crash & spawn recovery
- After death the bot automatically clicks Play again via JS
- If the spawn takes too long (>150 steps ≈ ~15 seconds), the page is fully reloaded
- During spawn wait, neutral steps are returned so the other environment isn't blocked

---

## Requirements

- Python 3.10+
- [Brave Browser](https://brave.com/) installed at:  
  `C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe`
- ChromeDriver matching your Brave/Chromium version → [download here](https://chromedriver.chromium.org/downloads), place `chromedriver.exe` in your project folder or PATH

Install Python dependencies:
```bash
pip install stable-baselines3[extra] gymnasium selenium opencv-python
```

---

## Project structure

```
SlitherMind/
├── slither_env.py          # Gymnasium environment – browser control, rewards, recovery
├── train.py                # Training script – PPO setup, checkpoints, Ctrl+C save
├── checkpoints/            # Auto-saved model backups during training
├── logs/                   # Tensorboard training logs
└── slither_ppo_model.zip   # Final model (created automatically)
```

---

## Usage

### Start training
```bash
python train.py
```

Two Brave windows open automatically and start playing. Training stats are printed to the console every 2048 steps.

### Resume training
Just run `python train.py` again – if `slither_ppo_model.zip` exists it will be loaded and training continues from where it left off.

### Stop training
Press `Ctrl+C` – the model is saved immediately before closing.

### Change number of windows
In `train.py`:
```python
NUM_ENVS = 2  # increase for more parallel games
```

### Monitor with Tensorboard (optional)
```bash
tensorboard --logdir ./logs/
```
Then open `http://localhost:6006` in your browser.

---

## Architecture

| Component | Detail |
|---|---|
| Algorithm | PPO (Proximal Policy Optimization) |
| Policy | CnnPolicy (3 conv layers → MLP → action/value head) |
| Learning rate | 3e-4 |
| Steps per update | 1024 per env |
| Batch size | 128 |
| Frame stack | 4 |
| Parallelism | DummyVecEnv (sequential, no inter-env blocking) |

---

## Known limitations

- The star background sometimes doesn't load on first browser start – this is cosmetic and has no effect on training since the bot only sees grayscale pixels
- Slither.io occasionally drops the WebSocket connection after a while – the bot detects this via a step timeout and reloads the page automatically
- The bot plays on real public slither.io servers, so latency and server stability affect training consistency
- No minimap awareness yet – the bot only reacts to what's directly visible in the 160×160 crop

---

## Built with

- [Stable Baselines3](https://github.com/DLR-RM/stable-baselines3)
- [Gymnasium](https://gymnasium.farama.org/)
- [Selenium](https://www.selenium.dev/)
- [OpenCV](https://opencv.org/)
