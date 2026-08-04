import hashlib
import json

from core.models import Document, LLMCache
from prompts.chat_prompt import PROMPT
from prompts.rank_prompt import RANK_PROMPT
from prompts.resume_analyze_prompt import ANALYZE_PROMPT
from .llm import get_llm
from .retrieval import context_retriever

def chat(document_id, question):
    context = context_retriever(document_id, question)

    prompt = PROMPT.invoke({
        'context' : context,
        'question' : question
    })

    llm = get_llm()

    response = llm.invoke(prompt)

    return response.content

def analyze_resume(document_id):
    document = Document.objects.get(id=document_id)
    cache_key = f"analysis:{document.id}:{document.file_hash}"
    cached = LLMCache.objects.filter(
        key=cache_key,
        cache_type=LLMCache.CACHE_TYPE_ANALYSIS,
    ).first()
    if cached and cached.value_text:
        return cached.value_text

    context = context_retriever(document_id,
                                "Summarize the candidate's experience, education, and technical skills."
    )

    prompt = ANALYZE_PROMPT.invoke({
        "context": context
    })

    llm = get_llm()

    response = llm.invoke(prompt)
    LLMCache.objects.update_or_create(
        key=cache_key,
        defaults={
            "cache_type": LLMCache.CACHE_TYPE_ANALYSIS,
            "document": document,
            "value_text": response.content,
            "value_json": None,
        },
    )

    return response.content


def rank_candidates(job_description, batch=None):
    results = []
    llm = None
    job_hash = hashlib.sha256(job_description.encode("utf-8")).hexdigest()

    if batch is None:
        documents_qs = Document.objects.all()
    elif isinstance(batch, str):
        normalized_batch = batch.strip()
        documents_qs = Document.objects.filter(batch__name__iexact=normalized_batch) if normalized_batch else Document.objects.all()
    else:
        documents_qs = Document.objects.filter(batch=batch)

    documents = documents_qs.order_by(
        'candidate_email',
        '-created_at'
    ).distinct('candidate_email')
    
    for document in documents:
        cache_key = f"ranking:{document.id}:{document.file_hash}:{job_hash}"
        cached = LLMCache.objects.filter(
            key=cache_key,
            cache_type=LLMCache.CACHE_TYPE_RANKING,
        ).first()

        if cached and isinstance(cached.value_json, dict):
            data = cached.value_json
        else:
            if llm is None:
                llm = get_llm()

            context = context_retriever(
                document.id,
                job_description
            )

            prompt = RANK_PROMPT.invoke({
                "context": context,
                "job_description": job_description,
            })
            response = llm.invoke(prompt)

            try:
                data = json.loads(response.content)
            except (json.JSONDecodeError, TypeError):
                data = {
                    "score": 0,
                    "summary": "Failed to analyze candidate data.",
                    "strengths": [],
                    "missing_skills": [],
                    "recommendation": "Manual review required."
                }

            LLMCache.objects.update_or_create(
                key=cache_key,
                defaults={
                    "cache_type": LLMCache.CACHE_TYPE_RANKING,
                    "document": document,
                    "value_text": "",
                    "value_json": data,
                },
            )

        # 3. For testing, fall back to the actual file name so you can identify rows easily
        results.append({
            "document_id": document.id,
            "candidate_name": document.candidate_name,  
            "candidate_email" : document.candidate_email,
            **data,
        })

    # 4. Sort the batch by score in descending order
    results.sort(
        key=lambda candidate: candidate.get("score", 0),
        reverse=True,
    )

    return results