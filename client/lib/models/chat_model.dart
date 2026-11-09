// Data models for Step 3: Per-Paper Grounded Chat (RAG)

class CitationModel {
  final int chunkId;
  final String quote;
  final String claim;

  const CitationModel({
    required this.chunkId,
    required this.quote,
    required this.claim,
  });

  factory CitationModel.fromJson(Map<String, dynamic> json) {
    return CitationModel(
      chunkId: json['chunk_id'] as int? ?? 0,
      quote: json['quote'] as String? ?? '',
      claim: json['claim'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'chunk_id': chunkId,
        'quote': quote,
        'claim': claim,
      };
}

class ChatMessageModel {
  final int id;
  final String role; // "user" or "assistant"
  final String content;
  final List<CitationModel> citations;
  final DateTime createdAt;
  final bool isAbstention;

  const ChatMessageModel({
    required this.id,
    required this.role,
    required this.content,
    required this.citations,
    required this.createdAt,
    this.isAbstention = false,
  });

  bool get isUser => role == 'user';

  factory ChatMessageModel.fromJson(Map<String, dynamic> json) {
    final citationsList = (json['citations'] as List<dynamic>?)
            ?.map((e) => CitationModel.fromJson(e as Map<String, dynamic>))
            .toList() ??
        [];

    final contentStr = json['content'] as String? ?? '';
    final isAbstain = contentStr.contains('The paper does not appear to cover that');

    return ChatMessageModel(
      id: json['id'] as int? ?? 0,
      role: json['role'] as String? ?? 'user',
      content: contentStr,
      citations: citationsList,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'] as String) ?? DateTime.now()
          : DateTime.now(),
      isAbstention: isAbstain,
    );
  }
}

class ChatResponseModel {
  final int sessionId;
  final String answer;
  final List<CitationModel> citations;
  final bool abstain;

  const ChatResponseModel({
    required this.sessionId,
    required this.answer,
    required this.citations,
    required this.abstain,
  });

  factory ChatResponseModel.fromJson(Map<String, dynamic> json) {
    final citationsList = (json['citations'] as List<dynamic>?)
            ?.map((e) => CitationModel.fromJson(e as Map<String, dynamic>))
            .toList() ??
        [];

    return ChatResponseModel(
      sessionId: json['session_id'] as int? ?? 0,
      answer: json['answer'] as String? ?? '',
      citations: citationsList,
      abstain: json['abstain'] as bool? ?? false,
    );
  }
}

class ChatSessionSummary {
  final int id;
  final int cardId;
  final String cardHeadline;
  final String? cardImageUrl;
  final DateTime startedAt;
  final DateTime lastActivityAt;
  final int messageCount;
  final String lastMessagePreview;

  const ChatSessionSummary({
    required this.id,
    required this.cardId,
    required this.cardHeadline,
    this.cardImageUrl,
    required this.startedAt,
    required this.lastActivityAt,
    required this.messageCount,
    required this.lastMessagePreview,
  });

  factory ChatSessionSummary.fromJson(Map<String, dynamic> json) {
    return ChatSessionSummary(
      id: json['id'] as int? ?? 0,
      cardId: json['card_id'] as int? ?? 0,
      cardHeadline: json['card_headline'] as String? ?? '',
      cardImageUrl: json['card_image_url'] as String?,
      startedAt: json['started_at'] != null
          ? DateTime.tryParse(json['started_at'] as String) ?? DateTime.now()
          : DateTime.now(),
      lastActivityAt: json['last_activity_at'] != null
          ? DateTime.tryParse(json['last_activity_at'] as String) ?? DateTime.now()
          : DateTime.now(),
      messageCount: json['message_count'] as int? ?? 0,
      lastMessagePreview: json['last_message_preview'] as String? ?? '',
    );
  }
}
