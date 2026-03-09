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

"""Tools for manipulating Python code.

It implements 2 classes representing unities of code:
- Function, containing all the information we need about functions: name, args,
  body and optionally a return type and a docstring.
- Program, which contains a code preface (which could be imports, global
  variables and classes, ...) and a List of Functions.
"""
import ast
from collections.abc import Iterator, MutableSet, Sequence
import dataclasses
import io
import tokenize
import astor
from typing import Union
from typing import List  # Add this import
from typing import Iterator  # Use Iterator from typing instead of collections.abc
from typing import Sequence  # Use Iterator from typing instead of collections.abc
from typing import Tuple  # Use Iterator from typing instead of collections.abc
from typing import MutableSet  # Use Iterator from typing instead of collections.abc
import clang.cindex
import os

# ─────────────────────────────────────────────────────────────────────────────
# 1) Try to pick up libclang from your Conda env
# ─────────────────────────────────────────────────────────────────────────────
_conda_libclang = os.path.join(
    os.environ.get("CONDA_PREFIX", ""),
    "lib",
    "libclang.so.13"
)
if os.path.isfile(_conda_libclang):
    clang.cindex.Config.set_library_file(_conda_libclang)
else:
    # fall back to the system install
    clang.cindex.Config.set_library_file("/usr/lib64/libclang.so.18.1.8")

@dataclasses.dataclass
class Function:
  """A parsed Python function."""

  name: str
  args: str
  body: str
  return_type: Union[str, None] = None
  docstring: Union[str, None] = None

  def __str__(self) -> str:
    return_type = f' -> {self.return_type}' if self.return_type else ''

    function = f'def {self.name}({self.args}){return_type}:\n'
    if self.docstring:
      # self.docstring is already indented on every line except the first one.
      # Here, we assume the indentation is always two spaces.
      new_line = '\n' if self.body else ''
      function += f'  """{self.docstring}"""{new_line}'
    # self.body is already indented.
    function += self.body + '\n\n'
    return function

  def __setattr__(self, name: str, value: str) -> None:
    # Ensure there aren't leading & trailing new lines in `body`.
    if name == 'body':
      value = value.strip('\n')
    # Ensure there aren't leading & trailing quotes in `docstring``.
    if name == 'docstring' and value is not None:
      if '"""' in value:
        value = value.strip()
        value = value.replace('"""', '')
    super().__setattr__(name, value)


@dataclasses.dataclass(frozen=True)
class Program:
  """A parsed Python program."""

  # `preface` is everything from the beginning of the code till the first
  # function is found.
  preface: str
  functions: List[Function]

  def __str__(self) -> str:
    program = f'{self.preface}\n' if self.preface else ''
    program += '\n'.join([str(f) for f in self.functions])
    return program

  def find_function_index(self, function_name: str) -> int:
    """Returns the index of input function name."""
    function_names = [f.name for f in self.functions]
    count = function_names.count(function_name)
    if count == 0:
      raise ValueError(
          f'function {function_name} does not exist in program:\n{str(self)}'
      )
    if count > 1:
      raise ValueError(
          f'function {function_name} exists more than once in program:\n'
          f'{str(self)}'
      )
    index = function_names.index(function_name)
    return index

  def get_function(self, function_name: str) -> Function:
    index = self.find_function_index(function_name)
    return self.functions[index]

  def get_function_names(self) -> List[Function]:
    """Returns all functions in the program."""
    return self.functions


