import hashlib
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ObjectDoesNotExist
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Batch, Document, DocumentChunk, LLMCache
from core.serializer import (
	AnalyzeSerializer,
	CandidateRankingSerializer,
	ChatSerializer,
	DocumentListSerializer,
	UploadPDFSerializer,
)
from rag.engine import analyze_resume, chat, rank_candidates
from rag.metadata import get_candidate_metadata, parse_pdf_date
from rag.orchestrator import process_document, process_upload, register_upload
from rag.retrieval import context_retriever, format_context
from rag.tasks.pdf_processing import process_resume
from rag.vectordb import similarity_search, upsert_document_chunks


class BaseModelFactoryMixin:
	def make_document(self, *, suffix="1", batch=None, processed=True):
		file_hash = hashlib.sha256(f"doc-{suffix}".encode("utf-8")).hexdigest()
		return Document.objects.create(
			file=SimpleUploadedFile(f"resume-{suffix}.pdf", b"%PDF-1.4 test"),
			created_at=timezone.now() - timedelta(days=1),
			file_hash=file_hash,
			candidate_name=f"Candidate {suffix}",
			candidate_email=f"candidate{suffix}@example.com",
			processed=processed,
			batch=batch,
		)


class SerializerTests(TestCase):
	def test_upload_serializer_requires_pdf(self):
		serializer = UploadPDFSerializer(data={})
		self.assertFalse(serializer.is_valid())
		self.assertIn("pdf", serializer.errors)

	def test_upload_serializer_accepts_optional_batch(self):
		pdf = SimpleUploadedFile("resume.pdf", b"%PDF", content_type="application/pdf")
		serializer = UploadPDFSerializer(data={"pdf": pdf, "batch": "summer"})
		self.assertTrue(serializer.is_valid())

	def test_chat_serializer_requires_question(self):
		serializer = ChatSerializer(data={"document_id": 1})
		self.assertFalse(serializer.is_valid())
		self.assertIn("question", serializer.errors)

	def test_analyze_serializer_rejects_non_integer_document_id(self):
		serializer = AnalyzeSerializer(data={"document_id": "not-int"})
		self.assertFalse(serializer.is_valid())

	def test_candidate_ranking_serializer_requires_job_description(self):
		serializer = CandidateRankingSerializer(data={})
		self.assertFalse(serializer.is_valid())
		self.assertIn("job_description", serializer.errors)


class DocumentChunkModelTests(BaseModelFactoryMixin, TestCase):
	def test_document_chunk_tracks_document_and_embedding(self):
		document = self.make_document(suffix="2")
		chunk = DocumentChunk.objects.create(
			document=document,
			chunk_index=0,
			content="Experienced backend engineer",
			metadata={"source": "resume.pdf"},
			embedding=[0.1] * 384,
		)

		self.assertEqual(chunk.document_id, document.id)
		self.assertEqual(chunk.chunk_index, 0)
		self.assertEqual(chunk.metadata["source"], "resume.pdf")
		self.assertEqual(len(chunk.embedding), 384)


class DocumentListSerializerTests(BaseModelFactoryMixin, TestCase):
	def test_document_list_serializer_exposes_batch_name(self):
		batch = Batch.objects.create(name="spring")
		document = self.make_document(suffix="3", batch=batch)
		payload = DocumentListSerializer(document).data

		self.assertEqual(payload["id"], document.id)
		self.assertEqual(payload["batch_name"], "spring")


