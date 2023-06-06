import jwt
from flask import render_template, Flask, request, session, send_file
import secrets
from datetime import datetime
import io
import random
import math
import uuid
import json

from jwt import PyJWTError
from werkzeug.exceptions import BadRequest
from werkzeug.utils import redirect
import pandas as pd

from microsetta_admin import metadata_util, upload_util
from microsetta_admin.config_manager import SERVER_CONFIG
from microsetta_admin._api import APIRequest
import importlib.resources as pkg_resources

TOKEN_KEY_NAME = 'token'
SEND_EMAIL_CHECKBOX_DEFAULT_NAME = 'send_email'

PUB_KEY = pkg_resources.read_text(
    'microsetta_admin',
    "authrocket.pubkey")

DUMMY_SELECT_TEXT = '-------'

RECEIVED_TYPE_DROPDOWN = \
    [DUMMY_SELECT_TEXT, "Blood (skin prick)", "Saliva", "Stool",
     "Sample Type Unclear (Swabs Included)"]

VALID_STATUS = "sample-is-valid"
NO_SOURCE_STATUS = "no-associated-source"
NO_ACCOUNT_STATUS = "no-registered-account"
NO_COLLECTION_INFO_STATUS = "no-collection-info"
INCONSISTENT_SAMPLE_STATUS = "sample-has-inconsistencies"
UNKNOWN_VALIDITY_STATUS = "received-unknown-validity"

STATUS_OPTIONS = [DUMMY_SELECT_TEXT, VALID_STATUS, NO_SOURCE_STATUS,
                  NO_ACCOUNT_STATUS, NO_COLLECTION_INFO_STATUS,
                  INCONSISTENT_SAMPLE_STATUS, UNKNOWN_VALIDITY_STATUS]

API_PROJECTS_URL = '/api/admin/projects'


def handle_pyjwt(pyjwt_error):
    # PyJWTError (Aka, anything wrong with token) will force user to log out
    # and log in again
    return redirect('/logout')


def parse_jwt(token):
    """
    Raises
    ------
        jwt.PyJWTError
            If the token is invalid
    """
    decoded = jwt.decode(token, PUB_KEY, algorithms=['RS256'], verify=True)
    return decoded


def build_login_variables():
    # Anything that renders sitebase.html must pass down these variables to
    # jinja2
    token_info = None
    if TOKEN_KEY_NAME in session:
        # If user leaves the page open, the token can expire before the
        # session, so if our token goes back we need to force them to login
        # again.
        token_info = parse_jwt(session[TOKEN_KEY_NAME])

    vars = {
        'endpoint': SERVER_CONFIG["endpoint"],
        'ui_endpoint': SERVER_CONFIG["ui_endpoint"],
        'authrocket_url': SERVER_CONFIG["authrocket_url"]
    }
    if token_info is not None:
        vars['email'] = token_info['email']
    return vars


def build_app():
    # Create the application instance
    app = Flask(__name__)

    flask_secret = SERVER_CONFIG["FLASK_SECRET_KEY"]
    if flask_secret is None:
        print("WARNING: FLASK_SECRET_KEY must be set to run with gUnicorn")
        flask_secret = secrets.token_urlsafe(16)
    app.secret_key = flask_secret
    app.config['SESSION_TYPE'] = 'memcached'
    app.config['SESSION_COOKIE_NAME'] = 'session-microsetta-admin'

    # Set mapping from exception type to response code
    app.register_error_handler(PyJWTError, handle_pyjwt)

    return app


app = build_app()


@app.context_processor
def utility_processor():
    def format_timestamp(timestamp_str):
        if not timestamp_str:
            return "None"
        datetime_obj = datetime.fromisoformat(timestamp_str)
        return datetime_obj.strftime("%Y %B %d  %H:%M:%S")
    return dict(format_timestamp=format_timestamp)


@app.route('/')
def home():
    return render_template('sitebase.html', **build_login_variables())


@app.route('/search', methods=['GET'])
def search():
    return _search()


@app.route('/search/sample', methods=['GET', 'POST'])
def search_sample():
    return _search('samples')


@app.route('/search/kit', methods=['GET', 'POST'])
def search_kit():
    return _search('kit')


@app.route('/search/email', methods=['GET', 'POST'])
def search_email():
    return _search('account')


def _search(resource=None):
    if request.method == 'GET':
        return render_template('search.html', **build_login_variables())
    elif request.method == 'POST':
        query = request.form['search_%s' % resource]

        status, result = APIRequest.get(
                '/api/admin/search/%s/%s' % (resource, query))

        if status == 404:
            result = {'error_message': "Query not found"}
            return render_template('search_result.html',
                                   **build_login_variables(),
                                   result=result), 200
        elif status == 200:
            return render_template('search_result.html',
                                   **build_login_variables(),
                                   resource=resource,
                                   result=result), 200
        else:
            return result


