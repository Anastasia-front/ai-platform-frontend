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

## Infrastructure

Frontend infrastructure lives in `infra/` and mirrors the backend Terraform
layout:

- `provider.tf` uses the AWS provider and variable-driven `aws_region`.
- `backend.tf` uses local Terraform state, matching the backend repository.
- `main.tf` composes small modules for network, IAM, EC2, ECR, and SSM.
- environment-specific runtime config is written to SSM Parameter Store as
  `SecureString` values under `/${project_name}-frontend`.

Create an environment-specific `infra/terraform.tfvars` from
`infra/terraform.tfvars.example` and set:

- AWS placement and access values such as `aws_region`, `ec2_ami`, `key_name`,
  `ssh_allowed_cidrs`, and `http_allowed_cidrs`.
- `backend_base_api_url`, which Terraform injects as `BASE_API_URL`.
- `google_client_id`, which Terraform injects as `GOOGLE_CLIENT_ID`.
- secret and runtime values in `env_values`, such as `SECRET_KEY`,
  `GOOGLE_CLIENT_SECRET`, `DEBUG`, `ALLOWED_HOSTS`, and backend timeout values.

Deploy infrastructure:

```bash
cd infra
terraform init
terraform plan
terraform apply
```

The frontend EC2 instance reads container images from ECR and receives runtime
configuration through the same SSM-to-`.env` deployment strategy used by the
backend.

## CI/CD

The GitHub Actions workflow in `.github/workflows/deploy.yml` builds the
frontend Docker image, pushes it to ECR, then deploys to EC2 through SSM.
The production container starts with Gunicorn on container port `8001` and is
published only on EC2 loopback with:

```text
127.0.0.1:8001:8001
```

Keep `localhost` and `127.0.0.1` in production `ALLOWED_HOSTS` because the EC2
deployment health check calls `http://127.0.0.1:8001/login/` with
`Host: 127.0.0.1`. The deployment also mounts
`ai-platform-frontend-data:/app/data` and sets `SQLITE_PATH=/app/data/db.sqlite3`
so SQLite migration state persists across replacement containers and rollback.

## Production Nginx and Cloudflare

Nginx runs on the EC2 host and proxies public traffic to the private Docker
binding at `http://127.0.0.1:8001`. Use the repository-managed config at
`deploy/nginx/ai-platform-frontend.conf`:

```bash
sudo cp deploy/nginx/ai-platform-frontend.conf /etc/nginx/sites-available/ai-platform-frontend
sudo ln -sfn /etc/nginx/sites-available/ai-platform-frontend /etc/nginx/sites-enabled/ai-platform-frontend
sudo nginx -t
sudo systemctl reload nginx
```

Cloudflare DNS should point the public hostnames to the EC2 public IPv4 address:

```text
Type: A      Name: @    Content: <EC2 public IPv4>       Proxy status: Proxied
Type: CNAME  Name: www  Target: ai-automation-platform.com  Proxy status: Proxied
```

Prefer Cloudflare SSL mode `Full (strict)`. Install either a public certificate
with Let's Encrypt/Certbot or a Cloudflare Origin Certificate on Nginx; do not
commit certificate private keys. Avoid Cloudflare `Flexible` because it can
create redirect loops and leaves Cloudflare-to-origin traffic unencrypted.

The EC2 security group should allow inbound TCP `80` and `443` to Nginx, and SSH
only from approved CIDR ranges. Do not open public inbound `8000` or `8001`; the
Docker container is reachable only from the host through loopback.

Production SSM environment values should include:

```env
DEBUG=False
ALLOWED_HOSTS=127.0.0.1,localhost,ai-automation-platform.com,www.ai-automation-platform.com
CSRF_TRUSTED_ORIGINS=https://ai-automation-platform.com,https://www.ai-automation-platform.com
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SQLITE_PATH=/app/data/db.sqlite3
```

Useful production checks:

```bash
curl -i -H "Host: 127.0.0.1" http://127.0.0.1:8001/login/
curl -i -H "Host: ai-automation-platform.com" http://127.0.0.1/health/
curl -I https://ai-automation-platform.com/health/
```

Required GitHub secrets:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `EC2_INSTANCE_ID`

Required GitHub repository variables:

- `AWS_REGION`, for example `eu-central-1`
- `ECR_REGISTRY`, for example `<account-id>.dkr.ecr.eu-central-1.amazonaws.com`
- `ECR_REPOSITORY`, for example `ai-platform-frontend`
- `SSM_PARAMETER_PATH`, for example `/ai-platform-frontend`

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
