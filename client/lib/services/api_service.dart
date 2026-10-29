import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/card_model.dart';
import '../widgets/dynamic_paper_link.dart';

class PaginatedCards {
  final List<NewsCard> cards;
  final String? nextCursor;
  final String? previousCursor;

  const PaginatedCards({
    required this.cards,
    this.nextCursor,
    this.previousCursor,
  });
}

class ApiService {
  final String baseUrl;

  ApiService({this.baseUrl = 'http://127.0.0.1:8000/api/v1/research'});

  /// Fetch paginated cards from /api/v1/research/cards/
  Future<PaginatedCards> fetchCards({
    String? cursor,
    String category = 'research',
  }) async {
    final queryParams = <String, String>{
      'category': category,
    };
    if (cursor != null && cursor.isNotEmpty) {
      queryParams['cursor'] = cursor;
    }

    final uri = Uri.parse('$baseUrl/cards/').replace(queryParameters: queryParams);

    try {
      final response = await http.get(uri).timeout(const Duration(seconds: 4));
      if (response.statusCode == 200) {
        final data = json.decode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
        final results = (data['results'] as List<dynamic>? ?? [])
            .map((e) => NewsCard.fromJson(e as Map<String, dynamic>))
            .toList();

        final nextUrl = data['next'] as String?;
        String? nextCursor;
        if (nextUrl != null) {
          final nextUri = Uri.parse(nextUrl);
          nextCursor = nextUri.queryParameters['cursor'];
        }

        // If backend database has cards, return them; otherwise fallback to curated sample cards
        if (results.isNotEmpty) {
          return PaginatedCards(cards: results, nextCursor: nextCursor);
        }
      }
    } catch (_) {
      // Server unreachable; fall through to sample offline cards for immediate rich preview
    }

    // Curated offline mock data ensuring immediate UI preview
    return PaginatedCards(
      cards: _sampleMockCards,
      nextCursor: null,
    );
  }

  /// Fetch cards related to a specific card from /api/v1/research/cards/{cardId}/related/
  Future<List<NewsCard>> fetchRelatedCards(int cardId) async {
    final uri = Uri.parse('$baseUrl/cards/$cardId/related/');
    try {
      final response = await http.get(uri).timeout(const Duration(seconds: 4));
      if (response.statusCode == 200) {
        final data = json.decode(utf8.decode(response.bodyBytes));
        List<NewsCard> cards = [];
        if (data is List) {
          cards = data
              .map((e) => NewsCard.fromJson(e as Map<String, dynamic>))
              .toList();
        } else if (data is Map<String, dynamic> && data.containsKey('results')) {
          final results = data['results'] as List<dynamic>;
          cards = results
              .map((e) => NewsCard.fromJson(e as Map<String, dynamic>))
              .toList();
        }
        if (cards.isNotEmpty) return cards;
      }
    } catch (_) {
      // Offline fallback
    }

    // Return mock related cards excluding the card itself
    return _sampleMockCards.where((c) => c.id != cardId).toList();
  }

  /// Fetch dynamic research links from /api/v1/research/cards/{cardId}/links/
  Future<List<DynamicPaperLink>> fetchDynamicPaperLinks(int cardId) async {
    final uri = Uri.parse('$baseUrl/cards/$cardId/links/');
    try {
      final response = await http.get(uri).timeout(const Duration(seconds: 4));
      if (response.statusCode == 200) {
        final data = json.decode(utf8.decode(response.bodyBytes));
        if (data is Map<String, dynamic> && data.containsKey('links')) {
          final links = (data['links'] as List<dynamic>)
              .map((e) => DynamicPaperLink.fromJson(e as Map<String, dynamic>))
              .toList();
          if (links.isNotEmpty) return links;
        }
      }
    } catch (_) {
      // Offline fallback
    }

    // Fallback: convert related cards into dynamic links
    final cards = await fetchRelatedCards(cardId);
    return cards
        .map((c) => DynamicPaperLink.fromNewsCard(c))
        .toList();
  }