def _translate_nones(a_dict, do_none_to_str):
    # Note: this ISN'T a deep copy. This function is NOT set up
    # for recursing through a multi-layer dictionary
    result = a_dict.copy()
    for k, v in result.items():
        if do_none_to_str and v is None:
            result[k] = ""
        elif not do_none_to_str and v == '':
            result[k] = None
    return result


def _get_projects(include_stats, is_active):
    projects_uri = API_PROJECTS_URL + f"?include_stats={include_stats}"
    if is_active is not None:
        projects_uri += f"&is_active={is_active}"
    status, projects_output = APIRequest.get(projects_uri)

    if status >= 400:
        result = {'error_message': f"Unable to load project list: "
                                   f"{projects_uri}"}
    else:
        cleaned_projects = [_translate_nones(x, True) for x in
                            projects_output]
        # if we're not using full project stats, sort
        # alphabetically by project name
        if not include_stats:
            cleaned_projects = sorted(cleaned_projects,
                                      key=lambda k: k['project_name'])
        result = {'projects': cleaned_projects}

    return status, result


@app.route('/manage_projects', methods=['GET', 'POST'])
def manage_projects():
    result = None
    is_active = request.args.get('is_active', None)
    if request.method == 'POST':
        model = {x: request.form[x] for x in request.form}
        project_id = model.pop('project_id')
        model['is_microsetta'] = model.get('is_microsetta', '') == 'true'
        model['bank_samples'] = model.get('bank_samples', '') == 'true'
        model = _translate_nones(model, False)

        if project_id.isdigit():
            # update (put) an existing project
            action = "update"
            status, api_output = APIRequest.put(
                '{}/{}'.format(API_PROJECTS_URL, project_id),
                json=model)
        else:
            # create (post) a new project
            action = "create"
            status, api_output = APIRequest.post(
                API_PROJECTS_URL, json=model)

        # if api post or put failed
        if status >= 400:
            result = {'error_message': f'Unable to {action} project.'}
    # end if post

    # if the above work (if any) didn't produce an error message, return
    # the projects list
    if result is None:
        _, result = _get_projects(include_stats=True, is_active=is_active)

    return render_template('manage_projects.html',
                           **build_login_variables(),
                           result=result), 200


@app.route('/email_stats', methods=['GET', 'POST'])
def email_stats():
    _, result = _get_projects(include_stats=False, is_active=True)
    projects = result.get('projects')

    if request.method == 'GET':
        project = request.args.get('project', None)
        email = request.args.get('email')
        if email is None:
            # They want to search for emails, show them the search dialog
            return render_template("email_stats_pulldown.html",
                                   **build_login_variables(),
                                   resource=None,
                                   search_error=None,
                                   projects=projects)
        emails = [email, ]
    elif request.method == 'POST':
        project = request.form.get('project', None)
        emails, upload_err = upload_util.parse_request_csv_col(
            request,
            'file',
            'email'
        )
        if upload_err is not None:
            return render_template('email_stats_pulldown.html',
                                   **build_login_variables(),
                                   resource=None,
                                   search_error=[{'error': upload_err}],
                                   projects=projects)
    else:
        raise BadRequest()

    if project == "":
        project = None

    # de-duplicate
    emails = list({e.lower() for e in emails})

    status, result = APIRequest.post(
        '/api/admin/account_email_summary',
        json={
            "emails": emails,
            "project": project
        })

    if status != 200:
        return render_template('email_stats_pulldown.html',
                               search_error=[{'error': result}],
                               resource=None,
                               **build_login_variables(),
                               projects=projects)

    # At a minimum, our table will display these columns.
    # We may show additional info depending on what comes back from the request
    base_data_template = {
        'email': 'XXX',
        'summary': 'XXX',
        'account_id': 'XXX',
        'creation_time': 'XXX',
        'kit_name': 'XXX',
        'project': 'XXX',
        'unclaimed-samples-in-kit': 0,
        'never-scanned': 0,
        'sample-is-valid': 0,
        'no-associated-source': 0,
        'no-registered-account': 0,
        'no-collection-info': 0,
        'sample-has-inconsistencies': 0,
        'received-unknown-validity': 0
    }

    df = pd.DataFrame([base_data_template] + result)
    df = df.drop(0)  # remove the template row
    numeric_cols = [
        "unclaimed-samples-in-kit", "never-scanned", "sample-is-valid",
        "no-associated-source", "no-registered-account", "no-collection-info",
        "sample-has-inconsistencies", "received-unknown-validity"
    ]
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric)
    df[numeric_cols] = df[numeric_cols].fillna(0)

    def urlify_account_id(id_):
        if pd.isnull(id_):
            return "No associated account"
        else:
            ui_endpoint = SERVER_CONFIG['ui_endpoint']
            account_url = f"{ui_endpoint}/accounts/{id_}"
            return f'<a target="_blank" href="{account_url}">{id_}</a>'

    # see https://stackoverflow.com/questions/20035518/insert-a-link-inside-a-pandas-table  # noqa
    df['account_id'] = df["account_id"].apply(urlify_account_id)
    return render_template("email_stats_pulldown.html",
                           search_error=None,
                           resource=df,
                           **build_login_variables(),
                           projects=projects)


