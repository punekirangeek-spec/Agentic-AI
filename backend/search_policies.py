import os
from dotenv import load_dotenv
from google import genai
import chromadb

load_dotenv()

CHROMA_DIR = "chroma_db"
COLLECTION_NAME = "hr_policies"
EMBEDDING_MODEL = "gemini-embedding-001"

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)


def get_embedding(text):
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text
    )
    return result.embeddings[0].values


def search_policy(query, top_k=3):
    query_embedding = get_embedding(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    matches = []
    for doc, meta, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        matches.append({
            "text": doc,
            "source": meta["source"],
            "distance": distance
        })

    return matches


if __name__ == "__main__":
    # Quick manual test
    test_query = "How many paternity leaves can I take?"
    print(f"Query: {test_query}\n")

    results = search_policy(test_query)
    for i, r in enumerate(results, 1):
        print(f"--- Match {i} (source: {r['source']}, distance: {r['distance']:.4f}) ---")
        print(r["text"])
        print()