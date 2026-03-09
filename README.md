# NeuroCache: LLM-Driven Discovery of CPU Cache Replacement Policies

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![C++](https://img.shields.io/badge/C++-17-blue.svg)](https://isocpp.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)

An evolutionary system that uses Large Language Models to automatically discover high-performance CPU cache replacement policies. This project adapts DeepMind's [FunSearch](https://www.nature.com/articles/s41586-023-06924-6) (*Nature 2023*) from mathematical problem-solving to computer architecture optimization.

## Overview

Cache replacement policies determine which memory block to evict when the cache is full—a critical decision that significantly impacts CPU performance. Traditionally, these policies are hand-crafted by experts (LRU, DRRIP, Hawkeye). This project instead uses an **evolutionary algorithm powered by LLMs** to automatically discover novel policies that can outperform human-designed baselines.

### How It Works

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   LLM       │────▶│  ChampSim   │────▶│   Fitness   │
│  (Codegen)  │     │ (Evaluate)  │     │ (Hit Rate)  │
└─────────────┘     └─────────────┘     └──────┬──────┘
       ▲                                       │
       └────────── Evolve Best Policies ────────┘
```

1. **Generation**: LLM generates C++ `find_victim()` function variations
2. **Evaluation**: Each policy is compiled into [ChampSim](https://github.com/ChampSim/ChampSim) and tested on memory traces
3. **Scoring**: Cache hit rate serves as the fitness function
4. **Evolution**: High-performing policies are fed back as seeds for further LLM refinement

## Architecture

| Component | Purpose |
|-----------|---------|
| `evaluator.py` | Manages ChampSim integration, compiles policies, extracts hit rates |
| `sampler.py` | LLM interface using HuggingFace Transformers (Llama with 4-bit quantization) |
| `programs_database.py` | Maintains evolutionary "islands" of diverse high-performing policies |
| `code_manipulation.py` | C++ parsing and function extraction using libclang |
| `starting_policies/` | Seed policies: LRU, DRRIP, SRRIP, Hawkeye, SHiP, LIME, DAN-CRC2 |

## Prerequisites

- Python 3.9+
- CUDA-capable GPU (for LLM inference)
- [ChampSim](https://github.com/ChampSim/ChampSim) cache simulator
- Memory trace files (e.g., SPEC CPU2006 traces)

## Installation

### 1. Clone and Setup Environment

```bash
git clone <your-repo-url>
cd Cache-Replacement-Policy-Generator

# Create conda environment
conda create -n neurocache python=3.10
conda activate neurocache

# Install dependencies
pip install -r requirements.txt
```

### 2. Setup ChampSim

ChampSim should be installed at the project root:

```bash
# From project root
git clone https://github.com/ChampSim/ChampSim.git

# Build ChampSim (follow ChampSim documentation)
cd ChampSim
./config.sh champsim_config.json
make
```

### 3. Download Memory Traces

Place memory traces in `ChampSim/` directory. Example traces used:
- `astar_23B.trace.xz` (SPEC CPU2006)

### 4. Configure LLM Path

Edit `funsearch/implementation/sampler.py` to point to your local model:

```python
model_path = "path/to/your/llama-model"  # Line 73
```

Or use the fine-tuning script in `scripts/task3_main.py` to train your own model on policy code.

## Usage

### Running on HPC (LSF)

```bash
# Request GPU node
bsub -Is -n 4 -R "span[hosts=1]" -W 8:00 -q gpu -gpu "num=1" bash

# Activate environment and run
conda activate neurocache
python -m funsearch.implementation.funsearch
```

### Running Locally

```bash
conda activate neurocache
python -m funsearch.implementation.funsearch
```

### Configuration

Edit `funsearch/implementation/funsearch.py` to adjust:
- Starting seed policies
- Number of islands for evolution
- Evaluation parameters

Example configuration:
```python
config = Config(
    files=[
        "funsearch/implementation/starting_policies/drrip.cc",
        "funsearch/implementation/starting_policies/hawkeye_final.cc",
        "funsearch/implementation/starting_policies/dancrc2.cc",
        "funsearch/implementation/starting_policies/lime.cc",
    ],
    function_to_evolve="find_victim",
    function_to_run="run",
    num_islands=1,
    num_evaluators=1,
    num_samplers=1,
)
```

## Project Structure

```
Cache-Replacement-Policy-Generator/
├── README.md                          # This file
├── funsearch/
│   ├── README.md                      # Original FunSearch documentation
│   ├── implementation/                # Core implementation
│   │   ├── funsearch.py               # Main entry point
│   │   ├── evaluator.py               # ChampSim evaluation
│   │   ├── sampler.py                 # LLM sampling
│   │   ├── programs_database.py       # Evolutionary database
│   │   ├── code_manipulation.py       # C++ parsing utilities
│   │   ├── config.py                  # Configuration classes
│   │   ├── starting_policies/         # Baseline policies
│   │   │   ├── lru.cc, lru.h           # LRU baseline
│   │   │   ├── drrip.cc, drrip.h       # DRRIP baseline
│   │   │   ├── srrip.cc                # SRRIP baseline
│   │   │   ├── hawkeye_final.cc        # Hawkeye baseline
│   │   │   ├── ship.cc                 # SHiP baseline
│   │   │   ├── lime.cc                 # LIME baseline
│   │   │   └── dancrc2.cc              # DAN-CRC2 baseline
│   │   └── policies/                  # Generated policies (runtime)
│   └── ...                            # Other FunSearch examples (cap_set, etc.)
├── scripts/
│   └── task3_main.py                  # LLM fine-tuning script
└── logs/                              # Execution logs (gitignored)
```

## Results

The system maintains a running log of the best discovered policies in `funsearch/implementation/cache_hit_rates.txt`. Evolved policies are saved to `funsearch/implementation/policies/` with their corresponding prompts for reproducibility.

### Example Output

```
new_policy_1 Cache Hit Rate: 0.8547
new_policy_7 Cache Hit Rate: 0.8712
new_policy_14 Cache Hit Rate: 0.8891
```

## Citation

This project builds on DeepMind's FunSearch:

```bibtex
@Article{FunSearch2023,
  author  = {Romera-Paredes, Bernardino and Barekatain, Mohammadamin and Novikov, Alexander and Balog, Matej and Kumar, M. Pawan and Dupont, Emilien and Ruiz, Francisco J. R. and Ellenberg, Jordan and Wang, Pengming and Fawzi, Omar and Kohli, Pushmeet and Fawzi, Alhussein},
  journal = {Nature},
  title   = {Mathematical discoveries from program search with large language models},
  year    = {2023},
  doi     = {10.1038/s41586-023-06924-6}
}
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](funsearch/LICENSE) file for details.

The original FunSearch implementation is Copyright 2023 DeepMind Technologies Limited.

## Acknowledgments

- [DeepMind FunSearch Team](https://github.com/google-deepmind/funsearch) for the original implementation
- [ChampSim](https://github.com/ChampSim/ChampSim) for the cache simulation infrastructure
- [HuggingFace Transformers](https://huggingface.co/docs/transformers) for LLM inference
