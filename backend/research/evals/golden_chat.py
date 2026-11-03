"""
research/evals/golden_chat.py — Golden evaluation set for Paper Chat (Step 3)

Exit criteria from phases.md:
  - Citation validity is 100% on the golden set (every quoted excerpt matches retrieved chunk).
  - Abstention works on the unanswerable set ("The paper does not appear to cover that.").
"""

from __future__ import annotations

GOLDEN_PAPER_TEXT = """\
Attention Is All You Need introduces the Transformer, a novel sequence transduction architecture
based entirely on attention mechanisms, dispensing with recurrence and convolutions entirely.
Experiments on two machine translation tasks show these models to be superior in quality while
being more parallelizable and requiring significantly less time to train.

Our model achieves 28.4 BLEU on the WMT 2014 English-to-German translation task, improving over
the existing best results, including ensembles, by over 2 BLEU. On the WMT 2014 English-to-French
translation task, our model establishes a new single-model state-of-the-art BLEU score of 41.8
after training for 3.5 days on eight GPUs.

The Transformer uses multi-head self-attention where the queries, keys and values are vectors of
dimension d_k. In our work, we set d_model = 512, with 8 parallel attention heads. For each head,
we use d_k = d_v = d_model / h = 64. Due to the reduced dimension of each head, the total
computational cost is similar to that of single-head attention with full dimensionality.

We train on the standard WMT 2014 English-German dataset consisting of about 4.5 million sentence pairs.
Sentences were encoded using byte-pair encoding, which has a shared source-target vocabulary of
about 37,000 tokens. For English-French, we used the significantly larger WMT 2014 English-French
dataset consisting of 36 million sentences.

The Transformer is the first transduction model relying entirely on self-attention to compute
representations of its input and output without using sequence-aligned RNNs or convolution.
"""

GOLDEN_CHAT_EXAMPLES = [
    {
        "id": "chat_001",
        "question": "What BLEU score does the model achieve on WMT 2014 English-to-German?",
        "is_answerable": True,
        "expected_substrings": ["28.4 BLEU"],
        "expected_quote": "Our model achieves 28.4 BLEU on the WMT 2014 English-to-German translation task",
    },
    {
        "id": "chat_002",
        "question": "How many parallel attention heads are used and what is the dimension of each head?",
        "is_answerable": True,
        "expected_substrings": ["8", "64"],
        "expected_quote": "with 8 parallel attention heads. For each head, we use d_k = d_v = d_model / h = 64.",
    },
    {
        "id": "chat_003",
        "question": "How many GPUs were used and how long was the English-to-French training?",
        "is_answerable": True,
        "expected_substrings": ["3.5 days", "eight GPUs"],
        "expected_quote": "after training for 3.5 days on eight GPUs.",
    },
    {
        "id": "chat_004",
        "question": "What encoding was used for sentences in the English-German dataset?",
        "is_answerable": True,
        "expected_substrings": ["byte-pair encoding", "37,000 tokens"],
        "expected_quote": "Sentences were encoded using byte-pair encoding, which has a shared source-target vocabulary of about 37,000 tokens.",
    },
    {
        "id": "chat_005",
        "question": "What is the key difference between this model and recurrent neural networks?",
        "is_answerable": True,
        "expected_substrings": ["dispensing with recurrence and convolutions entirely"],
        "expected_quote": "dispensing with recurrence and convolutions entirely.",
    },
    # Unanswerable questions (Rule 12 & design.md §5 honest abstention)
    {
        "id": "chat_unans_001",
        "question": "What is the learning rate schedule used for training the Vision Transformer on ImageNet?",
        "is_answerable": False,
        "expected_substrings": ["The paper does not appear to cover that."],
    },
    {
        "id": "chat_unans_002",
        "question": "What are the molecular docking binding affinities computed in the experiments?",
        "is_answerable": False,
        "expected_substrings": ["The paper does not appear to cover that."],
    },
    {
        "id": "chat_unans_003",
        "question": "What is the stock price impact on tech companies after this paper was released?",
        "is_answerable": False,
        "expected_substrings": ["The paper does not appear to cover that."],
    },
    {
        "id": "chat_unans_004",
        "question": "How does this model perform on audio speech recognition benchmarks like LibriSpeech?",
        "is_answerable": False,
        "expected_substrings": ["The paper does not appear to cover that."],
    },
]

