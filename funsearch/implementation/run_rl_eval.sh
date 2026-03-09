#!/bin/bash
#BSUB -n 4
#BSUB -W 1:00
#BSUB -q gpu
#BSUB -gpu "num=1"
#BSUB -J eval_rl_gpu
#BSUB -o /share/csc591s25/btarun/GenAI-for-Systems-Gym/project/logs/eval_rl_gpu.out.%J
#BSUB -e /share/csc591s25/btarun/GenAI-for-Systems-Gym/project/logs/eval_rl_gpu.err.%J

# 1) Load conda
source ~/.bashrc

# 2) Activate the shared HW2 env (FunSearch/ChampSim)
conda activate /share/csc591s25/bpreier_ttran_dshrest/hw2_env_new

# ────────────────────────────────────────────────────────
# 3) Redirect all caches into your project’s .cache folder
# ────────────────────────────────────────────────────────
export XDG_CACHE_HOME="$PWD/.cache"
export MPLCONFIGDIR="$PWD/.cache/matplotlib"
export HF_DATASETS_CACHE="$PWD/.cache/hf/datasets"
export HF_TRANSFORMERS_CACHE="$PWD/.cache/hf/transformers"
export HF_HOME="$PWD/.cache/hf"

mkdir -p \
  "$XDG_CACHE_HOME" \
  "$MPLCONFIGDIR" \
  "$HF_DATASETS_CACHE" \
  "$HF_TRANSFORMERS_CACHE" \
  "$HF_HOME"

# 4) Prepend your RL libraries (SB3, Gym, Torch, Transformers)
export PYTHONPATH="/share/csc591s25/btarun/my_custom_packages:$PYTHONPATH"

# 5) Go to project root
cd /share/csc591s25/bpreier_ttran_dshrest/GenAI-for-Systems-Gym/project

# 6) Improve PyTorch CUDA memory handling
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# 7) Run GPU‐accelerated evaluation
python funsearch/implementation/eval_rl.py

# 8) Deactivate
conda deactivate
