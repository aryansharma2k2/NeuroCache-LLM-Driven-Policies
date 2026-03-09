#!/usr/bin/env python3

import gym
import numpy as np
from gym import spaces

from funsearch.implementation.code_manipulation import text_to_program
from funsearch.implementation.rl_utils import generate_and_eval, ProgramsDatabaseTrain


class PolicyGenEnv(gym.Env):
    """Gym wrapper that, on each step, asks the LLM+policy to generate
    a new cache-replacement function and evaluates it in ChampSim."""

    def __init__(self, model, tokenizer, template_cc, function_to_evolve):
        super().__init__()
        self.current_step = 0
        self.observation_space = spaces.Box(0.0, 1.0, shape=(1,), dtype=np.float32)
        self.action_space  = spaces.Discrete(4)

        self.model, self.tokenizer = model, tokenizer
        self.template = text_to_program(template_cc)
        self.fn = function_to_evolve

        self.db = ProgramsDatabaseTrain(keep_top_k=10)

        starting_files = [
            "funsearch/implementation/starting_policies/drrip.cc",
            "funsearch/implementation/starting_policies/hawkeye_final.cc",
            "funsearch/implementation/starting_policies/dancrc2.cc",
            "funsearch/implementation/starting_policies/lime.cc",
        ]


        for file_path in starting_files:
            prog = text_to_program(file_path).get_function(self.fn)
            self.db.register_program(prog, None, {"reward": 0.0})

    def reset(self):
        return np.array([0.0], dtype=np.float32)

    def step(self, action):
        if action == 0:
            prompt = self.db.get_prompt(k=2)
        elif action == 1:
            prompt = self.db.get_prompt(k=3)
        elif action == 2:
            self.llm.set_temperature(0.7)
            prompt = self.db.get_prompt(k=4)
        elif action == 3:
            self.llm.set_temperature(0.5)
            prompt = self.db.get_prompt(k=4)
        else:
            raise ValueError(f"Invalid action: {action}")

        reward, generated_code = generate_and_eval(
            prompt, self.model, self.tokenizer, self.template, self.fn
        )
        self.db.register_program(
            code=generated_code,
            parent=None,
            stats={"reward": reward}
        )

        self.current_step += 1
        if self.current_step % 100 == 0:
            self.log_best_program(self.current_step)

        return np.array([reward], dtype=np.float32), reward, False, {}


    def log_best_program(self, step_count):
        """Prints the current best program in the database."""
        try:
            best_prog = self.db.get_best_program()
            best_reward = best_prog.stats.get("reward", 0.0)
            print("\n" + "="*60)
            print(f"[Step {step_count}] Best Program So Far (reward: {best_reward:.4f}):")
            print(best_prog.code)
            print("="*60 + "\n")
        except ValueError:
            # No programs yet
            print(f"[Step {step_count}] No programs available to log yet.")