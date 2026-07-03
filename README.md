# AI Platform Frontend

Django server-rendered frontend for the AI Workflow Automation Platform.

## Local Development

1. Create or update `.env`:

```env
BASE_API_URL=http://localhost:8000
BASE_API_TOKEN=
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
SECRET_KEY=change-me
```

2. Install dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Run the Django frontend on port `8001`:

```bash
python manage.py runserver 8001
```

The backend API should be available at `BASE_API_URL`. Protected backend endpoints also need `BASE_API_TOKEN`.

## Backend Endpoints

The main FastAPI endpoints discovered in `../ai-platform-backend/app/api` are:

- Health: `GET /health`
- Auth: `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- Projects: `GET /projects/`, `GET /projects/{project_id}`, `POST /projects/{project_id}/retrieve`
- Workflows: `GET /projects/{project_id}/workflows`, `GET /workflows/{workflow_id}`, `POST /workflows/{workflow_id}/run`
- Executions: `GET /runs/{run_id}`, `GET /runs/{run_id}/events`, `POST /runs/{run_id}/resume`
- Documents: `GET /projects/{project_id}/documents`, `GET /documents/{document_id}/chunks`, `POST /documents/{document_id}/process`
- Providers: `POST /documents/{document_id}/embeddings/rebuild`, `POST /projects/{project_id}/embeddings/sync`
