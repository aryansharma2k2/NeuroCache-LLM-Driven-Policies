#!/usr/bin/env python3

import os
import json
import subprocess

from funsearch.implementation.sampler   import LLM
from funsearch.implementation.evaluator import _trim_function_body, _sample_to_program


def generate_and_eval(
    prompt: str,
    model,
    tokenizer,
    template,
    function_to_evolve: str,
    trace: str = "ChampSim/astar_23B.trace.xz"
) -> float:
    """1) Use the LLM+policy to generate new find_victim code,
       2) drop it into Champsim,
       3) run a trace,
       4) parse and return the LLC hit-rate."""
    llm       = LLM(samples_per_prompt=1, model=model, tokenizer=tokenizer)
    gen_code  = llm._draw_sample(prompt)

    body, full = _sample_to_program(gen_code, version_generated=None,
                                    template=template, function_to_evolve=function_to_evolve)

    name    = "rl_policy"
    out_dir = os.path.join("..", "..", "ChampSim", "replacement", name)
    os.makedirs(out_dir, exist_ok=True)
    with open(f"{out_dir}/{name}.cc", "w") as f:
        f.write(full)

    #cfg_path = os.path.join("..", "..", "ChampSim", "champsim_config.json")
    cfg_path = "./ChampSim/champsim_config.json"
    cfg      = json.load(open(cfg_path))
    cfg["LLC"]["replacement"] = name
    json.dump(cfg, open(cfg_path, "w"), indent=2)

    cmd = (
        "ChampSim/bin/champsim "
        "--warmup_instructions 200000 "
        "--simulation_instructions 500000 "
        f"{trace}"
    )
    out = subprocess.check_output(cmd, shell=True, text=True)


    print("aryan", out)
    for line in out.splitlines():
        if "cpu0->LLC TOTAL" in line:
            parts  = line.split()
            access = int(parts[3])
            hit    = int(parts[5])
            return hit / access, gen_code

    return 0.0, gen_code


class ProgramTrain:
    """Simple container for a program and its metadata."""
    def __init__(self, code, parent=None, stats=None):
        self.code = code
        self.parent = parent  # Can track where it came from
        self.stats = stats or {}  # Cache hit rate, reward, etc.

class ProgramsDatabaseTrain:
    """Lightweight database for managing evolving programs during RL training."""

    def __init__(self, keep_top_k=10):
        """
        Args:
            keep_top_k (int): How many top programs to keep.
        """
        self.programs = []
        self.keep_top_k = keep_top_k

    def register_program(self, code, parent=None, stats=None):
        """Add a new program to the database."""
        new_program = ProgramTrain(code, parent, stats)
        self.programs.append(new_program)
        self._trim_database()

    def _trim_database(self):
        """Keep only the top-k programs based on reward."""
        if len(self.programs) <= self.keep_top_k:
            return

        # Sort by reward (highest first), assuming higher is better
        self.programs.sort(key=lambda p: p.stats.get("reward", 0.0), reverse=True)
        self.programs = self.programs[:self.keep_top_k]

    def get_prompt(self, k=3):
        """Return a prompt made from top-k programs."""
        if len(self.programs) == 0:
            raise ValueError("No programs in database yet!")

        # Sort by reward
        sorted_programs = sorted(self.programs, key=lambda p: p.stats.get("reward", 0.0), reverse=True)
        top_k_programs = sorted_programs[:min(k, len(sorted_programs))]

        prompt = "Here are some candidate programs:\n\n"
        for idx, prog in enumerate(top_k_programs):
            prompt += f"Program {idx+1}:\n{prog.code}\n\n"

        prompt += "Using inspiration from the above, generate a new candidate program:"
        return prompt

    def get_best_program(self):
        """Return the single best program (highest reward)."""
        if not self.programs:
            raise ValueError("No programs in database yet!")
        return max(self.programs, key=lambda p: p.stats.get("reward", 0.0))

    def get_all_programs(self):
        """Return all stored programs."""
        return self.programs
