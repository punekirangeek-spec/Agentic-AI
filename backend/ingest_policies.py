import os
from pathlib import Path
from dotenv import load_dotenv
from pypdf import PdfReader
from google import genai
import chromadb

load_dotenv()

# --- Config ---
POLICY_DIR = Path("policy_docs")
CHROMA_DIR = "chroma_db"
COLLECTION_NAME = "hr_policies"
EMBEDDING_MODEL = "gemini-embedding-001"

# --- Setup clients ---
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)


def extract_text_from_pdf(filepath):
    reader = PdfReader(filepath)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text


def chunk_text(text, chunk_size=800, overlap=100):
    """
    Splits text into overlapping chunks of roughly `chunk_size` characters.
    Overlap helps preserve context across chunk boundaries.
    """
    text = " ".join(text.split())  # normalize whitespace
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def get_embedding(text):
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text
    )
    return result.embeddings[0].values


def ingest_all_policies():
    pdf_files = list(POLICY_DIR.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF(s) in {POLICY_DIR}")

    doc_id_counter = 0

    for pdf_path in pdf_files:
        print(f"\nProcessing: {pdf_path.name}")
        text = extract_text_from_pdf(pdf_path)
        chunks = chunk_text(text)
        print(f"  → {len(chunks)} chunks extracted")

        for chunk in chunks:
            embedding = get_embedding(chunk)
            doc_id_counter += 1

            collection.add(
                ids=[f"doc_{doc_id_counter}"],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{"source": pdf_path.name}]
            )

    print(f"\nDone. Total chunks stored: {doc_id_counter}")


if __name__ == "__main__":
    ingest_all_policies()