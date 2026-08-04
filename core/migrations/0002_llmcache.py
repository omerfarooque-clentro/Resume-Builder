from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="LLMCache",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(db_index=True, max_length=255, unique=True)),
                (
                    "cache_type",
                    models.CharField(
                        choices=[("analysis", "Resume Analysis"), ("ranking", "Candidate Ranking")],
                        db_index=True,
                        max_length=32,
                    ),
                ),
                ("value_text", models.TextField(blank=True)),
                ("value_json", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "document",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="llm_cache_entries",
                        to="core.document",
                    ),
                ),
            ],
        ),
    ]
