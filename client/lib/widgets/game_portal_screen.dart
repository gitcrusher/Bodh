import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';
import 'quiz_modal.dart';
import 'user_avatar.dart';

/// Represents a curated milestone step in the AI/ML curriculum.
class RoadmapStep {
  final int stepNumber;
  final String title;
  final String subtitle;
  final String topicSlug;
  final String paperTitle;
  final String paperVenue;
  final String paperArxivUrl;
  final String paperSummary;
  final String keyInsight;
  final int xpReward;
  final String badgeName;
  final bool isCompleted;
  final bool isCurrent;
  final bool isLocked;

  const RoadmapStep({
    required this.stepNumber,
    required this.title,
    required this.subtitle,
    required this.topicSlug,
    required this.paperTitle,
    required this.paperVenue,
    required this.paperArxivUrl,
    required this.paperSummary,
    required this.keyInsight,
    required this.xpReward,
    required this.badgeName,
    this.isCompleted = false,
    this.isCurrent = false,
    this.isLocked = false,
  });
}

/// Represents a subject / category track in the AI/ML Gaming Portal.
class SubjectTrack {
  final String id;
  final String name;
  final String icon;
  final String description;
  final List<RoadmapStep> steps;

  const SubjectTrack({
    required this.id,
    required this.name,
    required this.icon,
    required this.description,
    required this.steps,
  });
}

/// Duolingo-style Gaming Portal Screen with visual winding roadmaps,
/// landmark canon research paper study cards, and anti-cheat milestone exams.
class GamePortalScreen extends StatefulWidget {
  final String initialTrackId;

  const GamePortalScreen({
    super.key,
    this.initialTrackId = 'transformers',
  });

  @override
  State<GamePortalScreen> createState() => _GamePortalScreenState();
}

class _GamePortalScreenState extends State<GamePortalScreen> {
  final ApiService _apiService = ApiService();
  final AuthService _auth = AuthService();

  late String _selectedTrackId;
  int _userXp = 450;
  final int _dailyStreak = 1;
  bool _isLoading = false;
  Map<String, dynamic>? _ingestStatus;

  late final List<SubjectTrack> _tracks;

  @override
  void initState() {
    super.initState();
    _selectedTrackId = widget.initialTrackId;
    _initTracks();
    _loadIngestStatus();
  }

