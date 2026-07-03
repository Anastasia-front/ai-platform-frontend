from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from dashboard.services.backend_api import BackendAPIError


class DashboardViewTests(TestCase):
    @patch('dashboard.views.backend_api.list_projects')
    @patch('dashboard.views.backend_api.get_health')
    def test_index_shows_backend_health_and_projects(self, mock_get_health, mock_list_projects):
        mock_get_health.return_value = {
            'status': 'ok',
            'database': 'connected',
        }
        mock_list_projects.return_value = [
            {
                'id': 1,
                'name': 'Research',
                'description': 'Knowledge workflows',
                'user_id': 2,
                'created_at': '2026-07-03T09:00:00',
            }
        ]

        response = self.client.get(reverse('dashboard:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')
        self.assertContains(response, 'ok')
        self.assertContains(response, 'connected')
        self.assertContains(response, 'Research')

    @patch('dashboard.views.backend_api.list_projects')
    @patch('dashboard.views.backend_api.get_health')
    def test_index_handles_backend_unavailable(self, mock_get_health, mock_list_projects):
        mock_get_health.side_effect = BackendAPIError('backend down')
        mock_list_projects.side_effect = BackendAPIError('unauthorized')

        response = self.client.get(reverse('dashboard:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Unavailable')
        self.assertContains(response, 'backend down')
        self.assertContains(response, 'unauthorized')

    @patch('dashboard.views.backend_api.get_project')
    def test_project_detail_uses_backend_project_endpoint(self, mock_get_project):
        mock_get_project.return_value = {
            'id': 1,
            'name': 'Research',
            'description': 'Knowledge workflows',
            'user_id': 2,
            'created_at': '2026-07-03T09:00:00',
        }

        response = self.client.get(reverse('dashboard:project_detail', args=[1]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Research')
        mock_get_project.assert_called_once_with(1)