@app.route('/per_sample_summary', methods=['GET', 'POST'])
def per_sample_summary():
    # get a list of all projects in the system
    _, result = _get_projects(include_stats=False, is_active=True)
    projects = result.get('projects')

    # filter out any projects that don't belong to Microsetta
    projects = [x for x in projects if x['is_microsetta'] is True]

    # build a list of dictionaries with just the project id and the project
    # name.
    projects = [{'project_name': x['project_name'],
                 'project_id': x['project_id']} for x in projects]

    # determine if user wants sample ids stripped
    strip_sampleid = request.form.get('strip_sampleid', 'off')
    strip_sampleid = strip_sampleid.lower() == 'on'

    if request.method == 'GET':
        # If user arrived via GET then they are either here w/out
        # querying and they simply need the default webpage, or they are
        # querying with either a list of barcodes, or with a project id.

        # look for both parameters to determine which state we are in.
        sample_barcode = request.args.get('sample_barcode')
        project_id = request.args.get('project_id')

        if sample_barcode is None and project_id is None:
            # user just wants the default page.
            return render_template('per_sample_summary.html',
                                   resource=None,
                                   projects=projects,
                                   **build_login_variables())

        if project_id is not None:
            # user wants to get summaries on all samples in a project.
            payload = {'project_id': project_id}
            status, result = APIRequest.post('/api/admin/account_barcode_summa'
                                             'ry?strip_sampleid=False',
                                             json=payload)

            if status == 200:
                if result['partial_result'] is True:
                    unprocessed_barcodes = result['unprocessed_barcodes']
                else:
                    unprocessed_barcodes = None

                resource = pd.DataFrame(result['samples'])
                order = ['sampleid', 'project', 'account-email',
                         'source-email', 'source-type', 'site-sampled',
                         'sample-status', 'sample-received', 'ffq-taken',
                         'ffq-complete', 'vioscreen_username']
                order.extend(sorted(set(resource.columns) - set(order)))
                resource = resource[order]
                if unprocessed_barcodes:
                    return render_template('per_sample_summary.html',
                                           resource=resource,
                                           projects=projects,
                                           error_message="Too many barcodes. S"
                                                         "erver processed only"
                                                         " the first 1000.",
                                           **build_login_variables())
                else:
                    return render_template('per_sample_summary.html',
                                           resource=resource,
                                           projects=projects,
                                           **build_login_variables())

            else:
                return render_template('per_sample_summary.html',
                                       resource=None,
                                       projects=projects,
                                       error_message=result,
                                       **build_login_variables())

        # if we are here then the user is querying using barcodes and we
        # simply need to set up the query below to perform.
        sample_barcodes = [sample_barcode, ]
    else:
        # assume POST, since there are only two methods defined in route.
        # if we are here, it is because the user is querying using an uploaded
        # file containing sample names.
        sample_barcodes, err = upload_util.parse_request_csv_col(request,
                                                                 'file',
                                                                 'sample_name')
        if err is not None:
            # there was an error. abort early.
            return render_template('per_sample_summary.html',
                                   resource=None,
                                   projects=projects,
                                   **build_login_variables(),
                                   search_error=[{'error': err}])

    # perform the main query.
    payload = {'sample_barcodes': sample_barcodes}
    status, result = APIRequest.post('/api/admin/account_barcode_summary?stri'
                                     'p_sampleid=%s' % str(strip_sampleid),
                                     json=payload)

    if status == 200:
        if result['partial_result'] is True:
            unprocessed_barcodes = result['unprocessed_barcodes']
        else:
            unprocessed_barcodes = None
        resource = pd.DataFrame(result['samples'])
        order = ['sampleid', 'project', 'account-email', 'source-email',
                 'source-type', 'site-sampled', 'sample-status',
                 'sample-received', 'ffq-taken', 'ffq-complete',
                 'vioscreen_username']
        order.extend(sorted(set(resource.columns) - set(order)))
        resource = resource[order]

        if unprocessed_barcodes:
            return render_template('per_sample_summary.html',
                                   resource=resource,
                                   projects=projects,
                                   error_message="Too many barcodes. S"
                                                 "erver processed only"
                                                 " the first 1000.",
                                   **build_login_variables())
        else:
            return render_template('per_sample_summary.html',
                                   resource=resource,
                                   projects=projects,
                                   **build_login_variables())
    else:
        return render_template('per_sample_summary.html',
                               resource=None,
                               projects=projects,
                               error_message=result,
                               **build_login_variables())


