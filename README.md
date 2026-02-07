# RapidScan AI – Backend

Flask API for chest X-ray triage: vision model (torchxrayvision), Gemini LLM, and hybrid RAG with Weaviate.

- **Setup:** Copy `.env.example` to `.env` and set `GEMINI_API_KEY`. Install deps: `pip install -r requirements.txt`.
- **Run:** `python app.py` (default port 5001). Optional: `docker compose -f docker-compose-weaviate.yml up -d` for Weaviate, then `POST /admin/seed-weaviate` to seed RAG.
- **Full docs:** [STATUS.md](STATUS.md) – API, DB, RAG, and deployment.