  void _initTracks() {
    _tracks = [
      const SubjectTrack(
        id: 'transformers',
        name: 'Transformers & LLMs',
        icon: '⚡',
        description: 'Foundational attention mechanisms, scaling laws, and modern frontier architectures.',
        steps: [
          RoadmapStep(
            stepNumber: 1,
            title: 'Attention & Sequence Foundations',
            subtitle: 'Eliminating recurrence with multi-head self-attention',
            topicSlug: 'transformers',
            paperTitle: 'Attention Is All You Need',
            paperVenue: 'NeurIPS 2017 · Tier 1 Landmark',
            paperArxivUrl: 'https://arxiv.org/abs/1706.03762',
            paperSummary:
                '• Proposes the Transformer architecture, replacing RNNs/LSTMs entirely with self-attention.\n'
                '• Draws global token dependencies in parallel, speeding up training by orders of magnitude.\n'
                '• Reaches SOTA on WMT English-to-German after only 12 hours on 8 GPUs.\n'
                '• Landmark substrate for BERT, GPT, Claude, and modern foundation models.',
            keyInsight: 'Self-Attention: Q, K, V projections and Scaled Dot-Product computation.',
            xpReward: 100,
            badgeName: 'Transformer Pioneer',
            isCompleted: true,
          ),
          RoadmapStep(
            stepNumber: 2,
            title: 'Scaling Laws & Pre-Training',
            subtitle: 'Compute-optimal scaling and high-throughput dense models',
            topicSlug: 'transformers',
            paperTitle: 'The Llama 3 Herd of Models',
            paperVenue: 'Meta AI 2024 · Tier 1 Landmark',
            paperArxivUrl: 'https://arxiv.org/abs/2407.21783',
            paperSummary:
                '• Scaling dense foundation models across 15+ trillion tokens of multilingual data.\n'
                '• Employs Grouped-Query Attention (GQA) with 128k context length natively.\n'
                '• Demonstrates post-training alignment at scale with iterative DPO and rejection sampling.\n'
                '• Open weights reference implementation for high-throughput enterprise systems.',
            keyInsight: 'Compute-Optimal Pretraining & GQA Memory Efficiency.',
            xpReward: 150,
            badgeName: 'Scaling Strategist',
            isCurrent: true,
          ),
          RoadmapStep(
            stepNumber: 3,
            title: 'IO-Aware Hardware Acceleration',
            subtitle: 'Optimizing SRAM tiling and asynchronous warp execution',
            topicSlug: 'transformers',
            paperTitle: 'FlashAttention-3: Fast Attention with Asynchrony',
            paperVenue: 'Stanford 2024 · Tier 1 Landmark',
            paperArxivUrl: 'https://arxiv.org/abs/2407.08608',
            paperSummary:
                '• Overlaps GEMM and softmax computations across warp-group specialization on NVIDIA Hopper.\n'
                '• Delivers up to 740 TFLOPs/s (75% theoretical peak H100 utilization).\n'
                '• Maintains exact mathematical attention without numerical approximations.\n'
                '• Critical engineering step for long-context inference and multi-modal attention.',
            keyInsight: 'SRAM Tiling & Asynchronous FP8 Warp Execution.',
            xpReward: 150,
            badgeName: 'Kernel Wizard',
            isLocked: false,
          ),
          RoadmapStep(
            stepNumber: 4,
            title: 'Parameter-Efficient Fine-Tuning',
            subtitle: 'Adapting billion-parameter models with low-rank decomposition',
            topicSlug: 'fine_tuning',
            paperTitle: 'LoRA: Low-Rank Adaptation of Large Language Models',
            paperVenue: 'ICLR 2022 · Tier 1 Landmark',
            paperArxivUrl: 'https://arxiv.org/abs/2106.09685',
            paperSummary:
                '• Freezes pre-trained weights and injects trainable rank decomposition matrices.\n'
                '• Reduces trainable parameters by 10,000x and GPU memory footprint by 3x.\n'
                '• Zero added inference latency: weights can be folded back Delta W = B * A at runtime.\n'
                '• Ubiquitous standard for fine-tuning LLMs on commodity consumer GPUs.',
            keyInsight: 'Intrinsic Dimensionality & Low-Rank Weight Invariant Decomposition.',
            xpReward: 200,
            badgeName: 'PEFT Master',
            isLocked: true,
          ),
          RoadmapStep(
            stepNumber: 5,
            title: 'Emergent Reasoning & Pure RL',
            subtitle: 'Incentivizing chain-of-thought without supervised cold-start',
            topicSlug: 'transformers',
            paperTitle: 'DeepSeek-R1: Pure RL Reasoning Emergence',
            paperVenue: 'DeepSeek 2025 · Frontier Milestone',
            paperArxivUrl: 'https://arxiv.org/abs/2501.12948',
            paperSummary:
                '• Demonstrates strong mathematical and coding reasoning purely through large-scale RL.\n'
                '• Group Relative Policy Optimization (GRPO) eliminating costly critic neural networks.\n'
                '• Autonomous emergence of self-reflection, rethinking, and test-time verification.\n'
                '• Paradigm shift from supervised pre-training to test-time compute expansion.',
            keyInsight: 'GRPO Policy Gradient & Verification Reward Models.',
            xpReward: 300,
            badgeName: 'Grandmaster Researcher',
            isLocked: true,
          ),
        ],
      ),
      const SubjectTrack(
        id: 'diffusion',
        name: 'Generative & Diffusion',
        icon: '🎨',
        description: 'Score-based modeling, DDPM, latent diffusion, and flow matching.',
        steps: [
          RoadmapStep(
            stepNumber: 1,
            title: 'Denoising Diffusion Probabilistic Models',
            subtitle: 'Langevin dynamics and reverse score matching',
            topicSlug: 'diffusion_models',
            paperTitle: 'Denoising Diffusion Probabilistic Models (DDPM)',
            paperVenue: 'NeurIPS 2020 · Landmark',
            paperArxivUrl: 'https://arxiv.org/abs/2006.11239',
            paperSummary:
                '• Proposes parameterizing reverse Markov transitions with neural networks.\n'
                '• Connects diffusion models with denoising score matching and Langevin dynamics.\n'
                '• First diffusion paper to rival GANs in photographic sample quality.',
            keyInsight: 'Forward Gaussian Markov Chains & Variational Lower Bound Denoising.',
            xpReward: 100,
            badgeName: 'Noise Architect',
            isCompleted: true,
          ),
          RoadmapStep(
            stepNumber: 2,
            title: 'High-Resolution Latent Diffusion',
            subtitle: 'Compressing perceptual space with autoencoders',
            topicSlug: 'diffusion_models',
            paperTitle: 'High-Resolution Image Synthesis with Latent Diffusion',
            paperVenue: 'CVPR 2022 · Landmark (Stable Diffusion)',
            paperArxivUrl: 'https://arxiv.org/abs/2112.10752',
            paperSummary:
                '• Applies diffusion in the latent space of a pretrained autoencoder.\n'
                '• Reduces computational training requirements by over 10x.\n'
                '• Foundation for the open-source Stable Diffusion revolution.',
            keyInsight: 'Cross-Attention Conditioning in Latent Space.',
            xpReward: 150,
            badgeName: 'Latent Explorer',
            isCurrent: true,
          ),
          RoadmapStep(
            stepNumber: 3,
            title: 'Diffusion Transformers & Flow Matching',
            subtitle: 'Scaling generative visual backbones with transformer blocks',
            topicSlug: 'diffusion_models',
            paperTitle: 'Scalable Diffusion Models with Transformers (DiT)',
            paperVenue: 'ICCV 2023 · Milestone (Sora Foundation)',
            paperArxivUrl: 'https://arxiv.org/abs/2212.09748',
            paperSummary:
                '• Replaces standard U-Net with ViT transformer blocks.\n'
                '• Demonstrates clear compute scaling laws for diffusion models.\n'
                '• Architectural backbone for modern video generation models like Sora.',
            keyInsight: 'Patchification & Adaptive LayerNorm Modulation.',
            xpReward: 200,
            badgeName: 'DiT Specialist',
            isLocked: true,
          ),
        ],
      ),
      const SubjectTrack(
        id: 'rag',
        name: 'RAG & Retrieval',
        icon: '🔍',
        description: 'Dense passage retrieval, hybrid BM25, reranking, and citation verification.',
        steps: [
          RoadmapStep(
            stepNumber: 1,
            title: 'Retrieval-Augmented Generation',
            subtitle: 'Knowledge-intensive NLP grounded in external corpora',
            topicSlug: 'rag',
            paperTitle: 'Retrieval-Augmented Generation for Knowledge-Intensive NLP',
            paperVenue: 'NeurIPS 2020 · Landmark',
            paperArxivUrl: 'https://arxiv.org/abs/2005.11401',
            paperSummary:
                '• Combines pre-trained parametric memory with non-parametric dense retrieval.\n'
                '• Employs Dense Passage Retriever (DPR) with BART generator.\n'
                '• Drastically reduces factual hallucinations in question answering.',
            keyInsight: 'Differentiable Dense Index Retrieval & Marginalized Generation.',
            xpReward: 100,
            badgeName: 'Knowledge Anchor',
            isCompleted: true,
          ),
          RoadmapStep(
            stepNumber: 2,
            title: 'Faithful Grounding & Citation Verification',
            subtitle: 'Eliminating hallucinations with 100% deterministic attribution',
            topicSlug: 'rag',
            paperTitle: 'Self-RAG: Learning to Retrieve, Generate, and Critique',
            paperVenue: 'ICLR 2024 · Milestone',
            paperArxivUrl: 'https://arxiv.org/abs/2310.11511',
            paperSummary:
                '• Trains models to output reflection tokens: Retrieve, IsRel, IsSup, IsUse.\n'
                '• Selectively retrieves documents only when factual uncertainty is high.\n'
                '• Enforces verified verbatim quoting from retrieved context.',
            keyInsight: 'Reflection Tokens & Verifiable Substring Attribution.',
            xpReward: 150,
            badgeName: 'Citation Sentry',
            isCurrent: true,
          ),
        ],
      ),
    ];
  }

