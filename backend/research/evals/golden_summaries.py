"""
research/evals/golden_summaries.py

Golden eval dataset for the research summarization recipe (SUMMARIZE_RECIPE).
Enforces Rule 41: "A module cannot ship an LLM step without golden examples."
"""

from core.eval.harness import EvalCase

SUMMARIZE_GOLDEN_CASES = [
    EvalCase(
        id="golden_attention_transformer",
        input={
            "title": "Attention Is All You Need",
            "abstract": (
                "The dominant sequence transduction models are based on complex recurrent or convolutional neural "
                "networks in an encoder-decoder configuration. We propose the Transformer, a model architecture "
                "eschewing recurrence and instead relying entirely on an attention mechanism to draw global dependencies "
                "between input and output. The Transformer allows for significantly more parallelization and can reach "
                "a new state of the art in translation quality after being trained for as little as twelve hours on eight P100 GPUs."
            ),
        },
        expected={
            "key_techniques": ["Transformer", "attention mechanism"],
            "key_metrics": ["twelve hours", "eight P100 GPUs"],
        },
        tags=["core_architecture", "benchmark"],
        notes="Foundational transformer paper, must capture attention mechanism and parallelization.",
    ),
    EvalCase(
        id="golden_lora_fine_tuning",
        input={
            "title": "LoRA: Low-Rank Adaptation of Large Language Models",
            "abstract": (
                "An important paradigm of natural language processing consists of large-scale pre-training on general domain data "
                "and adaptation to particular tasks or domains. As we pre-train larger models, full fine-tuning becomes less feasible. "
                "We propose Low-Rank Adaptation (LoRA), which freezes the pre-trained model weights and injects trainable rank decomposition "
                "matrices into each layer of the Transformer architecture, greatly reducing the number of trainable parameters for downstream tasks. "
                "Compared to GPT-3 175B fine-tuned with Adam, LoRA can reduce the number of trainable parameters by 10,000 times and the GPU memory requirement by 3 times."
            ),
        },
        expected={
            "key_techniques": ["LoRA", "low-rank adaptation", "rank decomposition"],
            "key_metrics": ["10,000 times", "3 times"],
        },
        tags=["parameter_efficient", "fine_tuning"],
        notes="Parameter-efficient adaptation paper, numerical ratios must be faithfully preserved.",
    ),
    EvalCase(
        id="golden_flash_attention",
        input={
            "title": "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness",
            "abstract": (
                "Transformers are slow and memory-hungry on long sequences, as the time and memory complexity of self-attention are quadratic in sequence length. "
                "We argue that a missing principle is making attention algorithms IO-aware—accounting for reads and writes between levels of GPU memory. "
                "We propose FlashAttention, an IO-aware exact attention algorithm that uses tiling to reduce the number of memory reads/writes between GPU high bandwidth memory (HBM) and GPU on-chip SRAM. "
                "FlashAttention trains Transformers faster than existing baselines: 15% speedup on BERT-large, 3x speedup on GPT-2, and enables 64k context lengths."
            ),
        },
        expected={
            "key_techniques": ["FlashAttention", "IO-aware", "tiling", "SRAM"],
            "key_metrics": ["15% speedup", "3x speedup", "64k context"],
        },
        tags=["hardware_optimization", "efficiency"],
        notes="Hardware-aware attention algorithm. Speedup numbers and context length must be exact.",
    ),
]
