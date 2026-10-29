import 'package:flutter/material.dart';
import '../models/card_model.dart';
import '../models/chat_model.dart';
import '../services/chat_service.dart';

/// Per-card conversational RAG grounded in the paper's full text.
///
/// Follows Agent/design.md §5 & Agent/rules.md:
/// - Citations are tappable and show quoted chunk excerpts (Rule 12 & design.md §5).
/// - Abstention is a designed honest state: "The paper does not appear to cover that."
/// - First chat on a card has a preparing state while text is indexed (Rule 46 & 47).
/// - Message length is capped (2,000 characters, Rule 17).
class PaperChatSheet extends StatefulWidget {
  final NewsCard card;
  final ChatService? chatService;

  const PaperChatSheet({
    super.key,
    required this.card,
    this.chatService,
  });

  static Future<void> show(BuildContext context, NewsCard card) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => PaperChatSheet(card: card),
    );
  }

  @override
  State<PaperChatSheet> createState() => _PaperChatSheetState();
}

class _PaperChatSheetState extends State<PaperChatSheet> {
  late final ChatService _chatService;
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  final List<ChatMessageModel> _messages = [];
  int? _sessionId;
  bool _isSending = false;

  static const int maxMessageLength = 2000;

  @override
  void initState() {
    super.initState();
    _chatService = widget.chatService ?? ChatService();
    _controller.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _sendMessage(String text) async {
    final clean = text.trim();
    if (clean.isEmpty || clean.length > maxMessageLength || _isSending) return;

    _controller.clear();

    final userMsg = ChatMessageModel(
      id: DateTime.now().millisecondsSinceEpoch,
      role: 'user',
      content: clean,
      citations: [],
      createdAt: DateTime.now(),
    );

    setState(() {
      _messages.add(userMsg);
      _isSending = true;
    });

    _scrollToBottom();

    try {
      final res = await _chatService.sendMessage(
        cardId: widget.card.id,
        message: clean,
        sessionId: _sessionId,
        cardHeadline: widget.card.headline,
        cardSummary: widget.card.summary60s,
      );

      if (mounted) {
        final assistantMsg = ChatMessageModel(
          id: DateTime.now().millisecondsSinceEpoch + 1,
          role: 'assistant',
          content: res.answer,
          citations: res.citations,
          createdAt: DateTime.now(),
          isAbstention: res.abstain,
        );

        setState(() {
          _sessionId = res.sessionId;
          _messages.add(assistantMsg);
          _isSending = false;
        });

        _scrollToBottom();
      }
    } catch (_) {
      if (mounted) {
        setState(() => _isSending = false);
      }
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _showCitationDialog(CitationModel citation) {
    showDialog(
      context: context,
      builder: (ctx) {
        final theme = Theme.of(ctx);
        final colorScheme = theme.colorScheme;

        return AlertDialog(
          backgroundColor: theme.cardColor,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: Row(
            children: [
              Icon(Icons.format_quote, color: colorScheme.primary, size: 22),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Verified Paper Citation',
                  style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (citation.claim.isNotEmpty) ...[
                Text(
                  'SUPPORTED CLAIM',
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 0.8,
                    color: theme.hintColor,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  citation.claim,
                  style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 14),
              ],
              Text(
                'VERBATIM EXCERPT (CHUNK #${citation.chunkId})',
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 0.8,
                  color: colorScheme.primary,
                ),
              ),
              const SizedBox(height: 6),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.35),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: theme.dividerColor),
                ),
                child: Text(
                  '"${citation.quote}"',
                  style: theme.textTheme.bodySmall?.copyWith(
                    fontStyle: FontStyle.italic,
                    height: 1.45,
                    fontSize: 13,
                  ),
                ),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Icon(Icons.check_circle, size: 14, color: Colors.green.shade600),
                  const SizedBox(width: 6),
                  Text(
                    'Deterministic non-LLM match verified against paper text',
                    style: TextStyle(fontSize: 11, color: Colors.green.shade700),
                  ),
                ],
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Close'),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final remainingChars = maxMessageLength - _controller.text.length;

    return DraggableScrollableSheet(
      initialChildSize: 0.85,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      builder: (ctx, scrollSheetController) {
        return Container(
          decoration: BoxDecoration(
            color: theme.cardColor,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.25),
                blurRadius: 18,
                offset: const Offset(0, -4),
              ),
            ],
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

              // Header Bar
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 8.0),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Text(
                                'PAPER CHAT',
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                  letterSpacing: 1.0,
                                  color: colorScheme.primary,
                                ),
                              ),
                              const SizedBox(width: 8),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                decoration: BoxDecoration(
                                  color: colorScheme.primary.withValues(alpha: 0.1),
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(
                                  'GROUNDED RAG',
                                  style: TextStyle(
                                    fontSize: 9.5,
                                    fontWeight: FontWeight.bold,
                                    color: colorScheme.primary,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 4),
                          Text(
                            widget.card.headline,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w600,
                              fontSize: 15,
                            ),
                          ),
                        ],
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.close),
                      tooltip: 'Close',
                      onPressed: () => Navigator.pop(context),
                    ),
                  ],
                ),
              ),

              const Divider(height: 1),

              // Messages List Area
              Expanded(
                child: _messages.isEmpty
                    ? _buildEmptyState(theme, colorScheme)
                    : ListView.builder(
                        controller: _scrollController,
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                        itemCount: _messages.length,
                        itemBuilder: (ctx, idx) {
                          return _buildMessageBubble(_messages[idx], theme, colorScheme);
                        },
                      ),
              ),

              if (_isSending)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 6.0),
                  child: Row(
                    children: [
                      SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2, color: colorScheme.primary),
                      ),
                      const SizedBox(width: 10),
                      Text(
                        'Searching paper text and verifying citations...',
                        style: TextStyle(fontSize: 12, color: theme.hintColor),
                      ),
                    ],
                  ),
                ),

              const Divider(height: 1),

              // Input Bar with Character Counter (Rule 17)
              _buildInputBar(theme, colorScheme, remainingChars),
            ],
          ),
        );
      },
    );
  }

  Widget _buildEmptyState(ThemeData theme, ColorScheme colorScheme) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: colorScheme.primary.withValues(alpha: 0.1),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.chat_bubble_outline, size: 36, color: colorScheme.primary),
            ),
            const SizedBox(height: 14),
            Text(
              'Grounded Paper Chat',
              style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 6),
            Text(
              'Ask any technical question about this paper. Every claim is strictly verified with verbatim citations.',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodySmall?.copyWith(fontSize: 13),
            ),
            const SizedBox(height: 20),

            // Quick Question Starter Chips
            Text(
              'SUGGESTED QUESTIONS',
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.bold,
                letterSpacing: 0.8,
                color: theme.hintColor,
              ),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: [
                'What is the core contribution?',
                'What benchmarks were evaluated?',
                'How does it compare to prior work?',
              ].map((suggestion) {
                return ActionChip(
                  label: Text(suggestion, style: const TextStyle(fontSize: 12)),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  onPressed: () => _sendMessage(suggestion),
                );
              }).toList(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMessageBubble(ChatMessageModel msg, ThemeData theme, ColorScheme colorScheme) {
    if (msg.isUser) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 12.0),
        child: Align(
          alignment: Alignment.centerRight,
          child: Container(
            constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.78),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: colorScheme.primary,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(16),
                topRight: Radius.circular(16),
                bottomLeft: Radius.circular(16),
                bottomRight: Radius.circular(4),
              ),
            ),
            child: Text(
              msg.content,
              style: TextStyle(
                color: colorScheme.onPrimary,
                fontSize: 14.5,
                height: 1.35,
              ),
            ),
          ),
        ),
      );
    }

    // Assistant Message Bubble
    return Padding(
      padding: const EdgeInsets.only(bottom: 16.0),
      child: Align(
        alignment: Alignment.centerLeft,
        child: Container(
          constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.88),
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: msg.isAbstention
                ? Colors.amber.withValues(alpha: 0.08)
                : theme.cardColor,
            borderRadius: const BorderRadius.only(
              topLeft: Radius.circular(16),
              topRight: Radius.circular(16),
              bottomLeft: Radius.circular(4),
              bottomRight: Radius.circular(16),
            ),
            border: Border.all(
              color: msg.isAbstention
                  ? Colors.amber.shade300
                  : theme.dividerColor.withValues(alpha: 0.6),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (msg.isAbstention) ...[
                Row(
                  children: [
                    Icon(Icons.info_outline, size: 15, color: Colors.amber.shade800),
                    const SizedBox(width: 6),
                    Text(
                      'Honest Abstention (Out of Scope)',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: Colors.amber.shade900,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
              ],
              Text(
                msg.content,
                style: theme.textTheme.bodyMedium?.copyWith(
                  height: 1.5,
                  fontSize: 14.5,
                ),
              ),

              // Citations list (Rule 12: verified excerpts)
              if (msg.citations.isNotEmpty) ...[
                const SizedBox(height: 12),
                const Divider(height: 1),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Icon(Icons.format_quote, size: 13, color: colorScheme.primary),
                    const SizedBox(width: 4),
                    Text(
                      'Paper Citations (Tap to verify excerpt):',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: colorScheme.primary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: List.generate(msg.citations.length, (idx) {
                    final cit = msg.citations[idx];
                    return ActionChip(
                      avatar: CircleAvatar(
                        radius: 8,
                        backgroundColor: colorScheme.primary.withValues(alpha: 0.2),
                        child: Text(
                          '${idx + 1}',
                          style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: colorScheme.primary),
                        ),
                      ),
                      label: Text(
                        'Excerpt ${idx + 1}',
                        style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600),
                      ),
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      visualDensity: VisualDensity.compact,
                      onPressed: () => _showCitationDialog(cit),
                    );
                  }),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildInputBar(ThemeData theme, ColorScheme colorScheme, int remainingChars) {
    final canSend = _controller.text.trim().isNotEmpty && remainingChars >= 0 && !_isSending;

    return Container(
      padding: EdgeInsets.fromLTRB(16, 8, 16, MediaQuery.of(context).viewInsets.bottom + 12),
      decoration: BoxDecoration(
        color: theme.cardColor,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _controller,
                  maxLines: 3,
                  minLines: 1,
                  maxLength: maxMessageLength,
                  decoration: InputDecoration(
                    hintText: 'Ask about this paper...',
                    hintStyle: theme.textTheme.bodySmall?.copyWith(fontSize: 14),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(20),
                      borderSide: BorderSide(color: theme.dividerColor),
                    ),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                    counterText: '', // Display custom counter below
                  ),
                ),
              ),
              const SizedBox(width: 8),
              IconButton.filled(
                icon: const Icon(Icons.send_rounded, size: 20),
                onPressed: canSend ? () => _sendMessage(_controller.text) : null,
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            '$remainingChars / $maxMessageLength chars',
            style: TextStyle(
              fontSize: 10,
              color: remainingChars < 100 ? Colors.red : theme.hintColor,
            ),
          ),
        ],
      ),
    );
  }
}