  Future<void> _loadIngestStatus() async {
    final status = await _apiService.fetchIngestionStatus();
    if (mounted) {
      setState(() => _ingestStatus = status);
    }
  }

  SubjectTrack get _currentTrack =>
      _tracks.firstWhere((t) => t.id == _selectedTrackId, orElse: () => _tracks.first);

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final track = _currentTrack;

    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      appBar: AppBar(
        backgroundColor: const Color(0xFF161B22),
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, color: Colors.white, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
        title: const Row(
          children: [
            Icon(Icons.sports_esports_rounded, color: Colors.greenAccent, size: 22),
            SizedBox(width: 8),
            Text(
              'GAMING PORTAL',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w900,
                letterSpacing: 1.0,
                color: Colors.white,
              ),
            ),
          ],
        ),
        actions: [
          // Ingestion Health Hub Button
          IconButton(
            tooltip: 'Paper Ingestion Status',
            icon: const Icon(Icons.cloud_sync_rounded, color: Colors.lightBlueAccent, size: 22),
            onPressed: _showIngestionModal,
          ),
          Padding(
            padding: const EdgeInsets.only(right: 14),
            child: UserAvatar(
              avatarUrl: _auth.avatarUrl,
              username: _auth.username,
              radius: 16,
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          // 1. Duolingo Stats Banner (Streak, XP, Anti-Cheat, Milestone progress)
          _buildDuolingoHeaderBanner(),

          // 2. Track / Subject Selector Pills
          _buildTrackSelector(),

          const Divider(height: 1, color: Colors.white12),

          // 3. The Winding Roadmap / Stepping Stones
          Expanded(
            child: _buildRoadmapView(track, theme, colorScheme),
          ),
        ],
      ),
    );
  }

  /// Duolingo Header Banner with Streak, XP, Anti-Cheat Shield, and Level
  Widget _buildDuolingoHeaderBanner() {
    return Container(
      color: const Color(0xFF161B22),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          // Streak
          Row(
            children: [
              const Icon(Icons.local_fire_department_rounded, color: Colors.deepOrangeAccent, size: 22),
              const SizedBox(width: 4),
              Text(
                '$_dailyStreak Day',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: Colors.white),
              ),
            ],
          ),

          // XP Points
          Row(
            children: [
              const Icon(Icons.star_rounded, color: Colors.amberAccent, size: 22),
              const SizedBox(width: 4),
              Text(
                '$_userXp XP',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: Colors.white),
              ),
            ],
          ),

          // Anti-Cheat Guarantee
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: Colors.blue.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.blueAccent.withValues(alpha: 0.3)),
            ),
            child: const Row(
              children: [
                Icon(Icons.shield_rounded, color: Color(0xFF58A6FF), size: 14),
                SizedBox(width: 4),
                Text(
                  'Anti-Cheat',
                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Color(0xFF58A6FF)),
                ),
              ],
            ),
          ),

          // Milestone Progress Counter
          Row(
            children: [
              const Icon(Icons.emoji_events_rounded, color: Colors.greenAccent, size: 20),
              const SizedBox(width: 4),
              Text(
                '${_currentTrack.steps.where((s) => s.isCompleted).length}/${_currentTrack.steps.length}',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Colors.white70),
              ),
            ],
          ),
        ],
      ),
    );
  }

  /// Horizontal scrolling track / category selector
  Widget _buildTrackSelector() {
    return Container(
      height: 48,
      color: const Color(0xFF12161D),
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        itemCount: _tracks.length,
        itemBuilder: (context, idx) {
          final t = _tracks[idx];
          final isSelected = t.id == _selectedTrackId;

          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: ChoiceChip(
              avatar: Text(t.icon, style: const TextStyle(fontSize: 13)),
              label: Text(t.name),
              selected: isSelected,
              onSelected: (val) {
                if (val) setState(() => _selectedTrackId = t.id);
              },
              selectedColor: const Color(0xFF238636),
              backgroundColor: const Color(0xFF161B22),
              labelStyle: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.bold,
                color: isSelected ? Colors.white : Colors.white70,
              ),
              side: BorderSide(
                color: isSelected ? Colors.greenAccent : Colors.white12,
              ),
            ),
          );
        },
      ),
    );
  }

  /// Winding Duolingo-style roadmap path with interactive step nodes
  Widget _buildRoadmapView(SubjectTrack track, ThemeData theme, ColorScheme colorScheme) {
    return ListView(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 20),
      children: [
        // Track Header Banner
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: const Color(0xFF161B22),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: Colors.white12),
          ),
          child: Row(
            children: [
              Text(track.icon, style: const TextStyle(fontSize: 32)),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      track.name.toUpperCase(),
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 0.8,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      track.description,
                      style: const TextStyle(fontSize: 12, color: Colors.white60, height: 1.3),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),

        const SizedBox(height: 24),

        // Steps Title
        const Center(
          child: Text(
            'CURATED RESEARCH ROADMAP · STEP-BY-STEP CANON',
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.bold,
              letterSpacing: 1.2,
              color: Colors.white38,
            ),
          ),
        ),

        const SizedBox(height: 20),

        // Winding Road Nodes
        for (int i = 0; i < track.steps.length; i++) ...[
          _buildWindingStepNode(track.steps[i], i, track.steps.length),
          if (i < track.steps.length - 1) _buildConnectingRoadLine(track.steps[i], track.steps[i + 1], i),
        ],

        const SizedBox(height: 40),

        // Footer Trophy Card
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF1A2634), Color(0xFF161B22)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: Colors.amber.withValues(alpha: 0.3)),
          ),
          child: const Row(
            children: [
              Icon(Icons.military_tech_rounded, size: 40, color: Colors.amberAccent),
              SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Grandmaster Mastery Track',
                      style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: Colors.white),
                    ),
                    SizedBox(height: 4),
                    Text(
                      'Complete all 5 landmark papers and milestone exams to earn the verified track credential.',
                      style: TextStyle(fontSize: 12, color: Colors.white70),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 40),
      ],
    );
  }

  /// Individual Stepping Stone Node (with left/center/right winding alignment)
  Widget _buildWindingStepNode(RoadmapStep step, int index, int total) {
    // Alternate alignment to create winding Duolingo path effect
    final alignments = [
      Alignment.center,
      const Alignment(-0.5, 0),
      const Alignment(0.5, 0),
      const Alignment(-0.4, 0),
      Alignment.center,
    ];
    final alignment = alignments[index % alignments.length];

    Color stoneColor;
    Color borderColor;
    IconData iconData;

    if (step.isCompleted) {
      stoneColor = const Color(0xFF238636); // Duolingo Green
      borderColor = const Color(0xFF2EA043);
      iconData = Icons.check_rounded;
    } else if (step.isCurrent) {
      stoneColor = const Color(0xFF1F6FEB); // Blue Active
      borderColor = const Color(0xFF388BFD);
      iconData = Icons.play_arrow_rounded;
    } else if (!step.isLocked) {
      stoneColor = const Color(0xFF8957E5); // Purple Unlocked
      borderColor = const Color(0xFFA371F7);
      iconData = Icons.menu_book_rounded;
    } else {
      stoneColor = const Color(0xFF21262D); // Grey Locked
      borderColor = const Color(0xFF30363D);
      iconData = Icons.lock_rounded;
    }

    return Align(
      alignment: alignment,
      child: GestureDetector(
        onTap: () => _openStepDetailModal(step),
        child: Column(
          children: [
            // Stepping Stone Avatar / Button
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: stoneColor,
                shape: BoxShape.circle,
                border: Border.all(color: borderColor, width: 3),
                boxShadow: [
                  BoxShadow(
                    color: stoneColor.withValues(alpha: step.isCurrent ? 0.6 : 0.3),
                    blurRadius: step.isCurrent ? 16 : 8,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Center(
                child: Icon(
                  iconData,
                  color: step.isLocked ? Colors.white38 : Colors.white,
                  size: 32,
                ),
              ),
            ),

            const SizedBox(height: 8),

            // Step Label Banner
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: const BoxDecoration(
                color: Color(0xFF161B22),
                borderRadius: BorderRadius.all(Radius.circular(10)),
                border: Border.fromBorderSide(BorderSide(color: Colors.white12)),
              ),
              child: Column(
                children: [
                  Text(
                    'STEP ${step.stepNumber}',
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 0.8,
                      color: step.isCurrent ? Colors.lightBlueAccent : Colors.white54,
                    ),
                  ),
                  Text(
                    step.paperTitle,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: Colors.white,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Winding road connector line between nodes
  Widget _buildConnectingRoadLine(RoadmapStep from, RoadmapStep to, int index) {
    final isDone = from.isCompleted;

    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Column(
          children: [
            for (int i = 0; i < 3; i++) ...[
              Container(
                width: 6,
                height: 8,
                margin: const EdgeInsets.symmetric(vertical: 2),
                decoration: BoxDecoration(
                  color: isDone ? const Color(0xFF2EA043) : Colors.white24,
                  borderRadius: BorderRadius.circular(3),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  /// Step Detail Modal: Shows the Curated Landmark Research Paper Card + Exam Trigger
  void _openStepDetailModal(RoadmapStep step) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: const Color(0xFF161B22),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) {
        return DraggableScrollableSheet(
          initialChildSize: 0.8,
          minChildSize: 0.5,
          maxChildSize: 0.95,
          expand: false,
          builder: (context, scrollCtrl) {
            return ListView(
              controller: scrollCtrl,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
              children: [
                // Drag handle
                Center(
                  child: Container(
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(
                      color: Colors.white24,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                ),

                const SizedBox(height: 18),

                // Step header
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.green.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: Colors.greenAccent.withValues(alpha: 0.4)),
                      ),
                      child: Text(
                        'STEP ${step.stepNumber} · ROADMAP CANON',
                        style: const TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          color: Colors.greenAccent,
                        ),
                      ),
                    ),
                    Row(
                      children: [
                        const Icon(Icons.star_rounded, color: Colors.amberAccent, size: 18),
                        const SizedBox(width: 4),
                        Text(
                          '+${step.xpReward} XP',
                          style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.amberAccent, fontSize: 13),
                        ),
                      ],
                    ),
                  ],
                ),

                const SizedBox(height: 12),

                Text(
                  step.title,
                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white),
                ),
                Text(
                  step.subtitle,
                  style: const TextStyle(fontSize: 13, color: Colors.white60),
                ),

                const SizedBox(height: 20),

                // Landmark Canon Research Paper Card (The fixed step to succeed in AI/ML)
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: const Color(0xFF0D1117),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: Colors.white12),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Icon(Icons.article_rounded, color: Color(0xFF58A6FF), size: 20),
                          const SizedBox(width: 8),
                          const Text(
                            'LANDMARK RESEARCH PAPER',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                              letterSpacing: 0.8,
                              color: Color(0xFF58A6FF),
                            ),
                          ),
                          const Spacer(),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: Colors.blue.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(6),
                              border: Border.all(color: Colors.blueAccent.withValues(alpha: 0.3)),
                            ),
                            child: Text(
                              step.paperVenue,
                              style: const TextStyle(fontSize: 10, color: Colors.white70),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Text(
                        step.paperTitle,
                        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        step.paperSummary,
                        style: const TextStyle(fontSize: 12.5, color: Colors.white70, height: 1.4),
                      ),
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: const Color(0xFF161B22),
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: Colors.white12),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.lightbulb_outline_rounded, color: Colors.amberAccent, size: 18),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                'Core Insight: ${step.keyInsight}',
                                style: const TextStyle(fontSize: 11.5, color: Colors.white70),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 14),

                      // Read Paper on arXiv Button
                      SizedBox(
                        width: double.infinity,
                        child: OutlinedButton.icon(
                          style: OutlinedButton.styleFrom(
                            foregroundColor: Colors.white,
                            side: const BorderSide(color: Colors.white24),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                          onPressed: () async {
                            final uri = Uri.parse(step.paperArxivUrl);
                            if (await canLaunchUrl(uri)) {
                              await launchUrl(uri, mode: LaunchMode.externalApplication);
                            }
                          },
                          icon: const Icon(Icons.open_in_new_rounded, size: 16),
                          label: const Text('Read Original arXiv Paper', style: TextStyle(fontSize: 12.5)),
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 24),

                // Anti-Cheat Knowledge Exam Box
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.green.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: Colors.greenAccent.withValues(alpha: 0.3)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Row(
                        children: [
                          Icon(Icons.shield_outlined, color: Colors.greenAccent, size: 20),
                          SizedBox(width: 8),
                          Text(
                            'ANTI-CHEAT KNOWLEDGE EXAM',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                              letterSpacing: 0.8,
                              color: Colors.greenAccent,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        '• Strictly one-way: no going back to edit answers.\n'
                        '• Tab-switch / blur detection: auto-swaps unanswered questions after 4s.\n'
                        '• Score >= 80% unlocks the next milestone and awards track badges.',
                        style: TextStyle(fontSize: 12, color: Colors.white70, height: 1.4),
                      ),
                      const SizedBox(height: 16),
                      SizedBox(
                        width: double.infinity,
                        height: 48,
                        child: ElevatedButton.icon(
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF238636),
                            foregroundColor: Colors.white,
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                            elevation: 2,
                          ),
                          onPressed: () {
                            Navigator.pop(ctx);
                            QuizModal.show(
                              context,
                              topicSlug: step.topicSlug,
                              topicDisplayName: step.title,
                              onCalibrationComplete: () {
                                setState(() {
                                  _userXp += step.xpReward;
                                });
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(
                                    content: Text('🎉 Milestone Exam Completed! +${step.xpReward} XP Earned!'),
                                    backgroundColor: const Color(0xFF238636),
                                  ),
                                );
                              },
                            );
                          },
                          icon: const Icon(Icons.play_arrow_rounded, size: 22),
                          label: Text(
                            step.isCompleted ? 'Retake Exam (Level Up)' : 'Take Milestone Exam Now',
                            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 20),
              ],
            );
          },
        );
      },
    );
  }

  /// Paper Ingestion Status and Sync Hub Modal
  void _showIngestionModal() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: const Color(0xFF161B22),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            final status = _ingestStatus;
            final totalCards = status?['total_cards'] ?? 9;
            final primaryCards = status?['primary_feed_cards'] ?? 7;
            final canonCards = status?['canon_landmark_cards'] ?? 2;
            final totalSources = status?['total_sources'] ?? 17;

            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Center(
                    child: Container(
                      width: 40,
                      height: 4,
                      decoration: BoxDecoration(
                        color: Colors.white24,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),
                  const SizedBox(height: 18),
                  Row(
                    children: [
                      const Icon(Icons.cloud_sync_rounded, color: Colors.lightBlueAccent, size: 24),
                      const SizedBox(width: 10),
                      const Text(
                        'Paper Ingestion Hub',
                        style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white),
                      ),
                      const Spacer(),
                      IconButton(
                        icon: const Icon(Icons.close_rounded, color: Colors.white54),
                        onPressed: () => Navigator.pop(ctx),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    'Daily batch ingestion pipeline scraping arXiv (cs.AI, cs.LG, cs.CL) and open venues. '
                    'Enforces deduplication, triage filtering, and stage ledger tracking.',
                    style: TextStyle(fontSize: 12.5, color: Colors.white60, height: 1.35),
                  ),
                  const SizedBox(height: 18),

                  // Stats grid
                  Row(
                    children: [
                      Expanded(
                        child: _buildIngestStatCard('Active Sources', '$totalSources', Icons.rss_feed_rounded, Colors.orangeAccent),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _buildIngestStatCard('Total Papers', '$totalCards', Icons.article_rounded, Colors.blueAccent),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Expanded(
                        child: _buildIngestStatCard('Frontier Cards', '$primaryCards', Icons.trending_up_rounded, Colors.greenAccent),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _buildIngestStatCard('Canon Landmarks', '$canonCards', Icons.star_rounded, Colors.amberAccent),
                      ),
                    ],
                  ),

                  const SizedBox(height: 20),

                  // Manual Sync Trigger
                  SizedBox(
                    width: double.infinity,
                    height: 48,
                    child: ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF1F6FEB),
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      onPressed: () async {
                        setModalState(() => _isLoading = true);
                        await _apiService.triggerIngestion();
                        await _loadIngestStatus();
                        setModalState(() => _isLoading = false);
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Landmark papers and sources synchronized.')),
                          );
                        }
                      },
                      icon: const Icon(Icons.sync_rounded, size: 20),
                      label: Text(
                        _isLoading ? 'Synchronizing...' : 'Sync & Re-ingest Landmark Papers',
                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13.5),
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                ],
              ),
            );
          },
        );
      },
    );
  }

  Widget _buildIngestStatCard(String label, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF0D1117),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white12),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 22),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(value, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white)),
              Text(label, style: const TextStyle(fontSize: 11, color: Colors.white54)),
            ],
          ),
        ],
      ),
    );
  }
}
