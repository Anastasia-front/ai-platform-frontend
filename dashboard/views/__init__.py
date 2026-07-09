from ..services import backend_api
from .utils import parse_contract_review_output, parse_job_vacancy_output

from .auth import (
    google_login_callback,
    google_login_start,
    index,
    login_view,
    logout_view,
    register_view,
)
from .chats import chat_detail, delete_chat, new_chat, send_chat_message
from .documents import delete_document, process_document, upload_document
from .executions import execution_detail, executions
from .projects import delete_project, new_project, project_detail, projects
from .providers import (
    check_provider_health,
    providers,
    rebuild_document_embeddings,
    sync_embeddings,
    update_chat_provider,
    update_embedding_provider,
)
from .settings import settings_function
from .workflows import (
    create_workflow,
    create_workflow_step,
    delete_workflow,
    delete_workflow_step,
    run_contract_review,
    run_job_vacancy,
    run_workflow,
    setup_contract_review,
    setup_job_vacancy,
    workflows,
)
