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

"""Class for evaluating programs proposed by the Sampler."""
import ast
from collections.abc import Sequence
import copy
from typing import Any
from typing import Tuple
from typing import Mapping
from typing import Union
from typing import List  # Add this import
from typing import Iterator  # Use Iterator from typing instead of collections.abc
from typing import Sequence  # Use Iterator from typing instead of collections.abc
from typing import MutableSet  # Use Iterator from typing instead of collections.abc
import clang.cindex
import os
import sys

from funsearch.implementation import code_manipulation
from funsearch.implementation import programs_database


class _FunctionLineVisitor():
  """Visitor that finds the last line number of a function with a given name."""

  def __init__(self, target_function_name: str, node: clang.cindex.Cursor) -> None:
    self._target_function_name: str = target_function_name
    self._function_end_line: int | None = None
    self.visit_FunctionDef(node)

  def visit_FunctionDef(self, node: clang.cindex.Cursor) -> None:  # pylint: disable=invalid-name
    """Collects the end line number of the target function."""
    for child in node.get_children():
      if child.kind == clang.cindex.CursorKind.CXX_METHOD or child.kind == clang.cindex.CursorKind.FUNCTION_DECL:
        if child.spelling == self._target_function_name:
          self._function_end_line = child.extent.end.line
          return

  @property
  def function_end_line(self) -> int:
    """Line number of the final line of function `target_function_name`."""
    assert self._function_end_line is not None  # Check internal correctness.
    return self._function_end_line


def _trim_function_body(generated_code: str, version_generated: Union[int,None]) -> str:
  print("TRIMMING FUNCTION BODY")
  import sys
  # if sys.stdin.isatty():
  #   # breakpoint()
  generated_function_name = "find_victim_v" + str(version_generated)
  print("generated function name", generated_function_name)
  index = clang.cindex.Index.create()
  file_name = "tmp.cc"
  with open(file_name, "w") as f:
    f.write(generated_code)
    os.chmod(file_name, 0o777)
  translation_unit = index.parse(file_name)
  node = translation_unit.cursor
  print("node")
  for child in node.get_children():
    print("child kind", child.kind)
    print("child spelling", child.spelling)
    print("child extent", child.extent)
    if child.kind == clang.cindex.CursorKind.CXX_METHOD or child.kind == clang.cindex.CursorKind.FUNCTION_DECL:
      if child.spelling == generated_function_name:
        start = child.extent.start.line - 1
        end = child.extent.end.line
        print("body")
        print("start", start)
        print("end", end)
        # body_lines = self._codelines[start:end]
        generated_code1 = "\n".join(generated_code.splitlines()[start:end])
        generated_code2 = "\n".join(generated_code[start:end])
        print("returning ", generated_code1)
        print("generated_code2", generated_code2)
        return generated_code1
        break
  print(generated_code)
  """Extracts the body of the generated function, trimming anything after it."""
  if not generated_code:
    print("returning 1")
    return ''
  code = f'def fake_function_header():\n{generated_code}'
  node = None
  # We keep trying and deleting code from the end until the parser succeeds.
  while node is None:
    try:
      index = clang.cindex.Index.create()
      file_name = "tmp.cc"
      with open(file_name, "w") as f:
        f.write(code)
        os.chmod(file_name, 0o777)
      translation_unit = index.parse(file_name)
      node = translation_unit.cursor
    except SyntaxError as e:
      code = '\n'.join(code.splitlines()[:e.lineno - 1])
  if not code:
    # Nothing could be saved from `generated_code`
    print("returning 2")
    return ''

  # visitor = ProgramVisitor(source_code, node)
  visitor = _FunctionLineVisitor('fake_function_header', node)
  # visitor.visit(node)
  body_lines = code.splitlines()[1:visitor.function_end_line]
  result = '\n'.join(body_lines) + '\n\n'
  print("AFTER")
  print(result)
  return result


