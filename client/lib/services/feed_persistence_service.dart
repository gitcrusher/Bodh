import '../models/card_model.dart';

/// Service managing reading position memory, seen cards tracking,
/// and fresh/unseen content prioritization.
///
/// Rules enforced:
/// 1. Same-Day Resume: Remembers where the reader left off if reopening on the same day.
/// 2. Unseen First: Surfaces newly scraped/unread papers at the top of the feed.
/// 3. Zero Duplicate Content: Guarantees no duplicated cards or headlines in the feed.
class FeedPersistenceService {
  static final FeedPersistenceService _instance = FeedPersistenceService._internal();
  factory FeedPersistenceService() => _instance;
  FeedPersistenceService._internal();

  int? _lastReadIndex;
  int? _lastReadCardId;
  String? _lastReadDate;
  final Set<int> _seenCardIds = <int>{};
  final Set<String> _seenHeadlines = <String>{};

  /// Returns today's calendar date as YYYY-MM-DD
  String _getTodayString() {
    final now = DateTime.now();
    return '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';
  }

  /// Records reading progress for a card
  void saveReadingProgress(int index, NewsCard card) {
    _lastReadIndex = index;
    _lastReadCardId = card.id;
    _lastReadDate = _getTodayString();
    _seenCardIds.add(card.id);
    _seenHeadlines.add(card.headline.trim().toLowerCase());
  }

  /// Determines whether the reader left off on the same day, returning the resume index.
  /// If the day has changed or index is out of bounds, returns 0.
  int getResumeIndex(List<NewsCard> cards) {
    if (cards.isEmpty) return 0;

    final today = _getTodayString();
    if (_lastReadDate != today) {
      // New day: start from beginning to see freshly scraped papers
      return 0;
    }

    // Try finding the exact card ID first
    if (_lastReadCardId != null) {
      final foundIdx = cards.indexWhere((c) => c.id == _lastReadCardId);
      if (foundIdx != -1) return foundIdx;
    }

    // Fallback to last recorded index if within range
    if (_lastReadIndex != null && _lastReadIndex! >= 0 && _lastReadIndex! < cards.length) {
      return _lastReadIndex!;
    }

    return 0;
  }

  /// Deduplicates cards and strictly drops already seen cards (Rule 61).
  /// Rule 58: Only includes isPrimaryFeed papers in the main vertical feed.
  /// Foundational prior-art papers are accessed through related clusters.
  /// Never repeats identical card IDs or headlines, and drops seen cards from active memory.
  List<NewsCard> filterAndPrioritize(List<NewsCard> incomingCards, {bool includeSeen = false}) {
    if (incomingCards.isEmpty) return [];

    final uniqueCards = <NewsCard>[];
    final trackedIds = <int>{};
    final trackedHeadlines = <String>{};

    // 1. Filter for primary feed and deduplicate incoming cards by ID and headline
    for (final card in incomingCards) {
      if (!card.isPrimaryFeed) continue; // Rule 58: prior-art belongs in related clusters
      final cleanHeadline = card.headline.trim().toLowerCase();
      if (!trackedIds.contains(card.id) && !trackedHeadlines.contains(cleanHeadline)) {
        trackedIds.add(card.id);
        trackedHeadlines.add(cleanHeadline);
        uniqueCards.add(card);
      }
    }

    // 2. Partition into unseen (new) and previously seen
    final unseen = <NewsCard>[];
    final seen = <NewsCard>[];

    for (final card in uniqueCards) {
      final cleanHeadline = card.headline.trim().toLowerCase();
      if (_seenCardIds.contains(card.id) || _seenHeadlines.contains(cleanHeadline)) {
        seen.add(card);
      } else {
        unseen.add(card);
      }
    }

    // 3. Rule 61: If includeSeen is false (default), DO NOT STORE OR RETURN SEEN CARDS!
    if (!includeSeen) {
      return unseen;
    }

    // Return unseen cards first, followed by previously read cards (for tests / inspection)
    return [...unseen, ...seen];
  }

  /// Explicitly marks a card as seen without requiring full reading progress record
  void markCardAsSeen(NewsCard card) {
    _seenCardIds.add(card.id);
    _seenHeadlines.add(card.headline.trim().toLowerCase());
  }

  /// Check whether a specific card has already been read
  bool isCardSeen(NewsCard card) {
    return _seenCardIds.contains(card.id) ||
        _seenHeadlines.contains(card.headline.trim().toLowerCase());
  }

  /// Clear session history (for testing or manual reset)
  void reset() {
    _lastReadIndex = null;
    _lastReadCardId = null;
    _lastReadDate = null;
    _seenCardIds.clear();
    _seenHeadlines.clear();
  }
}

