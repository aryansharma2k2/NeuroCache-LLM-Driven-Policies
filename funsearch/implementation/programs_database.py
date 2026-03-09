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

"""A programs database that implements the evolutionary algorithm."""
from collections.abc import Mapping, Sequence
import copy
import dataclasses
import time
from typing import Any

# from absl import logging
import numpy as np
import scipy
from typing import Tuple
from typing import Mapping
from typing import Union
from typing import List  # Add this import
from typing import Iterator  # Use Iterator from typing instead of collections.abc
from typing import Sequence  # Use Iterator from typing instead of collections.abc
from typing import MutableSet  # Use Iterator from typing instead of collections.abc

from funsearch.implementation import code_manipulation
from funsearch.implementation import config as config_lib

Signature = Tuple[float, ...]
ScoresPerTest = Mapping[Any, float]


def _softmax(logits: np.ndarray, temperature: float) -> np.ndarray:
  """Returns the tempered softmax of 1D finite `logits`."""
  if not np.all(np.isfinite(logits)):
    non_finites = set(logits[~np.isfinite(logits)])
    raise ValueError(f'`logits` contains non-finite value(s): {non_finites}')
  if not np.issubdtype(logits.dtype, np.floating):
    logits = np.array(logits, dtype=np.float32)

  result = scipy.special.softmax(logits / temperature, axis=-1)
  # Ensure that probabilities sum to 1 to prevent error in `np.random.choice`.
  index = np.argmax(result)
  result[index] = 1 - np.sum(result[0:index]) - np.sum(result[index+1:])
  return result


def _reduce_score(scores_per_test: ScoresPerTest) -> float:
  """Reduces per-test scores into a single score."""
  return scores_per_test[list(scores_per_test.keys())[-1]]


def _get_signature(scores_per_test: ScoresPerTest) -> Signature:
  """Represents test scores as a canonical signature."""
  return tuple(scores_per_test[k] for k in sorted(scores_per_test.keys()))


@dataclasses.dataclass(frozen=True)
class Prompt:
  """A prompt produced by the ProgramsDatabase, to be sent to Samplers.

  Attributes:
    code: The prompt, ending with the header of the function to be completed.
    version_generated: The function to be completed is `_v{version_generated}`.
    island_id: Identifier of the island that produced the implementations
       included in the prompt. Used to direct the newly generated implementation
       into the same island.
  """
  code: str
  version_generated: int
  island_id: int


class ProgramsDatabase:
  """A collection of programs, organized as islands."""

  def __init__(
      self,
      config: config_lib.ProgramsDatabaseConfig,
      template: code_manipulation.Program,
      function_to_evolve: str,
  ) -> None:
    self._config: config_lib.ProgramsDatabaseConfig = config
    self._template: code_manipulation.Program = template
    self._function_to_evolve: str = function_to_evolve

    # Initialize empty islands.
    self._islands: list[Island] = []
    for _ in range(config.num_islands):
      self._islands.append(
          Island(template, function_to_evolve, config.functions_per_prompt,
                 config.cluster_sampling_temperature_init,
                 config.cluster_sampling_temperature_period,
                 config.num_starting_policies
                 ))
    self._best_score_per_island: list[float] = (
        [-float('inf')] * config.num_islands)
    self._best_program_per_island: list[code_manipulation.Function | None] = (
        [None] * config.num_islands)
    self._best_scores_per_test_per_island: list[ScoresPerTest | None] = (
        [None] * config.num_islands)

    self._last_reset_time: float = time.time()

  def get_prompt(self) -> Prompt:
    """Returns a prompt containing implementations from one chosen island."""
    island_id = np.random.randint(len(self._islands))
    code, version_generated = self._islands[island_id].get_prompt()
    print(f"prompt v_${version_generated} constructed")
    return Prompt(code, version_generated, island_id)

  def _register_program_in_island(
      self,
      program: code_manipulation.Function,
      island_id: int,
      scores_per_test: ScoresPerTest,
  ) -> None:
    """Registers `program` in the specified island."""
    print("REGISTERING PROGRAM IN ISLAND")
    print(program)
    self._islands[island_id].register_program(program, scores_per_test)
    score = _reduce_score(scores_per_test)
    if score > self._best_score_per_island[island_id]:
      self._best_program_per_island[island_id] = program
      self._best_scores_per_test_per_island[island_id] = scores_per_test
      self._best_score_per_island[island_id] = score
      # logging.info('Best score of island %d increased to %s', island_id, score)

  def register_program(
      self,
      program: code_manipulation.Function,
      island_id: Union[int, None],
      scores_per_test: ScoresPerTest,
  ) -> None:
    """Registers `program` in the database."""
    # In an asynchronous implementation we should consider the possibility of
    # registering a program on an island that had been reset after the prompt
    # was generated. Leaving that out here for simplicity.
    if island_id is None:
      # This is a program added at the beginning, so adding it to all islands.
      for island_id in range(len(self._islands)):
        self._register_program_in_island(program, island_id, scores_per_test)
    else:
      self._register_program_in_island(program, island_id, scores_per_test)

    # Check whether it is time to reset an island.
    if (time.time() - self._last_reset_time > self._config.reset_period):
      self._last_reset_time = time.time()
      self.reset_islands()

  def reset_islands(self) -> None:
    """Resets the weaker half of islands."""
    # We sort best scores after adding minor noise to break ties.
    indices_sorted_by_score: np.ndarray = np.argsort(
        self._best_score_per_island +
        np.random.randn(len(self._best_score_per_island)) * 1e-6)
    num_islands_to_reset = self._config.num_islands // 2
    reset_islands_ids = indices_sorted_by_score[:num_islands_to_reset]
    keep_islands_ids = indices_sorted_by_score[num_islands_to_reset:]
    for island_id in reset_islands_ids:
      self._islands[island_id] = Island(
          self._template,
          self._function_to_evolve,
          self._config.functions_per_prompt,
          self._config.cluster_sampling_temperature_init,
          self._config.cluster_sampling_temperature_period)
      self._best_score_per_island[island_id] = -float('inf')
      founder_island_id = np.random.choice(keep_islands_ids)
      founder = self._best_program_per_island[founder_island_id]
      founder_scores = self._best_scores_per_test_per_island[founder_island_id]
      self._register_program_in_island(founder, island_id, founder_scores)