class ApiEndpointTests(BaseModelFactoryMixin, TestCase):
	def setUp(self):
		self.client = APIClient()

	def test_batch_list_endpoint(self):
		Batch.objects.create(name="summer")
		Batch.objects.create(name="winter")

		response = self.client.get("/api/batches/")

		self.assertEqual(response.status_code, 200)
		names = [item["name"] for item in response.data]
		self.assertIn("summer", names)
		self.assertIn("winter", names)

	def test_documents_endpoint_lists_documents(self):
		document = self.make_document(suffix="4")
		response = self.client.get("/api/documents/")

		self.assertEqual(response.status_code, 200)
		found = next(item for item in response.data if item["id"] == document.id)
		self.assertEqual(found["candidate_name"], document.candidate_name)

	def test_documents_endpoint_filters_by_batch_id(self):
		batch = Batch.objects.create(name="b1")
		scoped = self.make_document(suffix="5", batch=batch)
		self.make_document(suffix="6")

		response = self.client.get(f"/api/documents/?batch_id={batch.id}")

		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.data), 1)
		self.assertEqual(response.data[0]["id"], scoped.id)

	def test_documents_endpoint_alias_batch_query_param(self):
		batch = Batch.objects.create(name="b2")
		scoped = self.make_document(suffix="7", batch=batch)

		response = self.client.get(f"/api/documents/?batch={batch.id}")

		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.data), 1)
		self.assertEqual(response.data[0]["id"], scoped.id)

	def test_upload_endpoint_accepted(self):
		document = self.make_document(suffix="8")
		upload = SimpleUploadedFile("resume.pdf", b"%PDF", content_type="application/pdf")

		with patch(
			"core.views.orchestrator.register_upload",
			return_value={
				"status": "queued",
				"message": "Resume accepted for background processing.",
				"document": document,
			},
		), patch("core.views.process_resume.delay") as delay_mock:
			delay_mock.return_value = type("TaskResult", (), {"id": "task-123"})()
			response = self.client.post("/api/upload/", {"pdf": upload}, format="multipart")

		self.assertEqual(response.status_code, 202)
		self.assertEqual(response.data["status"], "accepted")
		self.assertEqual(response.data["document_id"], document.id)
		self.assertEqual(response.data["task_id"], "task-123")

	def test_upload_endpoint_rejected(self):
		upload = SimpleUploadedFile("resume.pdf", b"%PDF", content_type="application/pdf")
		with patch(
			"core.views.orchestrator.register_upload",
			return_value={"status": "rejected", "message": "Rejected"},
		):
			response = self.client.post("/api/upload/", {"pdf": upload}, format="multipart")

		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.data["status"], "rejected")

	def test_upload_endpoint_skipped(self):
		upload = SimpleUploadedFile("resume.pdf", b"%PDF", content_type="application/pdf")
		with patch(
			"core.views.orchestrator.register_upload",
			return_value={"status": "skipped", "message": "Duplicate"},
		):
			response = self.client.post("/api/upload/", {"pdf": upload}, format="multipart")

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["status"], "skipped")

	def test_chat_endpoint(self):
		with patch("core.views.chat", return_value="hello") as chat_mock:
			response = self.client.post(
				"/api/chat/",
				{"document_id": 1, "question": "profile?"},
				format="json",
			)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["answer"], "hello")
		chat_mock.assert_called_once_with(1, "profile?")

	def test_chat_endpoint_validation_error(self):
		response = self.client.post("/api/chat/", {"document_id": 1}, format="json")
		self.assertEqual(response.status_code, 400)

	def test_analyze_endpoint(self):
		with patch("core.views.analyze_resume", return_value="analysis") as analyze_mock:
			response = self.client.post("/api/resume/analyze/", {"document_id": 42}, format="json")

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["analysis"], "analysis")
		analyze_mock.assert_called_once_with(42)

	def test_rank_endpoint(self):
		payload = [{"document_id": 1, "score": 90}]
		with patch("core.views.rank_candidates", return_value=payload) as rank_mock:
			response = self.client.post("/api/resume/rank/", {"job_description": "Python"}, format="json")

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data, payload)
		rank_mock.assert_called_once_with("Python")

	def test_rank_endpoint_with_batch(self):
		payload = [{"document_id": 1, "score": 90}]
		with patch("core.views.rank_candidates", return_value=payload) as rank_mock:
			response = self.client.post(
				"/api/resume/rank/",
				{"job_description": "Python", "batch": "summer"},
				format="json",
			)

		self.assertEqual(response.status_code, 200)
		rank_mock.assert_called_once_with("Python", batch="summer")


