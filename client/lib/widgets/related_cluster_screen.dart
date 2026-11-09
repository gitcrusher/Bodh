import 'package:flutter/material.dart';
import '../models/card_model.dart';
import '../services/api_service.dart';
import 'news_card.dart';

/// Full-screen horizontal card collection for related papers.
///
/// Features:
/// 1. Horizontal swipe navigation between full Inshorts cards (PageView.builder, rendered on demand).
/// 2. Segmented story-style top progress line indicating total cards and active position.
/// 3. Back arrow button to seamlessly return to the home feed.
class RelatedCardsClusterScreen extends StatefulWidget {
  final NewsCard parentCard;
  final ApiService? apiService;

  const RelatedCardsClusterScreen({
    super.key,
    required this.parentCard,
    this.apiService,
  });

  static Future<void> show(BuildContext context, NewsCard parentCard) {
    return Navigator.push(
      context,
      MaterialPageRoute(
        builder: (ctx) => RelatedCardsClusterScreen(parentCard: parentCard),
      ),
    );
  }

  @override
  State<RelatedCardsClusterScreen> createState() => _RelatedCardsClusterScreenState();
}

class _RelatedCardsClusterScreenState extends State<RelatedCardsClusterScreen> {
  late final ApiService _apiService;
  final PageController _pageController = PageController();

  bool _isLoading = true;
  List<NewsCard> _relatedCards = [];
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();
    _apiService = widget.apiService ?? ApiService();
    _loadCluster();
  }

  Future<void> _loadCluster() async {
    setState(() => _isLoading = true);
    try {
      final list = await _apiService.fetchRelatedCards(widget.parentCard.id);
      if (mounted) {
        setState(() {
          // If the list does not include the parent card, prepend or ensure related items
          _relatedCards = list.isNotEmpty ? list : [widget.parentCard];
          _isLoading = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _relatedCards = [widget.parentCard];
          _isLoading = false;
        });
      }
    }
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final topicTitle = widget.parentCard.relatedTopic ??
        (widget.parentCard.tags.isNotEmpty
            ? widget.parentCard.tags.first.replaceAll('_', ' ').toUpperCase()
            : 'RELATED PAPERS');

    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: _isLoading
            ? const Center(child: CircularProgressIndicator.adaptive())
            : _relatedCards.isEmpty
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24.0),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.layers_clear_outlined, size: 48, color: theme.hintColor),
                          const SizedBox(height: 12),
                          Text(
                            'No other related papers indexed in this cluster.',
                            textAlign: TextAlign.center,
                            style: theme.textTheme.bodyMedium?.copyWith(color: theme.hintColor),
                          ),
                          const SizedBox(height: 16),
                          ElevatedButton.icon(
                            icon: const Icon(Icons.arrow_back),
                            label: const Text('Back to Home'),
                            onPressed: () => Navigator.pop(context),
                          ),
                        ],
                      ),
                    ),
                  )
                : Column(
                    children: [
                      // ---------------------------------------------------------
                      // 1. TOP HEADER BAR: Back Arrow < Topic Title + Share Icon
                      // ---------------------------------------------------------
                      Container(
                        height: 48,
                        padding: const EdgeInsets.symmetric(horizontal: 8),
                        color: Colors.black,
                        child: Row(
                          children: [
                            IconButton(
                              icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20, color: Colors.white),
                              tooltip: 'Back to Home Feed',
                              onPressed: () => Navigator.pop(context),
                            ),
                            const SizedBox(width: 4),
                            Expanded(
                              child: Row(
                                children: [
                                  Flexible(
                                    child: Text(
                                      topicTitle,
                                      style: const TextStyle(
                                        color: Colors.white,
                                        fontSize: 16,
                                        fontWeight: FontWeight.bold,
                                        letterSpacing: -0.2,
                                      ),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
                                    decoration: BoxDecoration(
                                      color: colorScheme.primary.withValues(alpha: 0.2),
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: const Text(
                                      'RELATED CLUSTER',
                                      style: TextStyle(
                                        fontSize: 9,
                                        fontWeight: FontWeight.w700,
                                        letterSpacing: 0.5,
                                        color: Color(0xFF2196F3),
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            IconButton(
                              icon: const Icon(Icons.share_outlined, size: 20, color: Colors.white70),
                              tooltip: 'Share cluster',
                              onPressed: () {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(content: Text('Sharing cluster: $topicTitle')),
                                );
                              },
                            ),
                          ],
                        ),
                      ),

                      // ---------------------------------------------------------
                      // 2. HORIZONTAL SCROLLABLE CARD COLLECTION (PageView.builder)
                      // ---------------------------------------------------------
                      Expanded(
                        child: PageView.builder(
                          controller: _pageController,
                          scrollDirection: Axis.horizontal,
                          physics: const BouncingScrollPhysics(),
                          itemCount: _relatedCards.length,
                          onPageChanged: (idx) {
                            setState(() => _currentIndex = idx);
                          },
                          itemBuilder: (ctx, idx) {
                            final card = _relatedCards[idx];
                            return NewsCardWidget(
                              card: card,
                              hideRelatedCapsule: true, // Prevents recursive nested capsule
                            );
                          },
                        ),
                      ),

                      // ---------------------------------------------------------
                      // 3. BOTTOM PROGRESS LINE & PAGE INDICATOR (matches video)
                      // ---------------------------------------------------------
                      Container(
                        height: 42,
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        color: Colors.black,
                        child: Row(
                          children: [
                            // Multi-segment progress bar showing count & current position
                            Expanded(
                              child: _buildSegmentedProgressLine(colorScheme, theme),
                            ),
                            const SizedBox(width: 14),
                            // Page count indicator (e.g. 6/10)
                            Text(
                              '${_currentIndex + 1}/${_relatedCards.length}',
                              style: const TextStyle(
                                color: Colors.white70,
                                fontSize: 13,
                                fontWeight: FontWeight.bold,
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

  /// Segmented story-style horizontal progress indicator line
  Widget _buildSegmentedProgressLine(ColorScheme colorScheme, ThemeData theme) {
    if (_relatedCards.isEmpty) return const SizedBox.shrink();

    final count = _relatedCards.length;

    return Row(
      children: List.generate(count, (index) {
        final isFilled = index <= _currentIndex;

        return Expanded(
          child: Container(
            margin: EdgeInsets.only(
              left: index == 0 ? 0 : 2,
              right: index == count - 1 ? 0 : 2,
            ),
            height: 3.5,
            decoration: BoxDecoration(
              color: isFilled
                  ? const Color(0xFF2196F3)
                  : Colors.white24,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
        );
      }),
    );
  }
}
