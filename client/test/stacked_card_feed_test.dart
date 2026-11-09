import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ai_news_client/models/card_model.dart';
import 'package:ai_news_client/widgets/stacked_card_feed.dart';

void main() {
  final sampleCards = [
    NewsCard(
      id: 1,
      category: 'research',
      headline: 'Card One Headline',
      summary60s: 'Summary One',
      tags: const ['tag1'],
      candidateTechniques: const [],
      sourceUrl: '',
      publishedAt: DateTime(2025, 1, 22),
      needsReview: false,
    ),
    NewsCard(
      id: 2,
      category: 'research',
      headline: 'Card Two Headline',
      summary60s: 'Summary Two',
      tags: const ['tag2'],
      candidateTechniques: const [],
      sourceUrl: '',
      publishedAt: DateTime(2024, 7, 12),
      needsReview: false,
    ),
    NewsCard(
      id: 3,
      category: 'research',
      headline: 'Card Three Headline',
      summary60s: 'Summary Three',
      tags: const ['tag3'],
      candidateTechniques: const [],
      sourceUrl: '',
      publishedAt: DateTime(2024, 12, 6),
      needsReview: false,
    ),
  ];

  testWidgets('StackedCardFeed renders current card in foreground and next card in background',
      (WidgetTester tester) async {
    int changedIndex = -1;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SizedBox(
            height: 700,
            width: 400,
            child: StackedCardFeed(
              cards: sampleCards,
              initialIndex: 0,
              onCardChanged: (idx) {
                changedIndex = idx;
              },
            ),
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();

    // Verify first card is in foreground
    expect(find.text('Card One Headline'), findsOneWidget);
    // Verify next card sits in background stack
    expect(find.text('Card Two Headline'), findsOneWidget);

    // Swipe UP to dismiss current card and bring next card from back blur
    await tester.drag(find.text('Card One Headline'), const Offset(0, -350));
    await tester.pumpAndSettle();

    // Verify index changed to 1
    expect(changedIndex, 1);
    expect(find.text('Card Two Headline'), findsOneWidget);
  });
}

