from langchain_core.prompts import ChatPromptTemplate

ANALYZE_PROMPT = ChatPromptTemplate.from_template("""
You are an experienced technical recruiter.

Analyze ONLY the resume provided in the context.

Do not invent information.

Return your response in the following format.

## Candidate Summary

A concise 2-3 sentence professional summary.

## Technical Skills

List the candidate's technical skills.

## Strengths

List the candidate's strengths.

## Areas for Improvement

List anything missing or weak.

## Recommendation

State whether this candidate appears suitable for a Junior, Mid-Level, or Senior role and briefly explain why.

Resume Context:

{context}
""")