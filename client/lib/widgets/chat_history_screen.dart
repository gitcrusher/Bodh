import 'package:flutter/material.dart';
import '../models/card_model.dart';
import '../models/chat_model.dart';
import '../services/chat_service.dart';
import 'paper_chat_sheet.dart';

/// ChatGPT/Gemini-style conversation history screen.
///
/// Shows all past paper chat sessions grouped by date (Today, Yesterday, Last 7 days, Older).
/// Tapping a session resumes the conversation in [PaperChatSheet].
/// Long-pressing or tapping the delete icon removes the session.
class ChatHistoryScreen extends StatefulWidget {
  final ChatService chatService;
  final List<NewsCard>? allCards; // pass to resolve card details for resuming

  const ChatHistoryScreen({
    super.key,
    required this.chatService,
    this.allCards,
  });

  static Future<void> show(BuildContext context, {required ChatService chatService, List<NewsCard>? allCards}) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      barrierColor: Colors.black54,
      builder: (ctx) => ChatHistoryScreen(chatService: chatService, allCards: allCards),
    );
  }

  @override
  State<ChatHistoryScreen> createState() => _ChatHistoryScreenState();
}

class _ChatHistoryScreenState extends State<ChatHistoryScreen> {
  List<ChatSessionSummary> _sessions = [];
  bool _loading = true;
  bool _hasError = false;

  @override
  void initState() {
    super.initState();
    _loadSessions();
  }

  Future<void> _loadSessions() async {
    setState(() { _loading = true; _hasError = false; });
    try {
      final sessions = await widget.chatService.fetchChatSessions();
      if (mounted) setState(() { _sessions = sessions; _loading = false; });
    } catch (_) {
      if (mounted) setState(() { _loading = false; _hasError = true; });
    }
  }

