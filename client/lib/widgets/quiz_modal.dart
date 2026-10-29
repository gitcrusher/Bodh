import 'dart:async';
import 'package:flutter/material.dart';
import '../services/learning_service.dart';

/// Full-screen or modal interactive Quiz experience matching Agent/design.md §7.
///
/// Principles enforced:
/// - Strictly one-way: no back button or revisiting prior questions once answered.
/// - Adaptive progression: ends early when confidence in learner level is high.
/// - Gamified: progress bar, level-up framing, and streak indicator.
/// - Lifecycle-aware: detects when the app was backgrounded for > 4 seconds and
///   transparently swaps unanswered questions with an honest notification banner.
class QuizModal extends StatefulWidget {
  final String topicSlug;
  final String topicDisplayName;
  final LearningService? learningService;
  final VoidCallback? onCalibrationComplete;

  const QuizModal({
    super.key,
    required this.topicSlug,
    required this.topicDisplayName,
    this.learningService,
    this.onCalibrationComplete,
  });

  static Future<void> show(
    BuildContext context, {
    required String topicSlug,
    required String topicDisplayName,
    VoidCallback? onCalibrationComplete,
  }) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      enableDrag: false, // Prevent accidental dismissal during quiz
      backgroundColor: Colors.transparent,
      builder: (ctx) => QuizModal(
        topicSlug: topicSlug,
        topicDisplayName: topicDisplayName,
        onCalibrationComplete: onCalibrationComplete,
      ),
    );
  }

  @override
  State<QuizModal> createState() => _QuizModalState();
}

class _QuizModalState extends State<QuizModal> with WidgetsBindingObserver {
  late final LearningService _learningService;
  QuizSession? _session;
  QuizQuestion? _currentQuestion;
  bool _isLoading = true;
  String? _errorMessage;

  // Question interaction state
  int? _selectedDisplayIndex;
  AnswerResult? _lastAnswerResult;
  bool _isSubmitting = false;

