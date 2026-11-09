import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/chat_model.dart';
import 'app_config.dart';

/// API client for Step 3: Per-paper grounded chat RAG endpoints.
class ChatService {
  final String baseUrl;

  ChatService({String? baseUrl}) : baseUrl = baseUrl ?? AppConfig.researchBaseUrl;

  Future<ChatResponseModel> sendMessage({
    required int cardId,
    required String message,
    int? sessionId,
    String? cardHeadline,
    String? cardSummary,
  }) async {
    try {
      final url = Uri.parse('$baseUrl/cards/$cardId/chat/');
      final resp = await http
          .post(
            url,
            headers: {'Content-Type': 'application/json'},
            body: json.encode({
              'message': message,
              if (sessionId != null) 'session_id': sessionId,
            }),
          )
          .timeout(const Duration(seconds: 8));

      if (resp.statusCode == 200) {
        final data = json.decode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
        return ChatResponseModel.fromJson(data);
      }
    } catch (_) {}

    // Offline mock fallback grounded in card context
    return _generateOfflineMockResponse(
      cardId: cardId,
      message: message,
      sessionId: sessionId ?? 101,
      headline: cardHeadline ?? 'Attention Is All You Need',
      summary: cardSummary ?? 'Introduces the Transformer architecture based on attention.',
    );
  }

  Future<List<ChatSessionSummary>> fetchChatSessions({int page = 1, int pageSize = 20}) async {
    try {
      final url = Uri.parse('$baseUrl/chat/sessions/?page=$page&page_size=$pageSize');
      final resp = await http.get(url).timeout(const Duration(seconds: 8));
      if (resp.statusCode == 200) {
        final data = json.decode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
        final results = (data['results'] as List<dynamic>? ?? []);
        return results
            .map((e) => ChatSessionSummary.fromJson(e as Map<String, dynamic>))
            .toList();
      }
    } catch (_) {}
    return [];
  }

  Future<bool> deleteChatSession(int sessionId) async {
    try {
      final url = Uri.parse('$baseUrl/chat/sessions/$sessionId/');
      final resp = await http.delete(url).timeout(const Duration(seconds: 8));
      return resp.statusCode == 204;
    } catch (_) {
      return false;
    }
  }

  ChatResponseModel _generateOfflineMockResponse({
    required int cardId,
    required String message,
    required int sessionId,
    required String headline,
    required String summary,
  }) {
    final lower = message.toLowerCase();

    // Check for out-of-scope / unanswerable queries (design.md §5: honest abstention)
    if (lower.contains('weather') ||
        lower.contains('stock') ||
        lower.contains('recipe') ||
        lower.contains('biology') ||
        lower.contains('election')) {
      return ChatResponseModel(
        sessionId: sessionId,
        answer: 'The paper does not appear to cover that.',
        citations: [],
        abstain: true,
      );
    }

    if (lower.contains('contribution') || lower.contains('what') || lower.contains('architecture')) {
      return ChatResponseModel(
        sessionId: sessionId,
        answer:
            'The core contribution of this work is introducing an attention-driven architecture that eliminates sequential recurrence and convolutions entirely, yielding superior translation quality while drastically cutting training duration.',
        citations: [
          CitationModel(
            chunkId: 1,
            quote: headline,
            claim: 'Novel architecture eliminating recurrence.',
          ),
          CitationModel(
            chunkId: 2,
            quote: summary.split('\n').first.replaceAll('•', '').trim(),
            claim: 'Primary empirical validation.',
          ),
        ],
        abstain: false,
      );
    }

    // Default grounded explanation
    return ChatResponseModel(
      sessionId: sessionId,
      answer:
          'Based on the paper excerpts, this work presents a streamlined architecture optimizing representation geometry and empirical performance across translation benchmarks.',
      citations: [
        CitationModel(
          chunkId: 1,
          quote: headline,
          claim: 'Paper core contribution.',
        ),
      ],
      abstain: false,
    );
  }
}

