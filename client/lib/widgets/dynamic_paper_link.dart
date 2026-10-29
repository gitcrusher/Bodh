import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../models/card_model.dart';
import 'deep_dive_sheet.dart';
import 'paper_chat_sheet.dart';

/// Data model representing a dynamic research link connecting two papers.
/// Rule 56 & 57: Ingest-time computed connections (shared technique, benchmark,
/// topic cluster, citation) exposed for reusable UI presentation.
class DynamicPaperLink {
  final int id;
  final String relationType;
  final String relationLabel;
  final double similarityScore;
  final DateTime? createdAt;
  final int targetCardId;
  final String targetHeadline;
  final String targetSummary60s;
  final String targetCategory;
  final String targetSourceUrl;
  final String? targetImageUrl;
  final DateTime? targetPublishedAt;
  final List<String> targetTags;
  final List<String> targetTechniques;

  const DynamicPaperLink({
    required this.id,
    required this.relationType,
    required this.relationLabel,
    this.similarityScore = 0.0,
    this.createdAt,
    required this.targetCardId,
    required this.targetHeadline,
    required this.targetSummary60s,
    this.targetCategory = 'research',
    required this.targetSourceUrl,
    this.targetImageUrl,
    this.targetPublishedAt,
    this.targetTags = const [],
    this.targetTechniques = const [],
  });

  factory DynamicPaperLink.fromJson(Map<String, dynamic> json) {
    return DynamicPaperLink(
      id: json['id'] as int? ?? 0,
      relationType: json['relation_type'] as String? ?? 'topic_cluster',
      relationLabel: json['relation_label'] as String? ?? 'Related Research',
      similarityScore: (json['similarity_score'] as num?)?.toDouble() ?? 0.0,
      createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at'] as String) : null,
      targetCardId: json['target_card_id'] as int? ?? 0,
      targetHeadline: json['target_headline'] as String? ?? '',
      targetSummary60s: json['target_summary_60s'] as String? ?? '',
      targetCategory: json['target_category'] as String? ?? 'research',
      targetSourceUrl: json['target_source_url'] as String? ?? '',
      targetImageUrl: json['target_image_url'] as String?,
      targetPublishedAt: json['target_published_at'] != null
          ? DateTime.tryParse(json['target_published_at'] as String)
          : null,
      targetTags: (json['target_tags'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? const [],
      targetTechniques:
          (json['target_techniques'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? const [],
    );
  }

  /// Converts a standard NewsCard into a DynamicPaperLink for seamless fallback & backward compatibility
  factory DynamicPaperLink.fromNewsCard(
    NewsCard card, {
    String relationType = 'topic_cluster',
    String? relationLabel,
    double similarityScore = 0.75,
  }) {
    String computedLabel = relationLabel ?? '';
    if (computedLabel.isEmpty) {
      if (card.candidateTechniques.isNotEmpty) {
        computedLabel = 'Shared Technique: ${card.candidateTechniques.first.toUpperCase()}';
      } else if (card.tags.isNotEmpty) {
        computedLabel = 'Topic: ${card.tags.first.replaceAll('_', ' ').toUpperCase()}';
      } else {
        computedLabel = 'Related Corpus Work';
      }
    }

    return DynamicPaperLink(
      id: card.id,
      relationType: relationType,
      relationLabel: computedLabel,
      similarityScore: similarityScore,
      targetCardId: card.id,
      targetHeadline: card.headline,
      targetSummary60s: card.summary60s,
      targetCategory: card.category,
      targetSourceUrl: card.sourceUrl,
      targetImageUrl: card.imageUrl,
      targetPublishedAt: card.publishedAt,
      targetTags: card.tags,
      targetTechniques: card.candidateTechniques,
    );
  }

  /// Rebuilds as a minimal NewsCard for opening Deep Dive or Chat sheets
  NewsCard toNewsCard() {
    return NewsCard(
      id: targetCardId,
      category: targetCategory,
      headline: targetHeadline,
      summary60s: targetSummary60s,
      tags: targetTags,
      candidateTechniques: targetTechniques,
      sourceUrl: targetSourceUrl,
      publishedAt: targetPublishedAt ?? DateTime.now(),
      needsReview: false,
      imageUrl: targetImageUrl,
    );
  }

  /// Clean 1-sentence contextual summary
  String get snippet {
    final firstLine = targetSummary60s
        .split('\n')
        .map((s) => s.trim())
        .firstWhere((s) => s.isNotEmpty, orElse: () => targetHeadline);
    return firstLine.startsWith('•') ? firstLine.substring(1).trim() : firstLine;
  }
}

/// Reusable dynamic research link tile (Rule 56 & 57).
/// Used inside RelatedCardsSheet and across research discovery surfaces.
class DynamicPaperLinkTile extends StatelessWidget {
  final DynamicPaperLink link;
  final VoidCallback? onTap;

  const DynamicPaperLinkTile({
    super.key,
    required this.link,
    this.onTap,
  });

  Future<void> _openSourceUrl(BuildContext context, String url) async {
    final uri = Uri.tryParse(url);
    if (uri != null && await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  Color _badgeColor(String type) {
    switch (type) {
      case 'shared_technique':
        return const Color(0xFF0D9488); // Teal
      case 'benchmark_comparison':
        return const Color(0xFF6366F1); // Indigo
      case 'direct_citation':
      case 'follow_up':
        return const Color(0xFFD97706); // Amber
      case 'topic_cluster':
      default:
        return const Color(0xFF2563EB); // Blue
    }
  }

  IconData _badgeIcon(String type) {
    switch (type) {
      case 'shared_technique':
        return Icons.hub_rounded;
      case 'benchmark_comparison':
        return Icons.insights_rounded;
      case 'direct_citation':
        return Icons.format_quote_rounded;
      case 'follow_up':
        return Icons.trending_up_rounded;
      case 'topic_cluster':
      default:
        return Icons.tag_rounded;
    }
  }

  String _formatPublishDate(DateTime? dt) {
    if (dt == null) return 'arXiv cs.AI';
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
    ];
    final day = dt.day.toString().padLeft(2, '0');
    final month = months[dt.month - 1];
    final year = dt.year;
    return '$day $month $year';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final badgeColor = _badgeColor(link.relationType);
    final badgeIcon = _badgeIcon(link.relationType);

    return Material(
      color: Colors.transparent,
      child: Container(
        decoration: BoxDecoration(
          color: theme.cardColor,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: theme.dividerColor.withValues(alpha: 0.6)),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.04),
              blurRadius: 10,
              offset: const Offset(0, 3),
            ),
          ],
        ),
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onTap ?? () => DeepDiveSheet.show(context, link.toNewsCard()),
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // 1. Contextual Header: Relation Pill + Similarity Match
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: badgeColor.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(badgeIcon, size: 13, color: badgeColor),
                          const SizedBox(width: 5),
                          Text(
                            link.relationLabel.toUpperCase(),
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w700,
                              letterSpacing: 0.5,
                              color: badgeColor,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const Spacer(),
                    if (link.similarityScore > 0)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: colorScheme.primary.withValues(alpha: 0.08),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          '${(link.similarityScore * 100).toInt()}% Match',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w600,
                            color: colorScheme.primary,
                          ),
                        ),
                      ),
                  ],
                ),

