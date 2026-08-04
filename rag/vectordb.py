from pgvector.django import CosineDistance

from core.models import DocumentChunk
from .embeddings import get_embedding_model


def upsert_document_chunks(document_id, chunks):

    if not chunks:
        DocumentChunk.objects.filter(document_id=document_id).delete()
        return 0

    embedding_model = get_embedding_model()
    texts = [chunk.page_content for chunk in chunks]
    embeddings = embedding_model.embed_documents(texts)

    DocumentChunk.objects.filter(document_id=document_id).delete()

    rows = []
    for index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        rows.append(
            DocumentChunk(
                document_id=document_id,
                chunk_index=index,
                content=chunk.page_content,
                metadata=chunk.metadata or {},
                embedding=embedding,
            )
        )
    DocumentChunk.objects.bulk_create(rows)
    return len(rows)


def similarity_search(document_id, query, top_k=4):
    normalized_query = (query or "summarize candidate profile").strip() or "summarize candidate profile"
    embedding_model = get_embedding_model()
    query_embedding = embedding_model.embed_query(normalized_query)

    return list(
        DocumentChunk.objects.filter(document_id=document_id)
        .annotate(distance=CosineDistance("embedding", query_embedding))
        .order_by("distance")[:top_k]
    )