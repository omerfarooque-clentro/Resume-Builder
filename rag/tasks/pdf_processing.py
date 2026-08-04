from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist

from rag.orchestrator import process_document


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=3)
def process_resume(self, document_id):
    try:
        process_document(document_id)
        return {"document_id": document_id, "status": "processed"}
    except ObjectDoesNotExist:
        return {"document_id": document_id, "status": "missing"}
