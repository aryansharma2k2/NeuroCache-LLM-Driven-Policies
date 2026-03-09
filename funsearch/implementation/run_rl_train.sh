#!/bin/bash
#BSUB -n 16
#BSUB -W 16:00
#BSUB -q gpu
#BSUB -gpu "num=1"
#BSUB -J train_rl
#BSUB -o /share/csc591s25/bpreier_ttran_dshrest/GenAI-for-Systems-Gym/project/logs/train_rl.out.%J
#BSUB -e /share/csc591s25/bpreier_ttran_dshrest/GenAI-for-Systems-Gym/project/logs/train_rl.err.%J

# 1) load bash profile
source ~/.bashrc

# 2) activate the HW2 env where we just installed SB3, Gym, Transformers, etc.
conda activate /share/csc591s25/bpreier_ttran_dshrest/hw2_env_new

# 3) cd to the project root
cd /share/csc591s25/bpreier_ttran_dshrest/GenAI-for-Systems-Gym/project

# 4) sandbox all caches under project/.cache (avoids home-dir quota issues)
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

# 5) improve PyTorch CUDA fragmentation behavior
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# 6) run the RL training via the package entrypoint
python -m funsearch.implementation.train_rl

# 7) deactivate when done
conda deactivate
