from django.urls import path
from .views import AnalyzeResumeView, BatchListView, UploadPDFView, ChatView, CandidateRankingView, DocumentListView

urlpatterns = [
    path("batches/", BatchListView.as_view(), name="batch-list"),
    path("documents/", DocumentListView.as_view(), name="document-list"),
    path("upload/", UploadPDFView.as_view(), name="upload-endpoint"),
    path('chat/', ChatView.as_view(), name = 'chat-bot'),
    path("resume/analyze/", AnalyzeResumeView.as_view()),
    path("resume/rank/", CandidateRankingView.as_view()),
]