class ProgramVisitor():
  """Parses code to collect all required information to produce a `Program`.

  Note that we do not store function decorators.
  """

  def __init__(self, sourcecode: str, node: clang.cindex.Cursor):
    self._codelines: List[str] = sourcecode.splitlines()
    self._preface: str = ''
    self._functions: List[Function] = []
    self._current_function: str | None = None
    self.FillVisitor(node)

  def FillVisitor(self,  # pylint: disable=invalid-name
                        node: clang.cindex.Cursor) -> None:
    """Collects all information about the function being parsed."""
    # print("node", node)
    print("parsing function")
    preface_set = False
    for child in node.get_children():
      # print("child", child)
      # print("child kind", child.kind)
      # print("child name", child.spelling)
      if child.kind == clang.cindex.CursorKind.CXX_METHOD or child.kind == clang.cindex.CursorKind.FUNCTION_DECL:
        # Set the preface if it hasn't been set yet
        if not preface_set:
            self._preface = '\n'.join(self._codelines[:child.extent.start.line - 1])
            preface_set = True
        # print("Function name:", child.spelling)
        # print("Return type:", child.result_type.spelling)
        # print("Arguments:")
        args = []
        for arg in child.get_arguments():
          print(" -", arg.spelling, ":", arg.type.spelling)
          args.append(f"{arg.type.spelling} {arg.spelling}")
                # Add the function to the list

        # Extract the body of the function
        start = child.extent.start.line - 1  # Convert to 0-based index
        end = child.extent.end.line
        body_lines = self._codelines[start:end]
        print("Body lines:", body_lines)
        body = "\n".join(body_lines)
        # print("Body:", body)
        return_type = child.result_type.spelling if node.result_type else None
        print("Return type:", return_type)
        self._functions.append(Function(
            name=child.spelling,
            args=", ".join(args),
            return_type=child.result_type.spelling if node.result_type else None,
            docstring=None,  # C++ doesn't have Python-style docstrings
            body=body.strip(),  # You can extract the body if needed, but it's not trivial
        ))
        # TODO: recursion?
            # Recursively visit child nodes
        # for child in node.get_children():
        #     self.FillVisitor(child)
        self.FillVisitor(child)

    # if node.col_offset == 0:  # We only care about first level functions.
    #   self._current_function = node.name
    #   if not self._functions:
    #     self._preface = '\n'.join(self._codelines[:node.lineno - 1])
    #   function_end_line = node.end_lineno
    #   body_start_line = node.body[0].lineno - 1
    #   # Extract the docstring.
    #   docstring = None
    #   if isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value,
    #                                                        ast.Str):
    #     docstring = f'  """{ast.literal_eval(astor.to_source(node.body[0]))}"""'
    #     if len(node.body) > 1:
    #       body_start_line = node.body[1].lineno - 1
    #     else:
    #       body_start_line = function_end_line

    #   self._functions.append(Function(
    #       name=node.name,
    #       args=astor.to_source(node.args),
    #       return_type=astor.to_source(node.returns) if node.returns else None,
    #       docstring=docstring,
    #       body='\n'.join(self._codelines[body_start_line:function_end_line]),
    #   ))
    # self.generic_visit(node)

  def return_program(self) -> Program:
    return Program(preface=self._preface, functions=self._functions)


def text_to_program(file: str) -> Program:
  """Returns Program object by parsing input text using Python AST."""
  try:
    # We assume that the program is composed of some preface (e.g. imports,
    # classes, assignments, ...) followed by a sequence of functions.
    index = clang.cindex.Index.create()
    print("file", file)
    with open(file, "r") as f:
      # raw_code = file.read()
      source_code = f.read()
    args = [
    '-std=c++17',  # or the standard your code uses
    '-I/path/to/includes',  # e.g., for STL headers
    ]
    translation_unit = index.parse(file, args=args)
    node = translation_unit.cursor
    # # Traverse the AST and print the function names
    # print("parsed")
    # for child in node.get_children():
    #   print("child", child)
    #   print("child kind", child.kind)
    #   if child.kind == clang.cindex.CursorKind.CXX_METHOD:
    #     print("Function name:", child.spelling)
    #     print("Return type:", child.result_type.spelling)
    #     print("Arguments:")
    #     for arg in child.get_arguments():
    #       print(" -", arg.spelling, ":", arg.type.spelling)
    # tree = ast.parse(text)
    # print(node)
    print("source code:")
    print(source_code)
    visitor = ProgramVisitor(source_code, node)
    # visitor.visit(node)
    return visitor.return_program()
  except Exception as e:
    # logging.warning('Failed parsing %s', text)
    raise e


def text_to_function(text: str) -> Function:
  """Returns Function object by parsing input text using Python AST."""
  file_name = "funsearch/implementation/tmp.cc"
  with open(file_name, "w") as f:
    f.write(text)
    os.chmod(file_name, 0o777)
  program = text_to_program(file_name)
  if len(program.functions) != 1:
    raise ValueError(f'Only one function expected, got {len(program.functions)}'
                     f':\n{program.functions}')
  return program.functions[0]


