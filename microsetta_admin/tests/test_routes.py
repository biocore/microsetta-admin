import json
from copy import deepcopy

from microsetta_admin.tests.base import TestBase

DUMMY_DAK_ORDER = {'contact_phone_number': '(858) 555-1212',
                   'projects': ['1', '32'],
                   'dak_article_code': '3510001E',
                   'quantity': '2',
                   'planned_send_date': '',
                   'description': '',
                   'fedex_ref_1': '',
                   'fedex_ref_2': '',
                   'fedex_ref_3': '',
                   'addresses_file': None}

DAK_SHIPPING = {'FedEx': ['Default', 'FEDEX_2_DAY', 'FEDEX_GROUND',
                          'PRIORITY_OVERNIGHT', 'STANDARD_OVERNIGHT'],
                'Freight': ['Default'],
                'TransSmart': ['Default'],
                'USPS': ['PRIORITY_EXPRESS', 'PRIORITY', 'FIRST_CLASS']}
DAK_ARTICLE = {'dak_article_code': '3510000E',
               'short_description': 'TMI 1 tube',
               'detailed_description': 'TMI 1 tube, American English'}
A_PROJECT = {'project_name': 'test_proj', 'is_microsetta': True,
             'bank_samples': False, 'plating_start_date': None,
             'contact_name': 'Jane Doe',
             'contact_email': 'jd@test.com',
             'additional_contact_name': 'John Doe',
             'deadlines': 'Spring 2021', 'num_subjects': 'Variable',
             'num_timepoints': '4', 'start_date': 'Fall 2020',
             'disposition_comments': 'Store', 'collection': 'AGP',
             'is_fecal': 'X', 'is_saliva': '', 'is_skin': '?',
             'is_blood': 'X', 'is_other': 'Nares, mouth',
             'do_16s': '', 'do_shallow_shotgun': 'Subset',
             'do_shotgun': 'X', 'do_rt_qpcr': '', 'do_serology': '',
             'do_metatranscriptomics': 'X', 'do_mass_spec': 'X',
             'mass_spec_comments': 'Dorrestein',
             'mass_spec_contact_name': 'Ted Doe',
             'mass_spec_contact_email': 'td@test.com',
             'do_other': '',
             'branding_associated_instructions': 'branding_doc.pdf',
             'branding_status': 'In Review',
             'subproject_name': 'IBL SIBL',
             'alias': 'Healthy Sitting', 'sponsor': 'Crowdfunded',
             'coordination': 'TMI', 'is_active': True,
             'project_id': 8}


class DummyResponse(object):
    def __init__(self, status_code, output_dict):
        self.status_code = status_code
        self.text = json.dumps(output_dict)
        self.json = lambda: output_dict


