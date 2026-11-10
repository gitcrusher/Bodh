import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../models/technique_grounding_model.dart';
import '../services/api_service.dart';

/// Modal bottom sheet displaying literature grounding for a technique (Step 7, Rule 52, Design §9).
/// Shows direct_match, related_only, or no_literature_found with verified citations from Semantic Scholar & OpenAlex.
class TechniqueGroundingSheet extends StatefulWidget {
  final int cardId;
  final String cardHeadline;
  final String? initialTechniqueName;

  const TechniqueGroundingSheet({
    super.key,
    required this.cardId,
    required this.cardHeadline,
    this.initialTechniqueName,
  });

  static Future<void> show(
    BuildContext context, {
    required int cardId,
    required String cardHeadline,
    String? initialTechniqueName,
  }) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => TechniqueGroundingSheet(
        cardId: cardId,
        cardHeadline: cardHeadline,
        initialTechniqueName: initialTechniqueName,
      ),
    );
  }

  @override
  State<TechniqueGroundingSheet> createState() => _TechniqueGroundingSheetState();
}

class _TechniqueGroundingSheetState extends State<TechniqueGroundingSheet> {
  final ApiService _apiService = ApiService();
  bool _isLoading = true;
  CardTechniqueGroundingResult? _result;

  @override
  void initState() {
    super.initState();
    _loadGrounding();
  }

  Future<void> _loadGrounding() async {
    setState(() => _isLoading = true);
    final res = await _apiService.fetchTechniqueGrounding(widget.cardId);
    if (mounted) {
      setState(() {
        _result = res;
        _isLoading = false;
      });
    }
  }

  Future<void> _launchUrl(String url) async {
    if (url.isEmpty) return;
    final uri = Uri.tryParse(url);
    if (uri != null && await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return DraggableScrollableSheet(
      initialChildSize: 0.75,
      minChildSize: 0.45,
      maxChildSize: 0.94,
      builder: (ctx, scrollController) {
        return Container(
          decoration: BoxDecoration(
            color: const Color(0xFF0D1117),
            borderRadius: const BorderRadius.vertical(top: Radius.circular(22)),
            border: Border.all(color: Colors.white12, width: 1),
          ),
          child: Column(
            children: [
              // Pull handle
              Center(
                child: Container(
                  margin: const EdgeInsets.only(top: 10, bottom: 8),
                  width: 36,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Colors.white24,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),

              // Header
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: Colors.tealAccent.withValues(alpha: 0.15),
                        shape: BoxShape.circle,
                      ),
                      child: const Icon(Icons.psychology_rounded, color: Colors.tealAccent, size: 22),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Technique Literature Grounding',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                            ),
                          ),
                          Text(
                            'Semantic Scholar & OpenAlex Index Verification',
                            style: TextStyle(
                              fontSize: 11.5,
                              color: Colors.white.withValues(alpha: 0.6),
                            ),
                          ),
                        ],
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.close_rounded, color: Colors.white70),
                      onPressed: () => Navigator.pop(context),
                    ),
                  ],
                ),
              ),

              const Divider(height: 1, color: Colors.white12),

