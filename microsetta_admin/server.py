import jwt
from flask import render_template, Flask, request, session, send_file
import secrets
from datetime import datetime
import io

from jwt import PyJWTError
from werkzeug.exceptions import BadRequest
from werkzeug.utils import redirect
import pandas as pd

from microsetta_admin import metadata_util
from microsetta_admin.config_manager import SERVER_CONFIG
from microsetta_admin._api import APIRequest
import importlib.resources as pkg_resources

TOKEN_KEY_NAME = 'token'

PUB_KEY = pkg_resources.read_text(
    'microsetta_admin',
    "authrocket.pubkey")

DUMMY_SELECT_TEXT = '-------'
VALID_STATUS = "sample-is-valid"
NO_SOURCE_STATUS = "no-associated-source"
NO_ACCOUNT_STATUS = "no-registered-account"
NO_COLLECTION_INFO_STATUS = "no-collection-info"
INCONSISTENT_SAMPLE_STATUS = "sample-has-inconsistencies"
UNKNOWN_VALIDITY_STATUS = "received-unknown-validity"

STATUS_OPTIONS = [DUMMY_SELECT_TEXT, VALID_STATUS, NO_SOURCE_STATUS,
                  NO_ACCOUNT_STATUS, NO_COLLECTION_INFO_STATUS,
                  INCONSISTENT_SAMPLE_STATUS, UNKNOWN_VALIDITY_STATUS]


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


@app.route('/create_project', methods=['GET', 'POST'])
def new_project():
    if request.method == 'GET':
        return render_template('create_project.html',
                               **build_login_variables())
    elif request.method == 'POST':
        project_name = request.form['project_name']
        is_microsetta = request.form.get('is_microsetta', 'No') == 'Yes'
        bank_samples = request.form.get('bank_samples', 'No') == 'Yes'
        plating_start_date = request.form.get('plating_start_date')
        if plating_start_date == '':
            plating_start_date = None

        status, result = APIRequest.post('/api/admin/create/project',
                                         json={'project_name': project_name,
                                               'is_microsetta': is_microsetta,
                                               'bank_samples': bank_samples,
                                               'plating_start_date':
                                                   plating_start_date
                                               })

        if status == 201:
            return render_template('create_project.html', message='Created!',
                                   **build_login_variables())
        else:
            return render_template('create_project.html',
                                   message='Unable to create',
                                   **build_login_variables())


@app.route('/create_kits', methods=['GET', 'POST'])
def new_kits():
    _, result = APIRequest.get('/api/admin/statistics/projects')
    projects = sorted([stats['project_name'] for stats in result])

    if request.method == 'GET':
        return render_template('create_kits.html',
                               projects=projects,
                               **build_login_variables())

    elif request.method == 'POST':
        num_kits = int(request.form['num_kits'])
        num_samples = int(request.form['num_samples'])
        prefix = request.form['prefix']
        selected_projects = request.form.getlist('projects')

        if selected_projects is None:
            return render_template('create_kits.html',
                                   error='No project selected',
                                   projects=projects,
                                   **build_login_variables())

        payload = {'number_of_kits': num_kits,
                   'number_of_samples': num_samples,
                   'projects': selected_projects}
        if prefix:
            payload['kit_id_prefix'] = prefix

        status, result = APIRequest.post(
                '/api/admin/create/kits',
                json=payload)

        if status != 201:
            return render_template('create_kits.html',
                                   error='Failed to create kits',
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
                         attachment_filename=fname,
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


@app.route('/scan', methods=['GET', 'POST'])
def scan():
    update_error = None

    # If its a get, grab the sample_barcode from the query string rather than
    # form parameters
    if request.method == 'GET':
        sample_barcode = request.args.get('sample_barcode')
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

            # sample_info may be None if barcode not in agp,
            # then no sample_site available
            return render_template(
                'scan.html',
                **build_login_variables(),
                barcode_info=result["barcode_info"],
                projects_info=result['projects_info'],
                scans_info=result['scans_info'],
                latest_status=latest_status,
                status_options=STATUS_OPTIONS,
                sample_info=result['sample'],
                extended_info=result,
                status_warning=status_warning,
                update_error=update_error
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
                update_error=update_error
            )
        else:
            raise BadRequest()

    # If its a post, make the changes, then refresh the page
    if request.method == 'POST':
        sample_barcode = request.form['sample_barcode']
        technician_notes = request.form['technician_notes']
        sample_status = request.form['sample_status']

        # Do the actual update
        status, response = APIRequest.post(
            '/api/admin/scan/%s' % sample_barcode,
            json={
                "sample_status": sample_status,
                "technician_notes": technician_notes
            }
        )

        # if the update failed, keep track of the error
        if status != 201:
            update_error = response

        # exit and show update results
        return render_template('scan.html',
                               update_error=update_error,
                               **build_login_variables())


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
        if 'file' not in request.files or \
                request.files['file'].filename == '':
            search_error = [{'error': 'Must specify a valid file'}]
            return render_template('metadata_pulldown.html',
                                   **build_login_variables(),
                                   search_error=search_error)
        file = request.files['file']
        try:
            barcodes_df = pd.read_csv(file, dtype=str)
            sample_barcodes = barcodes_df['sample_name'].tolist()
        except Exception as e:  # noqa
            search_error = [{'error': 'Could not parse barcodes file'}]
            return render_template('metadata_pulldown.html',
                                   **build_login_variables(),
                                   search_error=search_error)
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
                         attachment_filename="metadata_pulldown.tsv",
                         add_etags=False,
                         cache_timeout=None,
                         conditional=False,
                         last_modified=None,
                         )
    else:

        return render_template('metadata_pulldown.html',
                               **build_login_variables(),
                               info={'barcodes': sample_barcodes},
                               search_error=errors)


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