class RetrievalTests(TestCase):
	def test_format_context_joins_content(self):
		docs = [SimpleNamespace(content="A"), SimpleNamespace(content="B")]
		self.assertEqual(format_context(docs), "A\n\nB")

	def test_context_retriever_empty_result(self):
		with patch("rag.retrieval.similarity_search", return_value=[]):
			result = context_retriever(1, "question")
		self.assertEqual(result, "context_retriever: no relevant info found")

	def test_context_retriever_with_result(self):
		docs = [SimpleNamespace(content="chunk1"), SimpleNamespace(content="chunk2")]
		with patch("rag.retrieval.similarity_search", return_value=docs):
			result = context_retriever(1, "question")
		self.assertEqual(result, "chunk1\n\nchunk2")


class VectorDbTests(BaseModelFactoryMixin, TestCase):
	def test_upsert_document_chunks_clears_existing_when_empty(self):
		document = self.make_document(suffix="9")
		DocumentChunk.objects.create(
			document=document,
			chunk_index=0,
			content="old",
			metadata={},
			embedding=[0.1] * 384,
		)

		count = upsert_document_chunks(document.id, [])

		self.assertEqual(count, 0)
		self.assertFalse(DocumentChunk.objects.filter(document_id=document.id).exists())

	def test_upsert_document_chunks_writes_new_embeddings(self):
		document = self.make_document(suffix="10")
		chunks = [
			SimpleNamespace(page_content="alpha", metadata={"source": "a.pdf"}),
			SimpleNamespace(page_content="beta", metadata={"source": "b.pdf"}),
		]

		class FakeEmbeddings:
			def embed_documents(self, texts):
				self.texts = texts
				return [[0.2] * 384, [0.3] * 384]

		fake_embeddings = FakeEmbeddings()
		with patch("rag.vectordb.get_embedding_model", return_value=fake_embeddings):
			count = upsert_document_chunks(document.id, chunks)

		self.assertEqual(count, 2)
		rows = DocumentChunk.objects.filter(document_id=document.id).order_by("chunk_index")
		self.assertEqual(rows.count(), 2)
		self.assertEqual(rows[0].content, "alpha")
		self.assertEqual(rows[1].metadata["source"], "b.pdf")

	def test_similarity_search_uses_default_query_when_blank(self):
		with patch("rag.vectordb.get_embedding_model") as emb_mock, patch("rag.vectordb.DocumentChunk.objects") as objects_mock:
			emb_mock.return_value.embed_query.return_value = [0.1] * 384
			objects_mock.filter.return_value.annotate.return_value.order_by.return_value.__getitem__.return_value = ["hit"]

			result = similarity_search(document_id=1, query="", top_k=4)

		self.assertEqual(result, ["hit"])
		emb_mock.return_value.embed_query.assert_called_once_with("summarize candidate profile")


class MetadataTests(TestCase):
	def test_parse_pdf_date_adobe_format(self):
		parsed = parse_pdf_date("D:20260718121542")
		self.assertTrue(timezone.is_aware(parsed))
		self.assertEqual(parsed.year, 2026)

	def test_parse_pdf_date_invalid_returns_now_like_value(self):
		parsed = parse_pdf_date("invalid")
		self.assertTrue(timezone.is_aware(parsed))

	def test_get_candidate_metadata_extracts_email_and_name(self):
		pdf = SimpleUploadedFile("resume.pdf", b"%PDF", content_type="application/pdf")

		class FakePage:
			def extract_text(self):
				return "Name: Jane Doe\nContact jane@example.com"

		class FakeReader:
			metadata = {"CreationDate": "D:20260102030405"}
			pages = [FakePage()]

			def __enter__(self):
				return self

			def __exit__(self, exc_type, exc, tb):
				return False

		with patch("rag.metadata.pdfplumber.open", return_value=FakeReader()):
			metadata = get_candidate_metadata(pdf)

		self.assertEqual(metadata["email"], "jane@example.com")
		self.assertEqual(metadata["name"], "Jane Doe")
		self.assertTrue(timezone.is_aware(metadata["pdf_creation_date"]))