def _get_by_sample_barcode(sample_barcodes, strip_sampleid, projects):
    payload = {'sample_barcodes': sample_barcodes}
    status, result = APIRequest.post('/api/admin/account_barcode_summary?'
                                     'strip_sampleid=%s' % str(strip_sampleid),
                                     json=payload)
    if status == 200:
        if result['partial_result'] is True:
            unprocessed_barcodes = result['unprocessed_barcodes']
        else:
            unprocessed_barcodes = None

        resource = pd.DataFrame(result['samples'])
        order = ['sampleid', 'project', 'account-email', 'source-email',
                 'source-type', 'site-sampled', 'sample-status',
                 'sample-received', 'ffq-taken', 'ffq-complete',
                 'vioscreen_username']
        order.extend(sorted(set(resource.columns) - set(order)))
        resource = resource[order]

        if unprocessed_barcodes:
            return render_template('per_sample_summary.html',
                                   resource=resource,
                                   projects=projects,
                                   error_message="Too many barcodes. S"
                                                 "erver processed only"
                                                 " the first 1000.",
                                   **build_login_variables())
        else:
            return render_template('per_sample_summary.html',
                                   resource=resource,
                                   projects=projects,
                                   **build_login_variables())
    else:
        return render_template('per_sample_summary.html',
                               resource=None,
                               projects=projects,
                               error_message=result,
                               **build_login_variables())


@app.route('/create_kits', methods=['GET', 'POST'])
def new_kits():
    _, result = _get_projects(include_stats=False, is_active=True)
    projects = result.get('projects')

    if request.method == 'GET':
        return render_template('create_kits.html',
                               error_message=result.get('error_message'),
                               projects=projects,
                               **build_login_variables())

    elif request.method == 'POST':
        num_kits = int(request.form['num_kits'])
        num_samples = int(request.form['num_samples'])
        prefix = request.form['prefix']
        selected_project_ids = request.form.getlist('project_ids')
        payload = {'number_of_kits': num_kits,
                   'number_of_samples': num_samples,
                   'project_ids': selected_project_ids}
        if prefix:
            payload['kit_id_prefix'] = prefix

        status, result = APIRequest.post(
                '/api/admin/create/kits',
                json=payload)

        if status != 201:
            return render_template('create_kits.html',
                                   error_message='Failed to create kits',
                                   projects=projects,
                                   **build_login_variables())

        # StringIO/BytesIO based off https://stackoverflow.com/a/45111660
        buf = io.StringIO()
        payload = io.BytesIO()

        # explicitly expand out the barcode detail
        kits = pd.DataFrame(result['created'])
        for i in range(num_samples):
            kits['barcode_%d' % (i+1)] = [r['sample_barcodes'][i]
                                          for _, r in kits.iterrows()]
        kits.drop(columns='sample_barcodes', inplace=True)

        kits.to_csv(buf, sep=',', index=False, header=True)
        payload.write(buf.getvalue().encode('utf-8'))
        payload.seek(0)
        buf.close()

        stamp = datetime.now().strftime('%d%b%Y-%H%M')
        fname = f'kits-{stamp}.csv'

        return send_file(payload, as_attachment=True,
                         download_name=fname,
                         mimetype='text/csv')


def _check_sample_status(extended_barcode_info):
    warning = None
    in_microsetta_project = any(
        [x['is_microsetta'] for x in extended_barcode_info['projects_info']])

    # one warning to rule them all; check in order of precendence
    if not in_microsetta_project:
        warning = UNKNOWN_VALIDITY_STATUS
    elif extended_barcode_info['account'] is None:
        warning = NO_ACCOUNT_STATUS
    elif extended_barcode_info['source'] is None:
        warning = NO_SOURCE_STATUS
    # collection datetime is used as the bellwether for the whole
    # set of sample collection info because it is relevant to all
    # kinds of samples (whereas previously used field, sample site, is not
    # filled when environmental samples are returned).
    elif extended_barcode_info['sample'].get('datetime_collected') is None:
        warning = NO_COLLECTION_INFO_STATUS

    return warning


# Set up handlers for the cases,
#   GET to view the page,
#   POST to update info for a barcode -AND (possibly)-
#        email end user about the change in sample status,
def _scan_get(sample_barcode, update_error):
    # If there is no sample_barcode in the GET
    # they still need to enter one in the box, so show empty page
    if sample_barcode is None:
        return render_template('scan.html', **build_login_variables())

    # Assuming there is a sample barcode, grab that sample's information
    status, result = APIRequest.get(
        '/api/admin/search/samples/%s' % sample_barcode)

    # If we successfully grab it, show the page to the user
    if status == 200:
        # Process result in python because its easier than jinja2.
        status_warning = _check_sample_status(result)

        # check the latest scan to find the default sample_status for form
        latest_status = DUMMY_SELECT_TEXT
        if result['latest_scan']:
            latest_status = result['latest_scan']['sample_status']

        account = result.get('account')
        events = []
        if account:
            event_status, event_result = APIRequest.get(
                '/api/admin/events/accounts/%s' % account['id']
            )
            if event_status != 200:
                raise Exception("Couldn't pull event history")

            events = event_result

        return render_template(
            'scan.html',
            **build_login_variables(),
            barcode_info=result["barcode_info"],
            projects_info=result['projects_info'],
            scans_info=result['scans_info'],
            latest_status=latest_status,
            dummy_status=DUMMY_SELECT_TEXT,
            status_options=STATUS_OPTIONS,
            send_email=session.get(SEND_EMAIL_CHECKBOX_DEFAULT_NAME, True),
            sample_info=result['sample'],
            extended_info=result,
            status_warning=status_warning,
            update_error=update_error,
            received_type_dropdown=RECEIVED_TYPE_DROPDOWN,
            source=result['source'],
            events=events
        )
    elif status == 401:
        # If we fail due to unauthorized, need the user to log in again
        return redirect('/logout')
    elif status == 404:
        # If we fail due to not found, need to tell the user to pick a diff
        # barcode
        return render_template(
            'scan.html',
            **build_login_variables(),
            search_error="Barcode %s Not Found" % sample_barcode,
            update_error=update_error,
            received_type_dropdown=RECEIVED_TYPE_DROPDOWN
        )
    else:
        raise BadRequest()


