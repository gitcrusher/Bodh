/// Per-paper validity signal from backend API (design.md §6).
class PaperValiditySignal {
  final String venue;
  final int venueTier; // 1 = top, 2 = peer-reviewed, 3 = preprint/unknown
  final int affiliationTier; // 1 = top lab, 2 = known, 3 = unknown
  final String dataSource;
  final DateTime? fetchedAt;

  const PaperValiditySignal({
    required this.venue,
    required this.venueTier,
    required this.affiliationTier,
    required this.dataSource,
    this.fetchedAt,
  });

  factory PaperValiditySignal.fromJson(Map<String, dynamic> json) {
    return PaperValiditySignal(
      venue: json['venue'] as String? ?? '',
      venueTier: json['venue_tier'] as int? ?? 3,
      affiliationTier: json['affiliation_tier'] as int? ?? 3,
      dataSource: json['data_source'] as String? ?? 'arxiv_metadata',
      fetchedAt: json['fetched_at'] != null
          ? DateTime.tryParse(json['fetched_at'] as String)
          : null,
    );
  }

  /// Fact line text representation (design.md §6)
  /// e.g. "NeurIPS 2026 · authors from Google DeepMind" or "arXiv preprint · Tier 3"
  String get factLine {
    final v = venue.isNotEmpty ? venue : 'No venue verified';
    final tierLabel = venueTier == 1
        ? 'Tier 1 Venue'
        : (venueTier == 2 ? 'Peer-Reviewed' : 'Preprint');
    return '$v · $tierLabel';
  }
}
