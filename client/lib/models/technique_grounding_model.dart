/// Models for Step 7: Trending-Technique Grounding (The Reverse Pipeline, Design §9, Rule 52).

class TechniqueLiteratureLink {
  final int? id;
  final String workId;
  final String source; // semantic_scholar | openalex
  final String title;
  final int? year;
  final String url;
  final String matchType; // direct | related
  final String snippet;

  const TechniqueLiteratureLink({
    this.id,
    required this.workId,
    required this.source,
    required this.title,
    this.year,
    required this.url,
    required this.matchType,
    required this.snippet,
  });

  factory TechniqueLiteratureLink.fromJson(Map<String, dynamic> json) {
    return TechniqueLiteratureLink(
      id: json['id'] as int?,
      workId: json['work_id'] as String? ?? '',
      source: json['source'] as String? ?? 'semantic_scholar',
      title: json['title'] as String? ?? '',
      year: json['year'] as int?,
      url: json['url'] as String? ?? '',
      matchType: json['match_type'] as String? ?? 'direct',
      snippet: json['snippet'] as String? ?? '',
    );
  }
}

class TrendingTechnique {
  final int id;
  final String name;
  final String slug;
  final List<String> aliases;
  final String groundingStatus; // direct_match | related_only | no_literature_found
  final String verdictExplanation;
  final Map<String, dynamic> mentionTrend;
  final List<TechniqueLiteratureLink> literatureLinks;

  const TrendingTechnique({
    required this.id,
    required this.name,
    required this.slug,
    this.aliases = const [],
    required this.groundingStatus,
    required this.verdictExplanation,
    this.mentionTrend = const {},
    this.literatureLinks = const [],
  });

  bool get isDirectMatch => groundingStatus == 'direct_match';
  bool get isRelatedOnly => groundingStatus == 'related_only';
  bool get isNoLiteratureFound => groundingStatus == 'no_literature_found';

  factory TrendingTechnique.fromJson(Map<String, dynamic> json) {
    return TrendingTechnique(
      id: json['id'] as int,
      name: json['name'] as String? ?? '',
      slug: json['slug'] as String? ?? '',
      aliases: (json['aliases'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
      groundingStatus: json['grounding_status'] as String? ?? 'no_literature_found',
      verdictExplanation: json['verdict_explanation'] as String? ?? '',
      mentionTrend: json['mention_trend'] as Map<String, dynamic>? ?? const {},
      literatureLinks: (json['literature_links'] as List<dynamic>?)
              ?.map((e) => TechniqueLiteratureLink.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }
}

class CardTechniqueGroundingResult {
  final int cardId;
  final bool hasTechnique;
  final TrendingTechnique? technique;
  final String fallbackMessage;
  final List<Map<String, dynamic>> siblingCards;

  const CardTechniqueGroundingResult({
    required this.cardId,
    required this.hasTechnique,
    this.technique,
    this.fallbackMessage = '',
    this.siblingCards = const [],
  });

  factory CardTechniqueGroundingResult.fromJson(Map<String, dynamic> json) {
    return CardTechniqueGroundingResult(
      cardId: json['card_id'] as int? ?? 0,
      hasTechnique: json['has_technique'] as bool? ?? false,
      technique: json['technique'] != null
          ? TrendingTechnique.fromJson(json['technique'] as Map<String, dynamic>)
          : null,
      fallbackMessage: json['fallback_message'] as String? ?? '',
      siblingCards: (json['sibling_cards'] as List<dynamic>?)
              ?.map((e) => Map<String, dynamic>.from(e as Map))
              .toList() ??
          const [],
    );
  }
}
