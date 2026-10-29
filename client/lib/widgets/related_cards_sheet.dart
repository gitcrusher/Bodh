import 'package:flutter/material.dart';
import '../models/card_model.dart';
import '../services/api_service.dart';
import 'dynamic_paper_link.dart';

/// Modal bottom sheet displaying a dynamic flowing stream of research links.
/// Rule 56 & 57: Dynamic Research Links Flow (over nested duplicate cards).
///
/// Triggered when the reader taps the bottom Inshorts capsule on a card.
/// Automatically surfaces dynamically linked papers from the database
/// (shared techniques, benchmark comparisons, topic clusters, or citations).
class RelatedCardsSheet extends StatefulWidget {
  final NewsCard parentCard;
  final ApiService? apiService;

  const RelatedCardsSheet({
    super.key,
    required this.parentCard,
    this.apiService,
  });

  static Future<void> show(BuildContext context, NewsCard parentCard) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => RelatedCardsSheet(parentCard: parentCard),
    );
  }

  @override
  State<RelatedCardsSheet> createState() => _RelatedCardsSheetState();
}

class _RelatedCardsSheetState extends State<RelatedCardsSheet> {
  late final ApiService _apiService;
  bool _isLoading = true;
  List<DynamicPaperLink> _links = [];

  @override
  void initState() {
    super.initState();
    _apiService = widget.apiService ?? ApiService();
    _loadDynamicLinks();
  }

  Future<void> _loadDynamicLinks() async {
    setState(() => _isLoading = true);
    try {
      final list = await _apiService.fetchDynamicPaperLinks(widget.parentCard.id);
      if (mounted) {
        setState(() {
          _links = list;
          _isLoading = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final topic = widget.parentCard.relatedTopic ??
        (widget.parentCard.tags.isNotEmpty
            ? widget.parentCard.tags.first.replaceAll('_', ' ').toUpperCase()
            : 'RELATED RESEARCH');

    return DraggableScrollableSheet(
      initialChildSize: 0.82,
      minChildSize: 0.45,
      maxChildSize: 0.95,
      builder: (ctx, scrollController) {
        return Container(
          decoration: BoxDecoration(
            color: theme.cardColor,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.28),
                blurRadius: 20,
                offset: const Offset(0, -4),
              ),
            ],
          ),
          child: Column(
            children: [
              // 1. Grab Handle
              Center(
                child: Container(
                  margin: const EdgeInsets.only(top: 12, bottom: 8),
                  width: 42,
                  height: 4,
                  decoration: BoxDecoration(
                    color: theme.dividerColor,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),

              // 2. Header Bar
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 8.0),
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(9),
                      decoration: BoxDecoration(
                        color: colorScheme.primary.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Icon(Icons.hub_rounded, color: colorScheme.primary, size: 20),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Text(
                                'DYNAMIC RESEARCH LINKS',
                                style: TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                  letterSpacing: 0.8,
                                  color: colorScheme.primary,
                                ),
                              ),
                              const SizedBox(width: 6),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                decoration: BoxDecoration(
                                  color: Colors.amber.withValues(alpha: 0.14),
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(
                                  'DATABASE MATCH',
                                  style: TextStyle(
                                    fontSize: 9,
                                    fontWeight: FontWeight.bold,
                                    color: Colors.amber.shade800,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 2),
                          Text(
                            topic,
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.bold,
                              fontSize: 16.5,
                            ),
                          ),
                        ],
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.close_rounded),
                      onPressed: () => Navigator.pop(context),
                    ),
                  ],
                ),
              ),

              const Divider(height: 1),

              // 3. Flowing Stream of Dynamic Research Links
              Expanded(
                child: _isLoading
                    ? const Center(child: CircularProgressIndicator.adaptive())
                    : _links.isEmpty
                        ? Center(
                            child: Padding(
                              padding: const EdgeInsets.all(28.0),
                              child: Column(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(
                                    Icons.link_off_rounded,
                                    size: 40,
                                    color: theme.hintColor.withValues(alpha: 0.5),
                                  ),
                                  const SizedBox(height: 10),
                                  Text(
                                    'No dynamic research links bound to this paper yet.',
                                    textAlign: TextAlign.center,
                                    style: theme.textTheme.bodyMedium?.copyWith(
                                      color: theme.hintColor,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          )
                        : ListView.separated(
                            controller: scrollController,
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                            itemCount: _links.length,
                            separatorBuilder: (ctx, idx) => const SizedBox(height: 12),
                            itemBuilder: (ctx, idx) {
                              final link = _links[idx];
                              return DynamicPaperLinkTile(link: link);
                            },
                          ),
              ),
            ],
          ),
        );
      },
    );
  }
}
