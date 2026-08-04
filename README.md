# PDF Resume Builer

AI-powered resume screening app built with Django + DRF + Celery + PostgreSQL/pgvector.

Upload resume PDFs, process them into vector chunks, chat with a single candidate profile, generate candidate analysis, and rank candidates against a job description.

## Features

- Batch PDF upload with per-file outcomes (`accepted`, `rejected`, `skipped`)
- Duplicate detection using SHA-256 file hash
- Resume metadata extraction (name/email/date) and validation
- Async PDF processing with Celery + Redis
- Vector embeddings stored in PostgreSQL via pgvector
- RAG-based candidate chat and analysis
- Candidate ranking against a job description with JSON scoring
- LLM response caching for analysis and ranking
- Frontend pages for upload, chat, analysis, and ranking

## Tech Stack

- Backend: Django 6, Django REST Framework
- Async jobs: Celery
- Broker/Result backend: Redis
- Database: PostgreSQL + pgvector
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2`
- LLM: Groq (`llama-3.3-70b-versatile`)
- PDF parsing: `pdfplumber`, `pypdf`

## Project Structure

```text
.
├─ config/               # Django config + Celery setup
├─ core/                 # Models, serializers, API views, URL routes
├─ rag/                  # RAG pipeline (loader/splitter/retrieval/engine)
├─ prompts/              # Prompt templates
├─ frontend/             # Django templates (UI pages)
├─ media/documents/      # Uploaded files
├─ manage.py
└─ requirements.txt
```

## Prerequisites

- Python 3.12+
- PostgreSQL 14+ with pgvector extension
- Redis running locally on port `6379`
- Groq API key

## Environment Variables

Create a `.env` file in the project root:

```env
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=127.0.0.1
DB_PORT=5432
GROQ_API_KEY=your_groq_api_key
```

## Database Setup (PostgreSQL + pgvector)

1. Create your database.
2. Enable the vector extension:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## Installation

```bash
# 1) Clone
git clone <your-repo-url>
cd PDF-Chatbot

# 2) Create and activate virtual environment
python -m venv chatbot_env
# Windows (PowerShell)
.\chatbot_env\Scripts\Activate.ps1
# macOS/Linux
source chatbot_env/bin/activate

# 3) Install dependencies
pip install -r requirements.txt

# 4) Run migrations
python manage.py migrate
```

## Run the App

Start each service in a separate terminal.

### 1) Django server

```bash
python manage.py runserver
```

### 2) Celery worker

```bash
python -m celery -A config worker -l info -P solo --concurrency=1
```

### 3) Redis

Run Redis locally (example):

```bash
redis-server
```

## Web UI Routes

- `/` - Home
- `/upload/` - Upload resumes
- `/chat/` - Chat with a selected resume
- `/analysis/` - Generate candidate analysis
- `/ranking/` - Rank candidates against a job description

## UI Screenshots (Placeholders)

Replace these image paths with your real screenshots.

### Home Page (`/`)

```md
```

<img width="1366" height="768" alt="Screenshot 2026-08-04 163319" src="https://github.com/user-attachments/assets/bf1c04da-307b-428c-9ebb-1a04549a6cb9" />

### Upload Page (`/upload/`)

```md

```

<img width="1366" height="768" alt="Screenshot (49)" src="https://github.com/user-attachments/assets/e403e38a-2702-4abe-84b0-8471c7521453" /> 

### Chat Page (`/chat/`)

```md
)
```
<img width="1366" height="768" alt="Screenshot 2026-08-04 163549" src="https://github.com/user-attachments/assets/1f053652-c0ec-4d68-a646-dd14e387ad74" />


### Analysis Page (`/analysis/`)

```md
![Analysis Page](docs/images/analysis-page-placeholder.png)
```

<img width="1366" height="768" alt="Screenshot (50)" src="https://github.com/user-attachments/assets/4dd03665-9f99-4093-a0c8-4f7f5b15ef52" />
s Page](docs/images/analysis-page-placeholder.png)

### Ranking Page (`/ranking/`)

```md

```

<img width="1366" height="768" alt="Screenshot (48)" src="https://github.com/user-attachments/assets/9cf161be-8d54-4198-912b-fd4762553326" />
ge](docs/images/ranking-page-placeholder.png)

## API Endpoints

Base path: `/api/`

- `GET /api/batches/`
  - List all batches
  - Screenshot placeholder:
    ```md
    ![GET batches response](docs/images/api-batches-placeholder.png)
    ```

- `GET /api/documents/?batch_id=<id>`
  - List candidate documents (optionally filtered by batch)
  - Screenshot placeholder:
    ```md
    ![GET documents response](docs/images/api-documents-placeholder.png)
    ```

- `POST /api/upload/`
  - Multipart upload with one or more `pdf` files and optional `batch`
  - Returns totals + per-file details
  - Screenshot placeholder:
    ```md
    ![POST upload response](docs/images/api-upload-placeholder.png)
    ```

- `POST /api/chat/`
  - Body:
    ```json
    {
      "document_id": 1,
      "question": "What are this candidate's strengths?"
    }
    ```
  - Screenshot placeholder:
    ```md
    ![POST chat response](docs/images/api-chat-placeholder.png)
    ```

- `POST /api/resume/analyze/`
  - Body:
    ```json
    {
      "document_id": 1
    }
    ```
  - Screenshot placeholder:
    ```md
    ![POST analyze response](docs/images/api-analyze-placeholder.png)
    ```

- `POST /api/resume/rank/`
  - Body:
    ```json
    {
      "job_description": "Python backend engineer with NLP and Django",
      "batch": "Q4-hiring"
    }
    ```
  - Screenshot placeholder:
    ```md
    ![POST rank response](docs/images/api-rank-placeholder.png)
    ```

## Upload Response Format

`POST /api/upload/` returns:

```json
{
  "totals": {
    "accepted": 2,
    "rejected": 1,
    "skipped": 1
  },
  "details": [
    {
      "filename": "resume_a.pdf",
      "status": "accepted",
      "document_id": 12,
      "task_id": "..."
    },
    {
      "filename": "resume_b.pdf",
      "status": "rejected",
      "reason": "Rejected: Missing required email contact info."
    },
    {
      "filename": "resume_c.pdf",
      "status": "skipped",
      "reason": "Duplicate resume skipped."
    }
  ]
}
```

## Common Rejection/Skip Reasons

- `Rejected: Missing required email contact info.`
- `Duplicate resume skipped.`
- `Skipped: A newer version of this resume already exists.`

## Running Tests

```bash
python manage.py test
```

## Notes

- The current Django settings use `DEBUG=True` for development.
- Do not commit real secrets in `.env`.
- Ensure pgvector is enabled before running vector-related features.

## Troubleshooting

- Celery command not found:
  - Use the virtual environment and run `python -m celery ...` instead of `celery ...`.

- Upload works but processing never finishes:
  - Confirm Redis is running.
  - Confirm Celery worker is running.

- Database connection errors:
  - Verify `.env` values for `DB_*`.
  - Ensure PostgreSQL is reachable on the configured host/port.

- LLM requests failing:
  - Verify `GROQ_API_KEY` is present and valid.

## License

Add your preferred license (MIT, Apache-2.0, etc.).