              // Content Body
              Expanded(
                child: _isLoading
                    ? const Center(child: CircularProgressIndicator.adaptive())
                    : _buildBody(theme, scrollController),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildBody(ThemeData theme, ScrollController scrollController) {
    final result = _result;
    final technique = result?.technique;

    if (result == null || !result.hasTechnique || technique == null) {
      return ListView(
        controller: scrollController,
        padding: const EdgeInsets.all(24),
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: const Color(0xFF161B22),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.white10),
            ),
            child: Column(
              children: [
                const Icon(Icons.info_outline_rounded, size: 36, color: Colors.white54),
                const SizedBox(height: 12),
                const Text(
                  'No Named Trending Technique Detected',
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: Colors.white),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  'This paper discusses general methodology rather than a standalone named technical concept currently trending in community discussions.',
                  style: TextStyle(fontSize: 12.5, color: Colors.white.withValues(alpha: 0.65), height: 1.4),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ],
      );
    }

    return ListView(
      controller: scrollController,
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      children: [
        // Technique Name & Aliases Banner
        Container(
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
                  Expanded(
                    child: Text(
                      technique.name,
                      style: const TextStyle(
                        fontSize: 19,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                    ),
                  ),
                  _buildStatusPill(technique.groundingStatus),
                ],
              ),
              if (technique.aliases.isNotEmpty) ...[
                const SizedBox(height: 6),
                Wrap(
                  spacing: 6,
                  runSpacing: 4,
                  children: technique.aliases.map((alias) {
                    return Container(
                      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.08),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        'aka: $alias',
                        style: const TextStyle(fontSize: 10.5, color: Colors.white70),
                      ),
                    );
                  }).toList(),
                ),
              ],
              const SizedBox(height: 12),

              // Mention growth metric
              if (technique.mentionTrend.isNotEmpty) ...[
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.blue.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.blue.withValues(alpha: 0.3)),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.trending_up_rounded, color: Colors.lightBlueAccent, size: 16),
                      const SizedBox(width: 6),
                      Text(
                        '+${technique.mentionTrend['weekly_growth_pct'] ?? 100}% this week • ${technique.mentionTrend['mention_count'] ?? 0} mentions',
                        style: const TextStyle(
                          fontSize: 11.5,
                          fontWeight: FontWeight.w600,
                          color: Colors.lightBlueAccent,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
              ],

              // Rule 52 Truthful Verdict Explanation
              Text(
                technique.verdictExplanation,
                style: TextStyle(
                  fontSize: 12.5,
                  height: 1.45,
                  color: Colors.white.withValues(alpha: 0.85),
                ),
              ),
            ],
          ),
        ),

        // Technique-Cluster Fallback Notice (if card wasn't directly mentioned)
        if (result.fallbackMessage.isNotEmpty) ...[
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.purple.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.purpleAccent.withValues(alpha: 0.3)),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.hub_rounded, color: Colors.purpleAccent, size: 18),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    result.fallbackMessage,
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.purple.shade100,
                      height: 1.35,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],

        const SizedBox(height: 20),

        // Literature Evidence Section
        Row(
          children: [
            const Icon(Icons.menu_book_rounded, color: Colors.tealAccent, size: 18),
            const SizedBox(width: 8),
            Text(
              'INDEXED RESEARCH EVIDENCE (${technique.literatureLinks.length})',
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.bold,
                letterSpacing: 0.5,
                color: Colors.white70,
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),

        if (technique.literatureLinks.isEmpty)
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFF161B22),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Text(
              'No peer-reviewed papers cataloged in Semantic Scholar or OpenAlex for this specific naming. Community practitioners rely on empiric usage.',
              style: TextStyle(fontSize: 12, color: Colors.white54, height: 1.4),
            ),
          )
        else
          ...technique.literatureLinks.map((link) => _buildLiteratureCard(link)),

        const SizedBox(height: 24),
      ],
    );
  }

  Widget _buildStatusPill(String status) {
    Color bg;
    Color border;
    Color text;
    String label;

    switch (status) {
      case 'direct_match':
        bg = Colors.green.withValues(alpha: 0.15);
        border = Colors.greenAccent.withValues(alpha: 0.4);
        text = Colors.greenAccent;
        label = 'DIRECT MATCH';
        break;
      case 'related_only':
        bg = Colors.orange.withValues(alpha: 0.15);
        border = Colors.orangeAccent.withValues(alpha: 0.4);
        text = Colors.orangeAccent;
        label = 'RELATED ONLY';
        break;
      default:
        bg = Colors.blueGrey.withValues(alpha: 0.15);
        border = Colors.blueGrey.withValues(alpha: 0.4);
        text = Colors.white70;
        label = 'NO LITERATURE';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: border, width: 0.8),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.bold,
          letterSpacing: 0.4,
          color: text,
        ),
      ),
    );
  }

  Widget _buildLiteratureCard(TechniqueLiteratureLink link) {
    final isDirect = link.matchType == 'direct';

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: isDirect
              ? Colors.tealAccent.withValues(alpha: 0.3)
              : Colors.white12,
          width: 0.9,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: isDirect
                      ? Colors.teal.withValues(alpha: 0.2)
                      : Colors.orange.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  isDirect ? 'DIRECT CITATION' : 'FOUNDATIONAL CONTEXT',
                  style: TextStyle(
                    fontSize: 9.5,
                    fontWeight: FontWeight.bold,
                    color: isDirect ? Colors.tealAccent : Colors.orangeAccent,
                  ),
                ),
              ),
              const Spacer(),
              Text(
                '${link.source.replaceAll('_', ' ').toUpperCase()}${link.year != null ? ' (${link.year})' : ''}',
                style: const TextStyle(fontSize: 10.5, color: Colors.white54),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            link.title,
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w700,
              color: Colors.white,
              height: 1.3,
            ),
          ),
          if (link.snippet.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              link.snippet,
              style: TextStyle(
                fontSize: 12,
                color: Colors.white.withValues(alpha: 0.7),
                height: 1.4,
              ),
            ),
          ],
          if (link.url.isNotEmpty) ...[
            const SizedBox(height: 10),
            InkWell(
              onTap: () => _launchUrl(link.url),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: const [
                  Text(
                    'Read Paper on arXiv / Index',
                    style: TextStyle(
                      fontSize: 11.5,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF58A6FF),
                    ),
                  ),
                  SizedBox(width: 4),
                  Icon(Icons.open_in_new_rounded, size: 13, color: Color(0xFF58A6FF)),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}
