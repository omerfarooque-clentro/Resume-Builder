from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_llmcache"),
    ]

    operations = [
        migrations.CreateModel(
            name="VectorStoreCache",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(db_index=True, default="default", max_length=64, unique=True)),
                ("store_bytes", models.BinaryField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "last_document",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="vectorstore_cache_entries",
                        to="core.document",
                    ),
                ),
            ],
        ),
    ]
