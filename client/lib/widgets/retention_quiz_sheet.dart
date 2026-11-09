import 'dart:async';
import 'package:flutter/material.dart';
import '../services/auth_service.dart';

/// 10-Minute Maximum Periodic Comprehension Challenge (Rule 65 - OKF).
/// Tests retention of research papers scrolled over the past 15 days.
class RetentionQuizSheet extends StatefulWidget {
  final VoidCallback onCompleted;

  const RetentionQuizSheet({super.key, required this.onCompleted});

  @override
  State<RetentionQuizSheet> createState() => _RetentionQuizSheetState();
}

class _RetentionQuizSheetState extends State<RetentionQuizSheet> {
  bool _isLoading = true;
  String? _errorMessage;

  int? _sessionId;
  int _timeRemainingSeconds = 600; // Rule 65: 10 minutes max (600s)
  Timer? _timer;

  int _currentIndex = 0;
  int _totalQuestions = 0;
  Map<String, dynamic>? _currentQuestion;

  int? _selectedDisplayIndex;
  bool _isAnswerSubmitted = false;
  bool _isAnswerCorrect = false;
  String _explanation = '';
  int _correctCount = 0;

  bool _isQuizFinished = false;

  @override
  void initState() {
    super.initState();
    _startQuizSession();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _startTimer() {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!mounted) return;
      if (_timeRemainingSeconds > 0) {
        setState(() => _timeRemainingSeconds--);
      } else {
        _timer?.cancel();
        _onTimeExpired();
      }
    });
  }

  void _onTimeExpired() {
    setState(() {
      _isQuizFinished = true;
    });
  }

  Future<void> _startQuizSession() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    final auth = AuthService();
    final res = await auth.startRetentionQuiz(force: true);

    if (!mounted) return;

    if (res != null) {
      setState(() {
        _sessionId = res['session_id'] as int?;
        _totalQuestions = res['total_questions'] as int? ?? 5;
        _currentQuestion = res['current_question'] as Map<String, dynamic>?;
        _timeRemainingSeconds = res['time_limit_seconds'] as int? ?? 600;
        _isLoading = false;
      });
      _startTimer();
    } else {
      setState(() {
        _isLoading = false;
        _errorMessage = 'Could not generate retention quiz. Please check network connection.';
      });
    }
  }

  Future<void> _submitAnswer() async {
    if (_selectedDisplayIndex == null || _sessionId == null || _currentQuestion == null) return;

    final qId = _currentQuestion!['id'] as int;
    final optionOrder = (_currentQuestion!['option_order'] as List<dynamic>?)
            ?.map((e) => (e as num).toInt())
            .toList() ??
        [0, 1, 2, 3];

    final auth = AuthService();
    final res = await auth.submitQuizAnswer(
      sessionId: _sessionId!,
      questionId: qId,
      chosenDisplayIndex: _selectedDisplayIndex!,
      optionOrder: optionOrder,
    );

    if (!mounted) return;

    if (res != null) {
      final isCorrect = res['is_correct'] as bool? ?? false;
      final explanation = res['explanation'] as String? ?? '';
      final sessionEnded = res['session_ended'] as bool? ?? false;

      setState(() {
        _isAnswerSubmitted = true;
        _isAnswerCorrect = isCorrect;
        _explanation = explanation;
        if (isCorrect) _correctCount++;

        if (sessionEnded || res['next_question'] == null) {
          _isQuizFinished = true;
          _timer?.cancel();
        } else {
          // Prepare next question transition
          _nextQuestionPayload = res['next_question'] as Map<String, dynamic>?;
        }
      });
    }
  }

  Map<String, dynamic>? _nextQuestionPayload;

  void _proceedToNextQuestion() {
    if (_nextQuestionPayload != null) {
      setState(() {
        _currentIndex++;
        _currentQuestion = _nextQuestionPayload;
        _nextQuestionPayload = null;
        _selectedDisplayIndex = null;
        _isAnswerSubmitted = false;
        _explanation = '';
      });
    } else {
      setState(() {
        _isQuizFinished = true;
        _timer?.cancel();
      });
    }
  }

  String _formatTimer(int totalSeconds) {
    final mins = (totalSeconds ~/ 60).toString().padLeft(2, '0');
    final secs = (totalSeconds % 60).toString().padLeft(2, '0');
    return '$mins:$secs';
  }

  @override
  Widget build(BuildContext context) {
    return Dialog.fullscreen(
      backgroundColor: const Color(0xFF0F141A),
      child: SafeArea(
        child: _isLoading
            ? const Center(child: CircularProgressIndicator(color: Colors.white))
            : _errorMessage != null
                ? _buildErrorView()
                : _isQuizFinished
                    ? _buildCompletionView()
                    : _buildQuizActiveView(),
      ),
    );
  }

  Widget _buildErrorView() {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, size: 48, color: Colors.orange),
          const SizedBox(height: 16),
          Text(
            _errorMessage!,
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.white70, fontSize: 14),
          ),
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: _startQuizSession,
            style: ElevatedButton.styleFrom(backgroundColor: Colors.white, foregroundColor: Colors.black),
            child: const Text('Try Again'),
          ),
        ],
      ),
    );
  }

  Widget _buildQuizActiveView() {
    final question = _currentQuestion;
    if (question == null) return const SizedBox.shrink();

    final stem = question['stem'] as String? ?? '';
    final options = (question['options_randomised'] as List<dynamic>?)
            ?.map((e) => e.toString())
            .toList() ??
        (question['options'] as List<dynamic>?)?.map((e) => e.toString()).toList() ??
        [];

    final isUrgent = _timeRemainingSeconds < 120; // under 2 minutes

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Header Row: Bodh + 10-Min Timer + Progress
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(3),
                ),
                child: const Text(
                  'bodh',
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.w900, color: Colors.black),
                ),
              ),
              const SizedBox(width: 8),
              const Text(
                '15-Day Comprehension Challenge',
                style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Colors.white70),
              ),
              const Spacer(),
              // Countdown Timer
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: isUrgent ? Colors.red.withValues(alpha: 0.2) : Colors.white.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(
                    color: isUrgent ? Colors.redAccent : Colors.white24,
                    width: 0.8,
                  ),
                ),
                child: Row(
                  children: [
                    Icon(
                      Icons.timer_outlined,
                      size: 13,
                      color: isUrgent ? Colors.redAccent : const Color(0xFFFF9E7A),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      _formatTimer(_timeRemainingSeconds),
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                        color: isUrgent ? Colors.redAccent : const Color(0xFFFF9E7A),
                        fontFamily: 'monospace',
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),

          const SizedBox(height: 14),

          // Linear Progress Indicator
          LinearProgressIndicator(
            value: _totalQuestions > 0 ? (_currentIndex + 1) / _totalQuestions : 0.0,
            backgroundColor: Colors.white12,
            valueColor: const AlwaysStoppedAnimation<Color>(Color(0xFF58A6FF)),
            minHeight: 4,
          ),

          const SizedBox(height: 18),

          // Question Difficulty and Counter
          Row(
            children: [
              Text(
                'QUESTION ${_currentIndex + 1} OF $_totalQuestions',
                style: const TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 1.0,
                  color: Color(0xFF8B949E),
                ),
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: const Color(0xFF2E1A14),
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: const Color(0xFFFF6B4A).withValues(alpha: 0.4)),
                ),
                child: const Text(
                  'MEDIUM / HARD',
                  style: TextStyle(
                    fontSize: 9.5,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFFFF8C69),
                    letterSpacing: 0.5,
                  ),
                ),
              ),
            ],
          ),

          const SizedBox(height: 12),

          // Stem
          Text(
            stem,
            style: const TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w600,
              height: 1.45,
              color: Colors.white,
            ),
          ),

          const SizedBox(height: 20),

          // Options List
          Expanded(
            child: ListView.separated(
              itemCount: options.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (ctx, index) {
                final optionText = options[index];
                final isSelected = _selectedDisplayIndex == index;

                Color borderColor = Colors.white12;
                Color bgColor = const Color(0xFF161B22);

                if (_isAnswerSubmitted) {
                  if (isSelected) {
                    borderColor = _isAnswerCorrect ? Colors.green : Colors.red;
                    bgColor = _isAnswerCorrect
                        ? Colors.green.withValues(alpha: 0.15)
                        : Colors.red.withValues(alpha: 0.15);
                  }
                } else if (isSelected) {
                  borderColor = const Color(0xFF58A6FF);
                  bgColor = const Color(0xFF58A6FF).withValues(alpha: 0.12);
                }

                return GestureDetector(
                  onTap: _isAnswerSubmitted
                      ? null
                      : () => setState(() => _selectedDisplayIndex = index),
                  child: Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: bgColor,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: borderColor, width: 1.2),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${String.fromCharCode(65 + index)}.',
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                            color: isSelected ? const Color(0xFF58A6FF) : Colors.white54,
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            optionText,
                            style: const TextStyle(
                              fontSize: 13,
                              height: 1.4,
                              color: Color(0xFFE6EDF3),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),

          // Explanation feedback banner
          if (_isAnswerSubmitted && _explanation.isNotEmpty) ...[
            Container(
              margin: const EdgeInsets.only(bottom: 12),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: _isAnswerCorrect
                    ? Colors.green.withValues(alpha: 0.1)
                    : Colors.red.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: _isAnswerCorrect
                      ? Colors.green.withValues(alpha: 0.3)
                      : Colors.red.withValues(alpha: 0.3),
                ),
              ),
              child: Text(
                _explanation,
                style: const TextStyle(fontSize: 12, height: 1.35, color: Colors.white70),
              ),
            ),
          ],

          // Action Button
          ElevatedButton(
            onPressed: _selectedDisplayIndex == null
                ? null
                : _isAnswerSubmitted
                    ? _proceedToNextQuestion
                    : _submitAnswer,
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.white,
              foregroundColor: Colors.black,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            child: Text(
              _isAnswerSubmitted ? 'Continue' : 'Submit Answer',
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCompletionView() {
    final scorePct = _totalQuestions > 0 ? (_correctCount / _totalQuestions * 100).round() : 100;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: Colors.green.withValues(alpha: 0.15),
              border: Border.all(color: Colors.greenAccent.withValues(alpha: 0.5), width: 2),
            ),
            child: const Icon(Icons.check_circle_outline, size: 56, color: Colors.greenAccent),
          ),
          const SizedBox(height: 24),
          const Text(
            'Comprehension Verified',
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: Colors.white),
          ),
          const SizedBox(height: 10),
          Text(
            'Score: $_correctCount / $_totalQuestions ($scorePct%)',
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Color(0xFF58A6FF)),
          ),
          const SizedBox(height: 12),
          Text(
            'Your feed is unlocked for the next 15 days of research discovery.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 13, color: Colors.white.withValues(alpha: 0.7), height: 1.4),
          ),
          const SizedBox(height: 32),
          ElevatedButton(
            onPressed: () {
              widget.onCompleted();
              Navigator.of(context).maybePop();
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.white,
              foregroundColor: Colors.black,
              padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 14),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            child: const Text('Unlock Feed & Continue', style: TextStyle(fontWeight: FontWeight.w700)),
          ),
        ],
      ),
    );
  }
}
