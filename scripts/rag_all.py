import pickle
from langchain import PromptTemplate, LLMChain, HuggingFacePipeline
from sentence_transformers import SentenceTransformer, util
from transformers import pipeline
import torch
import re
from rag_source import *  # Ensure rag_source.py is in the same directory or PYTHONPATH
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# -----------------------------------------------------------------------------
# Directories and model paths (adjust as needed)
# -----------------------------------------------------------------------------
# Path to SentenceTransformer embedding model directory:
EMBEDDING_MODEL_DIR = "/share/csc591s25/btarun/GenAI-for-Systems-Gym/homework-2/RAG/models/all-MiniLM-L6-v2"

# Path to processed data pickle file:
PROCESSED_DATA_PATH = "/share/csc591s25/hw2_files/processed_data.pkl"

# Path to the fine-tuned text-generation model checkpoint:
LOCAL_MODEL_PATH = "/share/csc591s25/btarun/GenAI-for-Systems-Gym/homework-2/RAG/main_output/checkpoint-40000"

# -----------------------------------------------------------------------------
# Load the SentenceTransformer embedding model
# -----------------------------------------------------------------------------
embedding_model = SentenceTransformer(EMBEDDING_MODEL_DIR)
print("Embedding model loaded from:", EMBEDDING_MODEL_DIR)

# -----------------------------------------------------------------------------
# Load the processed data for the RAG system
# -----------------------------------------------------------------------------
with open(PROCESSED_DATA_PATH, 'rb') as f:
    loaded_data = pickle.load(f)
print("Processed data loaded from:", PROCESSED_DATA_PATH)

# -----------------------------------------------------------------------------
# Load the fine-tuned model checkpoint for text generation
# -----------------------------------------------------------------------------
mistral_pipeline = pipeline(
    "text-generation",
    model=LOCAL_MODEL_PATH,
    model_kwargs={"torch_dtype": torch.bfloat16},
    device_map="auto",
    temperature=0.3,        # Lower values yield more focused responses
    top_p=0.9,              # Filter unlikely words
    truncation=True,
    max_new_tokens=100
)
llm = HuggingFacePipeline(pipeline=mistral_pipeline)
print("LLM pipeline created from model at:", LOCAL_MODEL_PATH)

# -----------------------------------------------------------------------------
# Set up the prompt template and LLMChain using LangChain
# -----------------------------------------------------------------------------
prompt_template = PromptTemplate(
    input_variables=["prompt_text"],
    template="{prompt_text}"
)
llm_chain = LLMChain(
    prompt=prompt_template,
    llm=llm
)

# -----------------------------------------------------------------------------
# Function to analyze a text prompt using the RAG system
# -----------------------------------------------------------------------------
def analyze_text_prompt(query, processed_data):
    # process_query should be defined in rag_source.py
    prompt_text = process_query(query, processed_data, embedding_model) + " The correct answer is, "
    inputs = {"prompt_text": prompt_text}
    result = llm_chain.run(inputs)
    return prompt_text, result

# -----------------------------------------------------------------------------
# Benchmark queries
# -----------------------------------------------------------------------------
# Original 20 benchmark queries (if needed, you can change or combine them)
original_queries = [
    "Does the memory access with PC 0x401dc9 and address 0x47ea85d37f result in a cache hit or cache miss for the lbm workload and Parrot replacement policy?",
    "For the memory access with PC 0x4037ba and address 0xa3a0df59c8, does the LRU replacement policy result in a cache hit or miss?",
    "When the LRU replacement policy accesses address PC 0x405832 and address 0x2ad51d2d9d on the astar workload, does the cache hit or miss?",
    "For the cache access with PC 0x401e31 and address 0x35e798a637f on the lbm workload with MLP replacement policy, does the cache hit or miss?",
    "What is the miss rate for PC 0x4037ba on the mcf workload with PARROT replacement policy?",
    "Which replacement policy performs best on the astar workload?",
    "Which replacement policy has the lowest miss rate for PC 0x409270 on the astar workload?",
    "For the cache access with PC 0x405832 and address 0x1faecf1dd90 on the astar workload with Belady replacement policy, does the cache hit or miss?",
    "For the cache access with PC 0x405832 and address 0x99c4f1409d on the astar workload with Belady replacement policy, does the cache hit or miss?",
    "For the cache access with PC 0x405832 and address 0x3f11f2f463f on the astar workload with Belady replacement policy, does the cache hit or miss?",
    "How many unique cache sets were accessed at least 3 times during the execution of the astar benchmark (LRU policy)?",
    "Among all the cache lines that were reused at least once (i.e., re-accessed after insertion), which memory address had the highest reuse count under LRU?",
    "In set 0b11110101111, what was the cache line with the lowest LRU score right before the last observed access to that set? What address was most likely to be evicted next?",
    "What is the miss rate for PC 0x4037c1 on the mcf workload with PARROT replacement policy?",
    "Which replacement policy performs best on the mcf workload",
    "Which replacement policy has the lowest miss rate for PC 0x401804 on the lbm workload?",
    "When the PARROT replacement policy accesses address PC 0x4037aa and address 0xa3a0df8544 on the mcf workload, does the cache hit or miss?",
    "Did address 0x18a6a0dd67e (PC 0x401dc9) get evicted in the lbm workload under the PARROT replacement policy?",
    "Was address 0x160a69ba644 (PC 0x4037ba) ever evicted in the lbm workload under the LRU replacement policy?",
    "Did address 0xa3a0df7043 (PC 0x4037c1) result in an eviction in the astar workload under the LRU replacement policy?"
]

# New 9 benchmark queries for further analysis
new_queries = [
    "Why does the astar workload have a high miss rate across the LRU, MLP, and PARROT replacement policies?",
    "For the memory access with PC 0x405832 and address 0x2ad51d2d9d on the astar workload, which replacement policy made the best eviction decision?",
    "Why does the PARROT replacement policy achieve a lower miss rate for PC 0x401d8b on the lbm workload?",
    "On which workload does the MLP model have the lowest miss rate, and why might that workload be more challenging?",
    "Does the LRU replacement policy perform well on the mcf workload, or would a learned policy perform better?",
    "When does the mainQSort3 function cause cache misses in the bzip workload, such as for PC 0x403368, and which replacement policy is best equipped to handle this function?",
    "Does the PARROT policy do a good job of approximating Belady’s optimal policy for the astar workload?",
    "For the lbm workload at PC 0x401e47, which replacement policy delays cache misses the longest, and why might that be the case?",
    "In the mcf workload, does LRU or a learned policy retain cache data longer?",
    "For the astar workload, which replacement policy best balances evicting less critical data while preserving frequently used lines, and why is that balance beneficial?"
]

# Choose which queries to process
# For example, here we use the new queries:
queries = new_queries

# -----------------------------------------------------------------------------
# Process each query using the RAG system, print and store the results
# -----------------------------------------------------------------------------
results = []
for query in queries:
    prompt, response = analyze_text_prompt(query, loaded_data)
    # If the response begins with the prompt text, remove it for clarity.
    if response.startswith(prompt):
        response = response[len(prompt):]
    results.append({"query": query, "prompt": prompt, "response": response})
    print("\nQuery:", query)
    print("Response:", response)
    print("-" * 80)

print("RAG analysis complete.")