class RouteTests(TestBase):
    PROJ_LIST = [{'additional_contact_name': None,
                  'alias': None,
                  'bank_samples': False,
                  'branding_associated_instructions': None,
                  'branding_status': None,
                  'collection': None,
                  'computed_stats': {
                      'num_fully_returned_kits': 1,
                      'num_kits': 5,
                      'num_kits_w_problems': 0,
                      'num_no_associated_source': 0,
                      'num_no_collection_info': 0,
                      'num_no_registered_account': 0,
                      'num_partially_returned_kits': 1,
                      'num_received_unknown_validity': 0,
                      'num_sample_is_valid': 4,
                      'num_samples': 20,
                      'num_samples_received': 4,
                      'num_unique_sources': 4},
                  'contact_email': None,
                  'contact_name': None,
                  'coordination': None,
                  'deadlines': None,
                  'disposition_comments': None,
                  'do_16s': None,
                  'do_mass_spec': None,
                  'do_metatranscriptomics': None,
                  'do_other': None,
                  'do_rt_qpcr': None,
                  'do_serology': None,
                  'do_shallow_shotgun': None,
                  'do_shotgun': None,
                  'is_blood': None,
                  'is_fecal': None,
                  'is_microsetta': False,
                  'is_other': None,
                  'is_saliva': None,
                  'is_skin': None,
                  'mass_spec_comments': None,
                  'mass_spec_contact_email': None,
                  'mass_spec_contact_name': None,
                  'num_subjects': None,
                  'num_timepoints': None,
                  'plating_start_date': None,
                  'project_id': 8,
                  'project_name': 'Project - %u[zGmÅq=g',
                  'sponsor': None,
                  'start_date': None,
                  'subproject_name': None},
                 {'additional_contact_name': None,
                  'alias': None,
                  'bank_samples': False,
                  'branding_associated_instructions': None,
                  'branding_status': None,
                  'collection': None,
                  'computed_stats': {
                      'num_fully_returned_kits': 4,
                      'num_kits': 5,
                      'num_kits_w_problems': 1,
                      'num_no_associated_source': 1,
                      'num_no_collection_info': 0,
                      'num_no_registered_account': 0,
                      'num_partially_returned_kits': 1,
                      'num_received_unknown_validity': 0,
                      'num_sample_is_valid': 2,
                      'num_samples': 12,
                      'num_samples_received': 5,
                      'num_unique_sources': 2},
                  'contact_email': None,
                  'contact_name': None,
                  'coordination': None,
                  'deadlines': None,
                  'disposition_comments': None,
                  'do_16s': None,
                  'do_mass_spec': None,
                  'do_metatranscriptomics': None,
                  'do_other': None,
                  'do_rt_qpcr': None,
                  'do_serology': None,
                  'do_shallow_shotgun': None,
                  'do_shotgun': None,
                  'is_blood': None,
                  'is_fecal': None,
                  'is_microsetta': False,
                  'is_other': None,
                  'is_saliva': None,
                  'is_skin': None,
                  'mass_spec_comments': None,
                  'mass_spec_contact_email': None,
                  'mass_spec_contact_name': None,
                  'num_subjects': None,
                  'num_timepoints': None,
                  'plating_start_date': None,
                  'project_id': 12,
                  'project_name': 'New proj',
                  'sponsor': None,
                  'start_date': None,
                  'subproject_name': "sub sub"}
                 ]

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
        self.mock_get.return_value = DummyResponse(404, {})

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
        resp1 = {
            "barcode_info": {"barcode": "000004216"},
            "projects_info": [],
            "scans_info": [],
            "latest_scan": None,
            "sample": {'site': 'baz'},
            "source": {'name': 'a source a name',
                       'source_type': 'human',
                       'source_data': {'description': None}},
            "account": {'id': 'd8592c74-9694-2135-e040-8a80115d6401'}
        }

        resp2 = {
            "barcode_info": {"barcode": "000004216"},
            "projects_info": [],
            "scans_info": [],
            "latest_scan": None,
            "sample": {'site': 'baz'},
            "source": {'name': 'a source a name',
                       'source_type': 'human',
                       'source_data': {'description': None}},
            "account": {'id': 'd8592c74-9694-2135-e040-8a80115d6401'}
        }

        api_get_1 = DummyResponse(200, resp1)
        api_get_2 = DummyResponse(200, resp2)
        api_get_3 = DummyResponse(200, [])
        self.mock_get.side_effect = [api_get_1, api_get_2, api_get_3]

        response = self.app.get('/scan?sample_barcode=000004216',
                                follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<td>000004216</td>', response.data)
        self.assertNotIn(b'Status Warnings:', response.data)

    def test_scan_specific_no_collection_info_warning(self):
        resp1 = {
            "barcode_info": {"barcode": "000004216"},
            "projects_info": [{
                "project": "American Gut Project",
                "is_microsetta": True,
                "bank_samples": False,
                "plating_start_date": None
            }],
            "scans_info": [],
            "latest_scan": None,
            "sample": {'datetime_collected': None},
            "account": {'id': "ThizIzNotReal"},
            "source": {'name': 'a source a name',
                       'source_type': 'human',
                       'source_data': {'description': None}},
        }

        resp2 = {
            "barcode_info": {"barcode": "000004216"},
            "projects_info": [{
                "project": "American Gut Project",
                "is_microsetta": True,
                "bank_samples": False,
                "plating_start_date": None
            }],
            "scans_info": [],
            "latest_scan": None,
            "sample": {'datetime_collected': None},
            "account": {'id': "ThizIzNotReal"},
            "source": {'name': 'a source a name',
                       'source_type': 'human',
                       'source_data': {'description': None}},
        }

        api_get_1 = DummyResponse(200, resp1)
        api_get_2 = DummyResponse(200, resp2)
        api_get_3 = DummyResponse(200, [])
        self.mock_get.side_effect = [api_get_1, api_get_2, api_get_3]

        response = self.app.get('/scan?sample_barcode=000004216',
                                follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<td>000004216</td>', response.data)
        self.assertIn(b'Status Warning: no-collection-info', response.data)

    def test_scan_specific_no_associated_source_warning(self):
        resp1 = {"barcode_info": {"barcode": "000004216"},
                 "projects_info": [{
                     "project": "American Gut Project",
                     "is_microsetta": True,
                     "bank_samples": False,
                     "plating_start_date": None
                 }],
                 "scans_info": [],
                 "latest_scan": None,
                 "sample": None,
                 "account": {"id": "foo"},
                 "source": None}

        resp2 = {"barcode_info": {"barcode": "000004216"},
                 "projects_info": [{
                     "project": "American Gut Project",
                     "is_microsetta": True,
                     "bank_samples": False,
                     "plating_start_date": None
                 }],
                 "scans_info": [],
                 "latest_scan": None,
                 "sample": None,
                 "account": {"id": "foo"},
                 "source": None}

        api_get_1 = DummyResponse(200, resp1)
        api_get_2 = DummyResponse(200, resp2)
        api_get_3 = DummyResponse(200, [])
        self.mock_get.side_effect = [api_get_1, api_get_2, api_get_3]

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
                "source": None}
        self.mock_get.return_value = DummyResponse(200, resp)

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
                "source": None}
        self.mock_get.return_value = DummyResponse(200, resp)

        response = self.app.get('/scan?sample_barcode=000004216',
                                follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<td>000004216</td>', response.data)
        self.assertIn(b'Status Warning: received-unknown-validity',
                      response.data)

    def test_create_kits_get_success(self):
        proj_list = deepcopy(self.PROJ_LIST)
        self.mock_get.return_value = DummyResponse(200, proj_list)

        response = self.app.get('/create_kits', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<option value=\'12\'>New proj</option>',
                      response.data)

    def test_create_kits_get_fail(self):
        self.mock_get.return_value = DummyResponse(400, "")

        response = self.app.get('/create_kits', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Unable to load project list', response.data)

    def test_create_project_success(self):
        api_post_dummy = DummyResponse(201, {})
        api_get_dummy = DummyResponse(200, self.PROJ_LIST)
        self.mock_post.return_value = api_post_dummy
        self.mock_get.return_value = api_get_dummy

        create_input = deepcopy(self.PROJ_LIST[1])
        create_input["project_id"] = ""
        create_input.pop('computed_stats')
        response = self.app.post('/manage_projects',
                                 data=create_input,
                                 follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        # if the below is on the page, the table of projects is shown
        self.assertIn(b'<th>Flight Sub-Project Name</th>', response.data)

    def test_create_project_fail(self):
        self.mock_post.return_value = DummyResponse(401, {})

        create_input = deepcopy(self.PROJ_LIST[1])
        create_input["project_id"] = ""
        create_input.pop('computed_stats')
        response = self.app.post('/manage_projects',
                                 data=create_input,
                                 follow_redirects=True)
        # the api call failed, but the admin page call succeeds--in returning
        # a page reporting the error :)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Unable to create project.', response.data)

    def test_update_project_success(self):
        self.mock_put.return_value = DummyResponse(204, {})
        self.mock_get.return_value = DummyResponse(200, self.PROJ_LIST)

        create_input = deepcopy(self.PROJ_LIST[1])
        create_input.pop('computed_stats')
        response = self.app.post('/manage_projects',
                                 data=create_input,
                                 follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        # if the below is on the page, the table of projects is shown
        self.assertIn(b'<th>Flight Sub-Project Name</th>', response.data)

    def test_update_project_fail(self):
        self.mock_put.return_value = DummyResponse(400, {})

        create_input = deepcopy(self.PROJ_LIST[1])
        create_input.pop('computed_stats')
        response = self.app.post('/manage_projects',
                                 data=create_input,
                                 follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        # the api call failed, but the admin page call succeeds--in returning
        # a page reporting the error :)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Unable to update project.', response.data)

    def test_manage_projects_success(self):
        self.mock_get.return_value = DummyResponse(200, self.PROJ_LIST)

        response = self.app.get('/manage_projects', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        # if the below is on the page, the table of projects is shown
        self.assertIn(b'<th>Flight Sub-Project Name</th>', response.data)

    def test_manage_projects_fail(self):
        self.mock_get.return_value = DummyResponse(
            400, {"message": "hideous error"})

        response = self.app.get('/manage_projects', follow_redirects=True)
        # the api call failed, but the admin page call succeeds--in returning
        # a page reporting the error :)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Unable to load project list', response.data)

    def test_get_submit_daklapack_order_success(self):
        # server side issues three GETs to the API
        api_get_1 = DummyResponse(200, DAK_SHIPPING)
        api_get_2 = DummyResponse(200, [DAK_ARTICLE])
        api_get_3 = DummyResponse(200, [A_PROJECT])
        self.mock_get.side_effect = [api_get_1, api_get_2, api_get_3]

        response = self.app.get('/submit_daklapack_order',
                                follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<strong>Optionals:</strong>', response.data)

    def test_get_submit_daklapack_order_fail_shipping(self):
        dak_shipping = {'error_msg': 'hit a problem'}

        # server side issues three GETs to the API
        api_get_1 = DummyResponse(400, dak_shipping)
        api_get_2 = DummyResponse(200, [DAK_ARTICLE])
        api_get_3 = DummyResponse(200, [A_PROJECT])
        self.mock_get.side_effect = [api_get_1, api_get_2, api_get_3]

        response = self.app.get('/submit_daklapack_order',
                                follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Unable to load daklapack shipping information.',
                      response.data)

    def test_get_submit_daklapack_order_fail_articles(self):
        dak_article = {'error_msg': 'hit a problem'}

        # server side issues three GETs to the API
        api_get_1 = DummyResponse(200, DAK_SHIPPING)
        api_get_2 = DummyResponse(400, [dak_article])
        api_get_3 = DummyResponse(200, [A_PROJECT])
        self.mock_get.side_effect = [api_get_1, api_get_2, api_get_3]

        response = self.app.get('/submit_daklapack_order',
                                follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Unable to load daklapack articles list.',
                      response.data)

    def test_get_submit_daklapack_order_fail_projects(self):
        a_project = {'error_message': 'no projects for you'}

        # server side issues three GETs to the API
        api_get_1 = DummyResponse(200, DAK_SHIPPING)
        api_get_2 = DummyResponse(200, [DAK_ARTICLE])
        api_get_3 = DummyResponse(400, [a_project])
        self.mock_get.side_effect = [api_get_1, api_get_2, api_get_3]

        response = self.app.get('/submit_daklapack_order',
                                follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Unable to load project list', response.data)

    def _test_post_submit_daklapack_order(self, addresses_filename=None):
        if addresses_filename is None:
            addresses_filename = "order_addresses_sample.xlsx"
        addresses_fp = self.get_data_path(addresses_filename)
        with open(addresses_fp, "rb") as addresses_file:
            request_form = deepcopy(DUMMY_DAK_ORDER)
            request_form['addresses_file'] = addresses_file

            response = self.app.post('/submit_daklapack_order',
                                     data=request_form,
                                     follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        return response

    def test_post_submit_daklapack_order_success(self):
        # server side issues one POST to the API
        api_post_1 = DummyResponse(
            200,
            {'order_submissions':
                [
                    {'order_id': '11211',
                     'order_address': {'address1': '123 Main St',
                                       'address2': '',
                                       'city': 'San Diego',
                                       'companyName': 'Dan H',
                                       'country': 'USA',
                                       'countryCode': 'us',
                                       'firstName': 'Jane',
                                       'insertion': 'Apt 2',
                                       'lastName': 'Doe',
                                       'phone': '(858) 555-1212',
                                       'postalCode': '92210',
                                       'state': 'CA'},
                     'order_success': True},
                    {'order_id': '11212',
                     'daklapack_api_error_code': 409,
                     'daklapack_api_error_msg': 'Got 409',
                     'order_address': {'address1': '29 Side St',
                                       'address2': 'Kew Gardens',
                                       'city': 'Gananoque',
                                       'companyName': 'Dan H',
                                       'country': 'Canada',
                                       'countryCode': 'ca',
                                       'firstName': 'Tom',
                                       'insertion': '',
                                       'lastName': 'Thumb',
                                       'phone': '(858) 555-1212',
                                       'postalCode': 'KG7-448',
                                       'state': 'Ontario'},
                     'order_success': False}]}
        )
        self.mock_post.side_effect = [api_post_1]

        response = self._test_post_submit_daklapack_order()
        self.assertIn(b'The following orders were NOT successfully submitted '
                      b'to Daklapack.', response.data)
        self.assertIn(b'The following orders were successfully submitted '
                      b'to Daklapack', response.data)

    def test_post_submit_daklapack_order_fail_api(self):
        # server side issues one POST to the API
        api_post_1 = DummyResponse(400, {
            "isValid": False,
            "errors": [
                {
                    "propertyName": "orderId",
                    "errorMessage": "invalid format",
                    "severity": "Error",
                    "errorCode": "12",
                    "formattedMessagePlaceholderValues": {}
                }
            ],
            "ruleSetsExecuted": []
        })
        self.mock_post.side_effect = [api_post_1]

        response = self._test_post_submit_daklapack_order(
            "order_addresses_sample.xlsx")

        self.assertIn(b'formattedMessagePlaceholderValues', response.data)

    def test_post_submit_daklapack_order_fail_xlsx_format(self):
        # actually code shouldn't make it to private api call, but in case:
        api_post_1 = DummyResponse(201, {'order_id': '11211'})
        self.mock_post.side_effect = [api_post_1]

        response = self._test_post_submit_daklapack_order("empty.txt")
        self.assertIn(b'Could not parse addresses file', response.data)

    def test_post_submit_daklapack_order_fail_xlsx_headers(self):
        # actually code shouldn't make it to private api call, but in case:
        api_post_1 = DummyResponse(201, {'order_id': '11211'})
        self.mock_post.side_effect = [api_post_1]

        response = self._test_post_submit_daklapack_order(
            "order_addresses_malformed.xlsx")
        self.assertIn(b'do not match expected column names', response.data)
