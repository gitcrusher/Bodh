"""
learning/evals/golden_questions.py — Golden question bank for the quiz critic (Step 2)

Rule 41: a module cannot ship an LLM step without golden examples.
These questions are the ground-truth reference for:
  - Quiz critic evaluation (does the critic correctly assess difficulty?)
  - Regression tests (do option randomisation and answer mapping work?)

Each entry is a dict matching the QuizQuestion schema.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Seed data: core AI/ML topics, 3 difficulty tiers each
# ---------------------------------------------------------------------------

GOLDEN_QUESTIONS: list[dict] = [

    # ── Transformers ────────────────────────────────────────────────────────

    {
        "topic_slug": "transformers",
        "difficulty": "easy",
        "stem": "What is the primary role of the attention mechanism in a Transformer?",
        "options": [
            "To compress the input into a fixed-size vector",
            "To allow the model to focus on relevant parts of the input when producing each output",
            "To apply convolutions across the sequence",
            "To enforce positional ordering by masking future tokens",
        ],
        "correct_index": 1,
        "explanation": (
            "Self-attention lets each position 'attend' to all other positions, "
            "weighting them by relevance. This replaces recurrence and convolution "
            "as the main context-aggregation mechanism."
        ),
    },
    {
        "topic_slug": "transformers",
        "difficulty": "medium",
        "stem": (
            "In multi-head attention, why are multiple heads used instead of a single attention "
            "function over the full dimension?"
        ),
        "options": [
            "To reduce memory usage by sharing weights across heads",
            "To allow the model to jointly attend to information from different representation subspaces",
            "To enforce that each token attends only to its immediate neighbours",
            "To replace the feed-forward sublayer with cheaper operations",
        ],
        "correct_index": 1,
        "explanation": (
            "Multiple heads project queries, keys, and values into lower-dimensional subspaces "
            "independently. This lets the model capture different kinds of relationships "
            "(syntactic, semantic, positional) simultaneously."
        ),
    },
    {
        "topic_slug": "transformers",
        "difficulty": "hard",
        "stem": (
            "The original 'Attention Is All You Need' paper uses learned positional embeddings "
            "in some configurations and sinusoidal encodings in others. Which property of "
            "sinusoidal encodings motivated their inclusion?"
        ),
        "options": [
            "Sinusoidal encodings are parameter-free and can extrapolate to sequence lengths not seen during training",
            "Sinusoidal encodings are lower variance than learned embeddings, reducing overfitting",
            "Sinusoidal encodings enforce causal masking automatically",
            "Sinusoidal encodings are differentiable everywhere, making back-propagation stable",
        ],
        "correct_index": 0,
        "explanation": (
            "The paper hypothesised that sinusoidal encodings would allow the model to generalise "
            "to sequence lengths longer than those in training, because the relative positions can "
            "be expressed as linear functions of the sinusoidal values. Learned embeddings cannot "
            "extrapolate to unseen positions."
        ),
    },

    # ── Diffusion models ─────────────────────────────────────────────────────

    {
        "topic_slug": "diffusion_models",
        "difficulty": "easy",
        "stem": "What does a diffusion model learn to do during training?",
        "options": [
            "Compress images into a discrete codebook",
            "Predict the noise added to data at each step of a forward noising process",
            "Classify images into categories using contrastive loss",
            "Generate images by sampling from a learned discrete prior",
        ],
        "correct_index": 1,
        "explanation": (
            "Training minimises the difference between the actual noise added (forward process) "
            "and the noise the model predicts. At inference the model reverses this iteratively."
        ),
    },
    {
        "topic_slug": "diffusion_models",
        "difficulty": "medium",
        "stem": (
            "Classifier-free guidance (Ho & Salimans, 2021) improves sample quality at the cost "
            "of diversity. How does it work during inference?"
        ),
        "options": [
            "A separately trained classifier gradient steers the diffusion trajectory",
            "The model is conditioned and unconditioned at each step; outputs are linearly combined with a guidance scale",
            "The guidance signal is injected into the latent code before the reverse process",
            "Diversity is maintained by running multiple parallel chains and selecting the best sample",
        ],
        "correct_index": 1,
        "explanation": (
            "At each denoising step the model runs twice: once conditioned on the prompt and once "
            "unconditioned. The final noise prediction is: uncond + scale × (cond − uncond). "
            "Higher scale → more guidance → higher quality but less diversity."
        ),
    },
    {
        "topic_slug": "diffusion_models",
        "difficulty": "hard",
        "stem": (
            "Denoising Diffusion Implicit Models (DDIMs) reduce inference cost by taking larger "
            "steps. What theoretical property makes this possible?"
        ),
        "options": [
            "DDIMs replace the stochastic reverse process with a deterministic ODE, preserving the same marginals",
            "DDIMs use a learned step-size scheduler that skips noise levels with low signal-to-noise ratio",
            "DDIMs distil the full model into a smaller network trained to jump directly to clean data",
            "DDIMs apply importance sampling to concentrate steps near the final denoising stage",
        ],
        "correct_index": 0,
        "explanation": (
            "Song et al. (2020) show that a class of non-Markovian processes shares the same "
            "forward marginals as DDPM. The reverse of this process is a deterministic ODE that "
            "can be solved with far fewer function evaluations (e.g. 50 instead of 1000)."
        ),
    },

    # ── RAG (Retrieval-Augmented Generation) ─────────────────────────────────

    {
        "topic_slug": "rag",
        "difficulty": "easy",
        "stem": "What problem does Retrieval-Augmented Generation (RAG) primarily address?",
        "options": [
            "Reducing the number of parameters required for a language model",
            "Grounding generated answers in retrieved documents to reduce hallucinations",
            "Speeding up training by caching attention patterns",
            "Enabling models to generate structured outputs like tables and code",
        ],
        "correct_index": 1,
        "explanation": (
            "RAG retrieves relevant documents at inference time and conditions generation on them, "
            "so the model's answers are grounded in retrieved evidence rather than only its "
            "parametric memory — reducing factual hallucinations."
        ),
    },
    {
        "topic_slug": "rag",
        "difficulty": "medium",
        "stem": "In a RAG system, what is the role of the bi-encoder (dense retriever)?",
        "options": [
            "To re-rank candidate passages using cross-attention over the full query-passage pair",
            "To embed queries and passages independently and retrieve by maximum inner product search",
            "To extract exact answer spans from the retrieved passage",
            "To compress multiple retrieved passages into a single context vector",
        ],
        "correct_index": 1,
        "explanation": (
            "Bi-encoders (e.g. DPR) encode the query and each passage separately into dense vectors. "
            "Retrieval is then a nearest-neighbour search (MIPS) over a pre-built index. "
            "Cross-encoders, by contrast, see both inputs together but are too slow for first-stage retrieval."
        ),
    },
    {
        "topic_slug": "rag",
        "difficulty": "hard",
        "stem": (
            "When retrieval confidence is borderline in a RAG pipeline, the design rules for this "
            "app state that an extra LLM verification pass runs. What does 'borderline confidence' "
            "typically mean in a dense retrieval context?"
        ),
        "options": [
            "The retrieved passage score is below a threshold but above a floor, requiring a cross-encoder re-rank",
            "The retrieval model returns embeddings with high cosine variance across the top-k passages",
            "The generator assigns a low log-probability to the answer conditioned on the retrieved passage",
            "The top-1 and top-2 passage scores are within a narrow margin of each other",
        ],
        "correct_index": 3,
        "explanation": (
            "A borderline confidence signal commonly means the retriever cannot confidently pick "
            "one passage: the top-1 and top-2 scores are close. This ambiguity warrants a "
            "more expensive cross-encoder or LLM re-rank to confirm whether the best passage "
            "actually answers the query."
        ),
    },

    # ── Fine-tuning / RLHF ───────────────────────────────────────────────────

    {
        "topic_slug": "fine_tuning",
        "difficulty": "easy",
        "stem": "What is the main goal of RLHF (Reinforcement Learning from Human Feedback)?",
        "options": [
            "To compress a large model into a smaller distilled version",
            "To align a language model's outputs with human preferences",
            "To speed up inference by pruning unimportant attention heads",
            "To train a model on code datasets using a compiler as reward signal",
        ],
        "correct_index": 1,
        "explanation": (
            "RLHF trains a reward model on human preference comparisons, then fine-tunes "
            "the language model using RL (PPO) to maximise that reward — steering outputs "
            "toward what humans rate as helpful, harmless, and honest."
        ),
    },
    {
        "topic_slug": "fine_tuning",
        "difficulty": "medium",
        "stem": "LoRA (Low-Rank Adaptation) reduces training cost by:",
        "options": [
            "Freezing all layers except the final classification head",
            "Decomposing weight updates into two low-rank matrices and training only those",
            "Distilling the fine-tuned model back into the base model weights",
            "Quantising gradients to 8-bit during back-propagation",
        ],
        "correct_index": 1,
        "explanation": (
            "LoRA inserts trainable rank-r matrices A and B alongside frozen weight matrices W. "
            "The effective weight update ΔW = BA has rank ≤ r ≪ d, so parameter count and "
            "memory are dramatically reduced while full fine-tuning quality is approached."
        ),
    },
    {
        "topic_slug": "fine_tuning",
        "difficulty": "hard",
        "stem": (
            "Direct Preference Optimization (DPO) removes the need for a separate reward model. "
            "How does it achieve alignment?"
        ),
        "options": [
            "It trains the policy directly on a contrastive loss derived from the Bradley-Terry preference model, using the reference policy as an implicit reward",
            "It replaces PPO with a simpler cross-entropy loss over preferred completions only",
            "It fine-tunes using a verifier that scores outputs without human labels",
            "It augments the SFT loss with a KL penalty against the original model's distribution",
        ],
        "correct_index": 0,
        "explanation": (
            "DPO (Rafailov et al. 2023) shows that the RL objective under the Bradley-Terry model "
            "can be re-expressed as a classification loss over preference pairs. The reference "
            "model (frozen SFT checkpoint) acts as an implicit reward, so no separate reward "
            "model or PPO training loop is needed."
        ),
    },
]
