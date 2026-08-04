from django.db import migrations, models
import django.db.models.deletion
import pgvector.django.vector


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_batch_remove_document_folder_document_batch_and_more"),
    ]

    operations = [
        migrations.RunSQL("CREATE EXTENSION IF NOT EXISTS vector;", reverse_sql=migrations.RunSQL.noop),
        migrations.CreateModel(
            name="DocumentChunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("chunk_index", models.PositiveIntegerField(default=0)),
                ("content", models.TextField()),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("embedding", pgvector.django.vector.VectorField(dimensions=384)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "document",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chunks", to="core.document"),
                ),
            ],
            options={
                "ordering": ["document_id", "chunk_index"],
            },
        ),
        migrations.DeleteModel(
            name="VectorStoreCache",
        ),
    ]
