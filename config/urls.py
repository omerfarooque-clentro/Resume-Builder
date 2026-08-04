from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="index.html"), name="frontend-home"),
    path("upload/", TemplateView.as_view(template_name="upload.html"), name="upload-ui"),
    path("chat/", TemplateView.as_view(template_name="chat.html"), name="chat-ui"),
    path("analysis/", TemplateView.as_view(template_name="analysis.html"), name="analysis-ui"),
    path("ranking/", TemplateView.as_view(template_name="ranking.html"), name="ranking-ui"),
    path("api/", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)