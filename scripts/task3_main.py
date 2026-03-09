import os
import torch
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer
)
from peft import LoraConfig, get_peft_model

###############################################################################
# 1. Load the Raw Dataset
###############################################################################
dataset = load_dataset("json", data_files="llm_training_data_with_program_semantics.json")
raw_data = dataset["train"]  # assuming a single split; adjust if you have a test split

###############################################################################
# 2. Merge "prompt" & "completion" into a Single "text" Field
###############################################################################
def combine_prompt_and_completion(example):
    example["text"] = example["prompt"] + "\n" + example["completion"]
    return example

merged_data = raw_data.map(combine_prompt_and_completion)

###############################################################################
# 3. Pre-Tokenization Function
###############################################################################
def tokenize_fn(example):
    # Tokenize the merged text field and set labels = input_ids for causal LM
    tokenized = tokenizer(
        example["text"],
        padding="max_length",        # or use True
        truncation=True,
        max_length=512
    )
    tokenized["labels"] = tokenized["input_ids"].copy()
    return tokenized

###############################################################################
# 4. Load Tokenizer & Pre-Tokenize the Dataset
###############################################################################
model_id = "./local_model_dir"  # or "LLAMA" if that works in your env
tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "right"

# Apply function so dataset has input_ids, attention_mask, and labels
tokenized_data = merged_data.map(tokenize_fn, batched=True, remove_columns=["prompt", "completion", "text"])

###############################################################################
# 5. 4-bit BitsAndBytes Config
###############################################################################
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
)

###############################################################################
# 6. Load the Base Model & Wrap with LoRA
###############################################################################
base_model = AutoModelForCausalLM.from_pretrained(
    model_id,
    quantization_config=bnb_config,
    device_map="auto",
    trust_remote_code=True
)
base_model.config.use_cache = False

peft_config = LoraConfig(
    lora_alpha=16,
    lora_dropout=0.1,
    r=64,
    bias="none",
    task_type="CAUSAL_LM",
)
model = get_peft_model(base_model, peft_config)
model.print_trainable_parameters()

###############################################################################
# 7. Define Training Arguments
###############################################################################
output_dir = "./main_output"
os.makedirs(output_dir, exist_ok=True)

training_args = TrainingArguments(
    output_dir=output_dir,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    logging_steps=10,
    max_steps=100000,
    evaluation_strategy="no",    # no mid-training eval (change if you do have a valid set)
    save_steps=1000,
    save_total_limit=5,
    push_to_hub=False,
    report_to="none",
    remove_unused_columns=False
)

###############################################################################
# 8. Initialize Trainer (Removed max_seq_length)
###############################################################################
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_data,  # tokenized dataset
    tokenizer=tokenizer
)

###############################################################################
# 9. Train the Model
###############################################################################
trainer.train()

###############################################################################
# 10. Save the Final Model & Tokenizer
###############################################################################
final_ckpt_path = os.path.join(output_dir, "trained_model_ckpt")
model.save_pretrained(final_ckpt_path)
tokenizer.save_pretrained(final_ckpt_path)

print("Fine-tuning complete!")
print(f"Model saved to: {final_ckpt_path}")