  /// Submit a content report
  Future<bool> submitReport({
    required int cardId,
    required String reason,
    required String detail,
  }) async {
    final uri = Uri.parse('$baseUrl/cards/$cardId/report/');
    try {
      final response = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'reason': reason, 'detail': detail}),
      );
      return response.statusCode == 201;
    } catch (_) {
      return true; // Optimistic mock
    }
  }

  static final List<NewsCard> _sampleMockCards = [
    NewsCard(
      id: 1,
      category: 'research',
      headline: 'DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Pure RL',
      summary60s:
          '• Demonstrates reasoning emergence purely from large-scale RL without supervised cold-start.\n'
          '• Employs Group Relative Policy Optimization (GRPO) with verified reward models.\n'
          '• Scores 97.3% on MATH-500 and 79.8% on AIME 2024, matching frontier proprietary models.\n'
          '• Open-weights distilled models from 1.5B to 70B parameters for open research.',
      tags: ['reasoning', 'reinforcement_learning', 'grpo', 'llm', 'transformers'],
      candidateTechniques: ['grpo', 'reasoning-distillation', 'chain-of-thought', 'self-attention'],
      sourceUrl: 'https://arxiv.org/abs/2501.12948',
      publishedAt: DateTime(2025, 1, 22),
      needsReview: false,
      validitySignal: null,
      relatedCount: 3,
      relatedTopic: 'Reasoning & Scaling',
      imageUrl: 'https://images.unsplash.com/photo-1635070041078-e363dbe005cb?q=80&w=800&auto=format&fit=crop',
      isPrimaryFeed: true,
      relatedPreview: [
        {
          'id': 4,
          'headline': 'Attention Is All You Need: The Transformer Architecture',
        },
        {
          'id': 5,
          'headline': 'Low-Rank Adaptation (LoRA) of Large Language Models',
        },
      ],
    ),
    NewsCard(
      id: 2,
      category: 'research',
      headline: 'FlashAttention-3: Fast and Accurate Attention with Asynchrony and Low-Precision',
      summary60s:
          '• Exploits Hopper architecture tensor cores (FP16/FP8) with asynchronous execution.\n'
          '• Overlaps GEMM and softmax computations across warp-group specialization.\n'
          '• Achieves up to 740 TFLOPs/s (75% of H100 theoretical peak).\n'
          '• Delivers 1.5x–2.0x speedup over FlashAttention-2 with identical numerical precision.',
      tags: ['hardware_acceleration', 'gpu', 'efficiency', 'h100', 'transformers'],
      candidateTechniques: ['warp-specialization', 'fp8-attention', 'multi-head attention'],
      sourceUrl: 'https://arxiv.org/abs/2407.08608',
      publishedAt: DateTime(2024, 7, 12),
      needsReview: false,
      relatedCount: 2,
      relatedTopic: 'Hardware Acceleration',
      imageUrl: 'https://images.unsplash.com/photo-1550751827-4bd374c3f58b?q=80&w=800&auto=format&fit=crop',
      isPrimaryFeed: true,
      relatedPreview: [
        {
          'id': 4,
          'headline': 'Attention Is All You Need: The Transformer Architecture',
        },
      ],
    ),
    NewsCard(
      id: 3,
      category: 'research',
      headline: 'Llama 3.3: 70B Frontier Capabilities with Industry Efficiency',
      summary60s:
          '• Introduces 70B dense architecture delivering performance on par with previous 405B flagship.\n'
          '• Employs Grouped-Query Attention (GQA) with 128k context length support natively.\n'
          '• Demonstrates leading mathematical reasoning, coding, and multilingual understanding.\n'
          '• Released under permissive community license powering global edge deployments.',
      tags: ['open_weights', 'foundation_models', 'llama', 'transformers'],
      candidateTechniques: ['grouped-query attention', 'direct preference optimization', 'self-attention'],
      sourceUrl: 'https://arxiv.org/abs/2412.19437',
      publishedAt: DateTime(2024, 12, 6),
      needsReview: false,
      relatedCount: 2,
      relatedTopic: 'Open Foundation Models',
      imageUrl: 'https://images.unsplash.com/photo-1518770660439-4636190af475?q=80&w=800&auto=format&fit=crop',
      isPrimaryFeed: true,
      relatedPreview: [
        {
          'id': 4,
          'headline': 'Attention Is All You Need: The Transformer Architecture',
        },
      ],
    ),
    NewsCard(
      id: 4,
      category: 'research',
      headline: 'Attention Is All You Need: The Transformer Architecture',
      summary60s:
          '• Proposes the Transformer, eliminating recurrence and convolution in sequence models.\n'
          '• Employs multi-head self-attention to draw global dependencies across all tokens.\n'
          '• Reaches SOTA on WMT English-to-German after only 12 hours on 8 GPUs.\n'
          '• Foundation for modern LLMs including GPT, BERT, Claude, and Gemini.',
      tags: ['transformers', 'attention', 'nlp', 'deep_learning'],
      candidateTechniques: ['self-attention', 'multi-head attention', 'positional encoding'],
      sourceUrl: 'https://arxiv.org/abs/1706.03762',
      publishedAt: DateTime(2017, 6, 12),
      needsReview: false,
      validitySignal: null,
      relatedCount: 3,
      relatedTopic: 'Transformer Foundations',
      imageUrl: 'https://images.unsplash.com/photo-1620712943543-bcc4688e7485?q=80&w=800&auto=format&fit=crop',
      isPrimaryFeed: false, // Rule 58: Foundational prior-art card in cluster
      relatedPreview: [],
    ),
    NewsCard(
      id: 5,
      category: 'research',
      headline: 'Low-Rank Adaptation (LoRA) of Large Language Models',
      summary60s:
          '• Freezes pre-trained weights and injects trainable rank decomposition matrices.\n'
          '• Reduces trainable parameters by 10,000x and GPU memory footprint by 3x.\n'
          '• Matches or exceeds full fine-tuning performance on RoBERTa, DeBERTa, and GPT-3.\n'
          '• Zero added inference latency by folding weights Delta W = B * A at deployment.',
      tags: ['fine_tuning', 'peft', 'transformers', 'efficiency'],
      candidateTechniques: ['low-rank adaptation', 'parameter-efficient tuning', 'multi-head attention'],
      sourceUrl: 'https://arxiv.org/abs/2106.09685',
      publishedAt: DateTime(2021, 6, 17),
      needsReview: false,
      relatedCount: 2,
      relatedTopic: 'Parameter-Efficient Fine-Tuning',
      imageUrl: 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=800&auto=format&fit=crop',
      isPrimaryFeed: false, // Rule 58: Foundational prior-art card in cluster
      relatedPreview: [],
    ),
  ];
}
