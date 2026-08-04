from langchain_core.prompts import ChatPromptTemplate

PROMPT = ChatPromptTemplate.from_template("""
You are a helpful assistant.

Answer the user's question ONLY using the context below.

If the answer is not present in the context, say:
"I couldn't find that information in the uploaded document."

Context:
{context}

Question:
{question}
""")
