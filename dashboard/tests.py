from importlib import import_module
from unittest.mock import patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from dashboard.services.backend_api import BackendAPIError
from dashboard.templatetags.markdown_extras import (
    human_datetime,
    render_markdown,
    truncate_chars,
)
from dashboard.views import parse_contract_review_output, parse_job_vacancy_output
from dashboard.views.utils import redact_secrets, summarize_workflow_run


class TemplateFilterTests(TestCase):
    def test_human_datetime_formats_iso_timestamp(self):
        self.assertEqual(
            human_datetime("2026-07-10T11:49:52.231888Z"),
            "10/07/2026 - 11:49",
        )

    def test_human_datetime_formats_date_only_value(self):
        self.assertEqual(human_datetime("2026-07-05"), "05/07/2026 - 00:00")

    def test_truncate_chars_caps_text_with_ellipsis(self):
        self.assertEqual(truncate_chars("abcdefghij", 8), "abcde...")
        self.assertEqual(truncate_chars("abcdefgh", 8), "abcdefgh")


class SecretRedactionTests(TestCase):
    def test_redact_secrets_masks_sensitive_strings_and_fields(self):
        value = {
            "url": (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                "gemini:generateContent?key=AIzaSyA7y33CG1R3yGylCPBU-y00Wkjw-aQG5WU"
            ),
            "GOOGLE_API_KEY": "AIzaSyA7y33CG1R3yGylCPBU-y00Wkjw-aQG5WU",
            "nested": [
                {
                    "error": (
                        "api_key='secret-value' password=hunter2 "
                        "OPENAI_API_KEY=sk-project-secret"
                    )
                }
            ],
        }

        redacted = redact_secrets(value)

        self.assertNotIn("AIzaSyA7y33CG1R3yGylCPBU-y00Wkjw-aQG5WU", str(redacted))
        self.assertNotIn("secret-value", str(redacted))
        self.assertNotIn("hunter2", str(redacted))
        self.assertNotIn("sk-project-secret", str(redacted))
        self.assertEqual(redacted["GOOGLE_API_KEY"], "[redacted]")
        self.assertIn("?key=[redacted]", redacted["url"])


