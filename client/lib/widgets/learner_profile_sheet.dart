import 'package:flutter/material.dart';
import '../services/auth_service.dart';
import '../services/learning_service.dart';
import 'auth_screen.dart';
import 'byok_settings_sheet.dart';
import 'quiz_modal.dart';
import 'retention_quiz_sheet.dart';

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
  Map<String, dynamic>? _cycleStatus;

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
      final auth = AuthService();
      Map<String, dynamic>? cycle;
      if (auth.isAuthenticated) {
        cycle = await auth.checkCycleStatus();
      }

      if (mounted) {
        setState(() {
          _topics = topics;
          _profileMap = {for (final p in profiles) p.topicSlug: p};
          _cycleStatus = cycle;
          _isLoading = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  Widget _buildAuthAndCycleCard(ThemeData theme, ColorScheme colorScheme) {
    final auth = AuthService();
    final isAuth = auth.isAuthenticated;

    if (!isAuth) {
      return Container(
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: const Color(0xFF161B22),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: Colors.white12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.blue.withValues(alpha: 0.15),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.lock_outline_rounded, size: 20, color: Color(0xFF58A6FF)),
                ),
                const SizedBox(width: 12),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Rule 65: Open Knowledge Format (OKF)',
                        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13.5, color: Colors.white),
                      ),
                      SizedBox(height: 2),
                      Text(
                        '15-Day Periodic Comprehension Tracking',
                        style: TextStyle(fontSize: 11, color: Colors.white54),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            const Text(
              'Sign in to track every research paper you scroll and unlock the automated 15-day 10-minute comprehension challenge.',
              style: TextStyle(fontSize: 12, color: Colors.white70, height: 1.4),
            ),
            const SizedBox(height: 14),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: Colors.black,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  padding: const EdgeInsets.symmetric(vertical: 10),
                ),
                onPressed: () {
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (ctx) => AuthScreen(
                        onAuthenticated: _loadProfileData,
                      ),
                    ),
                  );
                },
                icon: const Icon(Icons.login_rounded, size: 18),
                label: const Text('Sign In / Register', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
              ),
            ),
          ],
        ),
      );
    }

    final cycle = _cycleStatus;
    final isGated = cycle?['is_gated'] == true || cycle?['is_quiz_due'] == true;
    final scrolledCount = cycle?['scrolled_cards_in_cycle'] ?? 0;
    final daysRemaining = cycle?['days_until_quiz_due'] ?? 15;

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isGated ? Colors.redAccent.withValues(alpha: 0.6) : Colors.white12,
          width: isGated ? 1.5 : 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              CircleAvatar(
                radius: 16,
                backgroundColor: isGated ? Colors.redAccent : const Color(0xFF238636),
                child: Text(
                  (auth.username?.isNotEmpty == true ? auth.username![0].toUpperCase() : 'U'),
                  style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.white, fontSize: 14),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '@${auth.username ?? "user"}',
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: Colors.white),
                    ),
                    Text(
                      isGated ? 'Comprehension Quiz Due (Feed Gated)' : 'OKF 15-Day Cycle Active',
                      style: TextStyle(
                        fontSize: 11,
                        color: isGated ? Colors.redAccent : Colors.greenAccent,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
              IconButton(
                icon: const Icon(Icons.logout_rounded, size: 20, color: Colors.white54),
                tooltip: 'Log out',
                onPressed: () async {
                  await auth.logout();
                  _loadProfileData();
                },
              ),
            ],
          ),
          const SizedBox(height: 12),
          const Divider(height: 1, color: Colors.white12),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Cards Read in Cycle', style: TextStyle(fontSize: 11, color: Colors.white54)),
                  const SizedBox(height: 2),
                  Text('$scrolledCount papers', style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Colors.white)),
                ],
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  const Text('Cycle Due Date', style: TextStyle(fontSize: 11, color: Colors.white54)),
                  const SizedBox(height: 2),
                  Text(
                    isGated ? 'DUE NOW' : '$daysRemaining days left',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                      color: isGated ? Colors.redAccent : Colors.white,
                    ),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: isGated ? const Color(0xFFE53935) : const Color(0xFF238636),
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                padding: const EdgeInsets.symmetric(vertical: 10),
              ),
              onPressed: () {
                showModalBottomSheet(
                  context: context,
                  isScrollControlled: true,
                  backgroundColor: Colors.transparent,
                  builder: (ctx) => RetentionQuizSheet(
                    onCompleted: () {
                      _loadProfileData();
                    },
                  ),
                );
              },
              icon: const Icon(Icons.timer_outlined, size: 18),
              label: Text(
                isGated ? 'Unlock Feed (10-Min Quiz)' : 'Take Retention Quiz Early',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
              ),
            ),
          ),
        ],
      ),
    );
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
                          // OKF 15-Day Cycle & Auth Card (Rule 65)
                          _buildAuthAndCycleCard(theme, colorScheme),

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
                          const SizedBox(height: 14),

                          // BYOK & Quota entry tile (Step 4)
                          InkWell(
                            borderRadius: BorderRadius.circular(14),
                            onTap: () {
                              Navigator.pop(context);
                              ByokSettingsSheet.show(context);
                            },
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                              decoration: BoxDecoration(
                                color: Colors.white.withValues(alpha: 0.05),
                                borderRadius: BorderRadius.circular(14),
                                border: Border.all(color: Colors.white12),
                              ),
                              child: Row(
                                children: [
                                  Container(
                                    padding: const EdgeInsets.all(8),
                                    decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.08), shape: BoxShape.circle),
                                    child: const Icon(Icons.vpn_key_rounded, size: 18, color: Colors.white),
                                  ),
                                  const SizedBox(width: 12),
                                  const Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text('LLM Providers & BYOK Keys', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13.5)),
                                        SizedBox(height: 2),
                                        Text('Manage custom keys & shared fallback quota', style: TextStyle(color: Colors.white54, fontSize: 11)),
                                      ],
                                    ),
                                  ),
                                  const Icon(Icons.chevron_right_rounded, color: Colors.white38),
                                ],
                              ),
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

