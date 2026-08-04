from langchain_text_splitters import RecursiveCharacterTextSplitter


def split_documents(documents):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )

    chunks = splitter.split_documents(documents)
    for chunk in chunks:
        chunk.metadata["source"] = chunk.metadata.get("source", "unknown")

    return chunks