class EngineTests(BaseModelFactoryMixin, TestCase):
	def test_chat_returns_llm_content(self):
		class FakeResponse:
			content = "model-answer"

		class FakeLLM:
			def invoke(self, prompt):
				return FakeResponse()

		with patch("rag.engine.context_retriever", return_value="ctx"), patch("rag.engine.get_llm", return_value=FakeLLM()):
			result = chat(1, "What?")

		self.assertEqual(result, "model-answer")

	def test_analyze_resume_uses_cache(self):
		document = self.make_document(suffix="11")
		cache_key = f"analysis:{document.id}:{document.file_hash}"
		LLMCache.objects.create(
			key=cache_key,
			cache_type=LLMCache.CACHE_TYPE_ANALYSIS,
			document=document,
			value_text="cached",
		)

		with patch("rag.engine.get_llm") as llm_mock:
			result = analyze_resume(document.id)

		self.assertEqual(result, "cached")
		llm_mock.assert_not_called()

	def test_analyze_resume_writes_cache(self):
		document = self.make_document(suffix="12")

		class FakeResponse:
			content = "new-analysis"

		class FakeLLM:
			def invoke(self, prompt):
				return FakeResponse()

		with patch("rag.engine.context_retriever", return_value="ctx"), patch("rag.engine.get_llm", return_value=FakeLLM()):
			result = analyze_resume(document.id)

		self.assertEqual(result, "new-analysis")
		cache_key = f"analysis:{document.id}:{document.file_hash}"
		self.assertTrue(LLMCache.objects.filter(key=cache_key).exists())

	def test_rank_candidates_fallback_for_bad_json(self):
		self.make_document(suffix="13")

		class FakeResponse:
			content = "not-json"

		class FakeLLM:
			def invoke(self, prompt):
				return FakeResponse()

		with patch("rag.engine.context_retriever", return_value="ctx"), patch("rag.engine.get_llm", return_value=FakeLLM()):
			results = rank_candidates("backend")

		self.assertEqual(len(results), 1)
		self.assertEqual(results[0]["score"], 0)

	def test_rank_candidates_uses_cached_json(self):
		document = self.make_document(suffix="14")
		job_description = "backend"
		job_hash = hashlib.sha256(job_description.encode("utf-8")).hexdigest()
		cache_key = f"ranking:{document.id}:{document.file_hash}:{job_hash}"
		LLMCache.objects.create(
			key=cache_key,
			cache_type=LLMCache.CACHE_TYPE_RANKING,
			document=document,
			value_json={
				"score": 88,
				"summary": "cached",
				"strengths": ["python"],
				"missing_skills": [],
				"recommendation": "interview",
			},
		)

		with patch("rag.engine.get_llm") as llm_mock:
			results = rank_candidates(job_description)

		self.assertEqual(results[0]["score"], 88)
		llm_mock.assert_not_called()