class Island:
  """A sub-population of the programs database."""

  def __init__(
      self,
      template: code_manipulation.Program,
      function_to_evolve: str,
      functions_per_prompt: int,
      cluster_sampling_temperature_init: float,
      cluster_sampling_temperature_period: int,
      num_starting_policies: int = 0,
  ) -> None:
    self._template: code_manipulation.Program = template
    self._function_to_evolve: str = function_to_evolve
    self._functions_per_prompt: int = functions_per_prompt
    self._cluster_sampling_temperature_init = cluster_sampling_temperature_init
    self._cluster_sampling_temperature_period = (
        cluster_sampling_temperature_period)

    self._clusters: dict[Signature, Cluster] = {}
    self._num_programs: int = 0
    self._num_starting_policies: int = num_starting_policies

  def register_program(
      self,
      program: code_manipulation.Function,
      scores_per_test: ScoresPerTest,
  ) -> None:
    """Stores a program on this island, in its appropriate cluster."""
    signature = _get_signature(scores_per_test)
    print("SIGNATURE")
    print(signature)
    if signature not in self._clusters:
      score = _reduce_score(scores_per_test)
      print("new cluster with program")
      print(program)
      self._clusters[signature] = Cluster(score, program)
      # breakpoint()
    else:
      self._clusters[signature].register_program(program)
    self._num_programs += 1
    print("Num programs in island now:", self._num_programs)

  def get_prompt(self) -> Tuple[str, int]:
    """Constructs a prompt containing functions from this island."""
    signatures = list(self._clusters.keys())
    cluster_scores = np.array(
        [self._clusters[signature].score for signature in signatures])
    print("CLUSTER SCORES COUNT ", len(cluster_scores))
    # Convert scores to probabilities using softmax with temperature schedule.
    period = self._cluster_sampling_temperature_period
    temperature = self._cluster_sampling_temperature_init * (
        1 - (self._num_programs % period) / period)
    probabilities = _softmax(cluster_scores, temperature)

    # At the beginning of an experiment when we have few clusters, place fewer
    # programs into the prompt.
    print("clusters", len(self._clusters))
    functions_per_prompt = min(len(self._clusters), self._functions_per_prompt) # why 2 clusters?
    print("functions_per_prompt", self._functions_per_prompt)
    functions_per_prompt = min(self._functions_per_prompt, len(signatures))
    print("signatures", len(signatures))
    idx = np.random.choice(
        len(signatures), size=functions_per_prompt, p=probabilities, replace=False)
    chosen_signatures = [signatures[i] for i in idx]
    print("CHOSEN SIGNATURES")
    print(chosen_signatures)
    implementations = []
    scores = []
    print(f"PUtting ${len(chosen_signatures)} functions in the prompt", )
    for signature in chosen_signatures:
      cluster = self._clusters[signature]
      program = cluster.sample_program()
      print(program)
      # breakpoint()
      implementations.append(program)
      scores.append(cluster.score)

    indices = np.argsort(scores)
    sorted_implementations = [implementations[i] for i in indices]
    version_generated = min(11, self._num_programs)
    print(f"PUTTING ${len(sorted_implementations)} functions in the prompt")
    # if sys.stdin.isatty():
    #   breakpoint()
    print("VERSION GENERATED", version_generated)
    
    return self._generate_prompt(sorted_implementations), version_generated

  def get_default_config(self) -> Sequence[code_manipulation.Function]:
    """Returns all implementations in this island."""
    signatures = list(self._clusters.keys())
    implementations = []
    for sig in signatures:
      cluster = self._clusters[sig]
      program = cluster.sample_program()
      print(program)
      # breakpoint()
      implementations.append(program)
    return implementations

  def _generate_prompt(
      self,
      implementations: Sequence[code_manipulation.Function]) -> str:
    """Creates a prompt containing a sequence of function `implementations`."""
    implementations = copy.deepcopy(implementations)  # We will mutate these.
    
    # Format the names and docstrings of functions to be included in the prompt.
    versioned_functions: list[code_manipulation.Function] = []
    for i, implementation in enumerate(implementations):
      new_function_name = f'{self._function_to_evolve}_v{i}'
      implementation.name = new_function_name
      # Update the docstring for all subsequent functions after `_v0`.
      if i > self._num_starting_policies + 1:
        implementation.docstring = (
            f'Add your code here; an improved replacement policy')
        # implementation.docstring = (f'')
      # If the function is recursive, replace calls to itself with its new name.
      try:
        print("RENAME FUNCTION CALLS")
        implementation = code_manipulation.rename_function_calls(
            str(implementation), self._function_to_evolve, new_function_name)
      except Exception as e:
        print("Token error:")
        print(implementation)
        print("string not working")
        print(str(implementation))


      versioned_functions.append(
          code_manipulation.text_to_function(str(implementation)))

    # Create the header of the function to be generated by the LLM.
    next_version = len(implementations)
    new_function_name = f'{self._function_to_evolve}_v{next_version}'
    string = f"""
            // Add your code here an improved cache replacement policy.
            """
    header = dataclasses.replace(
        implementations[-1],
        name=new_function_name,
        body=f"{{\n{string}\n}}"
        # docstring='',
        # docstring=(
        #     # f'Add your code here an improved version of \'{self._function_to_evolve}_v{next_version - 1}\'.'),
        #     f"""

        #     Add your code here an improved cache replacement policy.
        #     """),

    )
    versioned_functions.append(header)
    print("VERSIONED")
    print("count:", len(versioned_functions))
    for i, func in enumerate(versioned_functions):
      print(f"Function {i}:")
      print(func)
      print("Name:", func.name)
      print("Docstring:", func.docstring)
      print("Body:", func.body)
      print("-----")
    
    print("VERSIONED FUNCTIONS")
    print(versioned_functions)
    # breakpoint()
    # Replace functions in the template with the list constructed here.
    prompt = dataclasses.replace(self._template, functions=versioned_functions)
    return str(prompt)


class Cluster:
  """A cluster of programs on the same island and with the same Signature."""

  def __init__(self, score: float, implementation: code_manipulation.Function):
    self._score = score
    self._programs: list[code_manipulation.Function] = [implementation]
    self._lengths: list[int] = [len(str(implementation))]

  @property
  def score(self) -> float:
    """Reduced score of the signature that this cluster represents."""
    return self._score

  def register_program(self, program: code_manipulation.Function) -> None:
    """Adds `program` to the cluster."""
    print("REGISTERING PROGRAM")
    print(program)
    # breakpoint()
    self._programs.append(program)
    self._lengths.append(len(str(program)))

  def sample_program(self) -> code_manipulation.Function:
    """Samples a program, giving higher probability to shorther programs."""
    normalized_lengths = (np.array(self._lengths) - min(self._lengths)) / (
        max(self._lengths) + 1e-6)
    probabilities = _softmax(-normalized_lengths, temperature=1.0)
    return np.random.choice(self._programs, p=probabilities)
