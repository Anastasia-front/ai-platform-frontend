# AI Platform Frontend

Django server-rendered frontend for the AI Workflow Automation Platform.

## Local Development

1. Create or update `.env`:

```env
BASE_API_URL=http://localhost:8000
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

The backend API should be available at `BASE_API_URL`. JWT access tokens are stored server-side in the Django session after login.

## Implemented Frontend Flow

- Login, logout, and registration via the FastAPI auth endpoints.
- Project list, create, open, and delete.
- Project workspace with a left sidebar for projects and chats.
- Chat create, open, delete, message list, and message send.
- Document list, upload, and delete for a project.
- Graceful backend error handling, including expired-token cleanup.

## Backend Endpoints

The main FastAPI endpoints discovered in `../ai-platform-backend/app/api` are:

- Health: `GET /health`
- Auth: `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- Projects: `GET /projects/`, `POST /projects/`, `GET /projects/{project_id}`, `DELETE /projects/{project_id}`, `POST /projects/{project_id}/retrieve`
- Chats: `GET /projects/{project_id}/chats`, `POST /projects/{project_id}/chats`, `GET /chats/{chat_id}`, `DELETE /chats/{chat_id}`
- Messages: `GET /chats/{chat_id}/messages`, `POST /chats/{chat_id}/messages`
- Workflows: `GET /projects/{project_id}/workflows`, `GET /workflows/{workflow_id}`, `POST /workflows/{workflow_id}/run`
- Executions: `GET /runs/{run_id}`, `GET /runs/{run_id}/events`, `POST /runs/{run_id}/resume`
- Documents: `GET /projects/{project_id}/documents`, `POST /projects/{project_id}/documents`, `DELETE /documents/{document_id}`, `GET /documents/{document_id}/chunks`, `POST /documents/{document_id}/process`
- Providers: `POST /documents/{document_id}/embeddings/rebuild`, `POST /projects/{project_id}/embeddings/sync`
