from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from core.models import Batch, Document
from .serializer import AnalyzeSerializer, BatchSerializer, CandidateRankingSerializer, UploadPDFSerializer, ChatSerializer, DocumentListSerializer
from rag import orchestrator
from rag.engine import analyze_resume, chat, rank_candidates
from rag.tasks import process_resume


class BatchListView(APIView):
    def get(self, request):
        batches = Batch.objects.order_by("name")
        serializer = BatchSerializer(batches, many=True)
        return Response(serializer.data)


class DocumentListView(APIView):
    def get(self, request):
        batch_id = request.query_params.get("batch_id") or request.query_params.get("batch")
        documents = Document.objects.order_by("candidate_name", "-uploaded_at", "-id")
        if batch_id:
            documents = documents.filter(batch__id=batch_id)
        serializer = DocumentListSerializer(documents, many=True)
        return Response(serializer.data)

class UploadPDFView(APIView):

    def post(self, request):
        serializer = UploadPDFSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pdfs = serializer.validated_data.get('pdf', [])
        batch = serializer.validated_data.get('batch', None)
        if not pdfs:
            return Response(
                {"error": "No PDFs provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

        totals = {
            'accepted': 0,
            'rejected': 0,
            'skipped': 0,
        }
        processed_items = []
        
        for pdf in pdfs:
            file_bytes = pdf.read()
            pdf.seek(0)

            registration = orchestrator.register_upload(pdf, file_bytes, batch)
            reg_status = registration.get("status")

            if reg_status == "queued":
                totals['accepted'] += 1
                document = registration["document"]
                task = process_resume.delay(document.id)
                processed_items.append({
                    "filename": pdf.name,
                    "status": "accepted",
                    "document_id": document.id,
                    "task_id": task.id,
                })

            elif reg_status == "rejected":
                totals['rejected'] += 1
                processed_items.append({
                    "filename": pdf.name,
                    "status": "rejected",
                    "reason": registration.get("message"),
                })

            else:  # skipped / duplicate
                totals['skipped'] += 1
                processed_items.append({
                    "filename": pdf.name,
                    "status": "skipped",
                    "reason": registration.get("message"),
                })

        return Response(
            {
                "totals": totals,
                "details": processed_items,
            },
            status=status.HTTP_200_OK,
        )
    
class ChatView(APIView):
    def post(self, request):
        serializer = ChatSerializer(data = request.data)
        serializer.is_valid(raise_exception=True)
         
        document_id = serializer.validated_data['document_id'] 
        question = serializer.validated_data['question']
        answer = chat(document_id, question)

        return Response(
            {
                'answer' : answer,
            },

            status = status.HTTP_200_OK 
        )
        

class AnalyzeResumeView(APIView):
    def post(self, request):
        serializer = AnalyzeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        document_id = serializer.validated_data["document_id"]
        result = analyze_resume(document_id)

        return Response({
            "analysis": result
        })
    

class CandidateRankingView(APIView):

    def post(self, request):
        serializer = CandidateRankingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        job_description = serializer.validated_data["job_description"]

        batch = request.data.get("batch", None)
        if batch:
            ranking = rank_candidates(job_description, batch=batch)
        else:
            ranking = rank_candidates(job_description)

        return Response(ranking)