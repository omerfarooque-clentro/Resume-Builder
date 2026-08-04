from .vectordb import similarity_search

def format_context(documents):
    return "\n\n".join(doc.content for doc in documents)

def context_retriever(document_id, question=None):
    documents = similarity_search(document_id=document_id, query=question, top_k=4)
    if not documents:
        return "context_retriever: no relevant info found"

    return format_context(documents)