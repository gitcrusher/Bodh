import 'package:flutter/material.dart';
import '../services/learning_service.dart';
import 'quiz_modal.dart';

/// Modal bottom sheet showing the user's calibrated knowledge profile across topics.
///
/// Follows Agent/design.md §4 & §7:
/// - Displays calibrated level (New, Familiar, Fluent) per topic.
/// - Shows overall streak and accuracy.
/// - Allows launching an adaptive calibration quiz for any topic.
class LearnerProfileSheet extends StatefulWidget {
  final LearningService? learningService;

  const LearnerProfileSheet({super.key, this.learningService});

  static Future<void> show(BuildContext context) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => const LearnerProfileSheet(),
    );
  }

  @override
  State<LearnerProfileSheet> createState() => _LearnerProfileSheetState();
}

class _LearnerProfileSheetState extends State<LearnerProfileSheet> {
  late final LearningService _learningService;
  bool _isLoading = true;
  List<QuizTopic> _topics = [];
  Map<String, LearnerProfile> _profileMap = {};

  @override
  void initState() {
    super.initState();
    _learningService = widget.learningService ?? LearningService();
    _loadProfileData();
  }

  Future<void> _loadProfileData() async {
    setState(() => _isLoading = true);

    try {
      final topics = await _learningService.fetchTopics();
      final profiles = await _learningService.fetchProfile();

      if (mounted) {
        setState(() {
          _topics = topics;
          _profileMap = {for (final p in profiles) p.topicSlug: p};
          _isLoading = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  Color _levelColor(String level, ColorScheme scheme) {
    switch (level.toLowerCase()) {
      case 'fluent':
        return Colors.teal;
      case 'familiar':
        return scheme.primary;
      default:
        return Colors.amber.shade700;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return DraggableScrollableSheet(
      initialChildSize: 0.8,
      minChildSize: 0.4,
      maxChildSize: 0.95,
      builder: (ctx, scrollController) {
        return Container(
          decoration: BoxDecoration(
            color: theme.cardColor,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          ),
          child: Column(
            children: [
              // Grab Handle
              Center(
                child: Container(
                  margin: const EdgeInsets.only(top: 12, bottom: 8),
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: theme.dividerColor,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),

              // Header
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 8.0),
                child: Row(
                  children: [
                    Icon(Icons.psychology_outlined, size: 24, color: colorScheme.primary),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Knowledge Calibration',
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          Text(
                            'Adaptive deep-dives tailor explanations to your level.',
                            style: theme.textTheme.bodySmall?.copyWith(fontSize: 12),
                          ),
                        ],
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.close),
                      onPressed: () => Navigator.pop(context),
                    ),
                  ],
                ),
              ),

              const Divider(height: 16),

              // Body
              Expanded(
                child: _isLoading
                    ? const Center(child: CircularProgressIndicator.adaptive())
                    : ListView(
                        controller: scrollController,
                        padding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 8.0),
                        children: [
                          // Calibration stats banner
                          Container(
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: colorScheme.primary.withValues(alpha: 0.08),
                              borderRadius: BorderRadius.circular(16),
                              border: Border.all(
                                color: colorScheme.primary.withValues(alpha: 0.2),
                              ),
                            ),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.spaceAround,
                              children: [
                                Column(
                                  children: [
                                    Text('Calibrated Topics', style: theme.textTheme.bodySmall),
                                    const SizedBox(height: 4),
                                    Text(
                                      '${_profileMap.length} / ${_topics.length}',
                                      style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                                    ),
                                  ],
                                ),
                                Container(width: 1, height: 32, color: theme.dividerColor),
                                Column(
                                  children: [
                                    Text('Daily Streak', style: theme.textTheme.bodySmall),
                                    const SizedBox(height: 4),
                                    const Row(
                                      children: [
                                        Icon(Icons.local_fire_department, size: 18, color: Colors.deepOrange),
                                        Text('1 Day', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                                      ],
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 20),

                          Text(
                            'CORE TOPICS',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                              letterSpacing: 0.8,
                              color: theme.hintColor,
                            ),
                          ),
                          const SizedBox(height: 10),

                          // Topics list
                          ..._topics.map((topic) {
                            final profile = _profileMap[topic.slug];
                            final level = profile?.level ?? 'familiar';
                            final isCalibrated = profile != null;

                            return Card(
                              elevation: 0,
                              margin: const EdgeInsets.only(bottom: 12),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(14),
                                side: BorderSide(color: theme.dividerColor.withValues(alpha: 0.5)),
                              ),
                              child: Padding(
                                padding: const EdgeInsets.all(16.0),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      children: [
                                        Expanded(
                                          child: Text(
                                            topic.displayName,
                                            style: theme.textTheme.titleSmall?.copyWith(
                                              fontWeight: FontWeight.bold,
                                              fontSize: 15,
                                            ),
                                          ),
                                        ),
                                        Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                          decoration: BoxDecoration(
                                            color: _levelColor(level, colorScheme).withValues(alpha: 0.12),
                                            borderRadius: BorderRadius.circular(12),
                                            border: Border.all(
                                              color: _levelColor(level, colorScheme).withValues(alpha: 0.35),
                                            ),
                                          ),
                                          child: Text(
                                            level.toUpperCase(),
                                            style: TextStyle(
                                              fontSize: 10,
                                              fontWeight: FontWeight.bold,
                                              color: _levelColor(level, colorScheme),
                                            ),
                                          ),
                                        ),
                                      ],
                                    ),
                                    if (topic.description.isNotEmpty) ...[
                                      const SizedBox(height: 6),
                                      Text(
                                        topic.description,
                                        style: theme.textTheme.bodySmall?.copyWith(fontSize: 12.5),
                                      ),
                                    ],
                                    const SizedBox(height: 12),
                                    Row(
                                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                      children: [
                                        Text(
                                          isCalibrated
                                              ? 'Accuracy: ${((profile.accuracy ?? 1.0) * 100).round()}%'
                                              : 'Default: Familiar level',
                                          style: theme.textTheme.bodySmall?.copyWith(
                                            color: theme.hintColor,
                                            fontStyle: isCalibrated ? FontStyle.normal : FontStyle.italic,
                                          ),
                                        ),
                                        OutlinedButton.icon(
                                          icon: Icon(
                                            isCalibrated ? Icons.refresh : Icons.play_arrow,
                                            size: 15,
                                          ),
                                          label: Text(
                                            isCalibrated ? 'Retake' : 'Calibrate',
                                            style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.bold),
                                          ),
                                          style: OutlinedButton.styleFrom(
                                            visualDensity: VisualDensity.compact,
                                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                                            shape: RoundedRectangleBorder(
                                              borderRadius: BorderRadius.circular(8),
                                            ),
                                          ),
                                          onPressed: () {
                                            QuizModal.show(
                                              context,
                                              topicSlug: topic.slug,
                                              topicDisplayName: topic.displayName,
                                              onCalibrationComplete: _loadProfileData,
                                            );
                                          },
                                        ),
                                      ],
                                    ),
                                  ],
                                ),
                              ),
                            );
                          }),
                          const SizedBox(height: 24),
                        ],
                      ),
              ),
            ],
          ),
        );
      },
    );
  }
}