def _scan_post_update_info(sample_barcode,
                           technician_notes,
                           sample_status,
                           action,
                           issue_type,
                           template,
                           received_type,
                           recorded_type):

    ###
    # Bugfix Part 1 for duplicate emails being sent.  Theory is that client is
    # out of sync due to hitting back button after a scan has changed
    # state.
    # Can't test if client is up to date without ETags, so for right now,
    # we just validate whether or not they should send an email, duplicating
    # the client log.  (This can still break with multiple admin clients,
    # but that is unlikely at the moment.)
    latest_status = None
    # TODO:  Replace this with ETags!
    status, result = APIRequest.get(
        '/api/admin/search/samples/%s' % sample_barcode)

    if result['latest_scan']:
        latest_status = result['latest_scan']['sample_status']
    ###

    # Do the actual update
    status, response = APIRequest.post(
        '/api/admin/scan/%s' % sample_barcode,
        json={
            "sample_status": sample_status,
            "technician_notes": technician_notes
        }
    )

    # if the update failed, keep track of the error so it can be displayed
    if status != 201:
        update_error = response
        return _scan_get(sample_barcode, update_error)
    else:
        update_error = None

    # If we're not supposed to send an email, go back to GET
    if action != "send_email":
        return _scan_get(sample_barcode, update_error)

    ###
    # Bugfix Part 2 for duplicate emails being sent.
    if sample_status == latest_status:
        # This is what we'll hit if javascript thinks it's updating status
        # but is out of sync with the database.
        update_error = "Ignoring Send Email, sample_status would " \
                       "not have been updated (Displayed page was out of " \
                       "sync)"
        return _scan_get(sample_barcode, update_error)
    ###

    # This is what we'll hit if there are no email templates to send for
    # the new sample status (or if we screw up javascript side :D )
    if template is None:
        update_error = "Cannot Send Email: No Issue Type Specified " \
                       "(or no issue types available)"
        return _scan_get(sample_barcode, update_error)

    # Otherwise, send out an email to the end user
    status, response = APIRequest.post(
        '/api/admin/email',
        json={
            "issue_type": issue_type,
            "template": template,
            "template_args": {
                "sample_barcode": sample_barcode,
                "recorded_type": recorded_type,
                "received_type": received_type
            }
        }
    )

    # if the email failed to send, keep track of the error
    # so it can be displayed
    if status != 200:
        update_error = response
    else:
        update_error = None

    return _scan_get(sample_barcode, update_error)


@app.route('/scan', methods=['GET', 'POST'])
def scan():
    # Now that the handlers are set up, parse the request to determine what
    # to do.

    # If its a get, grab the sample_barcode from the query string rather than
    # form parameters
    if request.method == 'GET':
        sample_barcode = request.args.get('sample_barcode')
        return _scan_get(sample_barcode, None)

    # If its a post, make the changes, then refresh the page
    if request.method == 'POST':
        # Without some extra ajax, we can't persist the send_email checkbox
        # until they actually post the form
        send_email = request.form.get('send_email', False)
        session[SEND_EMAIL_CHECKBOX_DEFAULT_NAME] = send_email

        sample_barcode = request.form['sample_barcode']
        technician_notes = request.form['technician_notes']
        sample_status = request.form['sample_status']

        action = request.form.get('action')
        issue_type = request.form.get('issue_type')
        template = request.form.get('template')
        received_type = request.form.get('received_type')
        recorded_type = request.form.get('recorded_type')

        return _scan_post_update_info(sample_barcode,
                                      technician_notes,
                                      sample_status,
                                      action,
                                      issue_type,
                                      template,
                                      received_type,
                                      recorded_type)


def _get_color_code(cnt):
    codes = ["#C0C0C0", "#808080", "#800000", "#FF0000", "#800080", "#FF00FF",
             "#008000", "#00FF00", "#FFd700", "#000080", "#0000FF", "#00FFFF",
             "#FFE4C4", "#7FFFD4", "#DEB887", "#FF7F50", "#6495ED", "#FF8C00",
             "#FF1493", "#00BFFF", "#1E90FF", "#DAA520", "#4B0082", "#F0E68C",
             "#90EE90", "#778899", "#FFA500", "#BC8F8F", "#D8BFD8", "#DCDCDC"]

    if cnt >= len(codes):
        val = '0123456789ABCDEF'
        code = [random.choice(val) for i in range(6)]
        color_code = ['#' + ''.join(code)]
        return color_code[0]

    return codes[random.randrange(0, len(codes)-1)]


