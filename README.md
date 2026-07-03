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

The backend API should be available at `BASE_API_URL`.
