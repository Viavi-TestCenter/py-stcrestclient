"""
TestCenter Command Shell

Command shell that provides STC Automation API functionality using an
interactive command line interface, or command file.  This program accesses a
TestCenter Server over its HTTP interface, so no local BLL installation is
needed.

Type help to see help info.  Use <TAB> for command auto-completion.

"""
from __future__ import absolute_import
from __future__ import print_function

import os
import sys
import socket
import cmd
import shlex
import time
import getpass

if sys.version_info < (2, 7):
    print("requires python2.7 or later", file=sys.stderr)
    sys.exit(1)

if __name__ == '__main__' and __package__ is None:
    __package__ = 'stcrestclient'

try:
    from . import stchttp
    from . import resthttp
except ValueError:
    import stchttp
    import resthttp

if sys.hexversion < 0x03000000:
    input = raw_input


class TestCenterCommandShell(cmd.Cmd):

    intro = 'Welcome to TestCenter Command Shell (tccsh)'
    _stc = None
    _sessions = []
    _server = None
    _port = None
    _recording_path = None

    def preloop(self):
        # Do this once before entering command loop.
        self._update_sessions()
        self.postcmd(None, None)

    def postcmd(self, stop, line):
        # Do this after executing each command.
        if not self.use_rawinput:
            self.prompt = ''
            return stop

        if self._stc.session_id():
            self.prompt = '%s:%s> ' % (self._server, self._stc.session_id())
        else:
            self.prompt = '%s:> ' % (self._server,)

        if self._recording_path:
            self.prompt = '*' + self.prompt
            if not line.startswith('recording_'):
                with open(self._recording_path, 'a') as outf:
                    print(line, file=outf)
        return stop

    def do_ls(self, s):
        """List current sessions.
        -l    List session info with each session.
        """
        self._update_sessions()
        info = (s == '-l')
        current = self._stc.session_id()
        for session in self._sessions:
            if info:
                self.do_info(session)
            elif session == current:
                print('[%s] <-- current session' % (session,))
            else:
                print(session)

    def do_info(self, session):
        """Show information about the specified session: info testA - jdoe"""
        if not session:
            session = self._stc.session_id()
            if not session:
                print('no session specified')
                return
        if session.endswith(' -') and session.count('-') == 1:
            session += ' '
        print(session)
        try:
            info = self._stc.session_info(session)
        except Exception as e:
            print(e)
            return
        for k in info:
            print('  %s: %s' % (k, info[k]))

    def complete_info(self, text, line, begidx, endidx):
        return self._complete_session(text)

    def do_delete(self, session):
        """Delete the specified session

        Signals the session to cleanup and exit gracefully.

        Synopsis:
            delete session_name

        Example:
            delete traptest - waits

        """
        if session.endswith(' -') and session.count('-') == 1:
            session += ' '
        if self._not_session(session):
            return
        try:
            self._stc.end_session(True, session)
        except Exception as e:
            print(e)

    def complete_delete(self, text, line, begidx, endidx):
        return self._complete_session(text)

    def do_delete_all(self, s):
        """Delete all sessions from server."""
        self._update_sessions()
        current = self._stc.session_id()
        for session in self._sessions:
            if session != current:
                print('Deleting session:', session)
                self.do_delete(session)

    def do_new(self, s):
        """Create and join a new test session.

        The session that is created is named with the session name and the user
        name separated with ' - '.

        Synopsis:
            new [session_name] [user=user_name] [analytics=true/false]

        Examples:
            new
            new test1
            new user=samuels
            new rfctest user=taylor
            new checknet user=recardo analytics=false

        If the session name is not given, then a session name is automatically
        assigned, starting with "AutoCreatedSession_00".  If the user name is
        not specified, then tccsh tries to get the name of logged-in user.  If
        analytics is not specified, then the current server setting is used.

        """
        if self._stc.session_id():
            # End current session, without deleting TC session or
            # disconnecting REST API from TC session.
            self._stc.end_session(None)
        user_name = ''
        session_name = None
        analytics = None
        params = s.split()
        rm = []
        for i, p in enumerate(params):
            if not user_name and p.startswith('user='):
                rm.insert(0, i)
                u = p.split('=', 1)[-1].strip()
                if u:
                    user_name = u
            elif not analytics and p.startswith('analytics='):
                rm.insert(0, i)
                a = p.split('=', 1)[-1].strip()
                if a:
                    true_vals = ('1', 'true', 'on', 'yes', 'y', 't')
                    analytics = a.lower() in true_vals

        # Remove kw parameters from params list.
        for idx in rm:
            del params[idx]

        # If user name not specified, try to get the name of the current user.
        if not user_name:
            try:
                user_name = getpass.getuser()
            except:
                pass

        # If there is a parameter remaining, it must be session name.
        if params:
            session_name = params.pop(0)

        msg = 'Creating new session'
        if session_name:
            msg += ' "%s"' % (session_name,)
        if user_name:
            msg += ' for user "%s"' % (user_name,)
        if analytics is not None:
            msg += ' (analytics=%s)' % (analytics,)
        print(msg, '...')

        try:
            sid = self._stc.new_session(user_name, session_name,
                                        analytics=analytics)
        except Exception as e:
            print(e)
            return
        self._update_sessions()
        print('Created and joined session:', sid)

    def do_files(self, s):
        """List the files available in the current session."""
        if self._not_joined():
            return
        try:
            for f in self._stc.files():
                print(f)
        except Exception as e:
            print(e)
            return

    def do_join(self, session):
        """Join the specified session: join testA - jdoe

        If no test session is specified, then the client stops using the
        current session.  This does not communicate with the server, and will
        not end the session on the server.
        """
        if not session:
            if self._stc.session_id():
                self._stc.end_session(None)
            else:
                print('specify a session to join')
            return

        if session.endswith(' -') and session.count('-') == 1:
            session += ' '
        if self._not_session(session):
            return
        try:
            bll_ver = self._stc.join_session(session)
        except Exception as e:
            print(e)
            return

        print('Joined session "%s" (BLL ver: %s)' % (session, bll_ver))

    def complete_join(self, text, line, begidx, endidx):
        return self._complete_session(text)

    def do_debug_on(self, s):
        """Enable debug printing."""
        self._stc.enable_debug_print()

    def do_debug_off(self, s):
        """Disable debug printing."""
        self._stc.disable_debug_print()

    def do_recording_on(self, file_path):
        """Enable recording commands to a file.

        Commands recorded to a file can be executed later through tccsh.  This
        is done by specifying the file, containing the recorded commands, using
        the --file command line option.

        When the recording feature is enabled, a '*' appears in the prompt.
        """
        if not file_path:
            print('save file not given')
            return

        if (os.path.isfile(file_path) and self.use_rawinput and
            not self._confirm('Overwrite file', file_path)):
            print('recording not enabled')
            return

        with open(file_path, 'w') as outf:
            print('# tccsh commands recorded on:', time.ctime(), file=outf)
            print('#\n# Comment lines (starting with "#") and blank lines '
                  'are ignored.\n# To execute the commands in this file:\n'
                  '#    python -m stcrestclient.tccsh server --file ',
                  file_path, '\n#', file=outf)

        print('recording enabled')
        self._recording_path = file_path

    def do_recording_off(self, s):
        """Stop recording commands."""
        self._recording_path = None
        print('recording disabled')

    def do_exit(self, s):
        """Exit the TestCenter command shell."""
        return True

    def do_end(self, end_tcs):
        """End the current session: end yes

        An optional 'yes' or 'no' argument specifies whether or not to end the
        the server's test session (yes), or only end the controller (no).
        To stop using the current session without affecting the server at all,
        use the 'join' command without specifying a session.

        If a yes or no argument is not provided, it is prompted for.
        """
        if self._not_joined():
            return

        current = self._stc.session_id()
        yn = None
        if end_tcs:
            if end_tcs == 'yes':
                yn = True
            elif end_tcs == 'no':
                yn = False

        if yn is None:
            if self.use_rawinput:
                yn = self._confirm('End test session', current)
            else:
                yn = True

        if yn:
            print('...waiting for session to end...')

        ended = False
        try:
            self._stc.end_session(yn)
        except Exception as e:
            print(e)
            return
        if yn:
            self._update_sessions()
            print('Terminated test session', current)
        else:
            print('Detached from test session', current)

    def do_kill(self, session):
        """Terminate the specified test session

        For STC ReST API version >= 2.30, this forcefully terminates the test
        session on the server.  Otherwise, behavior is same as delete.

        Synopsis:
            kill session_name

        Example:
            kill so939 - joe

        """
        if not session:
            print('specify a session to join')
            return

        if session.endswith(' -') and session.count('-') == 1:
            session += ' '
        if self._not_session(session):
            return

        print('...waiting for session to end...')
        try:
            self._stc.end_session('kill', session)
        except Exception as e:
            print(e)
            return

        self._update_sessions()
        print('Terminated test session', session)

    def complete_kill(self, text, line, begidx, endidx):
        return self._complete_session(text)

    def do_server(self, server):
        """Specify STC server.

        If a port is not specified, then the value of the STC_SERVER_PORT
        environment variable is used.  If that is not set, then the default
        port 80 is tried.  If a connection cannot be make to the default, then
        port 8888 is used.

        Synopsis:
            server server_address [port]

        Example:
            server 10.109.120.84 80

        """
        server_ok = False
        while not server_ok:
            while not server:
                server = input('Enter server: ')
            try:
                socket.gethostbyname(server)
                server_ok = True
            except socket.gaierror as e:
                print(e)
                server = None

        try:
            self._stc = stchttp.StcHttp(
                server, debug_print=self._stc.debug_print())
        except RuntimeError as e:
            print(e)
            return

        self._server = server
        self._sessions = []

    def do_upload(self, file_path):
        """Upload a file to the session: upload sample.tcc"""
        if self._not_joined():
            return

        if file_path:
            if not os.path.isfile(file_path):
                print('file not found:', file_path)
                return
        else:
            while not file_path:
                file_path = input('upload file: ')
                if not file_path:
                    continue
                if not os.path.isfile(file_path):
                    print('file not found:', file_path)
                    return

        try:
            upload_info = self._stc.upload(file_path)
        except (resthttp.RestHttpError, RuntimeError) as e:
            print(e)
            return

        print('uploaded file:', file_path)
        for k in upload_info:
            print('  %s: %s' % (k, upload_info[k]))

    def do_download(self, file_name):
        """Download a file from the session.

        Synopsis:
            download file [saveas=download_path]

        Example:
            download bll.session.log
            download bll.session.log saveas=/tmp/sessionXYZ.log
        """
        if self._not_joined():
            return

        if file_name:
            file_name = file_name.strip()

        if not file_name:
            print('specify a file to download')
            return

        def check_path(save_path):
            if not save_path:
                return False
            if os.path.isdir(save_path):
                print(save_path, 'is a directory')
                return False
            if os.path.isfile(save_path):
                if (self.use_rawinput and
                    not self._confirm('overwrite', save_path)):
                    return False
            return True

        save_as = None
        if file_name.find('saveas=') != -1:
            file_name, save_as = file_name.split('saveas=', 1)
            file_name = file_name.strip()
            save_as = save_as.strip()
            if not file_name:
                print('specify a file to download')
                return

            while not check_path(save_as):
                save_as = input('save file as: ')

        elif not check_path(file_name.split('/')[-1]):
            save_as = input('save file as: ')
            while not check_path(save_as):
                save_as = input('save file as: ')

        try:
            save_path, bytes = self._stc.download(file_name, save_as)
        except RuntimeError as e:
            print(e)
            return

        print('wrote %s bytes to %s' % (bytes, save_path))

    def do_download_all(self, save_dir):
        """Download all available files.

        Synopsis:
            download_all [save_dir]

        Example:
            download_all
            download_all /tmp/testfiles

        This command will not prompt before overwriting existing files.
        """
        try:
            saves = self._stc.download_all(save_dir)
        except RuntimeError as e:
            print(e)
            return

        if saves:
            print('Downloaded files:')
            for name in saves:
                print('%s (size=%s)' % (name, saves[name]))

    def complete_download(self, text, line, begidx, endidx):
        files = self._stc.files()
        if not text:
            return files
        return [f for f in files if f.startswith(text)]

    def do_system_info(self, args):
        """Shows information about the connected STC system.

        The STC (BLL) version is only available if a current session is active.

        """
        sys_info = self._stc.system_info()
        for k in sys_info:
            print(k, ': ', sys_info[k], sep='')


    def do_set_timeout(self, timeout):
        """Set number of seconds to wait for response."""
        try:
            self._stc.set_timeout(float(timeout))
            print('timeout set to', timeout, 'seconds')
        except Exception as e:
            print(e)


    ###########################################################################
    # Automation API
    #

    def do_stc_apply(self, s):
        """Send test configuration to chassis."""
        if self._not_joined():
            return
        try:
            self._stc.apply()
        except resthttp.RestHttpError as e:
            print('error:', e)
            return
        print('OK')

    def do_stc_get(self, args):
        """Returns the value(s) of one or more object attributes.

        Synopsis:
            stc_get handle [attrib, ..]

        Example:
            stc_get system1 version name

        If multiple arguments, this method returns a dictionary of argument
        names mapped to the value returned by each argument.

        If a single argument is given, then the response is a list of values
        for that argument.

        """
        if self._not_joined():
            return
        args = args.split()
        if not args:
            print('missing object handle')
            return
        handle = args.pop(0)
        try:
            result = self._stc.get(handle, *args)
        except resthttp.RestHttpError as e:
            print(e)
            return

        if isinstance(result, dict):
            for k in result:
                print(k, ': ', result[k], sep='')
        print(result)

    def do_stc_create(self, args):
        """Create a new automation object.

        Attributes are specified as name=value.  If an attribute is assigned a
        list of values, then the list of values must be quoted with each value
        separated by a space: name="value1 value2 value3"

        Synopsis:
            stc_create object_type [under] [attribute=value, ..]

        Example:
            stc_create port project1
            stc_create port project1 location=//10.1.2.3/1/1

        """
        if self._not_joined():
            return
        args = args.split()
        if not args:
            print('missing object type')
            return
        obj_type = args.pop(0)
        under = args.pop(0) if args else None
        try:
            hnd = self._stc.create(obj_type, under, self._args_to_dict(args))
        except resthttp.RestHttpError as e:
            print(e)
            return
        print('created:', hnd)

    def do_stc_perform(self, args):
        """Perform a command.

        Parameters are specified as name=value.  If a parameter is assigned a
        list of values, then the list of values must be quoted with each value
        separated by a space: name="value1 value2 value3"

        Synopsis:
            stc_perform command [param=value, ...]

        Example:
            stc_perform SaveAsXml config=project1 filename=mytest.xml
            stc_perform AttachPorts portList="port1 port2 port3"

        """
        if self._not_joined():
            return
        args = shlex.split(args)
        if not args:
            print('missing command')
            return
        cmd = args.pop(0)
        params = self._args_to_dict(args)
        try:
            print(self._stc.perform(cmd, params))
        except resthttp.RestHttpError as e:
            print(e)

    def do_stc_config(self, args):
        """Sets or modifies one or more object attributes or relations.

        Attributes are specified as name=value.  If an attribute is assigned a
        list of values, then the list of values must be quoted with each value
        separated by a space: name="value1 value2 value3"

        Synopsis:
            stc_config handle [name=value, ...]

        Example:
            stc_config port1 location=//10.100.20.60/1/1

        """
        if self._not_joined():
            return
        args = shlex.split(args)
        if not args:
            print('missing object handle')
            return
        handle = args.pop(0)
        try:
            self._stc.config(handle, self._args_to_dict(args))
        except resthttp.RestHttpError as e:
            print(e)
            return
        print('OK')

    def do_stc_delete(self, handle):
        """Delete the specified object.

        Arguments:
        handle -- Handle of object to delete.

        """
        if self._not_joined():
            return
        if not handle:
            print('missing object handle')
            return
        try:
            self._stc.delete(handle)
        except resthttp.RestHttpError as e:
            print(e)
            return
        print('OK')

    def do_chassis(self, param):
        """Get list of chassis known by test session."""
        if self._not_joined():
            return
        try:
            chassis = self._stc.chassis()
        except resthttp.RestHttpError as e:
            print(e)
            return

        for c in chassis:
            print(c)

    def do_chassis_info(self, chassis):
        """Get information about the specified chassis.

        Synopsis:
            chassis_info chassis_addr

        Example:
            chassis_info 10.100.20.60

        """
        if self._not_joined():
            return
        if not chassis:
            print('missing chassis address, usage: chassis_info 10.100.73.37')
            return
        try:
            info = self._stc.chassis_info(chassis)
        except (resthttp.RestHttpError, RuntimeError) as e:
            print('error:', e)
            return

        for k in info:
            print(k, ': ', info[k], sep='')

    def do_connections(self, param):
        """Get the connected status of each chassis in the test session."""
        if self._not_joined():
            return
        ch_conns = self._stc.connections()
        for ch in ch_conns:
            print('  %-15s' % (ch,), 'CONNECTED' if ch_conns[ch] else '-')

    def do_is_connected(self, chassis):
        """Get the connection status of the specified chassis.

        Synopsis:
            is_connected chassis_addr

        Example:
            is_connected 10.100.20.60

        """
        if self._not_joined():
            return
        if self._stc.is_connected(chassis):
            print('chassis', chassis, 'CONNECTED')
        else:
            print('chassis', chassis, 'not connected')

    def do_stc_connect(self, args):
        """Establish connection to one or more chassis.

        Synopsis:
            stc_connect chassis_list

        Example:
            stc_connect 10.100.20.60 10.100.20.61 10.100.20.62

        Given a list of chassis (IP addresses or DNS names), connect the test
        session to each chassis in list.

        """
        if self._not_joined():
            return
        if not args:
            print('missing chassis')
            return
        chassis_list = args.split()
        try:
            chassis = self._stc.connect(chassis_list)
        except resthttp.RestHttpError as e:
            print(e)
            return
        print('connected %s chassis' % (len(chassis),))

    def do_stc_connectall(self, s):
        """Establish connections to all chassis (test ports) in this session.
        """
        if self._not_joined():
            return
        try:
            self._stc.connectall()
        except resthttp.RestHttpError as e:
            print(e)
            return
        print('OK')

    def do_stc_disconnect(self, args):
        """Disconnect one or more chassis

        Synopsis:
            stc_disconnect chassis_list

        Example:
            stc_disconnect 10.100.20.60 10.100.20.61 10.100.20.62

        Given a list of chassis (IP addresses or DNS names), disconnect each
        chassis in the list from the test session.

        """
        if self._not_joined():
            return
        chassis_list = args.split()
        try:
            self._stc.disconnect(chassis_list)
        except resthttp.RestHttpError as e:
            print(e)
            return
        print('disconnected %s chassis' % (len(chassis_list),))

    def do_stc_disconnectall(self, s):
        """Remove connections to all chassis (test ports) in this session."""
        if self._not_joined():
            return
        try:
            self._stc.disconnectall()
        except resthttp.RestHttpError as e:
            print(e)
            return
        print('OK')

    def do_stc_log(self, s):
        """Write a diagnostic message to a log file or to standard output.

        Synopsis:
            stc_log level message

        Example:
            stc_log ERROR Something unfortunate happened

        The log level can be one of: INFO, WARN, ERROR, FATAL
        """
        if self._not_joined():
            return
        level = msg = None
        params = s.split(' ', 1)
        if params:
            level = params.pop(0).strip().upper()
        if params:
            msg = params.pop(0).strip()

        if not level:
            print('missing argument: level')
            return
        if not msg:
            print('missing argument: message')
            return
        try:
            self._stc.log(level, msg)
        except Exception as e:
            print(e)
            return

        print('logged', level, 'message:', msg)

    def do_stc_help(self, subject):
        """Get help information about Automation API: help subject args

        The following values can be specified for the subject:
            <empty>        -- gets an overview of help.
            commands       -- gets a list of API functions
            <command name> -- get info about the specified command.
            <object type>  -- get info about the specified object type
            <handle value> -- get info about the object type referred to
            list commands [wildcard]    -- get info about STC commands
            list configTypes [wildcard] -- get info about STC config types

        List examples:
            stc_help list commands wait*

        """
        help_args = None
        if subject:
            help_args = subject.split()
            subject = help_args.pop(0)

        try:
            print(self._stc.help(subject, help_args))
        except resthttp.RestHttpError as e:
            print(e)
        except RuntimeError as e:
            if self._not_joined():
                return
            print(e)

    def do_wait_until_complete(self, timeout):
        """Wait until the sequencer is finished: wait_until_complete 30

        Waits until the STC sequencer has completed its operation, or until the
        timeout has elapsed.  If no timeout is specified, then waits forever.
        Waiting can be interrupted with CTRL-C.
        """
        if self._not_joined():
            return
        try:
            if timeout:
                timeout = int(timeout)
            else:
                timeout = None
            self._stc.wait_until_complete(timeout)
            print('sequencer finished')
        except KeyboardInterrupt:
            print('Stopped waiting in wait_until_complete.')
        except RuntimeError as e:
            print(e)
        except ValueError:
            print('timeout must be number of seconds to wait')
        except Exception as e:
            print('error:', e)
        return

    #def do_EOF(self, s):
    #    """Exit the TestCenter command shell."""
    #    return True

    ###########################################################################
    # Utility methods
    #

    def _update_sessions(self):
        try:
            self._sessions = self._stc.sessions()
        except Exception as e:
            print('Error updating sessions:', e)
            return False
        return True

    def _complete_session(self, text):
        if not text:
            return self._sessions
        return [s for s in self._sessions if s.startswith(text)]

    def _confirm(self, prompt, value, default=True):
        confirmed = None
        default_input = 'y' if default else 'n'
        while confirmed is None:
            prompt = '%s "%s" (y/n) [%s]: ' % (prompt, value, default_input)
            yn = input(prompt).lower()
            if yn in ('y', 'yes'):
                confirmed = True
            elif yn in ('n', 'no'):
                confirmed = False
            else:
                confirmed = default

        return confirmed

    def _not_joined(self):
        if not self._stc.session_id():
            print('you must first join a session')
            return True
        return False

    def _not_session(self, session):
        if session not in self._sessions:
            print('no such session: "%s"' % (session,))
            return True
        return False

    def _args_to_dict(self, args):
        params = {}
        for arg in args:
            if '=' in arg:
                k, v = arg.split('=', 1)
                if ' ' in v:
                    v = shlex.split(v)
                params[k] = v
            else:
                params[arg] = None
        return params


