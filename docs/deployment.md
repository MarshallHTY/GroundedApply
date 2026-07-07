# Deployment notes

## Local Streamlit

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m streamlit run app.py
```

Use **Local semantic rules** for a no-key demo, or **Gemini semantic matcher** when `GOOGLE_API_KEY` is set.

## Docker

```bash
docker build -t groundedapply .
docker run -p 8501:8501 groundedapply
```

## Optional Cloud Run source deploy

```bash
gcloud run deploy groundedapply \
  --source . \
  --region europe-west2 \
  --allow-unauthenticated
```

The deterministic pipeline runs without API keys. Add `GOOGLE_API_KEY` to exercise the live ADK/Gemini path:

```bash
export GOOGLE_API_KEY="your-api-key"
python -m streamlit run app.py
```

In Windows PowerShell:

```powershell
$env:GOOGLE_API_KEY="your-api-key"
python -m streamlit run app.py
```