def _get_legends(criteria):

    dict = {}
    curr_dict = session.get(criteria, None)

    if curr_dict is None or len(curr_dict) == 1:
        status, fields = APIRequest.get(
            '/api/admin/barcode_query_fields')

        if status == 200:
            for obj in fields:
                if obj["label"] == criteria:
                    cnt = 1
                    for val in obj["values"]:
                        color_code = None
                        if criteria == "Project":
                            color_code = _get_color_code(cnt)
                        elif "Sample" in criteria:
                            color_code = _get_color_code(cnt)

                        if color_code is not None:
                            while color_code in dict.values():
                                color_code = _get_color_code(cnt)

                            if criteria == "Sample Status":
                                tmp = obj["values"][val].replace(' ', '-')
                                tmp = tmp.lower()
                                dict[tmp] = color_code
                            else:
                                dict[obj["values"][val]] = color_code
                        cnt = cnt + 1

            dict['None'] = "#000000"
            session[criteria] = dict
    else:
        dict = session.get(criteria)

    return dict


def _compose_table(legends, type, scanned_data):
    output_dict = {}
    bulk_scan_id = session.get('bulk_scan_id', '')
    curr_row = ""
    curr_cols = []

    for rec in scanned_data:

        status, response = APIRequest.get(
            '/api/admin/rack/%s/sample/%s' % (bulk_scan_id, rec)
        )
        samples = response['result']

        for obj in samples:
            code = obj['barcode']

            status, data = APIRequest.get(
                '/api/admin/search/samples/%s' % code
            )

            val = ""
            proj = data["sample"]["sample_projects"][0]
            status = data["sample"]["_latest_scan_status"]
            src = data["sample"]["site"]

            if type == "Sample Site":
                val = data["sample"]["site"]
            elif type == "Sample Status":
                val = data["sample"]["_latest_scan_status"]
            elif type == "Project":
                val = data["sample"]["sample_projects"][0]

            if curr_row == "":
                curr_row = obj['location_row']
                if val is None or val == "":
                    tmp = legends['None']
                    curr_cols.append([code, tmp, proj, status, src])
                else:
                    curr_cols.append([code, legends[val], proj, status, src])
            elif curr_row == obj['location_row']:
                if val is None:
                    tmp = legends['None']
                    curr_cols.append([code, tmp, proj, status, src])
                else:
                    curr_cols.append([code, legends[val], proj, status, src])
            else:
                output_dict[curr_row] = curr_cols
                curr_cols = []
                curr_row = obj['location_row']
                if val is None:
                    tmp = legends['None']
                    curr_cols.append([code, tmp, proj, status, src])
                else:
                    curr_cols.append([code, legends[val], proj, status, src])

    output_dict[curr_row] = curr_cols
    return output_dict


def _visualize_scans():
    filename = request.form['scanned_file']
    criteria = request.form['sort_criteria']
    samples = json.loads(request.form['scanned_samples'])
    session['recent_criteria'] = criteria
    legends = _get_legends(criteria)

    return render_template('bulk_scan.html',
                           **build_login_variables(),
                           stage="Visualization",
                           filename=filename,
                           data=criteria,
                           legends=legends,
                           table=_compose_table(legends, criteria, samples),
                           status_options=STATUS_OPTIONS,
                           message="",
                           samples=json.dumps(samples)
                           )


def _post_bulk_scan_add():
    send_email = request.form.get('send_email', False)
    session[SEND_EMAIL_CHECKBOX_DEFAULT_NAME] = send_email

    sample_barcode = request.form['sample_barcode']
    technician_notes = request.form['technician_notes']
    sample_status = request.form['sample_status']
    samples = json.loads(request.form['scanned_samples'])

    # Do the actual update
    status, response = APIRequest.post(
        '/api/admin/scan/%s' % sample_barcode,
        json={
            "sample_status": sample_status,
            "technician_notes": technician_notes
        }
    )

    message = ""
    if status == 201:
        message = "Success: Sample scanned successfully!"
    else:
        message = "Error: Unable to scan sample!"

    filename = session.get('scan_file', "")
    criteria = session.get('recent_criteria', "Project")
    sample_json = json.dumps(samples)
    legends = _get_legends(criteria)
    return render_template('bulk_scan.html',
                           **build_login_variables(),
                           stage="Visualization",
                           filename=filename,
                           data=criteria,
                           legends=legends,
                           table=_compose_table(legends, criteria, samples),
                           status_options=STATUS_OPTIONS,
                           message=message,
                           samples=sample_json
                           )


