import 'package:flutter/material.dart';
import '../models/card_model.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';
import '../services/chat_service.dart';
import '../services/feed_persistence_service.dart';
import '../theme/tokens.dart';
import 'auth_screen.dart';
import 'chat_history_screen.dart';
import 'byok_settings_sheet.dart';
import 'learner_profile_sheet.dart';
import 'quiz_modal.dart';
import 'retention_quiz_sheet.dart';
import 'stacked_card_feed.dart';

/// Hardcore Inshorts-style main view with top horizontal navigation bar,
/// vertical snap page-view card feed, and bottom system bar.
///
/// Strictly matches the user-provided screenshots and video walkthrough:
/// - Top bar: Scrolling horizontal tabs: [My Feed], [Daily Ritual], [Research], [Hardware], [Reasoning]
/// - Card feed: Full-bleed vertical snap cards with research figures, headlines, narrative story, and topic capsules
/// - Bottom bar: Inshorts system navigation (Search, Home, Profile)
class FeedView extends StatefulWidget {
  final AppThemeFamily themeFamily;
  final bool isDark;
  final Function(AppThemeFamily) onThemeFamilyChanged;
  final Function(bool) onDarkThemeToggled;

  const FeedView({
    super.key,
    required this.themeFamily,
    required this.isDark,
    required this.onThemeFamilyChanged,
    required this.onDarkThemeToggled,
  });

  @override
  State<FeedView> createState() => _FeedViewState();
}

class _FeedViewState extends State<FeedView> {
  final ApiService _apiService = ApiService();
  final FeedPersistenceService _persistence = FeedPersistenceService();
  final ChatService _chatService = ChatService();
  final PageController _pageController = PageController();
  final PageController _horizontalTabController = PageController();

  List<NewsCard> _cards = [];
  String? _nextCursor;
  bool _isLoading = true;
  bool _isLoadingMore = false;
  String? _error;
  bool _isFeedGated = false;
  String? _gatedMessage;

  int _currentCardIndex = 0;
  String _activeTab = 'My Feed';
  int _bottomNavIndex = 1; // 0 = search, 1 = home, 2 = profile

  final List<String> _navTabs = const [
    'My Feed',
    'Daily Ritual',
    'Research',
    'Hardware',
    'Reasoning',
  ];

  @override
  void initState() {
    super.initState();
    _loadInitialCards();
  }

  @override
  void dispose() {
    _pageController.dispose();
    _horizontalTabController.dispose();
    super.dispose();
  }

  Future<void> _loadInitialCards() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final res = await _apiService.fetchCards();
      // Prioritize newly scraped / unseen cards first, eliminate duplicates
      final prioritized = _persistence.filterAndPrioritize(res.cards);
      final resumeIndex = _persistence.getResumeIndex(prioritized);

      setState(() {
        _cards = prioritized;
        _nextCursor = res.nextCursor;
        _currentCardIndex = resumeIndex;
        _isFeedGated = false;
        _gatedMessage = null;
        _isLoading = false;
      });

