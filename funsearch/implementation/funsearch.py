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

"""A single-threaded implementation of the FunSearch pipeline."""
from collections.abc import Sequence
from typing import Any
from typing import Tuple
from typing import Union
from typing import List  # Add this import
from typing import Iterator  # Use Iterator from typing instead of collections.abc
from typing import Sequence  # Use Iterator from typing instead of collections.abc
from typing import Tuple  # Use Iterator from typing instead of collections.abc
from typing import MutableSet  # Use Iterator from typing instead of collections.abc

from funsearch.implementation import code_manipulation
from funsearch.implementation import config as config_lib
from funsearch.implementation import evaluator
from funsearch.implementation import programs_database
from funsearch.implementation import sampler
import random

def _extract_function_names(specification: str) -> Tuple[str, str]:
  """Returns the name of the function to evolve and of the function to run."""
  run_functions = list(
      code_manipulation.yield_decorated(specification, 'funsearch', 'run'))
  if len(run_functions) != 1:
    raise ValueError('Expected 1 function decorated with `@funsearch.run`.')
  evolve_functions = list(
      code_manipulation.yield_decorated(specification, 'funsearch', 'evolve'))
  if len(evolve_functions) != 1:
    raise ValueError('Expected 1 function decorated with `@funsearch.evolve`.')
  return evolve_functions[0], run_functions[0]


def main(specification: str, inputs: Sequence[Any], config: config_lib.Config):
  """Launches a FunSearch experiment."""
  # function_to_evolve, function_to_run = _extract_function_names(specification)
  code_manipulation.init()
  function_to_evolve = config.function_to_evolve
  function_to_run = config.function_to_run
  print(function_to_evolve, function_to_run)
  template = code_manipulation.text_to_program(specification)
  database = programs_database.ProgramsDatabase(
      config.programs_database, template, function_to_evolve)

  file_list = config.files
  for file in file_list:
    print(file)
    # with open(file, "r") as file:
    #   # raw_code = file.read()
    program = code_manipulation.text_to_program(file)
    funcs = program.get_function_names()
    print(funcs)
    policy_function = program.get_function(function_to_evolve)
    print("policy_function to register")
    print(policy_function)
    scores_per_test = {}
    scores_per_test["cache_hit_rate"] = random.uniform(0.5, 0.8) 
    # TODO: run the actual test and report the scores?
    database.register_program(policy_function, None, scores_per_test)
  evaluators = []
  for _ in range(config.num_evaluators):
    evaluators.append(evaluator.Evaluator(
        database,
        template,
        function_to_evolve,
        function_to_run,
        inputs,
    ))
  # We send the initial implementation to be analysed by one of the evaluators.
  initial = template.get_function(function_to_evolve).body
  evaluators[0].analyse(initial, island_id=None, version_generated=None, prompt=None)
  samplers = [sampler.Sampler(database, evaluators, config.samples_per_prompt)
              for _ in range(config.num_samplers)]

  # This loop can be executed in parallel on remote sampler machines. As each
  # sampler enters an infinite loop, without parallelization only the first
  # sampler will do any work.
  for s in samplers:
    s.sample()



if __name__ == "__main__":
    # Example inputs
    with open("funsearch/implementation/specification_nonsymmetric_admissible_set.txt", "r") as f:
        specification = f.read()
        specification_path = "funsearch/implementation/starting_policies/lru.cc"
    inputs = []  # Replace with actual inputs
    config = config_lib.Config(
        files=[ 
           "funsearch/implementation/starting_policies/drrip.cc",
          #  ,"funsearch/implementation/starting_policies/lru.cc"
          # "funsearch/implementation/starting_policies/ship.cc",
          "funsearch/implementation/starting_policies/hawkeye_final.cc",
          "funsearch/implementation/starting_policies/dancrc2.cc",
          "funsearch/implementation/starting_policies/lime.cc",
          ],
        programs_database=config_lib.ProgramsDatabaseConfig(
            num_islands=1,
            functions_per_prompt=10,
            cluster_sampling_temperature_init=1.0,
            cluster_sampling_temperature_period=100,
            reset_period=60,
            num_starting_policies=4
        ),

        num_evaluators=1,
        num_samplers=1,
        samples_per_prompt=1,
        function_to_evolve="find_victim",
        function_to_run="run",
    )

    main(specification_path, inputs, config)
