# Copyright 2023 DeepMind Technologies Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

"""Class for sampling new programs."""
from collections.abc import Collection, Sequence

import numpy as np
from typing import Sequence
from typing import Collection
from funsearch.implementation import evaluator
from funsearch.implementation import programs_database
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import CheckpointCallback
import os
import sys

class LLM:
  """Language model that predicts continuation of provided source code."""

  def __init__(self, samples_per_prompt: int, model, tokenizer) -> None:
    self._model = model
    self._tokenizer = tokenizer
    self._samples_per_prompt = samples_per_prompt

  def _draw_sample(self, prompt: str) -> str:
    print("PROMPT: ")
    system_prompt = "System: You are a code generation assistant that is an expert on writing cache replacement policies. I need you to make a cache replacement policy for a cache simulator that maxmimzes the cache hit rate. Below I've provide some examples of policies and then a new policy for you to fill out which should be an improved version of the other policies. Write out the C++ code for the new improved policy to improve on the existing policies. Only write one new policy inside the function skeleton that I provided for you at the end of the code. Make sure to write over my placeholder comment and to use correct syntax. Code: "
    
    new_prompt = system_prompt + prompt
    
    inputs = self._tokenizer(new_prompt, return_tensors="pt")
    # breakpoint()
    outputs = self._model.generate(**inputs, max_new_tokens=512)
    print("OUTPUTS")
    print(outputs)
    response = self._tokenizer.decode(outputs[0], skip_special_tokens=False)
    print("RESPONSE")
    print(response)
    return response
    # raise NotImplementedError('Must provide a language model.')

  def draw_samples(self, prompt: str) -> Collection[str]:
    """Returns multiple predicted continuations of `prompt`."""
    return [self._draw_sample(prompt) for _ in range(self._samples_per_prompt)]


class Sampler:
  """Node that samples program continuations and sends them for analysis."""

  def __init__(
      self,
      database: programs_database.ProgramsDatabase,
      evaluators: Sequence[evaluator.Evaluator],
      samples_per_prompt: int,
  ) -> None:
    self._database = database
    self._evaluators = evaluators
    model_path = "models/checkpoint-48000/"
    model_path = "../homework-2/RAG/LLAMA"
    import torch
    print(torch.cuda.is_available())
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
    )
    model = AutoModelForCausalLM.from_pretrained(model_path, quantization_config=bnb_config, device_map="cuda")

    # with open("testoutput.txt", "w") as file:
    #     file.write(str(model) + "\n")
    
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    self._llm = LLM(samples_per_prompt, model, tokenizer)

  def sample(self):
    """Continuously gets prompts, samples programs, sends them for analysis."""
    while True:
      prompt = self._database.get_prompt()
      samples = self._llm.draw_samples(prompt.code)
      print("GOT SAMPLE for prompt # ", prompt.version_generated)
      
      # if sys.stdin.isatty():
      #   breakpoint()
      # This loop can be executed in parallel on remote evaluator machines.
      for sample in samples:
        chosen_evaluator = np.random.choice(self._evaluators)
        print("EVALUATING")
        chosen_evaluator.analyse(
            sample, prompt.island_id, prompt.version_generated, prompt)
        # if sys.stdin.isatty():
        #   breakpoint()
        print("FINISHED EVALUATING")
