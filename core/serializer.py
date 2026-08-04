from rest_framework import serializers

from core.models import Batch, Document


class BatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Batch
        fields = ["id", "name", "created_at"]


class DocumentListSerializer(serializers.ModelSerializer):
    batch_name = serializers.CharField(source="batch.name", read_only=True)

    class Meta:
        model = Document
        fields = [
            "id",
            "candidate_name",
            "candidate_email",
            "processed",
            "uploaded_at",
            "batch_name",
        ]


class UploadPDFSerializer(serializers.Serializer):
    pdf = serializers.ListField(
        child=serializers.FileField(),
        required=True
    )
    batch = serializers.CharField(required=False, allow_blank=True)

class ChatSerializer(serializers.Serializer):
    document_id = serializers.IntegerField()
    question = serializers.CharField(required = True)


class AnalyzeSerializer(serializers.Serializer):
    document_id = serializers.IntegerField()

class CandidateRankingSerializer(serializers.Serializer):
    job_description = serializers.CharField()
    batch = serializers.CharField(required=False, allow_blank=True)