class OrchestratorAndTaskTests(BaseModelFactoryMixin, TestCase):
	def test_register_upload_duplicate_hash_is_skipped(self):
		file_bytes = b"same-bytes"
		file_hash = hashlib.sha256(file_bytes).hexdigest()
		existing = self.make_document(suffix="15")
		existing.file_hash = file_hash
		existing.save(update_fields=["file_hash"])

		result = register_upload(SimpleUploadedFile("resume.pdf", b"%PDF"), file_bytes, batch="")

		self.assertEqual(result["status"], "skipped")

	def test_register_upload_rejects_missing_email(self):
		with patch(
			"rag.orchestrator.get_candidate_metadata",
			return_value={"email": "Unknown Email", "name": "N/A", "pdf_creation_date": timezone.now()},
		):
			result = register_upload(SimpleUploadedFile("resume.pdf", b"%PDF"), b"new-bytes", batch="")

		self.assertEqual(result["status"], "rejected")

	def test_register_upload_updates_existing_candidate_when_newer(self):
		existing = self.make_document(suffix="16")
		existing.candidate_email = "person@example.com"
		existing.created_at = timezone.now() - timedelta(days=3)
		existing.save(update_fields=["candidate_email", "created_at"])

		new_date = timezone.now() - timedelta(days=1)
		with patch(
			"rag.orchestrator.get_candidate_metadata",
			return_value={"email": "person@example.com", "name": "Updated", "pdf_creation_date": new_date},
		):
			result = register_upload(SimpleUploadedFile("resume-new.pdf", b"%PDF"), b"unique-bytes", batch="october")

		existing.refresh_from_db()
		self.assertEqual(result["status"], "queued")
		self.assertEqual(existing.candidate_name, "Updated")
		self.assertEqual(existing.batch.name, "october")
		self.assertFalse(existing.processed)

	def test_register_upload_skips_if_existing_resume_is_newer(self):
		existing = self.make_document(suffix="17")
		existing.candidate_email = "older@example.com"
		existing.created_at = timezone.now()
		existing.save(update_fields=["candidate_email", "created_at"])

		older_date = timezone.now() - timedelta(days=2)
		with patch(
			"rag.orchestrator.get_candidate_metadata",
			return_value={"email": "older@example.com", "name": "Older", "pdf_creation_date": older_date},
		):
			result = register_upload(SimpleUploadedFile("resume-old.pdf", b"%PDF"), b"bytes-old", batch="")

		self.assertEqual(result["status"], "skipped")

	def test_process_document_marks_processed_and_saves_chunks(self):
		document = self.make_document(suffix="18", processed=False)
		chunks = [SimpleNamespace(metadata={}), SimpleNamespace(metadata={})]

		with patch("rag.orchestrator.load_pdf", return_value=["page"]), patch(
			"rag.orchestrator.split_documents", return_value=chunks
		), patch("rag.orchestrator.upsert_document_chunks", return_value=2) as upsert_mock:
			result = process_document(document.id)

		document.refresh_from_db()
		self.assertEqual(result.id, document.id)
		self.assertTrue(document.processed)
		upsert_mock.assert_called_once_with(document.id, chunks)
		self.assertEqual(chunks[0].metadata["document_id"], document.id)

	def test_process_upload_short_circuits_when_not_queued(self):
		with patch("rag.orchestrator.register_upload", return_value={"status": "skipped", "message": "duplicate"}) as reg_mock, patch(
			"rag.orchestrator.process_document"
		) as proc_mock:
			result = process_upload(SimpleUploadedFile("resume.pdf", b"%PDF"), b"bytes")

		self.assertEqual(result["status"], "skipped")
		reg_mock.assert_called_once()
		proc_mock.assert_not_called()

	def test_process_upload_processes_when_queued(self):
		document = self.make_document(suffix="19")
		with patch("rag.orchestrator.register_upload", return_value={"status": "queued", "document": document}) as reg_mock, patch(
			"rag.orchestrator.process_document", return_value=document
		) as proc_mock:
			result = process_upload(SimpleUploadedFile("resume.pdf", b"%PDF"), b"bytes")

		self.assertEqual(result.id, document.id)
		reg_mock.assert_called_once()
		proc_mock.assert_called_once_with(document.id)

	def test_process_resume_task_processed(self):
		with patch("rag.tasks.pdf_processing.process_document", return_value=None) as process_mock:
			result = process_resume.run(100)

		self.assertEqual(result, {"document_id": 100, "status": "processed"})
		process_mock.assert_called_once_with(100)

	def test_process_resume_task_missing_document(self):
		with patch("rag.tasks.pdf_processing.process_document", side_effect=ObjectDoesNotExist):
			result = process_resume.run(101)

		self.assertEqual(result, {"document_id": 101, "status": "missing"})