def _sample_to_program(
    generated_code: str,
    version_generated: Union[int,None],
    template: code_manipulation.Program,
    function_to_evolve: str,
) -> Tuple[code_manipulation.Function, str]:
  """Returns the compiled generated function and the full runnable program."""
  print("BODY BEFORE TRIMMING")
  print(generated_code)
  body = _trim_function_body(generated_code, version_generated)
  print("BODY after trimming")
  print(body)
  print("VERSION GENERATED")
  print(version_generated)
  
  
  # if sys.stdin.isatty():
  #   breakpoint()
  if version_generated is not None:
    try :
      body = code_manipulation.rename_function_calls(
          body,
          f'{function_to_evolve}_v{version_generated}',
          function_to_evolve)
    except Exception as e:
      print("Error in renaming function calls")
      return None, str(e)

  program = copy.deepcopy(template)
  evolved_function = program.get_function(function_to_evolve)
  evolved_function.body = body
  return evolved_function, str(program)


class Sandbox:
  """Sandbox for executing generated code."""

  def run(
      self,
      program: str,
      function_to_run: str,
      test_input: str,
      timeout_seconds: int,
  ) -> Tuple[Any, bool]:
    """Executes untrusted code in a restricted environment."""
    try:
        # Compile the program in a restricted environment
        compiled_code = compile_restricted(program, '<string>', 'exec')
        exec_globals = safe_globals.copy()
        exec_locals = {}
        exec(compiled_code, exec_globals, exec_locals)
        
        # Call the function with the test input
        result = exec_locals[function_to_run](test_input)
        return result, True
    except Exception as e:
        print(f"Error during execution: {e}")
        return None, False

def _calls_ancestor(program: str, function_to_evolve: str) -> bool:
  """Returns whether the generated function is calling an earlier version."""
  for name in code_manipulation.get_functions_called(program):
    # In `program` passed into this function the most recently generated
    # function has already been renamed to `function_to_evolve` (wihout the
    # suffix). Therefore any function call starting with `function_to_evolve_v`
    # is a call to an ancestor function.
    if name.startswith(f'{function_to_evolve}_v'):
      return True
  return False


