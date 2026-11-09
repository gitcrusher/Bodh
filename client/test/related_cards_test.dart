import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ai_news_client/models/card_model.dart';
import 'package:ai_news_client/services/feed_persistence_service.dart';
import 'package:ai_news_client/widgets/news_card.dart';
import 'package:ai_news_client/widgets/related_cluster_screen.dart';

void main() {
  final cardWithRelated = NewsCard(
    id: 101,
    category: 'research',
    headline: 'Attention Is All You Need: The Transformer Architecture',
    summary60s:
        '• Proposes the Transformer eliminating recurrence and convolution.\n'
        '• Employs multi-head self-attention across all tokens.\n'
        '• Reaches SOTA on WMT English-to-German.',
    tags: const ['transformers', 'attention', 'nlp'],
    candidateTechniques: const ['self-attention', 'multi-head attention'],
    sourceUrl: 'https://arxiv.org/abs/1706.03762',
    publishedAt: DateTime.now(),
    needsReview: false,
    relatedCount: 3,
    relatedTopic: 'Transformer Scaling',
    relatedPreview: const [
      {'id': 102, 'headline': 'FlashAttention-3'},
    ],
  );

  final cardWithoutRelated = NewsCard(
    id: 102,
    category: 'research',
    headline: 'Standalone Solitary Paper',
    summary60s: '• Solitary paper with no database clusters.',
    tags: const [],
    candidateTechniques: const [],
    sourceUrl: 'https://arxiv.org/abs/9999.9999',
    publishedAt: DateTime.now(),
    needsReview: false,
    relatedCount: 0,
    relatedTopic: null,
  );

  testWidgets('NewsCardWidget renders Inshorts-style related capsule with horizontal cluster hint',
      (WidgetTester tester) async {
    bool relatedTapped = false;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: NewsCardWidget(
            card: cardWithRelated,
            onRelated: () {
              relatedTapped = true;
            },
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();

    // Verify topic title is prominently displayed on the capsule
    expect(find.text('Transformer Scaling'), findsOneWidget);

    // Verify related database count indicator with horizontal swipe hint
    expect(find.textContaining('3 related papers in cluster • Swipe horizontal'), findsOneWidget);

    // Verify thumbnail icon and circular chevron icon
    expect(find.byIcon(Icons.auto_stories_rounded), findsOneWidget);
    expect(find.byIcon(Icons.arrow_forward_ios_rounded), findsOneWidget);

    // Tap on the capsule
    await tester.tap(find.text('Transformer Scaling'));
    await tester.pumpAndSettle();

    expect(relatedTapped, isTrue);
  });

  testWidgets('NewsCardWidget does not render capsule when relatedCount is 0 and topic is null',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: NewsCardWidget(
            card: cardWithoutRelated,
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();

    expect(find.textContaining('related papers in cluster'), findsNothing);
    expect(find.byIcon(Icons.arrow_forward_ios_rounded), findsNothing);
  });

  testWidgets('RelatedCardsClusterScreen displays horizontal cards, back arrow, and progress line',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: RelatedCardsClusterScreen(
            parentCard: cardWithRelated,
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();

    // Verify top bar with back arrow and topic title
    expect(find.byIcon(Icons.arrow_back_ios_new_rounded), findsOneWidget);
    expect(find.text('Transformer Scaling'), findsOneWidget);
    expect(find.text('RELATED CLUSTER'), findsOneWidget);

    // Verify progress indicator text (1 / N)
    expect(find.textContaining('/'), findsOneWidget);

    // Verify PageView is configured for horizontal scrolling
    final pageViewFinder = find.byType(PageView);
    expect(pageViewFinder, findsOneWidget);
    final PageView pageView = tester.widget(pageViewFinder);
    expect(pageView.scrollDirection, Axis.horizontal);

    // Verify first card in cluster is rendered
    expect(find.textContaining('Attention Is All You Need'), findsOneWidget);

    // Swipe horizontally to next card
    await tester.drag(pageViewFinder, const Offset(-500, 0));
    await tester.pumpAndSettle();

    // Verify second card in cluster appears
    expect(find.textContaining('FlashAttention-3'), findsOneWidget);

    // Tap back button
    await tester.tap(find.byIcon(Icons.arrow_back_ios_new_rounded));
    await tester.pumpAndSettle();
  });

  test('FeedPersistenceService prioritizes unseen cards and prevents duplicates', () {
    final service = FeedPersistenceService();
    service.reset();

    final cardA = NewsCard(
      id: 1,
      category: 'research',
      headline: 'Paper A',
      summary60s: 'Summary A',
      tags: const [],
      candidateTechniques: const [],
      sourceUrl: '',
      publishedAt: DateTime.now(),
      needsReview: false,
    );

    final cardB = NewsCard(
      id: 2,
      category: 'research',
      headline: 'Paper B',
      summary60s: 'Summary B',
      tags: const [],
      candidateTechniques: const [],
      sourceUrl: '',
      publishedAt: DateTime.now(),
      needsReview: false,
    );

    final cardC = NewsCard(
      id: 3,
      category: 'research',
      headline: 'Paper C',
      summary60s: 'Summary C',
      tags: const [],
      candidateTechniques: const [],
      sourceUrl: '',
      publishedAt: DateTime.now(),
      needsReview: false,
    );

    // User has already read Paper A
    service.saveReadingProgress(0, cardA);

    // New feed arrives with [cardA, cardB, cardC, cardA duplicate]
    final filtered = service.filterAndPrioritize([cardA, cardB, cardC, cardA]);

    // Duplicates eliminated: length should be 3
    expect(filtered.length, 3);

    // Unseen papers (B and C) MUST come first, seen paper (A) comes after!
    expect(filtered[0].id, 2);
    expect(filtered[1].id, 3);
    expect(filtered[2].id, 1);

    // Same-day reading position resume
    expect(service.getResumeIndex(filtered), 2);
  });

  test('FeedPersistenceService excludes isPrimaryFeed=false prior-art from main vertical feed (Rule 58)', () {
    final service = FeedPersistenceService();
    service.reset();

    final freshCard = NewsCard(
      id: 10,
      category: 'research',
      headline: 'Fresh Breakthrough Paper 2026',
      summary60s: 'Summary',
      tags: const [],
      candidateTechniques: const [],
      sourceUrl: '',
      publishedAt: DateTime.now(),
      needsReview: false,
      isPrimaryFeed: true,
    );

    final priorArtCard = NewsCard(
      id: 11,
      category: 'research',
      headline: 'Foundational Landmark Prior Art 2017',
      summary60s: 'Summary',
      tags: const [],
      candidateTechniques: const [],
      sourceUrl: '',
      publishedAt: DateTime.now(),
      needsReview: false,
      isPrimaryFeed: false, // Rule 58
    );

    final result = service.filterAndPrioritize([freshCard, priorArtCard]);

    // Only fresh card belongs in main vertical feed; prior art is reserved for related clusters
    expect(result.length, 1);
    expect(result.first.id, 10);
  });
}
