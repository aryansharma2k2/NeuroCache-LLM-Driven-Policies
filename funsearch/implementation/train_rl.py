#!/usr/bin/env python3

import os
import torch
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
)
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import CheckpointCallback

from funsearch.implementation.rl_env import PolicyGenEnv

def main():
    # ────────────────────────────────────────────────────────────────────────────
    # 1) Load & quantize your fine-tuned LLaMA (4-bit NF4)
    # ────────────────────────────────────────────────────────────────────────────
    base = "../homework-2/RAG/LLAMA"
    tokenizer = AutoTokenizer.from_pretrained(base, use_fast=True)

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
    )
    model = AutoModelForCausalLM.from_pretrained(
        base,
        quantization_config=bnb_config,
        device_map="auto",       # automatically places layers on GPU/CPU
        trust_remote_code=True,  # if your checkpoint uses custom code
    )
    print("Loaded LLM in 4-bit quantized mode (device_map=auto)")
    
    # We no longer .to(device) the full model; device_map already did it.

    # ────────────────────────────────────────────────────────────────────────────
    # 2) Set up RL device & Gym env
    # ────────────────────────────────────────────────────────────────────────────
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"RL policy training on {device}")

    template_cc = "funsearch/implementation/starting_policies/lru.cc"
    fn          = "find_victim"
    env = DummyVecEnv([
        lambda: PolicyGenEnv(model, tokenizer, template_cc, fn)
    ])

    # ────────────────────────────────────────────────────────────────────────────
    # 3) Instantiate PPO
    # ────────────────────────────────────────────────────────────────────────────
    agent = PPO(
        policy="MlpPolicy",
        env=env,
        learning_rate=2e-5,
        n_steps=4,
        batch_size=4,
        gamma=0.99,
        verbose=1,
        device=device,
    )

    # ────────────────────────────────────────────────────────────────────────────
    # 4) Checkpoint every 200 steps
    # ────────────────────────────────────────────────────────────────────────────
    ckpt_dir = "checkpoints"
    os.makedirs(ckpt_dir, exist_ok=True)
    checkpoint_cb = CheckpointCallback(
        save_freq=200,
        save_path=ckpt_dir,
        name_prefix="ppo_checkpoint",
    )

    # ────────────────────────────────────────────────────────────────────────────
    # 5) Train!
    # ────────────────────────────────────────────────────────────────────────────
    agent.learn(total_timesteps=20000, callback=checkpoint_cb)

    # ────────────────────────────────────────────────────────────────────────────
    # 6) Final save
    # ────────────────────────────────────────────────────────────────────────────
    agent.save("ppo_policygen_rl_final")
    print("Training complete; final policy saved to ppo_policygen_rl_final.zip")

if __name__ == "__main__":
    main()
