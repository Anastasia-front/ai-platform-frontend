from importlib import import_module
from unittest.mock import patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from dashboard.services.backend_api import BackendAPIError
from dashboard.templatetags.markdown_extras import render_markdown


class AuthViewTests(TestCase):
    @patch('dashboard.views.backend_api.get_current_user')
    @patch('dashboard.views.backend_api.login')
    def test_login_stores_access_token_in_session(self, mock_login, mock_get_current_user):
        mock_login.return_value = {'access_token': 'token-123', 'token_type': 'bearer'}
        mock_get_current_user.return_value = {'email': 'ana@example.com'}

        response = self.client.post(
            reverse('dashboard:login'),
            {'email': 'ana@example.com', 'password': 'secret'},
        )

        self.assertRedirects(response, reverse('dashboard:projects'))
        self.assertEqual(self.client.session['access_token'], 'token-123')
        mock_login.assert_called_once_with('ana@example.com', 'secret')

    def test_projects_redirects_to_login_without_token(self):
        response = self.client.get(reverse('dashboard:projects'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('dashboard:login'), response['Location'])


class ProjectViewTests(TestCase):
    def setUp(self):
        engine = import_module(settings.SESSION_ENGINE)
        session = engine.SessionStore()
        session['access_token'] = 'token-123'
        session['user'] = {'email': 'ana@example.com'}
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    @patch('dashboard.views.backend_api.list_projects')
    def test_project_list_uses_backend_projects(self, mock_list_projects):
        mock_list_projects.return_value = [
            {
                'id': 1,
                'name': 'Research',
                'description': 'Knowledge workflows',
                'user_id': 2,
                'created_at': '2026-07-03T09:00:00',
            }
        ]

        response = self.client.get(reverse('dashboard:projects'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Research')
        self.assertContains(response, '/projects/research/')
        mock_list_projects.assert_called_with('token-123')

    @patch('dashboard.views.backend_api.create_project')
    @patch('dashboard.views.backend_api.list_projects')
    def test_create_project_redirects_to_project_workspace(
        self,
        mock_list_projects,
        mock_create_project,
    ):
        mock_list_projects.return_value = []
        mock_create_project.return_value = {'id': 7, 'name': 'New project'}

        response = self.client.post(
            reverse('dashboard:new_project'),
            {'name': 'New project', 'description': 'Draft'},
        )

        self.assertRedirects(
            response,
            reverse('dashboard:project_detail', args=['new-project']),
            fetch_redirect_response=False,
        )
        mock_create_project.assert_called_once_with('token-123', 'New project', 'Draft')

    @patch('dashboard.views.backend_api.list_project_documents')
    @patch('dashboard.views.backend_api.list_project_chats')
    @patch('dashboard.views.backend_api.list_projects')
    def test_open_project_renders_empty_chat_ui(
        self,
        mock_list_projects,
        mock_list_project_chats,
        mock_list_project_documents,
    ):
        mock_list_projects.return_value = [{'id': 1, 'name': 'Research'}]
        mock_list_project_chats.return_value = []
        mock_list_project_documents.return_value = []

        response = self.client.get(reverse('dashboard:project_detail', args=['research']))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Start a chat')
        self.assertContains(response, 'No chat selected')

    @patch('dashboard.views.backend_api.list_projects')
    def test_project_list_handles_backend_error(self, mock_list_projects):
        mock_list_projects.side_effect = BackendAPIError('backend down')

        response = self.client.get(reverse('dashboard:projects'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'backend down')

    @patch('dashboard.views.backend_api.list_projects')
    @patch('dashboard.views.backend_api.create_chat')
    def test_create_chat_uses_selected_agent_mode(self, mock_create_chat, mock_list_projects):
        mock_list_projects.return_value = [{'id': 1, 'name': 'Research'}]
        mock_create_chat.return_value = {'id': 9, 'title': 'Build helper'}

        response = self.client.post(
            reverse('dashboard:new_chat', args=['research']),
            {'title': 'Build helper', 'agent_name': 'coding'},
        )

        self.assertRedirects(
            response,
            reverse('dashboard:chat_detail', args=['research', 'build-helper']),
            fetch_redirect_response=False,
        )
        mock_create_chat.assert_called_once_with(
            'token-123',
            1,
            'Build helper',
            agent_name='coding',
        )

    @patch('dashboard.views.backend_api.list_project_documents')
    @patch('dashboard.views.backend_api.list_project_chats')
    @patch('dashboard.views.backend_api.list_projects')
    def test_project_workspace_defaults_agent_selector_to_assistant(
        self,
        mock_list_projects,
        mock_list_project_chats,
        mock_list_project_documents,
    ):
        mock_list_projects.return_value = [{'id': 1, 'name': 'Research'}]
        mock_list_project_chats.return_value = []
        mock_list_project_documents.return_value = []

        response = self.client.get(reverse('dashboard:project_detail', args=['research']))

        self.assertContains(response, '<option value="assistant" selected>Assistant</option>', html=True)

    @patch('dashboard.views.backend_api.upload_document')
    @patch('dashboard.views.backend_api.list_projects')
    def test_upload_document_returns_to_current_page(self, mock_list_projects, mock_upload_document):
        mock_list_projects.return_value = [{'id': 1, 'name': 'Research'}]
        uploaded_file = SimpleUploadedFile('notes.txt', b'hello', content_type='text/plain')
        next_url = '/projects/research/chats/first-chat/'

        response = self.client.post(
            reverse('dashboard:upload_document', args=['research']),
            {'file': uploaded_file, 'next': next_url},
        )

        self.assertRedirects(response, next_url, fetch_redirect_response=False)
        mock_upload_document.assert_called_once()

    @patch('dashboard.views.backend_api.delete_document')
    @patch('dashboard.views.backend_api.list_projects')
    def test_delete_document_returns_to_current_page(self, mock_list_projects, mock_delete_document):
        mock_list_projects.return_value = [{'id': 1, 'name': 'Research'}]
        next_url = '/projects/research/chats/first-chat/'

        response = self.client.post(
            reverse('dashboard:delete_document', args=['research', 42]),
            {'next': next_url},
        )

        self.assertRedirects(response, next_url, fetch_redirect_response=False)
        mock_delete_document.assert_called_once_with('token-123', 42)


class MarkdownRenderingTests(TestCase):
    def test_assistant_markdown_renders_as_html(self):
        rendered = render_markdown('**Bold** and *italic* with `code`\n- one\n- two')

        self.assertIn('<strong>Bold</strong>', rendered)
        self.assertIn('<em>italic</em>', rendered)
        self.assertIn('<code>code</code>', rendered)
        self.assertIn('<li>one</li>', rendered)