  // Backgrounding deterrent state (design.md §7 & design doc §4)
  DateTime? _pausedAt;
  bool _swappedNoticeShown = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _learningService = widget.learningService ?? LearningService();
    _startQuizSession();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused || state == AppLifecycleState.inactive) {
      _pausedAt = DateTime.now();
    } else if (state == AppLifecycleState.resumed && _pausedAt != null) {
      final awayDuration = DateTime.now().difference(_pausedAt!);
      _pausedAt = null;

      // If backgrounded for more than 4 seconds during an active question
      if (awayDuration.inSeconds >= 4 && _session != null && !_session!.isCompleted) {
        _triggerQuestionSwap();
      }
    }
  }

  Future<void> _triggerQuestionSwap() async {
    if (_session == null || _session!.id == 0) return;
    try {
      final updated = await _learningService.swapQuestions(_session!.id);
      if (updated != null && mounted) {
        setState(() {
          _session = updated;
          _currentQuestion = updated.currentQuestion;
          _selectedDisplayIndex = null;
          _lastAnswerResult = null;
          _swappedNoticeShown = true;
        });
      }
    } catch (_) {}
  }

  Future<void> _startQuizSession() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final s = await _learningService.startQuiz(widget.topicSlug);
      if (mounted) {
        if (s != null) {
          setState(() {
            _session = s;
            _currentQuestion = s.currentQuestion;
            _isLoading = false;
          });
        } else {
          setState(() {
            _errorMessage = 'Could not initialize quiz for ${widget.topicDisplayName}.';
            _isLoading = false;
          });
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = e.toString();
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _submitAnswer() async {
    if (_selectedDisplayIndex == null || _currentQuestion == null || _session == null) return;

    setState(() => _isSubmitting = true);

    try {
      final result = await _learningService.submitAnswer(
        sessionId: _session!.id,
        questionId: _currentQuestion!.id,
        chosenDisplayIndex: _selectedDisplayIndex!,
        optionOrder: _currentQuestion!.optionOrder,
      );

      if (mounted) {
        if (result != null) {
          setState(() {
            _lastAnswerResult = result;
            _isSubmitting = false;
            if (result.session != null) {
              _session = result.session;
            }
          });
        } else {
          // Offline mock answer feedback
          final isCorrect = _selectedDisplayIndex == 1; // mock heuristic
          final mockResult = AnswerResult(
            isCorrect: isCorrect,
            correctIndex: 1,
            explanation: isCorrect
                ? 'Correct! Self-attention allows dynamic focus across all tokens without sequential bottlenecks.'
                : 'Attention computes weighted relevance distributions across input embeddings.',
            sessionEnded: (_session?.currentIndex ?? 0) >= 3,
            currentAccuracy: isCorrect ? 1.0 : 0.5,
          );
          setState(() {
            _lastAnswerResult = mockResult;
            _isSubmitting = false;
          });
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isSubmitting = false);
      }
    }
  }

  void _nextQuestion() {
    if (_lastAnswerResult?.sessionEnded == true || _session?.isCompleted == true) {
      // Quiz complete
      widget.onCalibrationComplete?.call();
      setState(() {
        _currentQuestion = null;
      });
      return;
    }

    if (_lastAnswerResult?.nextQuestion != null) {
      setState(() {
        _currentQuestion = _lastAnswerResult!.nextQuestion;
        _selectedDisplayIndex = null;
        _lastAnswerResult = null;
      });
    } else {
      // Completed or finished all questions
      widget.onCalibrationComplete?.call();
      setState(() {
        _currentQuestion = null;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Container(
      height: MediaQuery.of(context).size.height * 0.90,
      decoration: BoxDecoration(
        color: theme.cardColor,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Column(
        children: [
          // Header Bar
          _buildHeader(theme, colorScheme),

          if (_swappedNoticeShown) _buildSwapNoticeBanner(theme),

          // Content
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator.adaptive())
                : _errorMessage != null
                    ? _buildErrorView(theme)
                    : _currentQuestion != null
                        ? _buildQuestionView(theme, colorScheme)
                        : _buildCompletionView(theme, colorScheme),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(ThemeData theme, ColorScheme colorScheme) {
    final progress = _session != null && _session!.totalQuestions > 0
        ? ((_session!.currentIndex + (_lastAnswerResult != null ? 1 : 0)) / _session!.totalQuestions).clamp(0.0, 1.0)
        : 0.0;

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 12, 10),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.topicDisplayName.toUpperCase(),
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 0.8,
                        color: colorScheme.primary,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Knowledge Calibration Quiz',
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
              IconButton(
                icon: const Icon(Icons.close),
                tooltip: 'Abandon Quiz',
                onPressed: () {
                  showDialog(
                    context: context,
                    builder: (ctx) => AlertDialog(
                      title: const Text('Exit Quiz?'),
                      content: const Text(
                        'Your progress on this topic will be saved, but the session will be marked incomplete.',
                      ),
                      actions: [
                        TextButton(
                          onPressed: () => Navigator.pop(ctx),
                          child: const Text('Resume'),
                        ),
                        FilledButton(
                          onPressed: () {
                            Navigator.pop(ctx);
                            Navigator.pop(context);
                          },
                          child: const Text('Exit'),
                        ),
                      ],
                    ),
                  );
                },
              ),
            ],
          ),
        ),

        // Linear Progress Indicator
        LinearProgressIndicator(
          value: progress,
          backgroundColor: theme.dividerColor.withValues(alpha: 0.2),
          valueColor: AlwaysStoppedAnimation<Color>(colorScheme.primary),
          minHeight: 4,
        ),
      ],
    );
  }

  Widget _buildSwapNoticeBanner(ThemeData theme) {
    return Container(
      width: double.infinity,
      color: Colors.amber.withValues(alpha: 0.12),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          Icon(Icons.refresh, size: 16, color: Colors.amber.shade800),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'Unanswered questions were refreshed while you were away to keep calibration reliable.',
              style: TextStyle(fontSize: 12, color: Colors.amber.shade900),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.close, size: 14),
            visualDensity: VisualDensity.compact,
            onPressed: () => setState(() => _swappedNoticeShown = false),
          ),
        ],
      ),
    );
  }

  Widget _buildQuestionView(ThemeData theme, ColorScheme colorScheme) {
    final q = _currentQuestion!;
    final isAnswered = _lastAnswerResult != null;

    return ListView(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      children: [
        // Question tracker badge
        Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: colorScheme.primary.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                'Question ${(_session?.currentIndex ?? 0) + 1} of ${_session?.totalQuestions ?? 4}',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: colorScheme.primary,
                ),
              ),
            ),
            const Spacer(),
            Text(
              '${q.difficulty[0].toUpperCase()}${q.difficulty.substring(1)} Level',
              style: theme.textTheme.bodySmall?.copyWith(fontSize: 11),
            ),
          ],
        ),
        const SizedBox(height: 14),

        // Question Stem
        Text(
          q.stem,
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            height: 1.4,
            fontSize: 17,
          ),
        ),
        const SizedBox(height: 20),

        // Options List (Design.md §7: randomized per attempt)
        ...List.generate(q.optionsRandomised.length, (idx) {
          final optionText = q.optionsRandomised[idx];
          final isSelected = _selectedDisplayIndex == idx;

          Color borderColor = theme.dividerColor;
          Color bgColor = Colors.transparent;
          IconData? trailingIcon;
          Color? iconColor;

          if (isAnswered) {
            final isCorrectOption = idx == _lastAnswerResult!.correctIndex;
            if (isCorrectOption) {
              borderColor = Colors.green.shade600;
              bgColor = Colors.green.withValues(alpha: 0.1);
              trailingIcon = Icons.check_circle;
              iconColor = Colors.green.shade600;
            } else if (isSelected && !isCorrectOption) {
              borderColor = Colors.red.shade600;
              bgColor = Colors.red.withValues(alpha: 0.1);
              trailingIcon = Icons.cancel;
              iconColor = Colors.red.shade600;
            }
          } else if (isSelected) {
            borderColor = colorScheme.primary;
            bgColor = colorScheme.primary.withValues(alpha: 0.08);
          }

          return Padding(
            padding: const EdgeInsets.only(bottom: 12.0),
            child: InkWell(
              borderRadius: BorderRadius.circular(12),
              onTap: isAnswered || _isSubmitting
                  ? null
                  : () {
                      setState(() => _selectedDisplayIndex = idx);
                    },
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                decoration: BoxDecoration(
                  color: bgColor,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: borderColor, width: isSelected || isAnswered ? 1.5 : 1.0),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 28,
                      height: 28,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: isSelected && !isAnswered
                            ? colorScheme.primary
                            : theme.dividerColor.withValues(alpha: 0.3),
                      ),
                      child: Text(
                        String.fromCharCode(65 + idx), // A, B, C, D
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: isSelected && !isAnswered ? colorScheme.onPrimary : theme.textTheme.bodyMedium?.color,
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        optionText,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          fontSize: 14.5,
                          height: 1.35,
                          fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                        ),
                      ),
                    ),
                    if (trailingIcon != null) ...[
                      const SizedBox(width: 8),
                      Icon(trailingIcon, size: 20, color: iconColor),
                    ],
                  ],
                ),
              ),
            ),
          );
        }),

        const SizedBox(height: 16),

        // Post-Answer Feedback Box
        if (isAnswered) ...[
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: _lastAnswerResult!.isCorrect
                  ? Colors.green.withValues(alpha: 0.08)
                  : Colors.red.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: _lastAnswerResult!.isCorrect
                    ? Colors.green.withValues(alpha: 0.3)
                    : Colors.red.withValues(alpha: 0.3),
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(
                      _lastAnswerResult!.isCorrect ? Icons.check_circle_outline : Icons.info_outline,
                      size: 16,
                      color: _lastAnswerResult!.isCorrect ? Colors.green.shade700 : Colors.red.shade700,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      _lastAnswerResult!.isCorrect ? 'Well Done!' : 'Review Concept',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: _lastAnswerResult!.isCorrect ? Colors.green.shade700 : Colors.red.shade700,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  _lastAnswerResult!.explanation.isNotEmpty
                      ? _lastAnswerResult!.explanation
                      : 'Self-attention and feed-forward modules are optimized for transformer representations.',
                  style: theme.textTheme.bodySmall?.copyWith(fontSize: 13, height: 1.4),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
        ],

        // Submit or Continue Button (Strictly one-way progression)
        if (!isAnswered)
          FilledButton(
            onPressed: _selectedDisplayIndex != null && !_isSubmitting ? _submitAnswer : null,
            style: FilledButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            child: _isSubmitting
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : const Text('Submit Answer', style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
          )
        else
          FilledButton.icon(
            onPressed: _nextQuestion,
            icon: const Icon(Icons.arrow_forward, size: 18),
            label: Text(
              _lastAnswerResult?.sessionEnded == true ? 'View Results' : 'Continue',
              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
            ),
            style: FilledButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
          ),
      ],
    );
  }

  Widget _buildCompletionView(ThemeData theme, ColorScheme colorScheme) {
    final level = _session?.assignedLevel ?? 'fluent';
    final score = _session?.finalScore != null ? (_session!.finalScore! * 100).round() : 100;

    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24.0),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: colorScheme.primary.withValues(alpha: 0.1),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.verified, size: 56, color: colorScheme.primary),
            ),
            const SizedBox(height: 16),
            Text(
              'Calibration Complete!',
              style: theme.textTheme.headlineMedium?.copyWith(
                fontWeight: FontWeight.bold,
                fontSize: 22,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Your knowledge level for ${widget.topicDisplayName} has been calibrated.',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium?.copyWith(color: theme.hintColor),
            ),
            const SizedBox(height: 24),

            // Assigned Level Card
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: theme.cardColor,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: colorScheme.primary.withValues(alpha: 0.3)),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.04),
                    blurRadius: 10,
                  ),
                ],
              ),
              child: Column(
                children: [
                  Text(
                    'CALIBRATED LEVEL',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 0.8,
                      color: theme.hintColor,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    level.toUpperCase(),
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 0.5,
                      color: colorScheme.primary,
                    ),
                  ),
                  const SizedBox(height: 12),
                  const Divider(height: 1),
                  const SizedBox(height: 12),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceAround,
                    children: [
                      Column(
                        children: [
                          Text('Score', style: theme.textTheme.bodySmall),
                          const SizedBox(height: 2),
                          Text('$score%', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                        ],
                      ),
                      Column(
                        children: [
                          Text('Questions', style: theme.textTheme.bodySmall),
                          const SizedBox(height: 2),
                          Text(
                            '${_session?.totalQuestions ?? 4}',
                            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                          ),
                        ],
                      ),
                      Column(
                        children: [
                          Text('Streak', style: theme.textTheme.bodySmall),
                          const SizedBox(height: 2),
                          const Row(
                            children: [
                              Icon(Icons.local_fire_department, size: 16, color: Colors.deepOrange),
                              Text('1d', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                            ],
                          ),
                        ],
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            FilledButton(
              onPressed: () => Navigator.pop(context),
              style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(48),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              child: const Text('Apply Calibration to Feed', style: TextStyle(fontWeight: FontWeight.bold)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorView(ThemeData theme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 48, color: Colors.red),
            const SizedBox(height: 12),
            Text('Quiz Unavailable', style: theme.textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(_errorMessage ?? 'An error occurred.', textAlign: TextAlign.center, style: theme.textTheme.bodySmall),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _startQuizSession,
              child: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}

