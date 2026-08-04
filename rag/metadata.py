import re
from datetime import datetime
import pdfplumber
from django.utils import timezone

#AI GENRATED CODE

def parse_pdf_date(raw_date_str):
    """
    Parses a raw PDF creation date string (e.g., 'D:20260718121542') or generic metadata 
    strings into a timezone-aware Python datetime object that Django's DateTimeField expects.
    """
    if not raw_date_str or not isinstance(raw_date_str, str):
        return timezone.now()

    try:
        # If it's the standard Adobe format (starts with D:), normalize it
        if raw_date_str.startswith("D:"):
            # Strip away all non-digits and isolate the first 14 numbers (YYYYMMDDHHMMSS)
            clean_digits = re.sub(r'\D', '', raw_date_str)[:14]
            
            # Make sure we have at least the date components before building the timestamp
            if len(clean_digits) >= 8:
                # Pad out missing hour/minute/second slots with zeros if necessary
                clean_digits = clean_digits.ljust(14, '0')
                naive_dt = datetime.strptime(clean_digits, '%Y%m%d%H%M%S')
                return timezone.make_aware(naive_dt, timezone.get_current_timezone())
        
        # Fallback parsing attempt if the string is clean but doesn't have the "D:" prefix
        # (Handles basic ISO strings or standard date shapes gracefully)
        clean_iso = raw_date_str.replace("Z", "").split(".")[0] # strip UTC/millisecond details if present
        naive_dt = datetime.fromisoformat(clean_iso)
        if timezone.is_naive(naive_dt):
            return timezone.make_aware(naive_dt, timezone.get_current_timezone())
        return naive_dt

    except Exception:
        # Fallback to the current database-configured operational timestamp if parsing fails
        return timezone.now()


def get_candidate_metadata(pdf):
    pdf.seek(0) 
    
    full_text = ""
    pdf_date = None
    
    with pdfplumber.open(pdf) as pdf_reader:
        # Extract internal PDF metadata (like creation date) safely
        if pdf_reader.metadata:
            # pdfplumber metadata often stores dates under 'CreationDate'
            pdf_date = pdf_reader.metadata.get('CreationDate') or pdf_reader.metadata.get('date')
            
        for page in pdf_reader.pages:
            full_text += page.extract_text() or ""

    # Normalize the extracted date into a timezone-aware datetime object immediately
    normalized_date = parse_pdf_date(pdf_date)

    metadata = {
        "name": "Unknown Candidate",
        "email": "Unknown Email",
        "pdf_creation_date": normalized_date  # Securely formatted datetime object
    }
    
    # 1. Extract Email
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', full_text)
    if email_match:
        metadata["email"] = email_match.group(0).strip()

    # 2. Extract Name
    label_match = re.search(r"Name:\s*([A-Za-z\s\-\.]+)", full_text)
    if label_match:
        metadata["name"] = label_match.group(1).strip()
    else:
        lines = [line.strip() for line in full_text.split('\n') if line.strip()]
        if lines:
            if "@" not in lines[0] and len(lines[0]) < 50:
                metadata["name"] = lines[0]

    return metadata