                const SizedBox(height: 10),

                // 2. Paper Headline
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Text(
                        link.targetHeadline,
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                          fontSize: 15.5,
                          height: 1.32,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Icon(
                      Icons.arrow_outward_rounded,
                      size: 16,
                      color: theme.hintColor.withValues(alpha: 0.7),
                    ),
                  ],
                ),

                const SizedBox(height: 6),

                // 3. Dynamic Snippet / Context
                Text(
                  link.snippet,
                  style: theme.textTheme.bodySmall?.copyWith(
                    fontSize: 13,
                    height: 1.45,
                    color: theme.textTheme.bodyMedium?.color?.withValues(alpha: 0.8),
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),

                const SizedBox(height: 10),

                // 4. Meta & Published Date Line (Rule 59: Authoritative publication date)
                Text(
                  '${_formatPublishDate(link.targetPublishedAt)} • arXiv cs.AI • arxiv.org',
                  style: theme.textTheme.bodySmall?.copyWith(
                    fontSize: 11,
                    color: theme.hintColor,
                  ),
                ),

                const SizedBox(height: 12),
                const Divider(height: 1),
                const SizedBox(height: 8),

                // 5. Interactive Action Triggers
                Row(
                  children: [
                    OutlinedButton.icon(
                      icon: const Icon(Icons.open_in_new_rounded, size: 13),
                      label: const Text('Read Paper', style: TextStyle(fontSize: 11.5)),
                      style: OutlinedButton.styleFrom(
                        visualDensity: VisualDensity.compact,
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      ),
                      onPressed: () => _openSourceUrl(context, link.targetSourceUrl),
                    ),
                    const SizedBox(width: 8),
                    OutlinedButton.icon(
                      icon: const Icon(Icons.auto_stories_rounded, size: 13),
                      label: const Text('Deep Dive', style: TextStyle(fontSize: 11.5)),
                      style: OutlinedButton.styleFrom(
                        visualDensity: VisualDensity.compact,
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      ),
                      onPressed: () => DeepDiveSheet.show(context, link.toNewsCard()),
                    ),
                    const Spacer(),
                    FilledButton.tonalIcon(
                      icon: const Icon(Icons.chat_bubble_outline_rounded, size: 13),
                      label: const Text('Chat', style: TextStyle(fontSize: 11.5)),
                      style: FilledButton.styleFrom(
                        visualDensity: VisualDensity.compact,
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                      ),
                      onPressed: () => PaperChatSheet.show(context, link.toNewsCard()),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