def _post_bulk_scan():
    obj_file = request.files['file_picker']
    s_type = request.form['sort_criteria']
    error_msg = ""
    samples = []
    legends = _get_legends(s_type)
    bulk_scan_id = str(uuid.uuid4())

    if obj_file is not None:
        filename = obj_file.filename
        ds = pd.read_csv(obj_file, dtype={'TubeCode': str, 'RackID': str})
        ds['LocationRow'] = ds['LocationRow'].fillna('')
        file_data = ds.values.tolist()

        row_cnt = 1
        for rec in file_data:
            obj = {}
            obj["rack_id"] = rec[6]
            if math.isnan(rec[3]):
                error_msg = "Error: Empty column in row number "
                error_msg += str(row_cnt)
                break
            else:
                obj["location_col"] = str(int(rec[3]))

            if len(rec[4]) == 0:
                error_msg = "Error: Empty row in row number " + str(row_cnt)
                break
            else:
                obj["location_row"] = rec[4]
            sample_barcode = rec[5]
            obj['bulk_scan_id'] = bulk_scan_id
            status, response = APIRequest.post(
                '/api/admin/rack/%s/add' % sample_barcode,
                json=obj
            )

            if rec[6] not in samples:
                samples.append(rec[6])
            row_cnt += 1

        samples_json = json.dumps(samples)
        session['bulk_scan_id'] = bulk_scan_id
        return render_template('bulk_scan.html',
                               **build_login_variables(),
                               stage="Visualization",
                               filename=filename,
                               data=s_type,
                               legends=legends,
                               table=_compose_table(legends, s_type, samples),
                               status_options=STATUS_OPTIONS,
                               message=error_msg,
                               samples=samples_json
                               )
    else:
        error_msg = "Invalid file type! Please check the file and try again."
        return render_template('bulk_scan.html',
                               **build_login_variables(),
                               stage="Scanning",
                               filename=filename,
                               data=s_type,
                               legends=legends,
                               table=_compose_table(legends, s_type, samples),
                               status_options=STATUS_OPTIONS,
                               message=error_msg,
                               samples=""
                               )


@app.route('/scan-bulk', methods=['GET', 'POST'])
def bulk_scan():

    if request.method == 'GET':
        return render_template('bulk_scan.html',
                               **build_login_variables(),
                               stage="Scanning",
                               filename="",
                               data="",
                               legends={},
                               table={},
                               status_options={},
                               message="",
                               samples=""
                               )

    if request.method == 'POST':
        stage = request.form["stage"]
        if stage == "Scanning":
            return _post_bulk_scan()
        elif stage == "Visualization":
            return _visualize_scans()
        elif stage == "Sample_Scan":
            return _post_bulk_scan_add()


@app.route('/metadata_pulldown', methods=['GET', 'POST'])
def metadata_pulldown():
    allow_missing = request.form.get('allow_missing_samples', False)

    if request.method == 'GET':
        sample_barcode = request.args.get('sample_barcode')
        # If there is no sample_barcode in the GET
        # they still need to enter one in the box, so show empty page
        if sample_barcode is None:
            return render_template('metadata_pulldown.html',
                                   **build_login_variables())
        sample_barcodes = [sample_barcode]
    elif request.method == 'POST':
        sample_barcodes, upload_err = upload_util.parse_request_csv_col(
                                                            request,
                                                            'file',
                                                            'sample_name'
        )
        if upload_err is not None:
            return render_template('metadata_pulldown.html',
                                   **build_login_variables(),
                                   search_error=[{'error': upload_err}])
    else:
        raise BadRequest()

    df, errors = metadata_util.retrieve_metadata(sample_barcodes)

    # Strangely, these api requests are returning an html error page rather
    # than a machine parseable json error response object with message.
    # This is almost certainly due to error handling for the cohosted minimal
    # client.  In future, we should just pass down whatever the api says here.
    if len(errors) == 0 or allow_missing:
        df = metadata_util.drop_private_columns(df)

        # TODO:  Streaming direct from pandas is a pain.  Need to search for
        #  better ways to iterate and chunk this file as we generate it
        strstream = io.StringIO()
        df.to_csv(strstream, sep='\t', index=True, header=True)

        # TODO: utf-8 or utf-16 encoding??
        bytestream = io.BytesIO()
        bytestream.write(strstream.getvalue().encode('utf-8'))
        bytestream.seek(0)

        strstream.close()
        return send_file(bytestream,
                         mimetype="text/tab-separated-values",
                         as_attachment=True,
                         download_name="metadata_pulldown.tsv",
                         etag=False,
                         max_age=None,
                         conditional=False,
                         last_modified=None,
                         )
    else:

        return render_template('metadata_pulldown.html',
                               **build_login_variables(),
                               info={'barcodes': sample_barcodes},
                               search_error=errors)


