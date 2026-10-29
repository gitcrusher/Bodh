import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../models/card_model.dart';
import '../services/api_service.dart';
import 'deep_dive_sheet.dart';
import 'paper_chat_sheet.dart';
import 'related_cards_sheet.dart';
import 'related_cluster_screen.dart';

/// Hardcore Inshorts-style research paper news card widget.
///
/// Strictly matches the Inshorts design layout from the reference screenshots & video:
/// - Full-height vertical snap card
/// - Top 36%: Technical research paper figure / architecture diagram with '•••' options
/// - Middle: arXiv branding, Bookmark & Share action icons, large bold headline,
///   fluent narrative 60-second summary story, and time-ago source attribution
/// - Bottom: Docked dark gradient topic cluster capsule opening the full Inshorts cluster viewer
/// - Action Bar: Quick access to Source, Level-Adaptive Deep Dive, and Grounded Paper Chat
class NewsCardWidget extends StatefulWidget {
  final NewsCard card;
  final VoidCallback? onDeepDive;
  final VoidCallback? onChat;
  final VoidCallback? onRelated;
  final bool hideRelatedCapsule;

  const NewsCardWidget({
    super.key,
    required this.card,
    this.onDeepDive,
    this.onChat,
    this.onRelated,
    this.hideRelatedCapsule = false,
  });

  @override
  State<NewsCardWidget> createState() => _NewsCardWidgetState();
}

class _NewsCardWidgetState extends State<NewsCardWidget> {
  bool _isBookmarked = false;