class AuthViewTests(TestCase):
    @patch("dashboard.views.backend_api.get_current_user")
    @patch("dashboard.views.backend_api.login")
    def test_login_stores_access_token_in_session(
        self, mock_login, mock_get_current_user
    ):
        mock_login.return_value = {"access_token": "token-123", "token_type": "bearer"}
        mock_get_current_user.return_value = {"email": "ana@example.com"}

        response = self.client.post(
            reverse("dashboard:login"),
            {"email": "ana@example.com", "password": "secret"},
        )

        self.assertRedirects(response, reverse("dashboard:projects"))
        self.assertEqual(self.client.session["access_token"], "token-123")
        mock_login.assert_called_once_with("ana@example.com", "secret")

    def test_projects_redirects_to_login_without_token(self):
        response = self.client.get(reverse("dashboard:projects"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("dashboard:login"), response["Location"])


class ProjectViewTests(TestCase):
    def setUp(self):
        engine = import_module(settings.SESSION_ENGINE)
        session = engine.SessionStore()
        session["access_token"] = "token-123"
        session["user"] = {"email": "ana@example.com"}
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    @patch("dashboard.views.backend_api.list_projects")
    def test_project_list_uses_backend_projects(self, mock_list_projects):
        mock_list_projects.return_value = [
            {
                "id": 1,
                "name": "Research",
                "description": "Knowledge workflows",
                "user_id": 2,
                "created_at": "2026-07-03T09:00:00",
            }
        ]

        response = self.client.get(reverse("dashboard:projects"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Research")
        self.assertContains(response, "/projects/research/")
        mock_list_projects.assert_called_with("token-123")

    @patch("dashboard.views.backend_api.create_project")
    @patch("dashboard.views.backend_api.list_projects")
    def test_create_project_redirects_to_project_workspace(
        self,
        mock_list_projects,
        mock_create_project,
    ):
        mock_list_projects.return_value = []
        mock_create_project.return_value = {"id": 7, "name": "New project"}

        response = self.client.post(
            reverse("dashboard:new_project"),
            {"name": "New project", "description": "Draft"},
        )

        self.assertRedirects(
            response,
            reverse("dashboard:project_detail", args=["new-project"]),
            fetch_redirect_response=False,
        )
        mock_create_project.assert_called_once_with("token-123", "New project", "Draft")

    @patch("dashboard.views.backend_api.list_project_documents")
    @patch("dashboard.views.backend_api.list_project_chats")
    @patch("dashboard.views.backend_api.list_projects")
    def test_open_project_renders_empty_chat_ui(
        self,
        mock_list_projects,
        mock_list_project_chats,
        mock_list_project_documents,
    ):
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]
        mock_list_project_chats.return_value = []
        mock_list_project_documents.return_value = [
            {"id": 7, "filename": "brief.pdf", "status": "processed", "text": "Ready"}
        ]

        response = self.client.get(
            reverse("dashboard:project_detail", args=["research"])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Start a chat")
        self.assertContains(response, "No chat selected")

    @patch("dashboard.views.backend_api.list_projects")
    def test_project_list_handles_backend_error(self, mock_list_projects):
        mock_list_projects.side_effect = BackendAPIError("backend down")

        response = self.client.get(reverse("dashboard:projects"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "backend down")

    @patch("dashboard.views.backend_api.list_projects")
    @patch("dashboard.views.backend_api.create_chat")
    def test_create_chat_defaults_to_assistant_agent(
        self, mock_create_chat, mock_list_projects
    ):
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]
        mock_create_chat.return_value = {"id": 9, "title": "Build helper"}

        response = self.client.post(
            reverse("dashboard:new_chat", args=["research"]),
            {"title": "Build helper"},
        )

        self.assertRedirects(
            response,
            reverse("dashboard:chat_detail", args=["research", "build-helper"]),
            fetch_redirect_response=False,
        )
        mock_create_chat.assert_called_once_with(
            "token-123",
            1,
            "Build helper",
            agent_name="assistant",
        )

    @patch("dashboard.views.backend_api.list_project_documents")
    @patch("dashboard.views.backend_api.list_project_chats")
    @patch("dashboard.views.backend_api.list_projects")
    def test_project_workspace_has_no_create_chat_agent_selector(
        self,
        mock_list_projects,
        mock_list_project_chats,
        mock_list_project_documents,
    ):
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]
        mock_list_project_chats.return_value = []
        mock_list_project_documents.return_value = []

        response = self.client.get(
            reverse("dashboard:project_detail", args=["research"])
        )

        self.assertNotContains(response, 'name="agent_name"')

    @patch("dashboard.views.backend_api.process_document")
    @patch("dashboard.views.backend_api.upload_document")
    @patch("dashboard.views.backend_api.list_projects")
    def test_upload_document_processes_file_and_returns_to_current_page(
        self,
        mock_list_projects,
        mock_upload_document,
        mock_process_document,
    ):
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]
        mock_upload_document.return_value = {"id": 42, "filename": "notes.txt"}
        uploaded_file = SimpleUploadedFile(
            "notes.txt", b"hello", content_type="text/plain"
        )
        next_url = "/projects/research/chats/first-chat/"

        response = self.client.post(
            reverse("dashboard:upload_document", args=["research"]),
            {"file": uploaded_file, "next": next_url},
        )

        self.assertRedirects(response, next_url, fetch_redirect_response=False)
        mock_upload_document.assert_called_once()
        mock_process_document.assert_called_once_with("token-123", 42)

    @patch("dashboard.views.backend_api.delete_document")
    @patch("dashboard.views.backend_api.list_projects")
    def test_delete_document_returns_to_current_page(
        self, mock_list_projects, mock_delete_document
    ):
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]
        next_url = "/projects/research/chats/first-chat/"

        response = self.client.post(
            reverse("dashboard:delete_document", args=["research", 42]),
            {"next": next_url},
        )

        self.assertRedirects(response, next_url, fetch_redirect_response=False)
        mock_delete_document.assert_called_once_with("token-123", 42)

    @patch("dashboard.views.backend_api.process_document")
    @patch("dashboard.views.backend_api.list_projects")
    def test_process_document_returns_to_current_page(
        self,
        mock_list_projects,
        mock_process_document,
    ):
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]
        next_url = "/workflows/?project=research&workflow=contract-review"

        response = self.client.post(
            reverse("dashboard:process_document", args=["research", 42]),
            {"next": next_url},
        )

        self.assertRedirects(response, next_url, fetch_redirect_response=False)
        mock_process_document.assert_called_once_with("token-123", 42)

    @patch("dashboard.views.backend_api.list_messages")
    @patch("dashboard.views.backend_api.send_message")
    @patch("dashboard.views.backend_api.list_project_chats")
    @patch("dashboard.views.backend_api.list_projects")
    def test_send_message_passes_agent_override(
        self,
        mock_list_projects,
        mock_list_project_chats,
        mock_send_message,
        mock_list_messages,
    ):
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]
        mock_list_project_chats.return_value = [{"id": 9, "title": "Build helper"}]
        mock_list_messages.return_value = []

        response = self.client.post(
            reverse("dashboard:send_chat_message", args=["research", "build-helper"]),
            {"content": "Explain this", "agent_name": "coding"},
        )

        self.assertRedirects(
            response,
            reverse("dashboard:chat_detail", args=["research", "build-helper"]),
            fetch_redirect_response=False,
        )
        mock_send_message.assert_called_once_with(
            "token-123",
            9,
            "Explain this",
            agent_name="coding",
        )


