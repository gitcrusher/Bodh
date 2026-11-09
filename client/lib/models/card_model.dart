import 'validity_signal.dart';

/// Trend summary matching Step 6 social signals (§6, §8).
class CardTrendSummary {
  final bool isTrending;
  final int totalMentions;
  final double highestEngagement;
  final List<String> platforms;
  final String primaryReason;

  const CardTrendSummary({
    this.isTrending = false,
    this.totalMentions = 0,
    this.highestEngagement = 0.0,
    this.platforms = const [],
    this.primaryReason = '',
  });

  factory CardTrendSummary.fromJson(Map<String, dynamic>? json) {
    if (json == null) return const CardTrendSummary();
    return CardTrendSummary(
      isTrending: json['is_trending'] as bool? ?? false,
      totalMentions: json['total_mentions'] as int? ?? 0,
      highestEngagement: (json['highest_engagement'] as num?)?.toDouble() ?? 0.0,
      platforms: (json['platforms'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
      primaryReason: json['primary_reason'] as String? ?? '',
    );
  }
}


/// 60-second News Card model matching backend DRF CardListSerializer / CardDetailSerializer.
class NewsCard {
  final int id;
  final String category;
  final String headline;
  final String summary60s;
  final List<String> tags;
  final List<String> candidateTechniques;
  final String? deepDiveBase;
  final String sourceUrl;
  final DateTime publishedAt;
  final bool needsReview;
  final DateTime? createdAt;
  final PaperValiditySignal? validitySignal;
  final int relatedCount;
  final String? relatedTopic;
  final List<Map<String, dynamic>> relatedPreview;
  final String? imageUrl;
  final bool isPrimaryFeed;
  final String publisherRelationship;
  final CardTrendSummary trendSummary;

  const NewsCard({
    required this.id,
    required this.category,
    required this.headline,
    required this.summary60s,
    required this.tags,
    required this.candidateTechniques,
    this.deepDiveBase,
    required this.sourceUrl,
    required this.publishedAt,
    required this.needsReview,
    this.createdAt,
    this.validitySignal,
    this.relatedCount = 0,
    this.relatedTopic,
    this.relatedPreview = const [],
    this.imageUrl,
    this.isPrimaryFeed = true,
    this.publisherRelationship = 'independent',
    this.trendSummary = const CardTrendSummary(),
  });

  factory NewsCard.fromJson(Map<String, dynamic> json) {
    return NewsCard(
      id: json['id'] as int,
      category: json['category'] as String? ?? 'research',
      headline: json['headline'] as String? ?? '',
      summary60s: json['summary_60s'] as String? ?? '',
      tags: (json['tags'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      candidateTechniques: (json['candidate_techniques'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      deepDiveBase: json['deep_dive_base'] as String?,
      sourceUrl: json['source_url'] as String? ?? '',
      publishedAt: json['published_at'] != null
          ? DateTime.parse(json['published_at'] as String)
          : DateTime.now(),
      needsReview: json['needs_review'] as bool? ?? false,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'] as String)
          : null,
      validitySignal: json['validity_signal'] != null
          ? PaperValiditySignal.fromJson(json['validity_signal'] as Map<String, dynamic>)
          : null,
      relatedCount: json['related_count'] as int? ?? 0,
      relatedTopic: json['related_topic'] as String?,
      relatedPreview: (json['related_preview'] as List<dynamic>?)
              ?.map((e) => e as Map<String, dynamic>)
              .toList() ??
          const [],
      imageUrl: json['image_url'] as String?,
      isPrimaryFeed: json['is_primary_feed'] as bool? ?? true,
      publisherRelationship: json['publisher_relationship'] as String? ?? 'independent',
      trendSummary: CardTrendSummary.fromJson(json['trend_summary'] as Map<String, dynamic>?),
    );
  }

  /// Flowing story paragraph matching Inshorts 60-word format
  String get narrativeStory {
    final cleaned = summary60s
        .split('\n')
        .map((line) => line.trim())
        .where((line) => line.isNotEmpty)
        .map((line) => line.startsWith('•') ? line.substring(1).trim() : line)
        .join(' ');
    return cleaned.isNotEmpty ? cleaned : summary60s;
  }

  /// Split bullet points from summary_60s for clean card rendering
  List<String> get bulletPoints {
    return summary60s
        .split('\n')
        .map((line) => line.trim())
        .where((line) => line.isNotEmpty)
        .map((line) => line.startsWith('•') ? line.substring(1).trim() : line)
        .toList();
  }
}
