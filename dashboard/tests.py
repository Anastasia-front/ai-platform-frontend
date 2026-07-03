from unittest.mock import patch

import requests
from django.test import TestCase
from django.urls import reverse


class DashboardViewTests(TestCase):
    @patch('dashboard.views.get_health')
    def test_index_shows_backend_health(self, mock_get_health):
        mock_get_health.return_value = {
            'status': 'ok',
            'database': 'connected',
        }

        response = self.client.get(reverse('dashboard:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'AI Platform Dashboard')
        self.assertContains(response, 'ok')
        self.assertContains(response, 'connected')

    @patch('dashboard.views.get_health')
    def test_index_handles_backend_unavailable(self, mock_get_health):
        mock_get_health.side_effect = requests.RequestException('backend down')

        response = self.client.get(reverse('dashboard:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'unavailable')
        self.assertContains(response, 'backend down')

# Create your tests here.
