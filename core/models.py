from django.db import models
from pgvector.django import VectorField


class Batch(models.Model):
    name = models.CharField(max_length=255, default="default", unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Document(models.Model):
    file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField()
    file_hash = models.CharField(max_length=64, unique=True, db_index=True)
    candidate_name = models.CharField(max_length=200, blank=True)
    candidate_email = models.EmailField(null=False, blank=False)
    processed = models.BooleanField(default=False)
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True, related_name="documents")
 
    def __str__(self):
        return self.file.name


class LLMCache(models.Model):
    CACHE_TYPE_ANALYSIS = "analysis"
    CACHE_TYPE_RANKING = "ranking"
    CACHE_TYPE_CHOICES = [
        (CACHE_TYPE_ANALYSIS, "Resume Analysis"),
        (CACHE_TYPE_RANKING, "Candidate Ranking"),
    ]

    key = models.CharField(max_length=255, unique=True, db_index=True)
    cache_type = models.CharField(max_length=32, choices=CACHE_TYPE_CHOICES, db_index=True)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="llm_cache_entries",
    )
    value_text = models.TextField(blank=True)
    value_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.cache_type}:{self.key}"


class DocumentChunk(models.Model):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    chunk_index = models.PositiveIntegerField(default=0)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    embedding = VectorField(dimensions=384)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document_id", "chunk_index"]

    def __str__(self):
        return f"chunk:{self.document_id}:{self.chunk_index}"