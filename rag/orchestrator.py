from core.models import Document, LLMCache
from .loader import load_pdf
from .splitter import split_documents
from .vectordb import upsert_document_chunks
import hashlib
from django.db import transaction
from .metadata import get_candidate_metadata
from core.models import Batch


def register_upload(pdf, file_bytes, batch):
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    existing_doc = Document.objects.filter(file_hash=file_hash).first()
    if existing_doc:
        return {
            "status": "skipped",
            "message": "Duplicate resume skipped.",
            "document": existing_doc,
        }

    candidate_metadata = get_candidate_metadata(pdf)
    if not candidate_metadata.get("email") or candidate_metadata["email"] == "Unknown Email":
        return {
            "status": "rejected",
            "message": "Rejected: Missing required email contact info.",
            "document": None,
        }

    creation_date = candidate_metadata.get("pdf_creation_date")

    with transaction.atomic():
        batch_object = None
        if batch:
            batch_object, _ = Batch.objects.get_or_create(name=batch.strip())
        existing_candidate = Document.objects.filter(
            candidate_email=candidate_metadata.get("email")
        ).first()

        if existing_candidate:
            if creation_date and existing_candidate.created_at >= creation_date:
                return {
                    "status": "skipped",
                    "message": "Skipped: A newer version of this resume already exists.",
                    "document": None,
                }

            existing_candidate.file = pdf
            existing_candidate.file_hash = file_hash
            existing_candidate.created_at = creation_date
            existing_candidate.candidate_name = candidate_metadata.get("name")
            existing_candidate.processed = False
            existing_candidate.batch = batch_object
            existing_candidate.save()
            document = existing_candidate
        else:
            document = Document.objects.create(
                file=pdf,
                created_at=creation_date,
                file_hash=file_hash,
                candidate_name=candidate_metadata.get("name"),
                candidate_email=candidate_metadata.get("email"),
                processed=False,
                batch=batch_object
                
            )

        LLMCache.objects.filter(document=document).delete()

    return {
        "status": "queued",
        "message": "Resume accepted for background processing.",
        "document": document,
    }

def process_document(document_id):
    document = Document.objects.get(id=document_id)
    pages = load_pdf(document.file.path)
    chunks = split_documents(pages)

    for chunk in chunks:
        chunk.metadata["document_id"] = document.id

    upsert_document_chunks(document.id, chunks)

    document.processed = True
    document.save(update_fields=["processed"])

    return document


def process_upload(pdf, file_bytes):
    registration = register_upload(pdf, file_bytes)
    if registration["status"] != "queued":
        return registration
    return process_document(registration["document"].id)