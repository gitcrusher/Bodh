from django.contrib import admin
from research.models import (
    Card,
    CardSource,
    ChatMessage,
    ChatSession,
    ContentReport,
    PaperChatChunk,
    PaperValiditySignal,
    RawItem,
    Source,
)

admin.site.register(Source)
admin.site.register(RawItem)
admin.site.register(Card)
admin.site.register(CardSource)
admin.site.register(PaperValiditySignal)
admin.site.register(ContentReport)
admin.site.register(PaperChatChunk)
admin.site.register(ChatSession)
admin.site.register(ChatMessage)