      // Same-day reading position resume
      if (resumeIndex > 0 && prioritized.isNotEmpty) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (_pageController.hasClients) {
            _pageController.jumpToPage(resumeIndex);
          }
        });
      }

      if (prioritized.isNotEmpty && resumeIndex < prioritized.length) {
        _persistence.saveReadingProgress(resumeIndex, prioritized[resumeIndex]);
      }
    } on FeedGatedException catch (e) {
      setState(() {
        _isFeedGated = true;
        _gatedMessage = e.message;
        _isLoading = false;
      });
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _showRetentionQuizModal();
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _loadMoreCards() async {
    if (_nextCursor == null || _isLoadingMore) return;
    setState(() => _isLoadingMore = true);

    try {
      final res = await _apiService.fetchCards(cursor: _nextCursor);
      // Deduplicate when appending new cards
      final combined = _persistence.filterAndPrioritize([..._cards, ...res.cards]);
      setState(() {
        _cards = combined;
        _nextCursor = res.nextCursor;
        _isLoadingMore = false;
      });
    } catch (_) {
      setState(() => _isLoadingMore = false);
    }
  }

  /// Marks card as read in persistence without destroying deck scroll history
  /// and registers card into Rule 65 (OKF) 15-day retention challenge pool
  void _onCardDismissed(NewsCard card) {
    _persistence.saveReadingProgress(_currentCardIndex, card);
    _persistence.markCardAsSeen(card);
    AuthService().recordScrolledCard(card);
  }

  void _showRetentionQuizModal() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      isDismissible: false,
      enableDrag: false,
      backgroundColor: Colors.transparent,
      builder: (ctx) => RetentionQuizSheet(
        onCompleted: () {
          setState(() {
            _isFeedGated = false;
            _gatedMessage = null;
          });
          _loadInitialCards();
        },
      ),
    );
  }

  void _showAuthScreen() {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (ctx) => AuthScreen(
          onAuthenticated: () {
            setState(() {});
            _loadInitialCards();
          },
        ),
      ),
    );
  }

  NewsCard? get _currentCard {
    if (_cards.isEmpty || _currentCardIndex >= _cards.length) return null;
    return _cards[_currentCardIndex];
  }

  void _showSearchDialog() {
    final queryController = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) {
        final theme = Theme.of(ctx);
        return AlertDialog(
          backgroundColor: theme.cardColor,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Text('Search Research Corpus'),
          content: TextField(
            controller: queryController,
            autofocus: true,
            decoration: InputDecoration(
              hintText: 'Enter keyword, e.g. "transformers", "attention"...',
              prefixIcon: const Icon(Icons.search),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                final q = queryController.text.trim().toLowerCase();
                Navigator.pop(ctx);
                if (q.isNotEmpty) {
                  final idx = _cards.indexWhere((c) =>
                      c.headline.toLowerCase().contains(q) ||
                      c.tags.any((t) => t.toLowerCase().contains(q)));
                  if (idx != -1) {
                    _pageController.animateToPage(
                      idx,
                      duration: const Duration(milliseconds: 350),
                      curve: Curves.easeInOut,
                    );
                  } else {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('No cards found for "$q" in current batch.')),
                    );
                  }
                }
              },
              child: const Text('Search'),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        bottom: false,
        top: true,
        child: Column(
          children: [
            // -----------------------------------------------------------
            // 1. TOP NAVBAR DOCKED AT TOP EDGE (Pure Black, No Emojis)
            // -----------------------------------------------------------
            _buildTopNavBar(theme),

            // -----------------------------------------------------------
            // 2. MAIN HORIZONTAL PAGEVIEW (Seamless Tab Swiping)
            // -----------------------------------------------------------
            Expanded(
              child: _buildMainBody(theme),
            ),

            // -----------------------------------------------------------
            // 3. BOTTOM NAVBAR DOCKED AT BOTTOM EDGE (Pure Black)
            // -----------------------------------------------------------
            _buildBottomSystemBar(theme),
          ],
        ),
      ),
    );
  }

  /// Horizontal scrolling Inshorts navigation tab bar (Pure black, docked at top edge)
  Widget _buildTopNavBar(ThemeData theme) {
    final auth = AuthService();
    return Container(
      height: 46,
      width: double.infinity,
      color: Colors.black,
      child: Row(
        children: [
          Expanded(
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              physics: const BouncingScrollPhysics(),
              padding: const EdgeInsets.symmetric(horizontal: 10),
              itemCount: _navTabs.length,
              itemBuilder: (ctx, idx) {
                final tab = _navTabs[idx];
                final isActive = _activeTab == tab;

                return GestureDetector(
                  onTap: () {
                    setState(() => _activeTab = tab);
                    if (_horizontalTabController.hasClients) {
                      _horizontalTabController.animateToPage(
                        idx,
                        duration: const Duration(milliseconds: 280),
                        curve: Curves.easeInOut,
                      );
                    }
                  },
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14),
                    alignment: Alignment.center,
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          tab,
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: isActive ? FontWeight.w700 : FontWeight.w500,
                            color: isActive ? const Color(0xFF2196F3) : Colors.white70,
                          ),
                        ),
                        if (isActive)
                          Container(
                            margin: const EdgeInsets.only(top: 4),
                            height: 2.5,
                            width: 22,
                            decoration: BoxDecoration(
                              color: const Color(0xFF2196F3),
                              borderRadius: BorderRadius.circular(2),
                            ),
                          ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: auth.isAuthenticated
                ? GestureDetector(
                    onTap: () => LearnerProfileSheet.show(context),
                    child: CircleAvatar(
                      radius: 13,
                      backgroundColor: const Color(0xFF238636),
                      child: Text(
                        auth.username?.isNotEmpty == true ? auth.username![0].toUpperCase() : 'U',
                        style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.white),
                      ),
                    ),
                  )
                : TextButton(
                    onPressed: _showAuthScreen,
                    style: TextButton.styleFrom(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      visualDensity: VisualDensity.compact,
                    ),
                    child: const Text(
                      'Sign In',
                      style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Color(0xFF58A6FF)),
                    ),
                  ),
          ),
        ],
      ),
    );
  }

  /// Seamless horizontal PageView for top tabs
  Widget _buildMainBody(ThemeData theme) {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator.adaptive());
    }

    // Rule 65: If feed is gated, block forward progression until 10-minute quiz is taken
    if (_isFeedGated) {
      return _buildGatedFeedView(theme);
    }

    if (_error != null && _cards.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.wifi_off_outlined, size: 48, color: Colors.grey),
              const SizedBox(height: 12),
              Text('Feed temporarily offline',
                  style: theme.textTheme.titleMedium?.copyWith(color: Colors.white)),
              const SizedBox(height: 8),
              Text(
                'Could not connect to the news server. Tap below to retry.',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodySmall?.copyWith(color: Colors.white60),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _loadInitialCards,
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    return PageView(
      controller: _horizontalTabController,
      physics: const ClampingScrollPhysics(),
      onPageChanged: (idx) {
        setState(() {
          _activeTab = _navTabs[idx];
        });
      },
      children: [
        // Tab 0: My Feed (All Papers)
        _buildVerticalCardsFeed(theme, null),

        // Tab 1: Daily Ritual
        _buildDailyRitualView(theme),

        // Tab 2: Research
        _buildVerticalCardsFeed(theme, 'Research'),

        // Tab 3: Hardware
        _buildVerticalCardsFeed(theme, 'Hardware'),

        // Tab 4: Reasoning
        _buildVerticalCardsFeed(theme, 'Reasoning'),
      ],
    );
  }

  /// Rule 65: Feed Gated View.
  /// If the 15-day comprehension check is due, the user is strictly not allowed to proceed forward
  /// until they complete the 10-minute maximum retention challenge.
  Widget _buildGatedFeedView(ThemeData theme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 28.0),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.red.withValues(alpha: 0.15),
                border: Border.all(color: Colors.redAccent.withValues(alpha: 0.5), width: 2),
              ),
              child: const Icon(Icons.lock_rounded, size: 48, color: Colors.redAccent),
            ),
            const SizedBox(height: 20),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              decoration: BoxDecoration(
                color: Colors.red.shade900.withValues(alpha: 0.4),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.redAccent.withValues(alpha: 0.4)),
              ),
              child: const Text(
                'RULE 65 — 15-DAY COMPREHENSION CHECK',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 0.8,
                  color: Colors.redAccent,
                ),
              ),
            ),
            const SizedBox(height: 14),
            Text(
              'Feed Gated for Knowledge Verification',
              style: theme.textTheme.titleMedium?.copyWith(
                color: Colors.white,
                fontWeight: FontWeight.bold,
                fontSize: 17,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 10),
            Text(
              _gatedMessage ??
                  'Your 15-day comprehension check is due. Complete the 10-minute quiz on scrolled papers to continue reading.',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodySmall?.copyWith(color: Colors.white70, height: 1.4),
            ),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              height: 48,
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFE53935),
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  elevation: 4,
                ),
                onPressed: _showRetentionQuizModal,
                icon: const Icon(Icons.timer_outlined, size: 20),
                label: const Text(
                  'Start 10-Minute Challenge',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Vertical snap feed of hardcore Inshorts cards ("flash scrollable cards")
  Widget _buildVerticalCardsFeed(ThemeData theme, String? category) {
    List<NewsCard> displayCards = _cards;
    if (category == 'Research') {
      final filtered = _cards
          .where((c) => c.category.toLowerCase() == 'research' || c.tags.contains('research'))
          .toList();
      if (filtered.isNotEmpty) displayCards = filtered;
    } else if (category == 'Hardware') {
      final filtered = _cards
          .where((c) => c.tags
              .any((t) => t.contains('hardware') || t.contains('gpu') || t.contains('efficiency')))
          .toList();
      if (filtered.isNotEmpty) displayCards = filtered;
    } else if (category == 'Reasoning') {
      final filtered = _cards
          .where((c) =>
              c.tags.any((t) => t.contains('reasoning') || t.contains('math') || t.contains('rl')))
          .toList();
      if (filtered.isNotEmpty) displayCards = filtered;
    }

    if (displayCards.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 32.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.05),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.check_circle_outline_rounded,
                    size: 52, color: Colors.greenAccent),
              ),
              const SizedBox(height: 16),
              Text(
                "You're All Caught Up!",
                style: theme.textTheme.titleMedium
                    ?.copyWith(color: Colors.white, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Text(
                "All unread research papers have been consumed. Tap below to fetch newly published research or reset.",
                textAlign: TextAlign.center,
                style: theme.textTheme.bodySmall?.copyWith(color: Colors.white60),
              ),
              const SizedBox(height: 20),
              ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.black,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                ),
                onPressed: () {
                  _persistence.reset();
                  _loadInitialCards();
                },
                icon: const Icon(Icons.refresh_rounded, size: 18),
                label: const Text('Refresh Feed'),
              ),
            ],
          ),
        ),
      );
    }

    return StackedCardFeed(
      cards: displayCards,
      initialIndex: category == null ? _currentCardIndex : 0,
      onCardChanged: (idx) {
        if (category == null) {
          setState(() => _currentCardIndex = idx);
          if (idx >= 0 && idx < displayCards.length) {
            _persistence.saveReadingProgress(idx, displayCards[idx]);
            _persistence.markCardAsSeen(displayCards[idx]);
          }
        }
      },
      onCardDismissed: (card) {
        if (category == null) {
          _onCardDismissed(card);
        } else {
          // For category views, also evict from primary list
          _onCardDismissed(card);
        }
      },
      onEndReached: () {
        if (category == null) {
          _loadMoreCards();
        }
      },
      onRefresh: _loadInitialCards,
    );
  }

  /// Daily Ritual & Quiz View (framed as a rounded card matching frame_552.jpg in video)
  Widget _buildDailyRitualView(ThemeData theme) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
      decoration: BoxDecoration(
        color: theme.cardColor,
        borderRadius: BorderRadius.circular(18),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(18),
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
          child: Column(
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text('Welcome to ', style: theme.textTheme.bodyMedium),
                  const Text('bodh',
                      style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
                  const Text(' research', style: TextStyle(fontWeight: FontWeight.bold)),
                ],
              ),
              const SizedBox(height: 6),
              const Text(
                'DAILY RITUAL',
                style: TextStyle(
                  fontSize: 26,
                  fontWeight: FontWeight.w900,
                  color: Color(0xFFE53935),
                  letterSpacing: 0.5,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                'Designed to turn staying informed into a daily habit!',
                style: theme.textTheme.bodySmall?.copyWith(fontSize: 13),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 28),

              // Step 1: Read Today's News
              _buildRitualStepCard(
                stepNumber: 'Step-1',
                title: "Read Today's Research",
                subtitle: 'Get the top AI papers that matter for the day in one place.',
                icon: Icons.newspaper_rounded,
                iconColor: Colors.blueAccent,
                theme: theme,
              ),

              const SizedBox(height: 18),

              // Step 2: Build Your Knowledge Streak (Rule 65 OKF)
              _buildRitualStepCard(
                stepNumber: 'Step-2',
                title: '15-Day Retention Challenge',
                subtitle: 'Test your understanding with 10-minute quizzes on papers you scrolled.',
                icon: Icons.local_fire_department_rounded,
                iconColor: Colors.orangeAccent,
                theme: theme,
              ),

              const SizedBox(height: 24),

              // Reader count banner
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: BoxDecoration(
                  color: Colors.red.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.group_rounded, color: Color(0xFFE53935), size: 22),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        'Lakhs of AI researchers and practitioners have made Daily Ritual their everyday habit.',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                          color: theme.textTheme.bodyLarge?.color,
                        ),
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 32),

              // Large Red "Tap Here to Start" Button (matches frame_552.jpg)
              SizedBox(
                width: double.infinity,
                height: 52,
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFE53935),
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                    elevation: 4,
                  ),
                  onPressed: () {
                    final auth = AuthService();
                    if (auth.isAuthenticated) {
                      _showRetentionQuizModal();
                    } else {
                      final card = _currentCard;
                      final topic = card?.tags.isNotEmpty == true ? card!.tags.first : 'transformers';
                      QuizModal.show(context,
                          topicSlug: topic, topicDisplayName: topic.toUpperCase());
                    }
                  },
                  child: Text(
                    AuthService().isAuthenticated ? 'Start 15-Day Retention Challenge (10 min)' : 'Tap Here to Start Quiz',
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildRitualStepCard({
    required String stepNumber,
    required String title,
    required String subtitle,
    required IconData icon,
    required Color iconColor,
    required ThemeData theme,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: theme.cardColor,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: theme.dividerColor.withValues(alpha: 0.6)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Positioned(
            top: -28,
            left: 0,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
              decoration: BoxDecoration(
                color: Colors.red.shade50,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                stepNumber,
                style: const TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFFE53935),
                ),
              ),
            ),
          ),
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: iconColor.withValues(alpha: 0.12),
                  shape: BoxShape.circle,
                ),
                child: Icon(icon, color: iconColor, size: 28),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        fontSize: 15.5,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      subtitle,
                      style: theme.textTheme.bodySmall?.copyWith(fontSize: 12.5),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  /// Hardcore Inshorts Bottom Navigation Bar (Pure black, docked at bottom edge)
  Widget _buildBottomSystemBar(ThemeData theme) {
    return Container(
      height: 52,
      width: double.infinity,
      color: Colors.black,
      padding: const EdgeInsets.symmetric(horizontal: 36),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          // Search Icon (matches Inshorts)
          IconButton(
            tooltip: 'Search papers',
            icon: Icon(
              Icons.search_rounded,
              size: 26,
              color: _bottomNavIndex == 0 ? const Color(0xFF2196F3) : Colors.white70,
            ),
            onPressed: () {
              setState(() => _bottomNavIndex = 0);
              _showSearchDialog();
            },
          ),

          // Home Icon (matches Inshorts)
          IconButton(
            tooltip: 'Home Feed',
            icon: Icon(
              Icons.home_filled,
              size: 28,
              color: _bottomNavIndex == 1 && _activeTab == 'My Feed'
                  ? Colors.white
                  : const Color(0xFF2196F3),
            ),
            onPressed: () {
              setState(() {
                _bottomNavIndex = 1;
                _activeTab = 'My Feed';
              });
              if (_horizontalTabController.hasClients) {
                _horizontalTabController.jumpToPage(0);
              }
              if (_pageController.hasClients) {
                _pageController.animateToPage(
                  0,
                  duration: const Duration(milliseconds: 300),
                  curve: Curves.easeInOut,
                );
              }
            },
          ),

          // Chats Icon
          IconButton(
            tooltip: 'Past Conversations',
            icon: Icon(
              Icons.chat_bubble_outline_rounded,
              size: 25,
              color: _bottomNavIndex == 2 ? const Color(0xFF2196F3) : Colors.white70,
            ),
            onPressed: () {
              setState(() => _bottomNavIndex = 2);
              ChatHistoryScreen.show(
                context,
                chatService: _chatService,
                allCards: _cards,
              );
            },
          ),

          // Profile / Settings Icon (matches Inshorts)
          GestureDetector(
            onLongPress: () {
              ByokSettingsSheet.show(context);
            },
            child: IconButton(
              tooltip: 'Learner Profile & BYOK Keys',
              icon: Icon(
                Icons.account_circle_rounded,
                size: 28,
                color: _bottomNavIndex == 3 ? const Color(0xFF2196F3) : Colors.white70,
              ),
              onPressed: () {
                setState(() => _bottomNavIndex = 3);
                LearnerProfileSheet.show(context);
              },
            ),
          ),
        ],
      ),
    );
  }
}