@app.route('/submit_daklapack_order', methods=['GET'])
def submit_daklapack_order():
    error_msg_key = "error_message"

    def return_error(msg):
        return render_template('submit_daklapack_order.html',
                               **build_login_variables(),
                               error_message=msg)

    status, dak_shipping_type_by_provider = APIRequest.get(
        '/api/admin/daklapack_shipping')
    if status >= 400:
        return return_error("Unable to load daklapack shipping information.")

    status, dak_articles_output = APIRequest.get(
        '/api/admin/daklapack_articles')
    if status >= 400:
        return return_error("Unable to load daklapack articles list.")

    status, projects_output = _get_projects(include_stats=False,
                                            is_active=True)
    if status >= 400:
        return return_error(projects_output[error_msg_key])

    return render_template('submit_daklapack_order.html',
                           **build_login_variables(),
                           error_message=None,
                           dummy_status=DUMMY_SELECT_TEXT,
                           dak_articles=dak_articles_output,
                           dak_shipping=dak_shipping_type_by_provider,
                           contact_phone_number=SERVER_CONFIG[
                               "order_contact_phone"],
                           projects=projects_output['projects'])


@app.route('/submit_daklapack_order', methods=['POST'])
def post_submit_daklapack_order():
    def return_error(msg):
        return render_template('submit_daklapack_order.html',
                               **build_login_variables(),
                               error_message=msg)

    error_message = success_submissions = failure_submissions = headers = None
    expected_headers = ["firstName", "lastName", "address1", "insertion",
                        "address2", "postalCode", "city", "state",
                        "country", "countryCode"]

    # get required fields; cast where expected by api
    phone_number = request.form['contact_phone_number']
    project_ids_list = list(map(int, request.form.getlist('projects')))
    dak_article_code = request.form['dak_article_code']
    article_quantity = int(request.form['quantity'])
    file = request.files['addresses_file']

    shipping_provider = request.form.get('dak_shipping_provider')
    shipping_type = request.form.get('dak_shipping_type')

    # get optional fields or defaults
    planned_send_str = request.form.get('planned_send_date')
    planned_send_date = planned_send_str if planned_send_str else None
    description = request.form.get('description')
    fedex_ref_1 = request.form.get('fedex_ref_1')
    fedex_ref_2 = request.form.get('fedex_ref_2')
    fedex_ref_3 = request.form.get('fedex_ref_3')

    try:
        # NB: import everything as a string so that zip codes beginning with
        # zero (e.g., 06710) don't get silently cast to numbers
        if file.filename.endswith('xls'):
            addresses_df = pd.read_excel(file, dtype=str)
        elif file.filename.endswith('xlsx'):
            addresses_df = pd.read_excel(file, engine='openpyxl', dtype=str)
        else:
            raise ValueError(f"Unrecognized extension on putative excel "
                             f"filename: {file.filename}")

        headers = list(addresses_df.columns)
    except Exception as e:  # noqa
        return return_error('Could not parse addresses file')

    if headers != expected_headers:
        return return_error(f"Received column names {headers} do "
                            f"not match expected column names"
                            f" {expected_headers}")

    # add (same) contact phone number to every address
    addresses_df['phone'] = phone_number

    addresses_df = addresses_df.fillna("")
    temp_dict = addresses_df.to_dict(orient='index')
    addresses_list = [temp_dict[n] for n in range(len(temp_dict))]

    status, post_output = APIRequest.post(
        '/api/admin/daklapack_orders',
        json={
            "project_ids": project_ids_list,
            "article_code": dak_article_code,
            "quantity": article_quantity,
            "addresses": addresses_list,
            "shipping_provider": shipping_provider,
            "shipping_type": shipping_type,
            "planned_send_date": planned_send_date,
            "description": description,
            "fedex_ref_1": fedex_ref_1,
            "fedex_ref_2": fedex_ref_2,
            "fedex_ref_3": fedex_ref_3
        }
    )

    # if the post failed, keep track of the error so it can be displayed
    if status != 200:
        error_message = post_output
    else:
        order_submissions = post_output["order_submissions"]
        success_submissions = [x for x in order_submissions if
                               x["order_success"]]
        failure_submissions = [x for x in order_submissions if not
                               x["order_success"]]

    return render_template('submit_daklapack_order.html',
                           **build_login_variables(),
                           error_message=error_message,
                           success_submissions=success_submissions,
                           failure_submissions=failure_submissions)


@app.route('/authrocket_callback')
def authrocket_callback():
    token = request.args.get('token')
    session[TOKEN_KEY_NAME] = token
    return redirect("/")


@app.route('/logout')
def logout():
    if TOKEN_KEY_NAME in session:
        del session[TOKEN_KEY_NAME]
    return redirect("/")


# If we're running in stand alone mode, run the application
if __name__ == '__main__':
    if SERVER_CONFIG["ssl_cert_path"] and SERVER_CONFIG["ssl_key_path"]:
        ssl_context = (
            SERVER_CONFIG["ssl_cert_path"], SERVER_CONFIG["ssl_key_path"]
        )
    else:
        ssl_context = None

    app.run(
        port=SERVER_CONFIG['port'],
        debug=SERVER_CONFIG['debug'],
        ssl_context=ssl_context
    )
