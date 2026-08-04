from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

from django.db import transaction
from django.utils import timezone

from core.models import Document, DocumentFolder, LLMCache


def build_folder_name(created_at: Optional[datetime] = None) -> str:
    """Create a stable folder name from a date, using the format yyyy-mm-dd or 'uncategorized'."""
    if created_at is None:
        created_at = timezone.now()
    if not created_at:
        return "uncategorized"
    return created_at.strftime("%Y-%m-%d")


def ensure_folder_for_document(document: Document) -> DocumentFolder:
    """Assign or create a folder for a document and keep the folder name stable."""
    folder_name = build_folder_name(document.created_at)
    folder, _ = DocumentFolder.objects.get_or_create(name=folder_name)
    if document.folder_id != folder.id:
        document.folder = folder
        document.save(update_fields=["folder"])
    return folder


def organize_document_file(document: Document) -> Optional[Path]:
    """Move a stored document into a folder-scoped directory under media/documents if needed."""
    folder = ensure_folder_for_document(document)
    storage_path = Path(document.file.name or "")
    if not storage_path.name:
        return None

    base_dir = Path("documents") / folder.name
    target_path = base_dir / storage_path.name

    if document.file.storage.exists(document.file.name):
        if document.file.name != str(target_path):
            with transaction.atomic():
                document.file.storage.save(str(target_path), document.file)
                document.file.name = str(target_path)
                document.save(update_fields=["file"])
    return target_path


def delete_folder_and_documents(folder_name: str) -> int:
    """Remove a folder, all documents inside it, and related cache entries."""
    folder = DocumentFolder.objects.filter(name=folder_name).first()
    if not folder:
        return 0

    documents = list(Document.objects.filter(folder=folder))
    for document in documents:
        try:
            if document.file:
                document.file.storage.delete(document.file.name)
        except Exception:
            pass
        LLMCache.objects.filter(document=document).delete()

    document_ids = [document.id for document in documents]
    Document.objects.filter(folder=folder).delete()
    folder.delete()
    return len(document_ids)


def estimate_prompt_tokens(question: str, context_chunks: Sequence[str] | None = None) -> int:
    """Estimate a rough token count without interacting with the LLM."""
    if not question and not context_chunks:
        return 0
    question_tokens = max(1, len(question.split()))
    context_tokens = sum(max(1, len(chunk.split())) for chunk in (context_chunks or []))
    return question_tokens + context_tokens 
