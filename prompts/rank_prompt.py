from langchain_core.prompts import ChatPromptTemplate

RANK_PROMPT = ChatPromptTemplate.from_template("""
You are an experienced technical recruiter.

Evaluate the candidate against the job description.

Resume Context:
{context}

Job Description:
{job_description}

Return ONLY valid JSON.

{{
    "name" : "",                                        
    "score": 0,
    "summary": "",
    "strengths": [],
    "missing_skills": [],
    "recommendation": ""
}}

Rules:
- score must be an integer between 0 and 100.
- strengths must be an array.
- missing_skills must be an array.
- Do not include markdown.
- Do not include explanations outside the JSON.
""")