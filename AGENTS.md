# AI Platform Frontend Context

This repository is the Django frontend for the AI Workflow Automation Platform.

Backend repository:
https://github.com/Anastasia-front/ai-platform-backend

Backend is a separate FastAPI API service.

Production API base URL:
http://ec2-3-75-228-59.eu-central-1.compute.amazonaws.com

Important:

- Do not use /docs as BASE_API_URL.
- /docs is only Swagger UI.
- Frontend must call backend API endpoints.
- Do not duplicate backend business logic in Django.
- Django is used for server-rendered frontend pages.
- Use Python requests/httpx to call the backend.
- Store backend URL in environment variable BASE_API_URL.
