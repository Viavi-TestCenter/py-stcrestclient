"""
STC REST API wrapper module.

This module allows python scripts to call the STC Automation API using HTTP or HTTPS.

To specify the HTTP/HTTPS (REST API) server, the client must set the value of the
environment variable STC_SERVER_ADDRESS, or specify the server when creating
the StcHttp object.

"""
from __future__ import absolute_import
from __future__ import print_function

import time
import os
import socket
import json
from requests.utils import quote

try:
    from . import resthttp
except ValueError:
    import resthttp

# Use this port if it is not specified when creating StcHttp, or by the
# STC_SERVER_PORT environment variable.
HTTP_DEFAULT_PORT  = 80
HTTPS_DEFAULT_PORT = 443

class StcHttp(object):

    """
    TestCenter ReST API wrapper object.

    """

    def __init__(self, server=None, port=None, api_version=1, use_https=False, ca_cert="",
                 debug_print=False, timeout=None, token=None):
        """Initialize the REST API wrapper object.

        If the port to connect to is not specified by the port argument, or by
        the STC_SERVER_PORT environment variable, then try connecting on the
        80 for HTTP or 443 for HTTPS.

        Arguments:
        server      -- STC REST API server to connect to. None to use environ.
        port        -- HTTP/HTTPS port to connect to server on.  Use environment
                       variable STC_SERVER_PORT or default port if None.
                       Default port is 80 for HTTP and 443 for HTTPS.
        use_https   -- Identify if STC REST API server uses HTTPS or not. 
                       True for HTTPS server while False for HTTP server.
        ca_cert     -- Identify the trusted CA-Signed certificates, 
                       e.g., ca_cert='/root/aion/cert/ca_crt.pem'
        api_version -- What API version to use.
        debug_print -- Enable debug print statements.
        timeout     -- Number of seconds to wait for a response.

        """

        default_port = HTTPS_DEFAULT_PORT if use_https else HTTP_DEFAULT_PORT
        proto = 'https' if use_https else 'http'

        if not server:
            server = os.environ.get('STC_SERVER_ADDRESS')
            if not server:
                raise RuntimeError('STC_SERVER_ADDRESS not set')
        if not port:
            port = os.environ.get('STC_SERVER_PORT', default_port)

        if use_https:
            cacert = os.environ.get('REQUESTS_CA_BUNDLE')
            if not cacert and ca_cert == "":
                raise RuntimeError('Trusted CA-Signed certificates not set to verify HTTPS server')
            if ca_cert:
                os.environ['REQUESTS_CA_BUNDLE'] = ca_cert

        self._dbg_print = bool(debug_print)
        rest = None

        url = resthttp.RestHttp.url(proto, server, port, 'stcapi')
        rest = resthttp.RestHttp(url, debug_print=debug_print, timeout=timeout)
        if token:
            rest.add_header('Authorization', 'Bearer ' + token)
        try:
            rest.get_request('sessions')
        except (socket.error, resthttp.ConnectionError,
                resthttp.RestHttpError):
            raise RuntimeError('Cannot connect to STC server: %s:%s' %
                               (server, port))

        self._rest = rest
        self._sid = None
        self._api_ver = None

    def session_id(self):
        return self._sid

    def timeout(self):
        """Return the current timeout value."""
        return self._rest.timeout()

    def set_timeout(self, timeout):
        """Seconds to wait for a response.  Any zero-value means no timeout."""
        self._rest.set_timeout(timeout)

    def new_session(self, user_name=None, session_name=None,
                    kill_existing=False, analytics=None):
        """Create a new test session.

        The test session is identified by the specified user_name and optional
        session_name parameters.  If a session name is not specified, then the
        server will create one.

        Arguments:
        user_name     -- User name part of session ID.
        session_name  -- Session name part of session ID.
        kill_existing -- If there is an existing session, with the same session
                         name and user name, then terminate it before creating
                         a new session
        analytics     -- Optional boolean value to disable or enable analytics
                         for new session.  None will use setting configured on
                         server.

        Return:
        True if session started, False if session was already started.

        """
        if self.started():
            return False
        if not session_name or not session_name.strip():
            session_name = ''
        if not user_name or not user_name.strip():
            user_name = ''
        params = {'userid': user_name, 'sessionname': session_name}
        if analytics not in (None, ''):
            params['analytics'] = str(analytics).lower()
        try:
            status, data = self._rest.post_request('sessions', None, params)
        except resthttp.RestHttpError as e:
            if kill_existing and str(e).find('already exists') >= 0:
                self.end_session('kill', ' - '.join((session_name, user_name)))
            else:
                raise RuntimeError('failed to create session: ' + str(e))

            # Starting session
            if self._dbg_print:
                print('===> starting session')
            status, data = self._rest.post_request('sessions', None, params)
            if self._dbg_print:
                print('===> OK, started')

        sid = data['session_id']
        if self._dbg_print:
            print('===> session ID:', sid)
            print('===> URL:', self._rest.make_url('sessions', sid))

        self._rest.add_header('X-STC-API-Session', sid)
        self._sid = sid
        return sid

    def join_session(self, sid):
        """Attach to an existing session."""
        self._rest.add_header('X-STC-API-Session', sid)
        self._sid = sid
        try:
            status, data = self._rest.get_request('objects', 'system1',
                                                  ['version', 'name'])
        except resthttp.RestHttpError as e:
            self._rest.del_header('X-STC-API-Session')
            self._sid = None
            raise RuntimeError('failed to join session "%s": %s' % (sid, e))

        return data['version']

    def end_session(self, end_tcsession=True, sid=None, timeout=30):
        """End this test session.

        A session can be ended in three ways, depending on the value of the
        end_tcsession parameter:
            - end_tcsession=None:
                Stop using session locally, do not contact server.
            - end_tcsession=False:
                End client controller, but leave test session on server.
            - end_tcsession=True:
                End client controller and terminate test session (default).
            - end_tcsession='kill':
                Forcefully terminate test session.

        Specifying end_tcsession=False is useful to do before attaching an STC
        GUI or legacy automation script, so that there are not multiple
        controllers to interfere with each other.

        When the session is ended, it is no longer available.  Clients should
        export any result or log files, that they want to preserve, before the
        session is ended.

        Arguments
        end_tcsession -- How to end the session (see above)
        sid           -- ID of session to end.  None to use current session.
        timeout       -- Seconds to wait for session to end.  None or 0 does
                         not wait and -1 waits forever for session to end.

        Return:
        True if session ended, false if session was not started.

        """
        if not sid or sid == self._sid:
            if not self.started():
                return False

            sid = self._sid
            self._sid = None
            self._rest.del_header('X-STC-API-Session')

        if end_tcsession is None:
            if self._dbg_print:
                print('===> detached from session')
            return True

        try:
            if end_tcsession:
                if self._dbg_print:
                    print('===> deleting session:', sid)
                if end_tcsession == 'kill':
                    status, data = self._rest.delete_request(
                        'sessions', sid, 'kill')
                else:
                    status, data = self._rest.delete_request('sessions', sid)

                if not timeout:
                    return True

                deadline = None
                if timeout > 0:
                    deadline = time.time() + timeout
                while 1:
                    time.sleep(5)
                    if self._dbg_print:
                        print('===> checking if session ended')
                    ses_list = self.sessions()
                    if not ses_list or sid not in ses_list:
                        break
                    if deadline and deadline - time.time() <= 0:
                        raise RuntimeError("timeout waiting for session to stop")
                if self._dbg_print:
                    print('===> ok - deleted test session')
            else:
                # Ending client session is supported on version >= 2.1.5
                if self._get_api_version() < (2, 1, 5):
                    raise RuntimeError('option no available on server')

                status, data = self._rest.delete_request(
                    'sessions', sid, 'false')
                if self._dbg_print:
                    print('===> OK - detached REST API from test session')
        except resthttp.RestHttpError as e:
            raise RuntimeError('failed to end session: ' + str(e))

        return True

    def debug_print(self):
        return self._dbg_print

    def enable_debug_print(self):
        """Enable debug messages."""
        self._dbg_print = True
        self._rest.enable_debug_print()

    def disable_debug_print(self):
        """Disable debug messages."""
        self._dbg_print = False
        self._rest.disable_debug_print()

    def started(self):
        """Return True is session is started.  Otherwise, return False."""
        return bool(self._sid)

    def sessions(self):
        """Get a list of active sessions on the server.

        Return:
        List of session ID values, one for each active session on server.

        """
        status, data = self._rest.get_request('sessions')
        return data

    def session_urls(self):
        """Get a list of active sessions on the server.

        Return:
        List of session URLs, one for each active session on server.

        """
        return [self._rest.make_url('sessions', sid)
                for sid in self.sessions()]

    def session_info(self, session_id=None):
        """Get information on session.

        If session_id is None, the default, then return information about this
        session.  If a session ID is given, then get information about that
        session.

        Arguments:
        session_id -- Id of session to get info for, if not this session.

        Return:
        Dictionary of session information.

        """
        if not session_id:
            if not self.started():
                return []
            session_id = self._sid
        status, data = self._rest.get_request('sessions', session_id)
        return data

    def files(self):
        """Get list of files, for this session, on server."""
        self._check_session()
        status, data = self._rest.get_request('files')
        return data

    def file_urls(self):
        """Get list of files, for this session, on server.

        Return:
        List of session URLs, one for each file on server.

        """
        return [self._rest.make_url('files', f) for f in self.files()]

    def bll_version(self):
        """Get the BLL version this session is connected to.

        Return:
        Version string if session started.  None if session not started.

        """
        if not self.started():
            return None
        status, data = self._rest.get_request('objects', 'system1',
                                              ['version', 'name'])
        return data['version']

    def system_info(self):
        """Return dictionary of STC and API information."""
        status, data = self._rest.get_request('system')
        return data

    def server_info(self):
        status, data = self._rest.get_request('objects', 'system1')
        return data

    def apply(self):
        """Send test configuration to chassis."""
        self._check_session()
        self._rest.put_request(None, 'apply')

    def get(self, handle, *args):
        """Returns the value(s) of one or more object attributes.

        If multiple arguments, this method returns a dictionary of argument
        names mapped to the value returned by each argument.

        If a single argument is given, then the response is a list of values
        for that argument.

        Arguments:
        handle -- Handle that identifies object to get info for.
        *args  -- Zero or more attributes or relationships.

        Return:
        If multiple input arguments are given:
        {attrib_name:attrib_val, attrib_name:attrib_val, ..}

        If single input argument is given, then a single string value is
        returned.  NOTE: If the string contains multiple substrings, then the
        client will need to parse these.

        """
        self._check_session()
        status, data = self._rest.get_request('objects', str(handle), args)
        return data

    def create(self, object_type, under=None, attributes=None, **kwattrs):
        """Create a new automation object.

        Arguments:
        object_type -- Type of object to create.
        under       -- Handle of the parent of the new object.
        attributes  -- Dictionary of attributes (name-value pairs).
        kwattrs     -- Optional keyword attributes (name=value pairs).

        Return:
        Handle of newly created object.

        """
        data = self.createx(object_type, under, attributes, **kwattrs)
        return data['handle']

    def createx(self, object_type, under=None, attributes=None, **kwattrs):
        """Create a new automation object.

        Arguments:
        object_type -- Type of object to create.
        under       -- Handle of the parent of the new object.
        attributes  -- Dictionary of attributes (name-value pairs).
        kwattrs     -- Optional keyword attributes (name=value pairs).

        Return:
        Dictionary containing handle of newly created object.

        """
        self._check_session()
        params = {'object_type': object_type}
        if under:
            params['under'] = under
        if attributes:
            params.update(attributes)
        if kwattrs:
            params.update(kwattrs)

        status, data = self._rest.post_request('objects', None, params)
        return data

    def delete(self, handle):
        """Delete the specified object.

        Arguments:
        handle -- Handle of object to delete.

        """
        self._check_session()
        self._rest.delete_request('objects', str(handle))

    def perform(self, command, params=None, **kwargs):
        """Execute a command.

        Arguments can be supplied either as a dictionary or as keyword
        arguments.  Examples:
            stc.perform('LoadFromXml', {'filename':'config.xml'})
            stc.perform('LoadFromXml', filename='config.xml')

        Arguments:
        command -- Command to execute.
        params  -- Optional.  Dictionary of parameters (name-value pairs).
        kwargs  -- Optional keyword arguments (name=value pairs).

        Return:
        Data from command.

        """
        self._check_session()
        if not params:
            params = {}
        if kwargs:
            params.update(kwargs)
        params['command'] = command
        status, data = self._rest.post_request('perform', None, params)
        return data

    def config(self, handle, attributes=None, **kwattrs):
        """Sets or modifies one or more object attributes or relations.

        Arguments can be supplied either as a dictionary or as keyword
        arguments.  Examples:
            stc.config('port1', location='//10.1.2.3/1/1')
            stc.config('port2', {'location': '//10.1.2.3/1/2'})

        Arguments:
        handle     -- Handle of object to modify.
        attributes -- Dictionary of attributes (name-value pairs).
        kwattrs    -- Optional keyword attributes (name=value pairs).

        """
        self._check_session()
        if kwattrs:
            if attributes:
                attributes.update(kwattrs)
            else:
                attributes = kwattrs
        self._rest.put_request('objects', str(handle), attributes)

    def chassis(self):
        """Get list of chassis known to test session."""
        self._check_session()
        status, data = self._rest.get_request('chassis')
        return data

    def chassis_info(self, chassis):
        """Get information about the specified chassis."""
        if not chassis or not isinstance(chassis, str):
            raise RuntimeError('missing chassis address')
        self._check_session()
        status, data = self._rest.get_request('chassis', chassis)
        return data

    def connections(self):
        """Get list of connections."""
        self._check_session()
        status, data = self._rest.get_request('connections')
        return data

    def is_connected(self, chassis):
        """Get Boolean connected status of the specified chassis."""
        self._check_session()
        try:
            status, data = self._rest.get_request('connections', chassis)
        except resthttp.RestHttpError as e:
            if int(e) == 404:
                # 404 NOT FOUND means the chassis in unknown, so return false.
                return False
        return bool(data and data.get('IsConnected'))

    def connect(self, chassis_list):
        """Establish connection to one or more chassis.

        Arguments:
        chassis_list -- List of chassis (IP addresses or DNS names)

        Return:
        List of chassis addresses.

        """
        self._check_session()
        if not isinstance(chassis_list, (list, tuple, set, dict, frozenset)):
            chassis_list = (chassis_list,)

        if len(chassis_list) == 1:
            status, data = self._rest.put_request(
                'connections', chassis_list[0])
            data = [data]
        else:
            params = {chassis: True for chassis in chassis_list}
            params['action'] = 'connect'
            status, data = self._rest.post_request('connections', None, params)
        return data

    def disconnect(self, chassis_list):
        """Remove connection with one or more chassis.

        Arguments:
        chassis_list -- List of chassis (IP addresses or DNS names)

        """
        self._check_session()
        if not isinstance(chassis_list, (list, tuple, set, dict, frozenset)):
            chassis_list = (chassis_list,)

        if len(chassis_list) == 1:
            self._rest.delete_request('connections', chassis_list[0])
        else:
            params = {chassis: True for chassis in chassis_list}
            params['action'] = 'disconnect'
            self._rest.post_request('connections', None, params)

    def connectall(self):
        """Establish connections to all chassis (test ports) in this session.

        """
        self._check_session()
        self._rest.post_request('connections', None, {'action': 'connectall'})

    def disconnectall(self):
        """Remove connections to all chassis (test ports) in this session.

        """
        self._check_session()
        self._rest.post_request('connections', None,
                                {'action': 'disconnectall'})

    def help(self, subject=None, args=None):
        """Get help information about Automation API.

        The following values can be specified for the subject:
            None -- gets an overview of help.
            'commands' -- gets a list of API functions
            command name -- get info about the specified command.
            object type  -- get info about the specified object type
            handle value -- get info about the object type referred to

        Arguments:
        subject -- Optional.  Subject to get help on.
        args    -- Optional.  Additional arguments for searching help.  These
                   are used when the subject is 'list'.

        Return:
        String of help information.

        """
        if subject:
            if subject not in (
                'commands', 'create', 'config', 'get', 'delete', 'perform',
                'connect', 'connectall', 'disconnect', 'disconnectall',
                'apply', 'log', 'help'):
                self._check_session()
            status, data = self._rest.get_request('help', subject, args)
        else:
            status, data = self._rest.get_request('help')

        if isinstance(data, (list, tuple, set)):
            return ' '.join((str(i) for i in data))
        return data['message'] if 'message' in data else data

    def log(self, level, msg):
        """Write a diagnostic message to a log file or to standard output.

        Arguments:
        level -- Severity level of entry.  One of: INFO, WARN, ERROR, FATAL.
        msg   -- Message to write to log.

        """
        self._check_session()
        level = level.upper()
        allowed_levels = ('INFO', 'WARN', 'ERROR', 'FATAL')
        if level not in allowed_levels:
            raise ValueError('level must be one of: ' +
                             ', '.join(allowed_levels))
        self._rest.post_request(
            'log', None, {'log_level': level.upper(), 'message': msg})

    def download(self, file_name, save_as=None):
        """Download the specified file from the server.

        Arguments:
        file_name -- Name of file resource to save.
        save_as   -- Optional path name to write file to.  If not specified,
                     then file named by the last part of the resource path is
                     downloaded to current directory.

        Return: (save_path, bytes)
        save_path -- Path where downloaded file was saved.
        bytes     -- Bytes downloaded.
        """
        self._check_session()
        try:
            if save_as:
                save_as = os.path.normpath(save_as)
                save_dir = os.path.dirname(save_as)
                if save_dir:
                    if not os.path.exists(save_dir):
                        os.makedirs(save_dir)
                    elif not os.path.isdir(save_dir):
                        raise RuntimeError(save_dir + " is not a directory")

            status, save_path, bytes = self._rest.download_file(
                'files', file_name, save_as, 'application/octet-stream')
        except resthttp.RestHttpError as e:
            raise RuntimeError('failed to download "%s": %s' % (file_name, e))
        return save_path, bytes

    def download_all(self, dst_dir=None):
        """Download all available files.

        Arguments:
        dst_dir   -- Optional destination directory to write files to.  If not
                     specified, then files are downloaded current directory.

        Return:
        Dictionary of {file_name: file_size, ..}

        """
        saved = {}
        save_as = None
        for f in self.files():
            if dst_dir:
                save_as = os.path.join(dst_dir, f.split('/')[-1])
            name, bytes = self.download(f, save_as)
            saved[name] = bytes
        return saved

    def upload(self, src_file_path, dst_file_name=None):
        """Upload the specified file to the server."""
        self._check_session()
        status, data = self._rest.upload_file(
            'files', src_file_path, dst_file_name)
        return data

    def wait_until_complete(self, timeout=None):
        """Wait until sequencer is finished.

        This method blocks your application until the sequencer has completed
        its operation.  It returns once the sequencer has finished.

        Arguments:
        timeout -- Optional.  Seconds to wait for sequencer to finish.  If this
                   time is exceeded, then an exception is raised.

        Return:
        Sequencer testState value.

        """
        timeout_at = None
        if timeout:
            timeout_at = time.time() + int(timeout)

        sequencer = self.get('system1', 'children-sequencer')
        while True:
            cur_test_state = self.get(sequencer, 'state')
            if 'PAUSE' in cur_test_state or 'IDLE' in cur_test_state:
                break
            time.sleep(2)
            if timeout_at and time.time() >= timeout_at:
                raise RuntimeError('wait_until_complete timed out after %s sec'
                                   % timeout)

        return self.get(sequencer, 'testState')

    def _check_session(self):
        if not self.started():
            raise RuntimeError('must first join session')

    def _get_api_version(self):
        if not self._api_ver:
            try:
                status, data = self._rest.get_request('system')
                v = data.get('stcapi_version')
                if v and v.count('.') == 2:
                    # Normalize a version string for comparison.
                    self._api_ver = tuple(map(int, v.split('.')))
                    if self._dbg_print:
                        print('===> stcapi version:', v)
                else:
                    raise RuntimeError('failed to get stcapi_version')
            except Exception as e:
                if self._dbg_print:
                    print('===>', e)
                return (0, 0, 0)

        return self._api_ver

    def has_bulk_ops(self):
        status, data = self._rest.get_request('system')
        if 'features' in data:
            features = data['features']
            if str(features).find('bulk-api') != -1:
                return True
        return False


    def bulkconfig(self, locations, attributes=None, **kwattrs):
        """Sets or modifies one or more object attributes or relations.

        Arguments can be supplied either as a dictionary or as keyword
        arguments.  Examples:
            stc.bulkconfig('emulateddevice[@name="mydev"]/bgprouterconfig/bgpipv4routeconfig[0]',  {'NextHopIncrement': '0.0.1.0'})
            stc.bulkconfig('emulateddevice[@name="mydev"]/bgprouterconfig/bgpipv4routeconfig[1]',  NextHopIncrement='0.0.1.0')

        Arguments:
        locations     -- the locations of object to modify.
        attributes -- Dictionary of attributes (name-value pairs).
        kwattrs    -- Optional keyword attributes (name=value pairs).

        """
        self._check_session()
        if kwattrs:
            if attributes:
                if isinstance(attributes, dict):
                    attributes.update(kwattrs)
                elif isinstance(attributes, list):
                    for attr in attributes:
                        attr.update(kwattrs)
            else:
                attributes = kwattrs
        
        attributes = json.dumps(attributes)
        status, data = self._rest.bulk_put_request('bulk/objects', quote(locations), attributes)
        return data

    def bulkcreate(self, object_type, attributes=None, **kwattrs):
        """Create a new automation object.

        Arguments:
        object_type -- Type of object to create.
        attributes  -- Dictionary of attributes (name-value pairs).
        kwattrs     -- Optional keyword attributes (name=value pairs).

        """
        data = self._bulkcreateex(object_type, None, attributes, **kwattrs)
        return data

    def bulkcreateex(self, under, attributes=None, **kwattrs):
        data = self._bulkcreateex(None, under, attributes, **kwattrs)
        return data

    def _bulkcreateex(self, object_type, under=None, attributes=None, **kwattrs):
        """Create a new automation object.

        Arguments:
        object_type -- Type of object to create.
        under       -- Handle of the parent of the new object.
        attributes  -- Dictionary of attributes (name-value pairs).
        kwattrs     -- Optional keyword attributes (name=value pairs).

        """
        self._check_session()
        params = {'object_type': object_type}
        if under:
            params['under'] = under
        if attributes:
            if isinstance(attributes, dict):
                params.update(attributes)
                if kwattrs:
                    params.update(kwattrs)
            elif isinstance(attributes, list):
                if kwattrs:
                    for attr in attributes:
                        attr.update(kwattrs)
                params['bulklist']  = attributes
        else:
            if kwattrs:
                params.update(kwattrs)

        myparams = json.dumps(params)
        status, data = self._rest.bulk_post_request('bulk/objects', None, myparams)
        return data

    def bulkget(self, locations, args=None, depth=1):
        """Returns the value(s) of one or more object attributes.

        If multiple arguments, this method returns a dictionary of argument
        names mapped to the value returned by each argument.

        If a single argument is given, then the response is a list of values
        for that argument.

        Arguments:
        handle -- Handle that identifies object to get info for.
        args  -- Zero or more attributes or relationships.


        """
        self._check_session()
        status, data = self._rest.bulk_get_request('bulk/objects', quote(locations), args, depth)
        return data

    def bulkperform(self, command, params=None, **kwargs):
        """Execute a command.

        Arguments:
        command -- Command to execute.
        params  -- Optional.  Dictionary of parameters (name-value pairs).
        kwargs  -- Optional keyword arguments (name=value pairs).

        Return:
        Data from command.

        """
        self._check_session()
        if not params:
            params = {}
        if kwargs:
            params.update(kwargs)
        params['command'] = command
        status, data = self._rest.post_request('bulk/perform', None, params)
        return data

    def bulkdelete(self, handles):
        """bulkDelete the specified object.

        Arguments:
        handle -- Handles of objects to delete.

        """
        self._check_session()
        status, data = self._rest.delete_request('bulk/objects', str(handles))
        return data