def show_help(prg):
    print('Usage: python -m stcrestclient.tccsh server [options]')
    print()
    print('Options:')
    print('  -c command_string\n'
          '      Command string.  Commands are separated by ";" (semicolon).')
    print()
    print('  -d, --debug\n'
          '      Enable debug output.')
    print()
    print('  -f, --file file_path\n'
          '      Read commands from the specified file.')
    print()
    print('  -h, --help\n'
          '      Prints this help information.')
    print()
    print('  -p, --port port_num\n'
          '      Server port to connect to (default %s).' %
          (stchttp.HTTP_DEFAULT_PORT,))
    print()


def main():
    import argparse
    ap = argparse.ArgumentParser(
        prog='python -m stcrestclient.tccsh',
        usage='python -m stcrestclient.tccsh server [options]',
        description='Command shell that provides STC Automation API '
        'functionality using an interactive command line interface, or '
        'command file.')
    ap.add_argument('server', nargs='?',
                    help='Address of TestCenter server to connect to.')
    ap.add_argument('-c', metavar='COMMAND_STRING', dest='cmd_str',
                    help='Command string.  Multiple commands are separated '
                    'by ";" (semicolon).')
    ap.add_argument('--debug', '-d', action='store_true',
                    help='Enable debug output.')
    ap.add_argument('--file', '-f', metavar='FILE_PATH', dest='cmd_file',
                    help='Read commands from the specified file.')
    ap.add_argument('--port', '-p', metavar='PORT', type=int,
                    help='Server port to connect to (default %s).'
                    % (stchttp.HTTP_DEFAULT_PORT,))
    ap.add_argument('--version', '-V', action='store_true',
                    help='Print stcrestclient version number and exit.')
    args = ap.parse_args()

    if args.version:
        import pkg_resources
        pkg_name = 'stcrestclient'
        print(pkg_name, pkg_resources.get_distribution(pkg_name).version)
        return 0

    server_ok = False
    while not server_ok:
        while not args.server:
            args.server = input('Enter server: ')

        try:
            socket.gethostbyname(args.server)
            server_ok = True
        except socket.gaierror as e:
            print('hostname not known')
            args.server = None

    if args.debug:
        print('===> connecting to', args.server, end=' ')
        if args.port:
            print('on port', args.port)
        else:
            print()

    cmds = []
    if args.cmd_file:
        with open(args.cmd_file) as cf:
            for c in cf:
                if not c:
                    continue
                c = c.strip()
                if not c or c[0] == '#':
                    continue
                cmds.append(c)
    elif args.cmd_str:
        for c in args.cmd_str.split(';'):
            if not c:
                continue
            c = c.strip()
            if not c or c[0] == '#':
                continue
            cmds.append(c)

    if cmds:
        tccsh = TestCenterCommandShell(None)
        tccsh.use_rawinput = False
        tccsh.intro = None
    else:
        tccsh = TestCenterCommandShell()

    tccsh._server = args.server
    tccsh._port = args.port
    try:
        tccsh._stc = stchttp.StcHttp(args.server, args.port,
                                     debug_print=args.debug)
        if cmds:
            tccsh.preloop()
            for c in cmds:
                if tccsh.onecmd(c):
                    break
        else:
            tccsh.cmdloop()
    except KeyboardInterrupt:
        print('\nGot keyboard interrupt. Exiting...')
    except Exception as e:
        print(e)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
