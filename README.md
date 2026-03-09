Prerequisites: On the HPC System, ChampSim installed, LLM Model connected

`bsub -Is -n 4 -R "span[hosts=1]" -W 8:00 -q gpu -gpu "num=1" bash`
To get a compute node with a GPU

`conda activate /share/csc591s25/bpreier_ttran_dshrest/hw2_env_new`

`python3 -m funsearch.implementation.funsearch`