def _tokenize(code: str) -> Iterator[tokenize.TokenInfo]:
  """Transforms `code` into Python tokens."""
  code_bytes = code.encode()
  code_io = io.BytesIO(code_bytes)
  return tokenize.tokenize(code_io.readline)


def _untokenize(tokens: Sequence[tokenize.TokenInfo]) -> str:
  """Transforms a List of Python tokens into code."""
  code_bytes = tokenize.untokenize(tokens)
  return code_bytes.decode()


def _yield_token_and_is_call(
    code: str) -> Iterator[Tuple[tokenize.TokenInfo, bool]]:
  """Yields each token with a bool indicating whether it is a function call."""
  try:
    print("trying to tokenize")
    print(code)
    tokens = _tokenize(code)
    print("tokenized")
    print(tokens)
    prev_token = None
    is_attribute_access = False
    for token in tokens:
      if (prev_token and  # If the previous token exists and
          prev_token.type == tokenize.NAME and  # it is a Python identifier
          token.type == tokenize.OP and  # and the current token is a delimiter
          token.string == '('):  # and in particular it is '('.
        yield prev_token, not is_attribute_access
        is_attribute_access = False
      else:
        if prev_token:
          is_attribute_access = (
              prev_token.type == tokenize.OP and prev_token.string == '.'
          )
          yield prev_token, False
      prev_token = token
    if prev_token:
      yield prev_token, False
  except Exception as e:
    # logging.warning('Failed parsing %s', code)
    print('Failed parsing %s', code)
    raise e


def rename_function_calls(code: str, source_name: str, target_name: str) -> str:
  """Renames function calls from `source_name` to `target_name`."""
  print(f"renaming {source_name} to {target_name}")
  if source_name not in code:
    return code
  modified_tokens = []
  # replace source_name with target_name
  # in the code

  for token, is_call in _yield_token_and_is_call(code):
    if is_call and token.string == source_name:
      # Replace the function name token
      modified_token = tokenize.TokenInfo(
          type=token.type,
          string=target_name,
          start=token.start,
          end=token.end,
          line=token.line,
      )
      modified_tokens.append(modified_token)
    else:
      modified_tokens.append(token)
  return _untokenize(modified_tokens)


def get_functions_called(code: str) -> MutableSet[str]:
  """Returns the set of all functions called in `code`."""
  return set(token.string for token, is_call in
             _yield_token_and_is_call(code) if is_call)


# def yield_decorated(code: str, module: str, name: str, file_name: str) -> Iterator[str]:
#   """Yields names of functions decorated with `@module.name` in `code`."""
#   # Set the path to libclang
#   clang.cindex.Config.set_library_file('/usr/lib/llvm-14/lib/libclang.so')

#   # Parse the C++ code
#   index = clang.cindex.Index.create()
#   translation_unit = index.parse("example.cpp")
#   node = translation_unit.cursor
#   # Traverse the AST and print the function names
#   for child in node.get_children():
#     if child.kind == clang.cindex.CursorKind.FUNCTION_DECL:
#       print("Function name:", child.spelling)
#       print("Return type:", child.result_type.spelling)
#       print("Arguments:")
#       for arg in child.get_arguments():
#         print(" -", arg.spelling, ":", arg.type.spelling)
#   tree = ast.parse(code)
#   for node in ast.walk(tree):
#     if isinstance(node, ast.FunctionDef):
#       for decorator in node.decorator_list:
#         attribute = None
#         if isinstance(decorator, ast.Attribute):
#           attribute = decorator
#         elif isinstance(decorator, ast.Call):
#           attribute = decorator.func
#         if (attribute is not None
#             and attribute.value.id == module
#             and attribute.attr == name):
#           yield node.name


def init() -> None:
  """Initializes the module."""
  # Set the path to libclang
  clang.cindex.Config.set_library_file('/usr/lib64/libclang.so.15')
  # Initialize the clang index
  clang.cindex.Index.create()
