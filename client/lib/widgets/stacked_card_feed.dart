import 'dart:ui' show ImageFilter, lerpDouble;
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/card_model.dart';
import 'news_card.dart';

/// Card Stack Feed with signature Inshorts depth motion:
/// - Cards are layered in a physical Stack.
/// - Active card sits sharply in front.
/// - Next card sits directly behind in the stack, scaled down and blurred.
/// - Swiping UP translates the front card away while the next card scales up and
///   unblurs smoothly from the background into crisp focus.
/// - Swiping DOWN slides the previous card down over the current card.
/// - Supports touch swipe, mouse scroll wheel, and keyboard navigation.
class StackedCardFeed extends StatefulWidget {
  final List<NewsCard> cards;
  final int initialIndex;
  final ValueChanged<int>? onCardChanged;
  final ValueChanged<NewsCard>? onCardDismissed;
  final VoidCallback? onEndReached;
  final Future<void> Function()? onRefresh;

  const StackedCardFeed({
    super.key,
    required this.cards,
    this.initialIndex = 0,
    this.onCardChanged,
    this.onCardDismissed,
    this.onEndReached,
    this.onRefresh,
  });

  @override
  State<StackedCardFeed> createState() => StackedCardFeedState();
}

class StackedCardFeedState extends State<StackedCardFeed>
    with SingleTickerProviderStateMixin {
  late int _currentIndex;
  late final AnimationController _controller;
  late final CurvedAnimation _curvedAnimation;

  double _animStart = 0.0;
  double _animTarget = 0.0;
  double _dragOffset = 0.0;
  double _accumulatedScrollDelta = 0.0;
  DateTime _lastWheelTime = DateTime.now();

  @override
  void initState() {
    super.initState();
    _currentIndex = widget.initialIndex.clamp(0, (widget.cards.length - 1).clamp(0, 9999));
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 380),
    );
    _curvedAnimation = CurvedAnimation(parent: _controller, curve: Curves.fastLinearToSlowEaseIn);
    _controller.addListener(() {
      setState(() {
        _dragOffset = lerpDouble(_animStart, _animTarget, _curvedAnimation.value) ?? _animTarget;
      });
    });
  }

  @override
  void didUpdateWidget(StackedCardFeed oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_currentIndex >= widget.cards.length && widget.cards.isNotEmpty) {
      _currentIndex = widget.cards.length - 1;
    }
  }

  @override
  void dispose() {
    _curvedAnimation.dispose();
    _controller.dispose();
    super.dispose();
  }

  /// Programmatic jump to a specific card index
  void jumpToCard(int index) {
    if (index >= 0 && index < widget.cards.length && index != _currentIndex) {
      setState(() {
        _currentIndex = index;
        _dragOffset = 0.0;
      });
      widget.onCardChanged?.call(_currentIndex);
    }
  }

  /// Programmatic animated advance to next card
  void nextCard() {
    if (_currentIndex < widget.cards.length - 1 && !_controller.isAnimating) {
      HapticFeedback.lightImpact();
      final h = context.size?.height ?? 600.0;
      final dismissedCard = widget.cards[_currentIndex];
      _animateToOffset(-h, onComplete: () {
        setState(() {
          _currentIndex++;
          _dragOffset = 0.0;
        });
        widget.onCardChanged?.call(_currentIndex);
        widget.onCardDismissed?.call(dismissedCard);
        if (_currentIndex >= widget.cards.length - 2) {
          widget.onEndReached?.call();
        }
      });
    }
  }

  /// Programmatic animated return to previous card
  void prevCard() {
    if (_currentIndex > 0 && !_controller.isAnimating) {
      HapticFeedback.lightImpact();
      final h = context.size?.height ?? 600.0;
      _animateToOffset(h, onComplete: () {
        setState(() {
          _currentIndex--;
          _dragOffset = 0.0;
        });
        widget.onCardChanged?.call(_currentIndex);
      });
    }
  }

  void _animateToOffset(double target, {VoidCallback? onComplete}) {
    _animStart = _dragOffset;
    _animTarget = target;
    _controller.forward(from: 0.0).then((_) {
      if (mounted) {
        setState(() {
          _dragOffset = target;
        });
        onComplete?.call();
      }
    });
  }

  void _onVerticalDragStart(DragStartDetails details) {
    if (_controller.isAnimating) {
      _controller.stop();
    }
  }

  void _onVerticalDragUpdate(DragUpdateDetails details) {
    final delta = details.primaryDelta ?? 0.0;
    setState(() {
      if (_currentIndex == 0 && _dragOffset + delta > 0) {
        // Rubber-band resistance at top of feed
        _dragOffset += delta * 0.35;
      } else if (_currentIndex == widget.cards.length - 1 && _dragOffset + delta < 0) {
        // Rubber-band resistance at bottom of feed
        _dragOffset += delta * 0.35;
      } else {
        _dragOffset += delta;
      }
    });
  }

  void _onVerticalDragEnd(DragEndDetails details) {
    final h = context.size?.height ?? 600.0;
    final vy = details.primaryVelocity ?? 0.0;
    const swipeThreshold = 65.0;
    const velocityThreshold = 260.0;

    if (_dragOffset < -swipeThreshold || vy < -velocityThreshold) {
      // Swiping UP -> Bring next card from back blur
      if (_currentIndex < widget.cards.length - 1) {
        final dismissedCard = widget.cards[_currentIndex];
        _animateToOffset(-h, onComplete: () {
          setState(() {
            _currentIndex++;
            _dragOffset = 0.0;
          });
          widget.onCardChanged?.call(_currentIndex);
          widget.onCardDismissed?.call(dismissedCard);
          if (_currentIndex >= widget.cards.length - 2) {
            widget.onEndReached?.call();
          }
        });
      } else {
        _animateToOffset(0.0);
      }
    } else if (_dragOffset > swipeThreshold || vy > velocityThreshold) {
      // Swiping DOWN -> Slide previous card down
      if (_currentIndex > 0) {
        _animateToOffset(h, onComplete: () {
          setState(() {
            _currentIndex--;
            _dragOffset = 0.0;
          });
          widget.onCardChanged?.call(_currentIndex);
        });
      } else {
        _animateToOffset(0.0);
      }
    } else {
      _animateToOffset(0.0);
    }
  }

  void _handlePointerSignal(PointerSignalEvent event) {
    if (event is PointerScrollEvent) {
      final now = DateTime.now();
      if (now.difference(_lastWheelTime).inMilliseconds > 400) {
        _accumulatedScrollDelta = 0.0;
      }
      _lastWheelTime = now;
      _accumulatedScrollDelta += event.scrollDelta.dy;

      if (_accumulatedScrollDelta > 18) {
        // Mouse wheel scrolled down -> Next card
        _accumulatedScrollDelta = 0.0;
        nextCard();
      } else if (_accumulatedScrollDelta < -18) {
        // Mouse wheel scrolled up -> Previous card
        _accumulatedScrollDelta = 0.0;
        prevCard();
      }
    }
  }

  KeyEventResult _handleKeyEvent(FocusNode node, KeyEvent event) {
    if (event is KeyDownEvent) {
      if (event.logicalKey == LogicalKeyboardKey.arrowDown ||
          event.logicalKey == LogicalKeyboardKey.pageDown ||
          event.logicalKey == LogicalKeyboardKey.space) {
        nextCard();
        return KeyEventResult.handled;
      } else if (event.logicalKey == LogicalKeyboardKey.arrowUp ||
          event.logicalKey == LogicalKeyboardKey.pageUp) {
        prevCard();
        return KeyEventResult.handled;
      }
    }
    return KeyEventResult.ignored;
  }

  @override
  Widget build(BuildContext context) {
    if (widget.cards.isEmpty) {
      return const SizedBox.shrink();
    }

    return LayoutBuilder(
      builder: (context, constraints) {
        final height = constraints.maxHeight;
        final width = constraints.maxWidth;
        final isActivelySwipingUp = _dragOffset < -1.0;
        final isActivelySwipingDown = _dragOffset > 1.0;

        return Focus(
          autofocus: true,
          onKeyEvent: _handleKeyEvent,
          child: Listener(
            onPointerSignal: _handlePointerSignal,
            child: GestureDetector(
              onVerticalDragStart: _onVerticalDragStart,
              onVerticalDragUpdate: _onVerticalDragUpdate,
              onVerticalDragEnd: _onVerticalDragEnd,
              onVerticalDragCancel: () => _animateToOffset(0.0),
              behavior: HitTestBehavior.opaque,
              child: Stack(
                fit: StackFit.expand,
                clipBehavior: Clip.none,
                children: [
                  // -----------------------------------------------------------
                  // Layer 1 (Background): Next card scaling up & unblurring
                  // Strictly rendered ONLY during an active upward swipe gesture
                  // -----------------------------------------------------------
                  if (isActivelySwipingUp && _currentIndex + 1 < widget.cards.length)
                    _buildNextCardBehind(height, width),

                  // -----------------------------------------------------------
                  // Layer 2 (Background): Current card blurring when pulling prev down
                  // Strictly rendered ONLY during an active downward pull gesture
                  // -----------------------------------------------------------
                  if (isActivelySwipingDown && _currentIndex > 0)
                    _buildCurrentCardAsBackground(height, width),

                  // -----------------------------------------------------------
                  // Layer 3 (Foreground): Current card translating upward, or rubber-band at top
                  // -----------------------------------------------------------
                  if (_dragOffset <= 0 || _currentIndex == 0)
                    _buildCurrentCardForeground(height, width),

                  // -----------------------------------------------------------
                  // Layer 4 (Foreground): Previous card sliding down from top
                  // Strictly rendered ONLY during an active downward pull gesture
                  // -----------------------------------------------------------
                  if (isActivelySwipingDown && _currentIndex > 0)
                    _buildPrevCardForeground(height, width),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  /// Next card sitting in the stack behind the active card:
  /// Starts at scale 0.90, blur 14.0, opacity 0.65.
  /// Smoothly scales to 1.0, unblurs to 0, and opacity to 1.0 as the user swipes up.
  Widget _buildNextCardBehind(double height, double width) {
    final progress = (-_dragOffset / (height * 0.75)).clamp(0.0, 1.0);
    final scale = lerpDouble(0.90, 1.0, progress)!;
    final blur = lerpDouble(14.0, 0.0, progress)!;
    final opacity = lerpDouble(0.65, 1.0, progress)!;

    final nextCard = widget.cards[_currentIndex + 1];

    Widget cardWidget = NewsCardWidget(
      card: nextCard,
      key: ValueKey('card_${nextCard.id}'),
    );

    // Apply hardware-accelerated blur when sitting in background
    if (blur > 0.4) {
      cardWidget = ImageFiltered(
        imageFilter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
        child: cardWidget,
      );
    }

    return Transform.scale(
      scale: scale,
      alignment: Alignment.center,
      child: Opacity(
        opacity: opacity,
        child: cardWidget,
      ),
    );
  }

  /// Current card acting as background when pulling previous card down from top
  Widget _buildCurrentCardAsBackground(double height, double width) {
    final progress = (_dragOffset / (height * 0.75)).clamp(0.0, 1.0);
    final scale = lerpDouble(1.0, 0.90, progress)!;
    final blur = lerpDouble(0.0, 14.0, progress)!;
    final opacity = lerpDouble(1.0, 0.65, progress)!;

    final currentCard = widget.cards[_currentIndex];

    Widget cardWidget = NewsCardWidget(
      card: currentCard,
      key: ValueKey('card_${currentCard.id}'),
    );

    if (blur > 0.4) {
      cardWidget = ImageFiltered(
        imageFilter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
        child: cardWidget,
      );
    }

    return Transform.scale(
      scale: scale,
      alignment: Alignment.center,
      child: Opacity(
        opacity: opacity,
        child: cardWidget,
      ),
    );
  }

  /// Current card actively moving in foreground when swiping up
  Widget _buildCurrentCardForeground(double height, double width) {
    final currentCard = widget.cards[_currentIndex];
    // Subtle page-lift tilt: as the card moves up, tilt forward slightly
    final liftProgress = (_dragOffset < 0) ? (-_dragOffset / height).clamp(0.0, 1.0) : 0.0;
    final tiltX = liftProgress * 0.04; // radians — very subtle forward tilt

    final matrix = Matrix4.identity()
      ..setEntry(3, 2, 0.0008) // perspective
      ..rotateX(tiltX);

    return Transform(
      transform: matrix,
      alignment: Alignment.topCenter,
      child: Transform.translate(
        offset: Offset(0, _dragOffset),
        child: Container(
          decoration: BoxDecoration(
            boxShadow: [
              if (_dragOffset < -4)
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.55 + liftProgress * 0.2),
                  blurRadius: 20 + liftProgress * 16,
                  spreadRadius: liftProgress * 3,
                  offset: Offset(0, 8 + liftProgress * 8),
                ),
            ],
          ),
          child: NewsCardWidget(
            card: currentCard,
            key: ValueKey('card_${currentCard.id}'),
          ),
        ),
      ),
    );
  }

  /// Previous card sliding into foreground from top
  Widget _buildPrevCardForeground(double height, double width) {
    final prevCard = widget.cards[_currentIndex - 1];

    return Transform.translate(
      offset: Offset(0, -height + _dragOffset),
      child: Container(
        decoration: BoxDecoration(
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.5),
              blurRadius: 16,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: NewsCardWidget(
          card: prevCard,
          key: ValueKey('card_${prevCard.id}'),
        ),
      ),
    );
  }
}