  Future<void> _deleteSession(ChatSessionSummary session) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1A1A1A),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Delete conversation?', style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
        content: Text(
          'This will permanently delete your chat about "${session.cardHeadline}".',
          style: const TextStyle(color: Colors.white60, fontSize: 14),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel', style: TextStyle(color: Colors.white54)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete', style: TextStyle(color: Color(0xFFEF5350))),
          ),
        ],
      ),
    );
    if (confirmed == true && mounted) {
      await widget.chatService.deleteChatSession(session.id);
      setState(() => _sessions.removeWhere((s) => s.id == session.id));
    }
  }

  void _resumeSession(ChatSessionSummary session) {
    // Find the matching card if available
    NewsCard? matchCard;
    if (widget.allCards != null) {
      try {
        matchCard = widget.allCards!.firstWhere((c) => c.id == session.cardId);
      } catch (_) {
        matchCard = null;
      }
    }

    // Build a minimal stub card if the full card isn't in memory
    final card = matchCard ?? NewsCard(
      id: session.cardId,
      category: 'research',
      headline: session.cardHeadline,
      summary60s: '',
      tags: [],
      candidateTechniques: [],
      imageUrl: session.cardImageUrl,
      sourceUrl: '',
      publishedAt: session.startedAt,
      needsReview: false,
      isPrimaryFeed: false,
    );

    Navigator.pop(context); // close history screen
    PaperChatSheet.showWithSession(context, card, sessionId: session.id);
  }

  // Group sessions by relative date
  Map<String, List<ChatSessionSummary>> _groupedSessions() {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final yesterday = today.subtract(const Duration(days: 1));
    final last7 = today.subtract(const Duration(days: 7));

    final Map<String, List<ChatSessionSummary>> groups = {
      'Today': [],
      'Yesterday': [],
      'Last 7 days': [],
      'Older': [],
    };

    for (final s in _sessions) {
      final d = DateTime(s.lastActivityAt.year, s.lastActivityAt.month, s.lastActivityAt.day);
      if (!d.isBefore(today)) {
        groups['Today']!.add(s);
      } else if (!d.isBefore(yesterday)) {
        groups['Yesterday']!.add(s);
      } else if (d.isAfter(last7)) {
        groups['Last 7 days']!.add(s);
      } else {
        groups['Older']!.add(s);
      }
    }
    return groups;
  }

  @override
  Widget build(BuildContext context) {
    final screenH = MediaQuery.of(context).size.height;
    return Container(
      height: screenH * 0.88,
      decoration: const BoxDecoration(
        color: Color(0xFF111111),
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Column(
        children: [
          // Handle
          Center(
            child: Container(
              margin: const EdgeInsets.only(top: 10, bottom: 4),
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: Colors.white24,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          // Header
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
            child: Row(
              children: [
                const Icon(Icons.chat_bubble_outline_rounded, color: Color(0xFF2196F3), size: 22),
                const SizedBox(width: 10),
                const Text(
                  'Past Conversations',
                  style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700, letterSpacing: -0.3),
                ),
                const Spacer(),
                if (!_loading)
                  Text(
                    '${_sessions.length} chats',
                    style: const TextStyle(color: Colors.white38, fontSize: 13),
                  ),
              ],
            ),
          ),
          const Divider(color: Colors.white12, height: 1),
          // Body
          Expanded(child: _buildBody()),
        ],
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator(color: Color(0xFF2196F3), strokeWidth: 2));
    }
    if (_hasError) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off_rounded, color: Colors.white30, size: 48),
            const SizedBox(height: 12),
            const Text('Could not load conversations', style: TextStyle(color: Colors.white38, fontSize: 14)),
            const SizedBox(height: 16),
            TextButton(onPressed: _loadSessions, child: const Text('Retry', style: TextStyle(color: Color(0xFF2196F3)))),
          ],
        ),
      );
    }
    if (_sessions.isEmpty) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.chat_bubble_outline_rounded, color: Colors.white12, size: 56),
            SizedBox(height: 14),
            Text('No conversations yet', style: TextStyle(color: Colors.white38, fontSize: 16, fontWeight: FontWeight.w500)),
            SizedBox(height: 6),
            Text('Tap the chat button on any card to start', style: TextStyle(color: Colors.white24, fontSize: 13)),
          ],
        ),
      );
    }

    final groups = _groupedSessions();
    final groupOrder = ['Today', 'Yesterday', 'Last 7 days', 'Older'];

    return RefreshIndicator(
      color: const Color(0xFF2196F3),
      backgroundColor: const Color(0xFF1A1A1A),
      onRefresh: _loadSessions,
      child: ListView.builder(
        padding: const EdgeInsets.only(bottom: 32),
        itemCount: groupOrder.fold<int>(
          0,
          (sum, g) => sum + (groups[g]!.isEmpty ? 0 : 1 + groups[g]!.length),
        ),
        itemBuilder: (ctx, index) {
          // Flatten groups into a list of section headers + items
          int cursor = 0;
          for (final groupKey in groupOrder) {
            final items = groups[groupKey]!;
            if (items.isEmpty) continue;
            if (index == cursor) {
              return _buildGroupHeader(groupKey);
            }
            cursor++;
            if (index < cursor + items.length) {
              return _buildSessionTile(items[index - cursor]);
            }
            cursor += items.length;
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }

  Widget _buildGroupHeader(String label) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 6),
      child: Text(
        label,
        style: const TextStyle(color: Colors.white38, fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 0.6),
      ),
    );
  }

  Widget _buildSessionTile(ChatSessionSummary session) {
    return Dismissible(
      key: ValueKey('session_${session.id}'),
      direction: DismissDirection.endToStart,
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 24),
        color: const Color(0xFFEF5350),
        child: const Icon(Icons.delete_outline_rounded, color: Colors.white, size: 22),
      ),
      confirmDismiss: (_) async {
        await _deleteSession(session);
        return false; // We manage state manually in _deleteSession
      },
      child: InkWell(
        onTap: () => _resumeSession(session),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 13),
          decoration: const BoxDecoration(
            border: Border(bottom: BorderSide(color: Colors.white10, width: 0.5)),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Paper image avatar
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: session.cardImageUrl != null && session.cardImageUrl!.isNotEmpty
                    ? Image.network(
                        session.cardImageUrl!,
                        width: 44,
                        height: 44,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => _placeholderAvatar(),
                      )
                    : _placeholderAvatar(),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      session.cardHeadline,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w500, height: 1.35),
                    ),
                    if (session.lastMessagePreview.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        session.lastMessagePreview,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(color: Colors.white38, fontSize: 12, height: 1.3),
                      ),
                    ],
                    const SizedBox(height: 5),
                    Row(
                      children: [
                        const Icon(Icons.chat_bubble_outline, size: 11, color: Colors.white30),
                        const SizedBox(width: 4),
                        Text(
                          '${session.messageCount} messages',
                          style: const TextStyle(color: Colors.white30, fontSize: 11),
                        ),
                        const SizedBox(width: 10),
                        Text(
                          _relativeTime(session.lastActivityAt),
                          style: const TextStyle(color: Colors.white30, fontSize: 11),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              const Icon(Icons.chevron_right_rounded, color: Colors.white24, size: 20),
            ],
          ),
        ),
      ),
    );
  }

  Widget _placeholderAvatar() {
    return Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(
        color: const Color(0xFF1E1E2E),
        borderRadius: BorderRadius.circular(8),
      ),
      child: const Icon(Icons.article_outlined, color: Colors.white24, size: 20),
    );
  }

  String _relativeTime(DateTime dt) {
    final diff = DateTime.now().difference(dt);
    if (diff.inMinutes < 1) return 'Just now';
    if (diff.inHours < 1) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return '${dt.day}/${dt.month}/${dt.year}';
  }
}
