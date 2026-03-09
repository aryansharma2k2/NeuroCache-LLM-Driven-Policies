#!/usr/bin/env python3

import numpy as np
import csv
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from stable_baselines3 import PPO

from funsearch.implementation.rl_utils       import generate_and_eval
from funsearch.implementation.code_manipulation import text_to_program
from funsearch.implementation.programs_database import ProgramsDatabase


def eval_model(policy_model, tokenizer, template, fn, n=10):
    results = []
    for _ in range(n):
        cfg    = ProgramsDatabase.get_default_config()
        db     = ProgramsDatabase(cfg, template, fn)
        prompt = db.get_prompt().code
        results.append(generate_and_eval(
            prompt, policy_model, tokenizer, template, fn
        ))
    return results


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"▶ Evaluation device: {device}")

    # Load base LLaMA
    base = "../homework-2/RAG/LLAMA"
    tokenizer = AutoTokenizer.from_pretrained(base, use_fast=True)
    llm_model = AutoModelForCausalLM.from_pretrained(base).to(device)
    llm_model.eval()

    template = text_to_program("funsearch/implementation/starting_policies/lru.cc")
    fn       = "find_victim"

    # Pre-RL
    pre = eval_model(llm_model, tokenizer, template, fn, n=10)
    print("Pre-RL hit-rates:", pre)

    # Post-RL
    ppo_agent = PPO.load("ppo_policygen_rl", device=device)
    policy    = ppo_agent.policy.to(device)
    policy.eval()
    post = eval_model(policy, tokenizer, template, fn, n=10)
    print("Post-RL hit-rates:", post)

    # Write CSV
    with open("rl_results.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["variant", "mean_hit_rate", "max_hit_rate"])
        w.writerow(["pre",  np.mean(pre),  np.max(pre)])
        w.writerow(["post", np.mean(post), np.max(post)])
    print("✔ Results saved to rl_results.csv")


if __name__ == "__main__":
    main()
