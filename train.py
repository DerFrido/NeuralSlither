import os
import sys
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv, VecFrameStack
from stable_baselines3.common.callbacks import CheckpointCallback
from slither_env import SlitherEnv

# ============================================================
# EINSTELLUNGEN
# ============================================================
NUM_ENVS = 2               # Anzahl paralleler Browserfenster
MODEL_NAME = "slither_ppo_model_fresh"
LOG_DIR = "./logs/"
CHECKPOINT_DIR = "./checkpoints/"
TOTAL_TIMESTEPS = 10_000_000  # 10 Millionen Timesteps - viel mehr Zeit zum Lernen
RESET_TRAINING = True
# ============================================================


def make_env(rank):
    def _init():
        return SlitherEnv(env_idx=rank)
    return _init


if __name__ == "__main__":
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)

    print("\n=== INITIALISIERUNG ===")
    print(f"Starte {NUM_ENVS} Umgebung(en) mit SubprocVecEnv (echte Parallelisierung)...")

    # SubprocVecEnv: jede Umgebung läuft in eigenem Prozess → keine Blockierung zwischen Envs
    env = SubprocVecEnv([make_env(i) for i in range(NUM_ENVS)])

    # Frame-Stacking: 4 Frames übereinander für Bewegungserkennung
    print("Aktiviere 4x Frame-Stacking...")
    env = VecFrameStack(env, n_stack=4, channels_order="last")

    # Modell laden oder neu erstellen
    model_path = f"{MODEL_NAME}.zip"
    if os.path.exists(model_path) and not RESET_TRAINING:
        print(f"Lade bestehendes Modell: {model_path}")
        model = PPO.load(model_path, env=env, tensorboard_log=LOG_DIR)
    else:
        print("Kein Modell gefunden. Erstelle neues PPO-Modell...")
        model = PPO(
            policy="CnnPolicy",
            env=env,
            learning_rate=3e-4,
            n_steps=1024,
            batch_size=128,
            n_epochs=4,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.2,
            verbose=1,
            tensorboard_log=LOG_DIR,
        )

    # Checkpoint-Callback: speichert regelmäßig Backups
    checkpoint_callback = CheckpointCallback(
        save_freq=max(5000, 10000 // NUM_ENVS),
        save_path=CHECKPOINT_DIR,
        name_prefix=MODEL_NAME,
    )

    print(f"\n=== TRAINING STARTET ({TOTAL_TIMESTEPS:,} Schritte) ===\n")

    try:
        model.learn(
            total_timesteps=TOTAL_TIMESTEPS,
            callback=checkpoint_callback,
            reset_num_timesteps=False,
        )
        model.save(MODEL_NAME)
        print(f"\n-> Training abgeschlossen. Modell gespeichert: {MODEL_NAME}.zip")

    except KeyboardInterrupt:
        print("\n=== TRAINING UNTERBROCHEN ===")
        print("Speichere Modell...")
        try:
            model.save(MODEL_NAME)
            print(f"✓ Erfolgreich gespeichert: {MODEL_NAME}.zip")
        except Exception as e:
            print(f"✗ Fehler beim Speichern: {e}")

        print("Schliesse Browser (kann kurz dauern)...")
        try:
            env.close()
            print("✓ Browser geschlossen.")
        except Exception:
            pass

        print("=== BEENDET ===")
        sys.exit(0)