class Evaluator:
  """Class that analyses functions generated by LLMs."""

  def __init__(
      self,
      database: programs_database.ProgramsDatabase,
      template: code_manipulation.Program,
      function_to_evolve: str,
      function_to_run: str,
      inputs: Sequence[Any],
      timeout_seconds: int = 30,
  ):
    self._database = database
    self._template = template
    self._function_to_evolve = function_to_evolve
    self._function_to_run = function_to_run
    self._inputs = inputs
    self._timeout_seconds = timeout_seconds
    self._sandbox = Sandbox()
    self._eval_count = 0
    with open("funsearch/implementation/cache_hit_rates.txt", "w") as file:
      file.write("")  # Clear the file contents

  def analyse(
      self,
      sample: str,
      island_id: Union[int , None],
      version_generated: Union[int , None],
      prompt: str,
  ) -> None:
    self._eval_count += 1
    """Compiles the sample into a program and executes it on test inputs."""
    print("ANALYSING")
    new_function, program = _sample_to_program(
        sample, version_generated, self._template, self._function_to_evolve)
    if new_function is None:
      print("Error in sample_to_program")
      return

    scores_per_test = {}
    print("PRINTING PROGRAM")
    print(program)
    print(new_function)
    # for current_input in self._inputs:
    #   test_output, runs_ok = self._sandbox.run(
    #       program, self._function_to_run, current_input, self._timeout_seconds)
    #   if (runs_ok and not _calls_ancestor(program, self._function_to_evolve)
    #       and test_output is not None):
    #     if not isinstance(test_output, (int, float)):
    #       raise ValueError('@function.run did not return an int/float score.')
    #     scores_per_test[current_input] = test_output
    rate = None
    # In champsim, make a new folder in the replacement folder for your new policy
    # Change the replacement value in the champsim config to this new policy
    # Run bin/champsim on some trace, Idk which one
    # In the output of champsim, look at Last Level Cache (LLC) Access stats cpu0->LLC TOTAL    	ACCESS:	9983649 HIT:	6682964 MISS:	3300685 MSHR_MERGE:      	0

    # Make the new Policy Directory
    new_policy_name = "new_policy_" + str(self._eval_count)  # Replace with your new policy name
    import json
    import subprocess
    try:
        command = "mkdir ChampSim/replacement/" + new_policy_name
        subprocess.run(command, shell=True, check=True)
        print("Command executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e}")

    # write new policy to a file
    with open("funsearch/implementation/policies/" + new_policy_name +".cc", "w") as f:
          f.write(program)


    if prompt is not None:
      # write prompt to a file
      with open("funsearch/implementation/policies/" + new_policy_name +"prompt.txt", "w") as f:
            f.write(prompt.code)
   
    # Copy the new policy files to the new directory
    command = "cp funsearch/implementation/policies/" + new_policy_name +".cc"+ " ChampSim/replacement/" + new_policy_name
    result = None
    try:
        result = subprocess.run(command, shell=True, check=True, encoding='utf-8', capture_output=True)
    except subprocess.CalledProcessError as e:
          print(f"Error occurred: {e}")

    # Copy lru.h to the new directory
    command = "cp lru.h"+ " ChampSim/replacement/" + new_policy_name
    result = None
    try:
        result = subprocess.run(command, shell=True, check=True, encoding='utf-8', capture_output=True)
    except subprocess.CalledProcessError as e:
          print(f"Error occurred: {e}")


    # Set the new policy in the Config
    with open("ChampSim/champsim_config.json", "r") as file:
        champsim_config = json.load(file)
        champsim_config["LLC"]["replacement"] = new_policy_name
        # Save the modified config back to the file
    with open("ChampSim/champsim_config.json", "w") as file:
        json.dump(champsim_config, file, indent=4)

    
    # Run Champsim
    command = "ChampSim/bin/champsim --warmup_instructions 200000 --simulation_instructions 500000 ChampSim/astar_23B.trace.xz"
    result = None
    try:
        result = subprocess.run(command, shell=True, check=True, encoding='utf-8', capture_output=True)
        output = result.stdout
        # print(output)
        print("Command executed successfully.")
        example_string = """Heartbeat CPU 0 instructions: 60000009 cycles: 84698515 heartbeat IPC: 0.4978 cumulative IPC: 0.503 (Simulation time: 00 hr 08 min 02 sec)
Simulation finished CPU 0 instructions: 50000000 cycles: 98265577 cumulative IPC: 0.5088 (Simulation time: 00 hr 09 min 43 sec)
Simulation complete CPU 0 instructions: 50000000 cycles: 98265577 cumulative IPC: 0.5088 (Simulation time: 00 hr 09 min 43 sec)

ChampSim completed all CPUs

=== Simulation ===
CPU 0 runs ChampSim/astar_23B.trace.xz

Region of Interest Statistics

CPU 0 cumulative IPC: 0.5088 instructions: 50000000 cycles: 98265577
CPU 0 Branch Prediction Accuracy: 71.83% MPKI: 53.76 Average ROB Occupancy at Mispredict: 5.724
Branch type MPKI
BRANCH_DIRECT_JUMP: 0.0005
BRANCH_INDIRECT: 0
BRANCH_CONDITIONAL: 53.76
BRANCH_DIRECT_CALL: 0.00032
BRANCH_INDIRECT_CALL: 0
BRANCH_RETURN: 0.00036

cpu0->cpu0_STLB TOTAL        ACCESS:    1241031 HIT:     942103 MISS:     298928 MSHR_MERGE:          0
cpu0->cpu0_STLB LOAD         ACCESS:    1241031 HIT:     942103 MISS:     298928 MSHR_MERGE:          0
cpu0->cpu0_STLB RFO          ACCESS:          0 HIT:          0 MISS:          0 MSHR_MERGE:          0
cpu0->cpu0_STLB PREFETCH     ACCESS:          0 HIT:          0 MISS:          0 MSHR_MERGE:          0
cpu0->cpu0_STLB WRITE        ACCESS:          0 HIT:          0 MISS:          0 MSHR_MERGE:          0
cpu0->cpu0_STLB TRANSLATION  ACCESS:          0 HIT:          0 MISS:          0 MSHR_MERGE:          0
cpu0->cpu0_STLB PREFETCH REQUESTED:          0 ISSUED:          0 USEFUL:          0 USELESS:          0
cpu0->cpu0_STLB AVERAGE MISS LATENCY: 9.895 cycles
cpu0->cpu0_L2C TOTAL        ACCESS:    2030759 HIT:    1422524 MISS:     608235 MSHR_MERGE:          0
cpu0->cpu0_L2C LOAD         ACCESS:    1488731 HIT:     889909 MISS:     598822 MSHR_MERGE:          0
cpu0->cpu0_L2C RFO          ACCESS:      22694 HIT:      18955 MISS:       3739 MSHR_MERGE:          0
cpu0->cpu0_L2C PREFETCH     ACCESS:          0 HIT:          0 MISS:          0 MSHR_MERGE:          0
cpu0->cpu0_L2C WRITE        ACCESS:     496428 HIT:     496402 MISS:         26 MSHR_MERGE:          0
cpu0->cpu0_L2C TRANSLATION  ACCESS:      22906 HIT:      17258 MISS:       5648 MSHR_MERGE:          0
cpu0->cpu0_L2C PREFETCH REQUESTED:          0 ISSUED:          0 USEFUL:          0 USELESS:          0
cpu0->cpu0_L2C AVERAGE MISS LATENCY: 49.78 cycles
cpu0->cpu0_L1I TOTAL        ACCESS:       6253 HIT:       6114 MISS:        139 MSHR_MERGE:         38
cpu0->cpu0_L1I LOAD         ACCESS:       6253 HIT:       6114 MISS:        139 MSHR_MERGE:         38
cpu0->cpu0_L1I RFO          ACCESS:          0 HIT:          0 MISS:          0 MSHR_MERGE:          0
cpu0->cpu0_L1I PREFETCH     ACCESS:          0 HIT:          0 MISS:          0 MSHR_MERGE:          0
cpu0->cpu0_L1I WRITE        ACCESS:          0 HIT:          0 MISS:          0 MSHR_MERGE:          0
cpu0->cpu0_L1I TRANSLATION  ACCESS:          0 HIT:          0 MISS:          0 MSHR_MERGE:          0
cpu0->cpu0_L1I PREFETCH REQUESTED:          0 ISSUED:          0 USEFUL:          0 USELESS:          0
cpu0->cpu0_L1I AVERAGE MISS LATENCY: 207.5 cycles
cpu0->cpu0_L1D TOTAL        ACCESS:   14690019 HIT:   12808485 MISS:    1881534 MSHR_MERGE:     347298
cpu0->cpu0_L1D LOAD         ACCESS:   12248708 HIT:   10414219 MISS:    1834489 MSHR_MERGE:     345855
cpu0->cpu0_L1D RFO          ACCESS:          0 HIT:          0 MISS:          0 MSHR_MERGE:          0
cpu0->cpu0_L1D PREFETCH     ACCESS:          0 HIT:          0 MISS:          0 MSHR_MERGE:          0
cpu0->cpu0_L1D WRITE        ACCESS:    2142381 HIT:    2118612 MISS:      23769 MSHR_MERGE:       1073
cpu0->cpu0_L1D TRANSLATION  ACCESS:     298930 HIT:     275654 MISS:      23276 MSHR_MERGE:        370
cpu0->cpu0_L1D PREFETCH REQUESTED:          0 ISSUED:          0 USEFUL:          0 USELESS:          0
cpu0->cpu0_L1D AVERAGE MISS LATENCY: 28.14 cycles
cpu0->cpu0_ITLB TOTAL        ACCESS:       5623 HIT:       5601 MISS:         22 MSHR_MERGE:         12
cpu0->cpu0_ITLB LOAD         ACCESS:       5623 HIT:       5601 MISS:         22 MSHR_MERGE:         12
cpu0->cpu0_ITLB RFO          ACCESS:          0 HIT:          0 MISS:          0 MSHR_MERGE:          0
cpu0->cpu0_ITLB PREFETCH     ACCESS:          0 HIT:          0 MISS:          0 MSHR_MERGE:          0
cpu0->cpu0_ITLB WRITE        ACCESS:          0 HIT:          0 MISS:          0 MSHR_MERGE:          0
cpu0->cpu0_ITLB TRANSLATION  ACCESS:          0 HIT:          0 MISS:          0 MSHR_MERGE:          0
cpu0->cpu0_ITLB PREFETCH REQUESTED:          0 ISSUED:          0 USEFUL:          0 USELESS:          0
cpu0->cpu0_ITLB AVERAGE MISS LATENCY: 462.5 cycles
cpu0->cpu0_DTLB TOTAL        ACCESS:   14318231 HIT:   12766647 MISS:    1551584 MSHR_MERGE:     310563
cpu0->cpu0_DTLB LOAD         ACCESS:   14318231 HIT:   12766647 MISS:    1551584 MSHR_MERGE:     310563
cpu0->cpu0_DTLB RFO          ACCESS:          0 HIT:          0 MISS:          0 MSHR_MERGE:          0
cpu0->cpu0_DTLB PREFETCH     ACCESS:          0 HIT:          0 MISS:          0 MSHR_MERGE:          0
cpu0->cpu0_DTLB WRITE        ACCESS:          0 HIT:          0 MISS:          0 MSHR_MERGE:          0
cpu0->cpu0_DTLB TRANSLATION  ACCESS:          0 HIT:          0 MISS:          0 MSHR_MERGE:          0
cpu0->cpu0_DTLB PREFETCH REQUESTED:          0 ISSUED:          0 USEFUL:          0 USELESS:          0
cpu0->cpu0_DTLB AVERAGE MISS LATENCY: 7.621 cycles
cpu0->LLC TOTAL        ACCESS:     836719 HIT:     714958 MISS:     121761 MSHR_MERGE:          0
cpu0->LLC LOAD         ACCESS:     598801 HIT:     477921 MISS:     120880 MSHR_MERGE:          0
cpu0->LLC RFO          ACCESS:       3739 HIT:       3542 MISS:        197 MSHR_MERGE:          0
cpu0->LLC PREFETCH     ACCESS:          0 HIT:          0 MISS:          0 MSHR_MERGE:          0
cpu0->LLC WRITE        ACCESS:     228531 HIT:     228415 MISS:        116 MSHR_MERGE:          0
cpu0->LLC TRANSLATION  ACCESS:       5648 HIT:       5080 MISS:        568 MSHR_MERGE:          0
cpu0->LLC PREFETCH REQUESTED:          0 ISSUED:          0 USEFUL:          0 USELESS:          0
cpu0->LLC AVERAGE MISS LATENCY: 172.7 cycles

DRAM Statistics

Channel 0 RQ ROW_BUFFER_HIT:        357
  ROW_BUFFER_MISS:     121259
  AVG DBUS CONGESTED CYCLE: 18.68
Channel 0 WQ ROW_BUFFER_HIT:      11075
  ROW_BUFFER_MISS:      60434
  FULL:          0
Channel 0 REFRESHES ISSUED:       8189"""
        lines = output.splitlines()
        rate = 0
        for line in lines:
            if "LLC TOTAL" in line:
                parts = line.split()
                access = int(parts[3])
                hit = int(parts[5])
                miss = int(parts[7])
                rate = hit / access if access > 0 else 0
                break
        scores_per_test["cache_hit_rate"] = rate
        with open("funsearch/implementation/cache_hit_rates.txt", "a") as file:
          file.write(new_policy_name +" Cache Hit Rate: " + str(rate) + "\n")
        if scores_per_test:
          self._database.register_program(new_function, island_id, scores_per_test)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e}")
    
    