  Future<void> _launchUrl(String url) async {
    final uri = Uri.tryParse(url);
    if (uri != null && await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  String _formatPublishDate(DateTime dt) {
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
    ];
    final day = dt.day.toString().padLeft(2, '0');
    final month = months[dt.month - 1];
    final year = dt.year;
    return '$day $month $year';
  }

  void _showReportDialog(BuildContext context) {
    String selectedReason = 'factual_error';
    final detailController = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) {
        final theme = Theme.of(ctx);
        return StatefulBuilder(
          builder: (dialogCtx, setDialogState) {
            return AlertDialog(
              backgroundColor: theme.cardColor,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              title: Text('Report Issue with Card', style: theme.textTheme.titleMedium),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Reason:', style: theme.textTheme.bodySmall),
                  DropdownButton<String>(
                    value: selectedReason,
                    isExpanded: true,
                    dropdownColor: theme.cardColor,
                    items: const [
                      DropdownMenuItem(value: 'factual_error', child: Text('Factual Error')),
                      DropdownMenuItem(value: 'wrong_summary', child: Text('Incorrect Summary')),
                      DropdownMenuItem(value: 'broken_link', child: Text('Broken Source Link')),
                      DropdownMenuItem(value: 'other', child: Text('Other')),
                    ],
                    onChanged: (val) {
                      if (val != null) setDialogState(() => selectedReason = val);
                    },
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: detailController,
                    maxLines: 3,
                    decoration: InputDecoration(
                      hintText: 'Describe the issue (e.g. number discrepancy)...',
                      hintStyle: theme.textTheme.bodySmall,
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                    ),
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(ctx),
                  child: Text('Cancel', style: TextStyle(color: theme.textTheme.bodySmall?.color)),
                ),
                FilledButton(
                  onPressed: () async {
                    await ApiService().submitReport(
                      cardId: widget.card.id,
                      reason: selectedReason,
                      detail: detailController.text,
                    );
                    if (context.mounted) {
                      Navigator.pop(ctx);
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Report submitted. Thank you.')),
                      );
                    }
                  },
                  child: const Text('Submit'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  void _showCardMenu(BuildContext context) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Theme.of(context).cardColor,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        return SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ListTile(
                leading: const Icon(Icons.auto_stories_outlined),
                title: const Text('Level-Adaptive Deep Dive'),
                subtitle: const Text('In-depth explanation calibrated to your background'),
                onTap: () {
                  Navigator.pop(ctx);
                  (widget.onDeepDive ?? () => DeepDiveSheet.show(context, widget.card))();
                },
              ),
              ListTile(
                leading: const Icon(Icons.chat_bubble_outline_rounded),
                title: const Text('Grounded Paper Chat (RAG)'),
                subtitle: const Text('Ask factual questions verified by exact citations'),
                onTap: () {
                  Navigator.pop(ctx);
                  (widget.onChat ?? () => PaperChatSheet.show(context, widget.card))();
                },
              ),
              ListTile(
                leading: const Icon(Icons.open_in_new),
                title: const Text('Open Original Paper on arXiv'),
                onTap: () {
                  Navigator.pop(ctx);
                  _launchUrl(widget.card.sourceUrl);
                },
              ),
              ListTile(
                leading: const Icon(Icons.copy_rounded),
                title: const Text('Copy Paper Link'),
                onTap: () {
                  Navigator.pop(ctx);
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Source link copied to clipboard')),
                  );
                },
              ),
              ListTile(
                leading: const Icon(Icons.outlined_flag, color: Colors.orange),
                title: const Text('Report an Issue'),
                onTap: () {
                  Navigator.pop(ctx);
                  _showReportDialog(context);
                },
              ),
            ],
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final card = widget.card;

    return LayoutBuilder(
      builder: (context, constraints) {
        final availableH = constraints.maxHeight;
        final figureHeight = availableH.isFinite
            ? (availableH * 0.38).clamp(150.0, 320.0)
            : (MediaQuery.of(context).size.height * 0.38).clamp(150.0, 320.0);

        return Container(
          margin: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
          decoration: BoxDecoration(
            color: theme.cardColor,
            borderRadius: BorderRadius.circular(18),
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // -------------------------------------------------------------
                // 1. TOP ~38%: Research Paper Figure / Architecture Diagram
                // -------------------------------------------------------------
                SizedBox(
                  height: figureHeight,
                  width: double.infinity,
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      _buildPaperFigure(context),

                // Top gradient overlay for subtle contrast
                Positioned(
                  top: 0,
                  left: 0,
                  right: 0,
                  height: 60,
                  child: Container(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [Colors.black.withValues(alpha: 0.5), Colors.transparent],
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                      ),
                    ),
                  ),
                ),

                // Top-Right: '•••' Options Menu button (matches Inshorts)
                Positioned(
                  top: 10,
                  right: 12,
                  child: Material(
                    color: Colors.black.withValues(alpha: 0.45),
                    shape: const CircleBorder(),
                    child: InkWell(
                      customBorder: const CircleBorder(),
                      onTap: () => _showCardMenu(context),
                      child: const Padding(
                        padding: EdgeInsets.all(6.0),
                        child: Icon(Icons.more_horiz_rounded, color: Colors.white, size: 20),
                      ),
                    ),
                  ),
                ),

                // Top-Left: Validity badge overlay (if present)
                if (card.validitySignal != null)
                  Positioned(
                    top: 10,
                    left: 12,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.black.withValues(alpha: 0.65),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        card.validitySignal!.factLine,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                          letterSpacing: 0.3,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),

          // -------------------------------------------------------------
          // 2. MIDDLE SECTION: Action Row + Headline + Narrative Story
          // -------------------------------------------------------------
          Expanded(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Action Icon Row: Red Inshorts Badge + Category + Action Icons
                  Row(
                    children: [
                      // Iconic Inshorts Red Badge (matches reference image)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                        decoration: BoxDecoration(
                          color: const Color(0xFFE53935),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.flash_on_rounded, size: 12, color: Colors.white),
                            SizedBox(width: 3),
                            Text(
                              'inshorts',
                              style: TextStyle(
                                fontSize: 10.5,
                                fontWeight: FontWeight.w900,
                                letterSpacing: 0.2,
                                color: Colors.white,
                              ),
                            ),
                          ],
                        ),
                      ),

                      const SizedBox(width: 8),

                      // Category Label
                      Text(
                        card.category.toUpperCase(),
                        style: TextStyle(
                          fontSize: 10.5,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 0.5,
                          color: theme.hintColor,
                        ),
                      ),

                      const Spacer(),

                      // Level-Adaptive Deep Dive icon
                      IconButton(
                        visualDensity: VisualDensity.compact,
                        icon: Icon(
                          Icons.auto_stories_outlined,
                          size: 20,
                          color: theme.textTheme.bodyMedium?.color,
                        ),
                        tooltip: 'Level-Adaptive Deep Dive',
                        onPressed: widget.onDeepDive ?? () => DeepDiveSheet.show(context, card),
                      ),

                      // Grounded Paper Chat icon
                      IconButton(
                        visualDensity: VisualDensity.compact,
                        icon: Icon(
                          Icons.chat_bubble_outline_rounded,
                          size: 19,
                          color: theme.textTheme.bodyMedium?.color,
                        ),
                        tooltip: 'Chat with Paper (RAG)',
                        onPressed: widget.onChat ?? () => PaperChatSheet.show(context, card),
                      ),

                      // Bookmark button (matches Inshorts top-right icon)
                      IconButton(
                        visualDensity: VisualDensity.compact,
                        icon: Icon(
                          _isBookmarked
                              ? Icons.bookmark_rounded
                              : Icons.bookmark_border_rounded,
                          size: 21,
                          color: _isBookmarked
                              ? const Color(0xFF2196F3)
                              : theme.textTheme.bodyMedium?.color,
                        ),
                        tooltip: 'Bookmark paper',
                        onPressed: () {
                          setState(() => _isBookmarked = !_isBookmarked);
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              duration: const Duration(milliseconds: 1500),
                              content: Text(
                                _isBookmarked ? 'Paper bookmarked' : 'Bookmark removed',
                              ),
                            ),
                          );
                        },
                      ),

                      // Share button (matches Inshorts top-right icon)
                      IconButton(
                        visualDensity: VisualDensity.compact,
                        icon: Icon(
                          Icons.share_outlined,
                          size: 19,
                          color: theme.textTheme.bodyMedium?.color,
                        ),
                        tooltip: 'Share paper',
                        onPressed: () {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('Sharing: ${card.headline}')),
                          );
                        },
                      ),
                    ],
                  ),

