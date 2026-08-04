from celery import shared_task
from .orchestrator import process_upload

@shared_task
def process_resume(document_id):
    process_upload(document_id)