class MarkdownRenderingTests(TestCase):
    def test_assistant_markdown_renders_as_html(self):
        rendered = render_markdown("**Bold** and *italic* with `code`\n- one\n- two")

        self.assertIn("<strong>Bold</strong>", rendered)
        self.assertIn("<em>italic</em>", rendered)
        self.assertIn("<code>code</code>", rendered)
        self.assertIn("<li>one</li>", rendered)

    def test_assistant_markdown_renders_headings_and_rules(self):
        rendered = render_markdown(
            "Error Handling Workflow\n\n=========================\n\n"
            "In this example, we will create a workflow.\n\n"
            "### Service Classes\n\n---"
        )

        self.assertIn("<h1>Error Handling Workflow</h1>", rendered)
        self.assertIn("<h3>Service Classes</h3>", rendered)
        self.assertIn("<hr>", rendered)


class ProviderViewTests(TestCase):
    def setUp(self):
        engine = import_module(settings.SESSION_ENGINE)
        session = engine.SessionStore()
        session["access_token"] = "token-123"
        session["user"] = {"email": "ana@example.com"}
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    @patch("dashboard.views.backend_api.list_project_documents")
    @patch("dashboard.views.backend_api.get_providers")
    @patch("dashboard.views.backend_api.list_projects")
    def test_provider_page_renders_status_cards(
        self,
        mock_list_projects,
        mock_get_providers,
        mock_list_project_documents,
    ):
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]
        mock_list_project_documents.return_value = []
        mock_get_providers.return_value = provider_payload()

        response = self.client.get(reverse("dashboard:providers"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chat Providers")
        self.assertContains(response, "Embedding Providers")
        self.assertContains(response, "Save Chat Defaults")
        self.assertContains(response, "Sync Project Embeddings")
        self.assertContains(response, 'data-loading-form')
        self.assertContains(response, 'data-loading-label="Checking..."', count=3)
        self.assertContains(response, 'data-loading-label="Syncing..."')

    @patch("dashboard.views.backend_api.update_chat_provider_defaults")
    def test_update_chat_provider_saves_defaults(
        self, mock_update_chat_provider_defaults
    ):
        response = self.client.post(
            reverse("dashboard:update_chat_provider"),
            {
                "provider": "groq",
                "model": "llama-3.1",
                "fallback_model": "",
                "base_url": "https://api.groq.com/openai/v1",
                "api_key": "secret-key",
            },
        )

        self.assertRedirects(
            response,
            reverse("dashboard:providers"),
            fetch_redirect_response=False,
        )
        mock_update_chat_provider_defaults.assert_called_once_with(
            "token-123",
            provider="groq",
            model="llama-3.1",
            fallback_model="",
            base_url="https://api.groq.com/openai/v1",
            api_key="secret-key",
        )


class WorkflowViewTests(TestCase):
    def setUp(self):
        engine = import_module(settings.SESSION_ENGINE)
        session = engine.SessionStore()
        session["access_token"] = "token-123"
        session["user"] = {"email": "ana@example.com"}
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    @patch("dashboard.views.backend_api.list_workflow_steps")
    @patch("dashboard.views.backend_api.list_project_documents")
    @patch("dashboard.views.backend_api.list_project_workflows")
    @patch("dashboard.views.backend_api.list_projects")
    def test_workflows_page_renders_visual_steps(
        self,
        mock_list_projects,
        mock_list_project_workflows,
        mock_list_project_documents,
        mock_list_workflow_steps,
    ):
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]
        mock_list_project_workflows.return_value = [
            {
                "id": 3,
                "name": "Order Flow",
                "status": "running",
                "created_at": "2026-07-05",
            }
        ]
        mock_list_project_documents.return_value = []
        mock_list_workflow_steps.return_value = [
            {
                "id": 10,
                "workflow_id": 3,
                "step_order": 1,
                "name": "Validate order",
                "prompt_template": "Check the order",
                "depends_on": [],
                "condition": None,
            }
        ]

        response = self.client.get(
            f"{reverse('dashboard:workflows')}?project=research&workflow=order-flow"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Order Flow")
        self.assertContains(response, "Validate order")
        self.assertContains(response, "Run Workflow")

    @patch("dashboard.views.backend_api.create_workflow")
    @patch("dashboard.views.backend_api.list_projects")
    def test_create_workflow_redirects_to_visual_workspace(
        self,
        mock_list_projects,
        mock_create_workflow,
    ):
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]
        mock_create_workflow.return_value = {"id": 4, "name": "Order Flow"}

        response = self.client.post(
            reverse("dashboard:create_workflow", args=["research"]),
            {"name": "Order Flow"},
        )

        self.assertRedirects(
            response,
            f"{reverse('dashboard:workflows')}?project=research&workflow=order-flow",
            fetch_redirect_response=False,
        )
        mock_create_workflow.assert_called_once_with("token-123", 1, "Order Flow")

    @patch("dashboard.views.backend_api.create_workflow_step")
    @patch("dashboard.views.backend_api.list_workflow_steps")
    @patch("dashboard.views.backend_api.create_workflow")
    @patch("dashboard.views.backend_api.list_project_workflows")
    @patch("dashboard.views.backend_api.list_projects")
    def test_setup_contract_review_creates_template_steps(
        self,
        mock_list_projects,
        mock_list_project_workflows,
        mock_create_workflow,
        mock_list_workflow_steps,
        mock_create_workflow_step,
    ):
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]
        mock_list_project_workflows.return_value = []
        mock_create_workflow.return_value = {"id": 8, "name": "Contract review"}
        mock_list_workflow_steps.return_value = []
        mock_create_workflow_step.side_effect = [
            {"id": 101},
            {"id": 102},
            {"id": 103},
            {"id": 104},
        ]

        response = self.client.post(
            reverse("dashboard:setup_contract_review", args=["research"])
        )

        self.assertRedirects(
            response,
            f"{reverse('dashboard:workflows')}?project=research&workflow=contract-review&template=contract-review",
            fetch_redirect_response=False,
        )
        mock_create_workflow.assert_called_once_with("token-123", 1, "Contract review")
        self.assertEqual(mock_create_workflow_step.call_count, 4)
        self.assertEqual(
            mock_create_workflow_step.call_args_list[1].kwargs["depends_on"], [101]
        )

    @patch("dashboard.views.backend_api.run_workflow")
    @patch("dashboard.views.backend_api.list_project_documents")
    @patch("dashboard.views.backend_api.list_project_workflows")
    @patch("dashboard.views.backend_api.list_projects")
    def test_run_contract_review_uses_document_and_saves_structured_result(
        self,
        mock_list_projects,
        mock_list_project_workflows,
        mock_list_project_documents,
        mock_run_workflow,
    ):
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]
        mock_list_project_workflows.return_value = [
            {"id": 8, "name": "Contract review", "status": "running"}
        ]
        mock_list_project_documents.return_value = [
            {
                "id": 33,
                "filename": "contract.pdf",
                "text": "Contract starts on July 1 and renews yearly.",
            }
        ]
        mock_run_workflow.return_value = {
            "output": (
                '{"key_dates":[{"name":"Start date","date":"2026-07-01",'
                '"notes":"Agreement begins"}],"risk_level":"medium",'
                '"summary":"Annual renewal contract."}'
            )
        }

        response = self.client.post(
            reverse("dashboard:run_contract_review", args=["research"]),
            {"document_id": "33"},
        )

        self.assertRedirects(
            response,
            f"{reverse('dashboard:workflows')}?project=research&workflow=contract-review&template=contract-review",
            fetch_redirect_response=False,
        )
        mock_run_workflow.assert_called_once()
        self.assertIn("Contract starts on July 1", mock_run_workflow.call_args.args[2])
        self.assertNotIn("contract_review_result", self.client.session)

    @patch("dashboard.views.backend_api.run_workflow")
    @patch("dashboard.views.backend_api.list_project_documents")
    @patch("dashboard.views.backend_api.list_project_workflows")
    @patch("dashboard.views.backend_api.list_projects")
    def test_run_contract_review_stays_on_workflows_when_run_is_pending(
        self,
        mock_list_projects,
        mock_list_project_workflows,
        mock_list_project_documents,
        mock_run_workflow,
    ):
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]
        mock_list_project_workflows.return_value = [
            {"id": 8, "name": "Contract review", "status": "running"}
        ]
        mock_list_project_documents.return_value = [
            {"id": 33, "filename": "contract.pdf", "text": "Contract text."}
        ]
        mock_run_workflow.return_value = {"id": 77, "status": "pending", "output": None}

        response = self.client.post(
            reverse("dashboard:run_contract_review", args=["research"]),
            {"document_id": "33"},
        )

        self.assertRedirects(
            response,
            f"{reverse('dashboard:workflows')}?project=research&workflow=contract-review&template=contract-review",
            fetch_redirect_response=False,
        )
        self.assertNotIn("contract_review_result", self.client.session)

    @patch("dashboard.views.backend_api.list_workflow_runs")
    @patch("dashboard.views.backend_api.list_project_workflows")
    @patch("dashboard.views.backend_api.list_projects")
    def test_executions_list_renders_input_source_preview(
        self,
        mock_list_projects,
        mock_list_project_workflows,
        mock_list_workflow_runs,
    ):
        mock_list_projects.return_value = [{"id": 1, "name": "sop"}]
        mock_list_project_workflows.return_value = [
            {"id": 8, "name": "SOP / Process generator"}
        ]
        mock_list_workflow_runs.return_value = [
            {
                "id": 13,
                "workflow_id": 8,
                "status": "completed",
                "created_at": "2026-07-10T11:45:00Z",
                "input": (
                    "SOP / Process generator REQUEST\n\n"
                    "Document filename: sop_operations_manual_for_the_entire_european_operations_team_2026.docx\n\n..."
                ),
            }
        ]

        response = self.client.get(reverse("dashboard:executions"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Execution #13")
        self.assertContains(
            response,
            "Document filename: sop_operations_manual_for_the_entire_european_operations_t...",
        )
        self.assertNotContains(
            response,
            "Document filename: sop_operations_manual_for_the_entire_european_operations_team_2026.docx",
        )

    @patch("dashboard.views.backend_api.list_workflow_run_events")
    @patch("dashboard.views.backend_api.get_workflow_run")
    @patch("dashboard.views.backend_api.list_projects")
    def test_execution_detail_renders_contract_review_fields(
        self, mock_list_projects, mock_get_workflow_run, mock_list_events
    ):
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]
        mock_get_workflow_run.return_value = {
            "id": 77,
            "workflow_id": 8,
            "workflow_name": "Contract review",
            "status": "completed",
            "created_at": "2026-07-01T00:00:00Z",
            "input": "Contract review REQUEST\n\nDocument filename: contract.pdf\n\n...",
            "output": (
                '{"key_dates":[{"name":"Start date","date":"2026-07-01",'
                '"notes":"Agreement begins"}],"risk_level":"medium",'
                '"summary":"Annual renewal contract."}'
            ),
        }
        mock_list_events.return_value = []

        response = self.client.get(reverse("dashboard:execution_detail", args=[77]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Annual renewal contract.")
        self.assertContains(response, "medium")
        self.assertContains(response, "Start date")
        self.assertContains(response, "Document filename: contract.pdf")
        self.assertContains(response, "Contract review")

    @patch("dashboard.views.backend_api.list_workflow_run_events")
    @patch("dashboard.views.backend_api.get_workflow_run")
    @patch("dashboard.views.backend_api.list_projects")
    def test_execution_detail_renders_job_vacancy_fields(
        self, mock_list_projects, mock_get_workflow_run, mock_list_events
    ):
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]
        mock_get_workflow_run.return_value = {
            "id": 78,
            "workflow_id": 9,
            "workflow_name": "Vacancy helper",
            "status": "completed",
            "created_at": "2026-07-01T00:00:00Z",
            "input": "Vacancy helper REQUEST\n\nVacancy link: https://example.com/job\n\n...",
            "output": (
                '{"score":91,"comparison":{"strong_matches":[{"area":"Python",'
                '"details":"5 years experience"}],"missing_requirements":[],'
                '"seniority_alignment":{"alignment":"Match"}},'
                '"cover_letter":"Dear team...","application_note":"Apply now."}'
            ),
        }
        mock_list_events.return_value = []

        response = self.client.get(reverse("dashboard:execution_detail", args=[78]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "91")
        self.assertContains(response, "Python")
        self.assertContains(response, "Apply now.")
        self.assertContains(response, "Vacancy link: https://example.com/job")

    @patch("dashboard.views.backend_api.list_workflow_run_events")
    @patch("dashboard.views.backend_api.get_workflow_run")
    @patch("dashboard.views.backend_api.list_projects")
    def test_execution_detail_renders_generic_template_rows(
        self, mock_list_projects, mock_get_workflow_run, mock_list_events
    ):
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]
        mock_get_workflow_run.return_value = {
            "id": 79,
            "workflow_id": 10,
            "workflow_name": "Invoice processing",
            "status": "completed",
            "created_at": "2026-07-01T00:00:00Z",
            "input": "Invoice processing REQUEST\n\nDocument filename: invoice.pdf\n\n...",
            "output": '{"vendor":"Acme","total":42,"warnings":["Missing tax id"]}',
        }
        mock_list_events.return_value = []

        response = self.client.get(reverse("dashboard:execution_detail", args=[79]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Acme")
        self.assertContains(response, "Missing tax id")
        self.assertContains(response, "Document filename: invoice.pdf")

    @patch("dashboard.views.backend_api.list_workflow_run_events")
    @patch("dashboard.views.backend_api.get_workflow_run")
    @patch("dashboard.views.backend_api.list_projects")
    def test_execution_detail_redacts_secrets_from_events(
        self, mock_list_projects, mock_get_workflow_run, mock_list_events
    ):
        leaked_key = "AIzaSyA7y33CG1R3yGylCPBU-y00Wkjw-aQG5WU"
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]
        mock_get_workflow_run.return_value = {
            "id": 80,
            "workflow_id": 10,
            "workflow_name": "Meeting minutes generator",
            "status": "failed",
            "created_at": "2026-07-10T21:08:00Z",
            "input": f"GOOGLE_API_KEY={leaked_key}",
            "output": "",
            "error": f"api_key={leaked_key}",
        }
        mock_list_events.return_value = [
            {
                "event_type": "step_error",
                "created_at": "2026-07-10T21:08:00Z",
                "payload": {
                    "error": (
                        "Client error '429 Too Many Requests' for url "
                        "'https://generativelanguage.googleapis.com/v1beta/models/"
                        f"gemini-2.5-flash-lite:generateContent?key={leaked_key}'"
                    ),
                    "env": {"GOOGLE_API_KEY": leaked_key},
                },
            }
        ]

        response = self.client.get(reverse("dashboard:execution_detail", args=[80]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, leaked_key)
        self.assertContains(response, "?key=[redacted]")
        self.assertContains(response, "'GOOGLE_API_KEY': '[redacted]'")

    @patch("dashboard.views.backend_api.list_workflow_run_events")
    @patch("dashboard.views.backend_api.get_workflow_run")
    @patch("dashboard.views.backend_api.list_projects")
    def test_workflows_page_has_no_result_cards(
        self, mock_list_projects, mock_get_workflow_run, mock_list_events
    ):
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]

        response = self.client.get(
            f"{reverse('dashboard:workflows')}?project=research"
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "contract-result-grid")

    @patch("dashboard.views.backend_api.create_workflow_step")
    @patch("dashboard.views.backend_api.list_workflow_steps")
    @patch("dashboard.views.backend_api.create_workflow")
    @patch("dashboard.views.backend_api.list_project_workflows")
    @patch("dashboard.views.backend_api.list_projects")
    def test_setup_job_vacancy_creates_template_steps(
        self,
        mock_list_projects,
        mock_list_project_workflows,
        mock_create_workflow,
        mock_list_workflow_steps,
        mock_create_workflow_step,
    ):
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]
        mock_list_project_workflows.return_value = []
        mock_create_workflow.return_value = {"id": 9, "name": "Vacancy helper"}
        mock_list_workflow_steps.return_value = []
        mock_create_workflow_step.side_effect = [
            {"id": 201},
            {"id": 202},
            {"id": 203},
            {"id": 204},
        ]

        response = self.client.post(
            reverse("dashboard:setup_job_vacancy", args=["research"])
        )

        self.assertRedirects(
            response,
            f"{reverse('dashboard:workflows')}?project=research&workflow=job-vacancy-automation&template=job-vacancy",
            fetch_redirect_response=False,
        )
        mock_create_workflow.assert_called_once_with("token-123", 1, "Vacancy helper")
        self.assertEqual(mock_create_workflow_step.call_count, 4)
        self.assertEqual(
            mock_create_workflow_step.call_args_list[1].kwargs["depends_on"], [201]
        )

    @patch("dashboard.views.backend_api.run_workflow")
    @patch("dashboard.views.backend_api.list_project_documents")
    @patch("dashboard.views.backend_api.list_project_workflows")
    @patch("dashboard.views.backend_api.list_projects")
    def test_run_job_vacancy_uses_vacancy_and_cv(
        self,
        mock_list_projects,
        mock_list_project_workflows,
        mock_list_project_documents,
        mock_run_workflow,
    ):
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]
        mock_list_project_workflows.return_value = [
            {"id": 9, "name": "Vacancy helper", "status": "running"}
        ]
        mock_list_project_documents.return_value = [
            {"id": 44, "filename": "cv.pdf", "text": "Python and Django experience."}
        ]
        mock_run_workflow.return_value = {
            "output": (
                '{"score":91,"comparison":"Strong match","cover_letter":"Dear team...",'
                '"application_note":"Apply with Django focus."}'
            )
        }

        response = self.client.post(
            reverse("dashboard:run_job_vacancy", args=["research"]),
            {"cv_document_id": "44", "vacancy_text": "Need Python Django engineer."},
        )

        self.assertRedirects(
            response,
            f"{reverse('dashboard:workflows')}?project=research&workflow=job-vacancy-automation&template=job-vacancy",
            fetch_redirect_response=False,
        )
        mock_run_workflow.assert_called_once()
        self.assertIn(
            "Need Python Django engineer", mock_run_workflow.call_args.args[2]
        )
        self.assertIn(
            "Python and Django experience", mock_run_workflow.call_args.args[2]
        )
        self.assertNotIn("job_vacancy_result", self.client.session)

    def test_contract_review_parser_reads_markdown_fenced_json(self):
        output = (
            "```json\n"
            "{\n"
            '  "key_dates": [\n'
            '    {"name": "Effective date", "date": "2026-07-01", "notes": "Starts"}\n'
            "  ],\n"
            '  "risk_level": "high",\n'
            '  "summary": "High-risk contract with strict deadlines."\n'
            "}\n"
            "```"
        )

        parsed = parse_contract_review_output(output)

        self.assertEqual(parsed["risk_level"], "high")
        self.assertEqual(parsed["summary"], "High-risk contract with strict deadlines.")
        self.assertEqual(parsed["key_dates"][0]["name"], "Effective date")

    def test_job_vacancy_parser_reads_structured_output(self):
        parsed = parse_job_vacancy_output(
            '{"score":88,"comparison":"Good match","cover_letter":"Hello",'
            '"application_note":"Save and apply."}'
        )

        self.assertEqual(parsed["score"], 88)
        self.assertEqual(parsed["cover_letter"], "Hello")
        self.assertEqual(parsed["application_note"], "Save and apply.")

    def test_job_vacancy_parser_preserves_dedicated_comparison_fields(self):
        parsed = parse_job_vacancy_output(
            '{"score":65,"comparison":{"strong_matches":[{"area":"JavaScript",'
            '"details":"Strong frontend fit","evidence":"CV lists React"}],'
            '"missing_requirements":[{"area":"Experience","details":"Needs 5+ years",'
            '"evidence":"CV states 2 years"}],"seniority_alignment":{"alignment":"Mismatch",'
            '"details":"Junior profile for senior role","evidence":"Job asks 5+ years"}},"cover_letter":"Dear team",'
            '"application_note":"Fix CV dates."}'
        )

        self.assertIn("strong_matches", parsed["comparison"])
        self.assertEqual(parsed["strong_matches"][0]["area"], "JavaScript")
        self.assertEqual(parsed["missing_requirements"][0]["area"], "Experience")
        self.assertEqual(parsed["seniority_alignment"]["alignment"], "Mismatch")

    def test_execution_summary_uses_job_vacancy_fields_for_job_runs(self):
        summary = summarize_workflow_run(
            {
                "input": "Vacancy helper REQUEST\nVacancy link: https://example.com",
                "output": (
                    '{"score":72,"comparison":{"strong_matches":[{"area":"React"}]},'
                    '"cover_letter":"Hello","application_note":"Apply carefully."}'
                ),
            },
            [{"event_type": "completed"}],
        )

        self.assertEqual(summary["template_type"], "job-vacancy")
        self.assertEqual(summary["structured"]["score"], 72)
        self.assertEqual(summary["structured"]["strong_matches"][0]["area"], "React")
        self.assertEqual(
            summary["input_source"], "Vacancy link: https://example.com"
        )

    def test_execution_summary_falls_back_to_generic_rows(self):
        summary = summarize_workflow_run(
            {
                "input": "Invoice processing REQUEST\nDocument filename: invoice.pdf",
                "output": '{"vendor":"Acme","total":42,"warnings":["Missing tax"]}',
            },
            [],
        )

        self.assertEqual(summary["template_type"], "invoice-processing")
        self.assertEqual(summary["input_source"], "Document filename: invoice.pdf")
        row_labels = {row["label"] for row in summary["rows"]}
        self.assertIn("Vendor", row_labels)
        self.assertIn("Warnings", row_labels)

    def test_execution_summary_returns_no_input_source_when_unlabeled(self):
        summary = summarize_workflow_run(
            {"input": "Just some free-form text.", "output": "{}"}, []
        )

        self.assertIsNone(summary["input_source"])


class BackgroundJobPollingTests(TestCase):
    """Covers the persistent-background-jobs frontend behavior: process/run
    calls return immediately (no waiting on the backend job), status
    partials poll only while active and stop at terminal states, and
    returning to a page re-reads current state from the backend rather than
    from any locally cached/session value."""

    def setUp(self):
        engine = import_module(settings.SESSION_ENGINE)
        session = engine.SessionStore()
        session["access_token"] = "token-123"
        session["user"] = {"email": "ana@example.com"}
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    @patch("dashboard.views.backend_api.get_document")
    def test_document_status_partial_polls_while_queued(self, mock_get_document):
        mock_get_document.return_value = {
            "id": 42,
            "project_id": 1,
            "status": "queued",
            "text": None,
            "processing_error": None,
        }

        response = self.client.get(
            reverse("dashboard:document_status_partial", args=[42])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hx-trigger")
        self.assertContains(response, "queued")

    @patch("dashboard.views.backend_api.get_document")
    def test_document_status_partial_stops_polling_when_indexed(
        self, mock_get_document
    ):
        mock_get_document.return_value = {
            "id": 42,
            "project_id": 1,
            "status": "indexed",
            "text": "extracted text",
            "processing_error": None,
        }

        response = self.client.get(
            reverse("dashboard:document_status_partial", args=[42])
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "hx-trigger")

    @patch("dashboard.views.backend_api.get_document")
    def test_document_status_partial_stops_polling_when_failed(
        self, mock_get_document
    ):
        mock_get_document.return_value = {
            "id": 42,
            "project_id": 1,
            "status": "failed",
            "text": None,
            "processing_error": "Unsupported document type",
        }

        response = self.client.get(
            reverse("dashboard:document_status_partial", args=[42])
        )

        self.assertNotContains(response, "hx-trigger")
        self.assertContains(response, "Unsupported document type")

    @patch("dashboard.views.backend_api.get_workflow_run")
    def test_execution_status_partial_polls_while_running(
        self, mock_get_workflow_run
    ):
        mock_get_workflow_run.return_value = {
            "id": 77,
            "workflow_id": 8,
            "status": "running",
            "input": "x",
            "output": None,
            "created_at": "2026-07-10T00:00:00Z",
        }

        response = self.client.get(
            reverse("dashboard:execution_status_partial", args=[77])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hx-trigger")

    @patch("dashboard.views.backend_api.get_workflow_run")
    def test_execution_status_partial_stops_polling_when_completed(
        self, mock_get_workflow_run
    ):
        mock_get_workflow_run.return_value = {
            "id": 77,
            "workflow_id": 8,
            "status": "completed",
            "input": "x",
            "output": "done",
            "created_at": "2026-07-10T00:00:00Z",
        }

        response = self.client.get(
            reverse("dashboard:execution_status_partial", args=[77])
        )

        self.assertNotContains(response, "hx-trigger")
        self.assertContains(response, "View full results")

    @patch("dashboard.views.backend_api.run_workflow")
    @patch("dashboard.views.backend_api.list_project_workflows")
    @patch("dashboard.views.backend_api.list_projects")
    def test_run_workflow_returns_to_workflow_page_while_pending(
        self,
        mock_list_projects,
        mock_list_project_workflows,
        mock_run_workflow,
    ):
        """The view must not show the execution detail page for a queued
        run because the detail view has no useful output/events yet."""
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]
        mock_list_project_workflows.return_value = [
            {"id": 3, "name": "Order Flow", "status": "running"}
        ]
        # Simulate the 202 response: run created + queued, not yet finished.
        mock_run_workflow.return_value = {
            "id": 90,
            "status": "pending",
            "output": None,
        }

        response = self.client.post(
            reverse("dashboard:run_workflow", args=["research", "order-flow"]),
            {"input": "Do the thing"},
        )

        self.assertRedirects(
            response,
            f"{reverse('dashboard:workflows')}?project=research&workflow=order-flow",
            fetch_redirect_response=False,
        )

    @patch("dashboard.views.backend_api.get_document")
    def test_returning_to_document_status_reads_fresh_backend_state(
        self, mock_get_document
    ):
        """Simulates navigation-away-and-back: the status partial always
        re-reads from the backend (Postgres via the API) rather than any
        cached/session value, so a job that kept running in the worker
        while the user was elsewhere is reflected immediately on return."""
        mock_get_document.return_value = {
            "id": 42,
            "project_id": 1,
            "status": "processing",
            "text": None,
            "processing_error": None,
        }
        first = self.client.get(
            reverse("dashboard:document_status_partial", args=[42])
        )
        self.assertContains(first, "processing")
        self.assertContains(first, "hx-trigger")

        # Worker finished the job while the user was navigated away.
        mock_get_document.return_value = {
            "id": 42,
            "project_id": 1,
            "status": "indexed",
            "text": "done",
            "processing_error": None,
        }
        second = self.client.get(
            reverse("dashboard:document_status_partial", args=[42])
        )
        self.assertContains(second, "indexed")
        self.assertNotContains(second, "hx-trigger")

    @patch("dashboard.views.backend_api.process_document")
    @patch("dashboard.views.backend_api.list_projects")
    def test_duplicate_process_document_submission_is_forwarded_but_backend_guards_it(
        self, mock_list_projects, mock_process_document
    ):
        """The frontend doesn't need its own duplicate-submission logic --
        it simply calls the backend each time; the backend endpoint (see
        ai-platform-backend tests) is responsible for the idempotency
        guard. This test only verifies the frontend keeps returning to the
        current page and doesn't error out on a second submission."""
        mock_list_projects.return_value = [{"id": 1, "name": "Research"}]
        next_url = "/projects/research/"

        for _ in range(2):
            response = self.client.post(
                reverse("dashboard:process_document", args=["research", 42]),
                {"next": next_url},
            )
            self.assertRedirects(response, next_url, fetch_redirect_response=False)

        self.assertEqual(mock_process_document.call_count, 2)


def provider_payload():
    return {
        "chat": [
            {
                "name": "ollama",
                "kind": "chat",
                "active": True,
                "default_model": "gemma2:2b",
                "base_url": "http://localhost:11434",
                "api_key_configured": False,
                "supports_api_key": False,
                "supports_health_check": True,
            },
            {
                "name": "groq",
                "kind": "chat",
                "active": False,
                "default_model": "llama-3.1",
                "base_url": "https://api.groq.com/openai/v1",
                "api_key_configured": True,
                "supports_api_key": True,
                "supports_health_check": True,
            },
        ],
        "embeddings": [
            {
                "name": "ollama",
                "kind": "embedding",
                "active": True,
                "default_model": "nomic-embed-text",
                "base_url": "http://localhost:11434",
                "api_key_configured": False,
                "supports_api_key": False,
                "supports_health_check": True,
            }
        ],
        "current": {
            "chat": {
                "provider": "ollama",
                "model": "gemma2:2b",
                "fallback_model": "llama3.2:3b",
                "base_url": "http://localhost:11434",
                "api_key_configured": False,
            },
            "embeddings": {
                "provider": "ollama",
                "model": "nomic-embed-text",
                "dimensions": 768,
                "base_url": "http://localhost:11434",
                "api_key_configured": False,
            },
        },
    }