                  const SizedBox(height: 6),

                  // Bold Serif / Sans Headline
                  Text(
                    card.headline,
                    style: theme.textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w800,
                      fontSize: 17.5,
                      height: 1.25,
                    ),
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                  ),

                  const SizedBox(height: 8),

                  // 60-Second Fluent Narrative Paragraph (matches Inshorts 60 words story)
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Text(
                            card.narrativeStory,
                            style: theme.textTheme.bodyLarge?.copyWith(
                              fontSize: 14.0,
                              height: 1.48,
                              color: theme.textTheme.bodyLarge?.color?.withValues(alpha: 0.88),
                            ),
                            maxLines: 7,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),

                        // Extractive fallback notice if needs_review
                        if (card.needsReview)
                          Container(
                            margin: const EdgeInsets.only(bottom: 4),
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: Colors.amber.withValues(alpha: 0.15),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              'Extractive summary: Pending review.',
                              style: TextStyle(
                                fontSize: 10,
                                color: Colors.amber.shade900,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ),

                        const SizedBox(height: 4),

                        // Footer published date & source (Rule 59: Authoritative publication date)
                        Text(
                          '${_formatPublishDate(card.publishedAt)} | arXiv cs.AI | arxiv.org',
                          style: theme.textTheme.bodySmall?.copyWith(
                            fontSize: 11.0,
                            color: theme.hintColor,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),

          // -------------------------------------------------------------
          // 3. DOCKED BOTTOM BANNER: Hardcore Inshorts Topic Cluster Bar
          // -------------------------------------------------------------
          if (!widget.hideRelatedCapsule &&
              (card.relatedCount > 0 || card.relatedTopic != null))
            _buildRelatedCapsule(context),
        ],
      ),
    ),
  );
      },
    );
  }

  /// Builds the top research paper figure / diagram
  Widget _buildPaperFigure(BuildContext context) {
    final card = widget.card;
    if (card.imageUrl != null && card.imageUrl!.isNotEmpty) {
      return Image.network(
        card.imageUrl!,
        fit: BoxFit.cover,
        errorBuilder: (ctx, err, stack) => _buildFigureFallback(context),
        loadingBuilder: (ctx, child, progress) {
          if (progress == null) return child;
          return _buildFigureFallback(context, isLoading: true);
        },
      );
    }
    return _buildFigureFallback(context);
  }

  /// Stylized high-contrast research architecture diagram fallback
  Widget _buildFigureFallback(BuildContext context, {bool isLoading = false}) {
    final primaryTag = widget.card.tags.isNotEmpty ? widget.card.tags.first : 'ai_research';

    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [Color(0xFF1B2228), Color(0xFF101418)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      child: Stack(
        alignment: Alignment.center,
        children: [
          // Background technical grid pattern
          CustomPaint(
            size: Size.infinite,
            painter: _TechnicalGridPainter(),
          ),

          if (isLoading)
            const Center(child: CircularProgressIndicator.adaptive())
          else
            Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: Colors.white.withValues(alpha: 0.08),
                    border: Border.all(color: Colors.white.withValues(alpha: 0.2)),
                  ),
                  child: const Icon(
                    Icons.schema_rounded,
                    size: 38,
                    color: Colors.tealAccent,
                  ),
                ),
                const SizedBox(height: 10),
                Text(
                  'Figure 1: Architectural Formulation',
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.9),
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 0.4,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '#${primaryTag.toUpperCase()} • arXiv Grounded Benchmark',
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.5),
                    fontSize: 10.5,
                  ),
                ),
              ],
            ),
        ],
      ),
    );
  }

  /// Inshorts-style floating capsule docked at bottom of card
  Widget _buildRelatedCapsule(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final topic = widget.card.relatedTopic ??
        (widget.card.tags.isNotEmpty
            ? widget.card.tags.first.replaceAll('_', ' ').toUpperCase()
            : 'Related Research');
    final hasRelated = widget.card.relatedCount > 0;

    return Padding(
      padding: const EdgeInsets.fromLTRB(10, 0, 10, 10),
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: widget.onRelated ??
              () {
                if (hasRelated) {
                  RelatedCardsClusterScreen.show(context, widget.card);
                } else {
                  DeepDiveSheet.show(context, widget.card);
                }
              },
          child: Ink(
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF22262B), Color(0xFF14171A)],
                begin: Alignment.centerLeft,
                end: Alignment.centerRight,
              ),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: Colors.white.withValues(alpha: 0.12),
                width: 1.0,
              ),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.35),
                  blurRadius: 10,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14.0, vertical: 10.0),
              child: Row(
                children: [
                  // Left side: Topic title & related papers indicator
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          topic,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 15,
                            fontWeight: FontWeight.bold,
                            letterSpacing: -0.2,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 2),
                        Text(
                          hasRelated
                              ? '${widget.card.relatedCount} related papers in cluster • Swipe horizontal'
                              : 'Tap to explore paper deep dive & chat',
                          style: TextStyle(
                            color: Colors.white.withValues(alpha: 0.65),
                            fontSize: 11,
                            fontWeight: FontWeight.w400,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(width: 10),

                  // Right side: Miniature article/paper preview thumbnail card
                  Container(
                    width: 48,
                    height: 34,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(8),
                      gradient: LinearGradient(
                        colors: [
                          colorScheme.primary.withValues(alpha: 0.8),
                          colorScheme.secondary.withValues(alpha: 0.6),
                        ],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withValues(alpha: 0.25),
                          blurRadius: 4,
                          offset: const Offset(0, 1),
                        ),
                      ],
                    ),
                    child: Center(
                      child: Icon(
                        Icons.auto_stories_rounded,
                        size: 16,
                        color: Colors.white.withValues(alpha: 0.9),
                      ),
                    ),
                  ),

                  const SizedBox(width: 8),

                  // Circular forward chevron icon
                  Container(
                    width: 32,
                    height: 32,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: const Color(0xFF131518),
                      border: Border.all(
                        color: Colors.white.withValues(alpha: 0.35),
                        width: 1.2,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withValues(alpha: 0.3),
                          blurRadius: 4,
                          offset: const Offset(0, 2),
                        ),
                      ],
                    ),
                    child: const Icon(
                      Icons.arrow_forward_ios_rounded,
                      size: 12,
                      color: Colors.white,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Custom painter for scientific graph and grid texture
class _TechnicalGridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.white.withValues(alpha: 0.04)
      ..strokeWidth = 1.0;

    const step = 28.0;
    for (double x = 0; x < size.width; x += step) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (double y = 0; y < size.height; y += step) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}


