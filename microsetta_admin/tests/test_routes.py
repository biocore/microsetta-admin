import json

from microsetta_admin.tests.base import TestBase


class RouteTests(TestBase):
    def test_home_simple(self):
        response = self.app.get('/', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<title>Microsetta Admin</title>', response.data)

    def test_search_simple(self):
        response = self.app.get('/search', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<h3>Microsetta Search</h3>', response.data)

    def test_search_specific_barcode(self):
        # server side issues a GET to the API
        self.mock_get.return_value.status_code = 200

        response = self.app.post('/search/sample',
                                 data={'search_samples': '000004216'},
                                 follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<h3>Microsetta Search</h3>', response.data)

    def test_search_missing_barcode(self):
        # server side issues a GET to the API
        self.mock_get.return_value.status_code = 404
        self.mock_get.return_value.text = '{}'
        self.mock_get.return_value.json = lambda: {}  # noqa

        response = self.app.post('/search/sample',
                                 data={'search_samples': 'missing'},
                                 follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Query not found', response.data)

    def test_scan_simple(self):
        response = self.app.get('/scan', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<h3>Microsetta Scan</h3>', response.data)

    def test_scan_specific_no_warnings(self):
        resp = {"barcode_info": {"barcode": "000004216"},
                "projects_info": [],
                "scans_info": [],
                "latest_scan": None,
                "sample": {'site': 'baz'},
                "account": 'foo',
                "source": 'bar'}

        self.mock_get.return_value.status_code = 200
        self.mock_get.return_value.text = json.dumps(resp)
        self.mock_get.return_value.json = lambda: resp  # noqa

        response = self.app.get('/scan?sample_barcode=000004216',
                                follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<td>000004216</td>', response.data)
        self.assertNotIn(b'Status Warnings:', response.data)

    def test_scan_specific_no_collection_info_warning(self):
        resp = {"barcode_info": {"barcode": "000004216"},
                "projects_info": [{
                    "project": "American Gut Project",
                    "is_microsetta": True,
                    "bank_samples": False,
                    "plating_start_date": None
                }],
                "scans_info": [],
                "latest_scan": None,
                "sample": {'datetime_collected': None},
                "account": 'foo',
                "source": 'bar'}

        self.mock_get.return_value.status_code = 200
        self.mock_get.return_value.text = json.dumps(resp)
        self.mock_get.return_value.json = lambda: resp  # noqa

        response = self.app.get('/scan?sample_barcode=000004216',
                                follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<td>000004216</td>', response.data)
        self.assertIn(b'Status Warning: no-collection-info', response.data)

    def test_scan_specific_no_associated_source_warning(self):
        resp = {"barcode_info": {"barcode": "000004216"},
                "projects_info": [{
                    "project": "American Gut Project",
                    "is_microsetta": True,
                    "bank_samples": False,
                    "plating_start_date": None
                }],
                "scans_info": [],
                "latest_scan": None,
                "sample": None,
                "account": "foo",
                "source": None}

        self.mock_get.return_value.status_code = 200
        self.mock_get.return_value.text = json.dumps(resp)
        self.mock_get.return_value.json = lambda: resp  # noqa

        response = self.app.get('/scan?sample_barcode=000004216',
                                follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<td>000004216</td>', response.data)
        self.assertIn(b'Status Warning: no-associated-source', response.data)

    def test_scan_specific_no_registered_account_warning(self):
        resp = {"barcode_info": {"barcode": "000004216"},
                "projects_info": [{
                    "project": "American Gut Project",
                    "is_microsetta": True,
                    "bank_samples": False,
                    "plating_start_date": None
                }],
                "scans_info": [],
                "latest_scan": None,
                "sample": None,
                "account": None,
                "source": 'bar'}

        self.mock_get.return_value.status_code = 200
        self.mock_get.return_value.text = json.dumps(resp)
        self.mock_get.return_value.json = lambda: resp  # noqa

        response = self.app.get('/scan?sample_barcode=000004216',
                                follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<td>000004216</td>', response.data)
        self.assertIn(b'Status Warning: no-registered-account', response.data)

    def test_scan_specific_received_unknown_validity_warning(self):
        resp = {"barcode_info": {"barcode": "000004216"},
                "projects_info": [],
                "scans_info": [],
                "latest_scan": None,
                "sample": None,
                "account": None,
                "source": 'bar'}

        self.mock_get.return_value.status_code = 200
        self.mock_get.return_value.text = json.dumps(resp)
        self.mock_get.return_value.json = lambda: resp  # noqa

        response = self.app.get('/scan?sample_barcode=000004216',
                                follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<td>000004216</td>', response.data)
        self.assertIn(b'Status Warning: received-unknown-validity', response.data)

    def test_create_kits_simple(self):
        self.mock_get.return_value.status_code = 200
        self.mock_get.return_value.text = '[{"project_name": "foo"}]'
        self.mock_get.return_value.json = lambda: [{"project_name": "foo"}]

        response = self.app.get('/create_kits', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<h3>Microsetta Create Kits</h3>', response.data)

    def test_create_project_simple(self):
        response = self.app.get('/create_project', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<h3>Microsetta Create Project</h3>', response.data)
