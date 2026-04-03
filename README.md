# Python STC ReST API Client: stcrestclient

The stcrestclient package provides the `stchttp` ReST API library module.  This allows simple function calls, nearly identical to those provided by `StcPython.py`, to be used to access TestCenter server sessions via the STC ReST API.

The stcrestclient package also includes the command-line shell `tccsh` that lets you work interactively with remote STC sessions via the ReST API.  This is useful for testing and debugging without having to write any code.

Basic ReST functionality is provided by the `resthttp` module, and may be used for writing ReST clients independent of STC.  This module is built on top of the [Requests](http://docs.python-requests.org/) package.

All code works with Python2.7 and Python3.x.

## Topics

- [Quick Start](https://github.com/Spirent-STC/py-stcrestclient#quick-start)
- [Installation](https://github.com/Spirent-STC/py-stcrestclient#installation)
- [stchttp Module](https://github.com/Spirent-STC/py-stcrestclient#using-the-stchttp-module)
- [Aion Platform Usage](https://github.com/Spirent-STC/py-stcrestclient#using-aionstchttp-with-the-aion-platform)
- [Using tccsh Command Shell](https://github.com/Spirent-STC/py-stcrestclient#using-the-rest-api-command-line-shell-tccsh)
- [Automation Client ReST Adapter](https://github.com/Spirent-STC/py-stcrestclient#automation-client-rest-api-adapter)
- [TestCenter Server Information](https://github.com/Spirent-STC/py-stcrestclient#testcenter-server-information)
- [Ending Sessions](https://github.com/Spirent-STC/py-stcrestclient#ending-sessions-with-stcrestclient)
- [Automation to ReST API Quick Reference](https://github.com/Spirent-STC/py-stcrestclient#automation-api-to-rest-api-quick-reference)

## Quick Start
- Get Python pip if not already installed (Download https://bootstrap.pypa.io/get-pip.py):

   `python get-pip.py`

- Install latest stcrestclient:

   `pip install -U stcrestclient`

- Interact with TestCenter server using the [command-line shell](https://github.com/Spirent-STC/py-stcrestclient#using-the-rest-api-command-line-shell-tccsh):

   `tccsh`

- Get information about a TestCenter server (and check if it is running):

   `stcinfo server_addr`

- Write Python code to talk with TestCenter server:

   `python`
   ```python
   >>> from stcrestclient import stchttp
   >>> stc = stchttp.StcHttp('stcserver.somewhere.com', timeout=5)
   >>> sid = stc.new_session('JoeUser', 'ExampleTest')
   >>> stc.system_info()
   ```

- Install [client adapter](https://github.com/Spirent-STC/py-stcrestclient#automation-client-rest-api-adapter) for Python automation scripts to use ReST API, without any code change:

   ```
   python -m stcrestclient.adapt
   export STC_REST_API=1
   export STC_SERVER_ADDRESS=10.107.119.174'
   ```

- Display API documentation:

   `pydoc stcrestclient.stchttp`

## Installation

### Install Using pip

Make sure Python pip is installed on you system.  If you are using virtualenv, then pip is already installed into environments created by virtualenv, and using sudo is not needed.  If you do not have pip installed, download this file:
<https://bootstrap.pypa.io/get-pip.py> and run `python get-pip.py`.  If installing into your system Python, you will need sufficient privileges for this, as wall as for the commands below. 

To install or upgrade to the latest, use pip to install from pypi:

    pip install -U stcrestclient

Or, install from the repository archive URL:

    pip install -U https://github.com/Spirent-STC/py-stcrestclient/archive/master.zip

### Show information about stcrestclient:

If you want to check if the stcrestclient package is installed and see information about the installed package use the following command:

    pip show stcrestclient

### Install From Source

The stcrestclient package is installed from source using distutils in the usual way.  Download the [source distribution](https://github.com/Spirent-STC/py-stcrestclient/archive/master.zip) first.  Unzip the zip archive and run the setup.py script to install the package site-wide.  Here are to commands to do that:

    wget https://github.com/Spirent-STC/py-stcrestclient/archive/master.zip py-stcrestclient.zip
    unzip py-stcrestclient.zip
    cd py-stcrestclient-*
    sudo python setup.py install
    
You can also clone the [repository](https://github.com/Spirent-STC/py-stcrestclient) from GitHub.  Instructions for this not included here.

## Using the stchttp module

To use the STC ReST client library, import the `stchttp.py` module, create a new session or join an existing session, and then call the STC API automation functions provided by the module.

```python
from stcrestclient import stchttp
stc = stchttp.StcHttp('stcserver.somewhere.com')

# Set seconds to wait for response.  A zero-value means no timeout.
stc.set_timeout(5)

# Create and join new session
sid = stc.new_session('JoeUser', 'ExampleTest')

# Join an already existing session.
stc.join('OtherTest - JoeUser')

# Get system information
stc.system_info()

# Create a Project
project = stc.create('project')

# Create Port under project
port_handle = stc.create('port', project)

# Connect to a chassis
stc.connect('172.16.23.54')

# Configure port location (params as kwargs or dictionary)
stc.config(port_handle, location='//172.16.23.54/1/1')
stc.config(port_handle, {'location': "//172.16.23.54/1/1"})

# Create StreamBlock under Port
sb_handle = stc.create('streamBlock', port_handle)

# Apply config
stc.apply()

# Run STAK command to archive log files
stc.perform('spirent.core.ArchiveDiagnosticLogsCommand')

# Wait for sequencer to finish
stc.wait_until_complete(timeout=30)

# Write a message to the log file
stc.log('INFO', 'Done with my test')

# Get a list of available files
files_list = stc.files()

# Download and save the diagnostics.tgz file
name, size = stc.download('diagnostics.tgz')

# ...Or, download all files
name_size_dict = stc.download_all()

# Upload config file
stc.upload(config.xml')

# Load STC config from file (params as kwargs or dictionary).
stc.perform('LoadFromXml', filename='config.xml')
stc.perform('LoadFromXml', {'filename': 'config.xml'})

# Detach from and delete the session
stc.end_session(end_tcsession=True)
```

For example usage, look in the [examples](https://github.com/Spirent-STC/py-stcrestclient/tree/master/examples) directory for Python code examples.  The examples, like the client lib, will run with either Python2.7 or Python3.x.  The print out command line help for a specific function above, use `pydoc`. For example: `pydoc stcrestclient.stchttp.StcHttp.new_session`

## Using AionStcHttp with the AION Platform

`AionStcHttp` is a drop-in replacement for `StcHttp` that handles AION authentication and product-instance discovery automatically.  It authenticates with the AION platform, discovers the target STC LabServer endpoint from the AION inventory, and injects a Bearer token into every HTTP request.  Tokens are refreshed proactively (at 80% of their lifetime) and reactively (on 401 responses), so long-running sessions remain authenticated without any extra code.

### Parameters

| Parameter | Environment Variable | Description |
|---|---|---|
| `aion_url` | `AION_URL` | Base URL of the AION platform, e.g. `https://aion.example.com`. |
| `username` | `AION_USERNAME` | AION user email / username. |
| `password` | `AION_PASSWORD` | AION user password. |
| `node_name` | — | AION node name hosting the target product instance, e.g. `10.109.120.117`. Use together with `ui_port` to uniquely identify an instance when multiple nodes or instances are present. |
| `ui_port` | — | UI port of the target product instance. Use together with `node_name` to uniquely identify an instance when multiple instances are running on the same node. The UI port is the port number visible in AION's Product Manager web page (e.g. `64006`). Omit when only one instance is present. |
| `product_ca_cert` | — | Path to CA certificate bundle used to verify the stcapi HTTPS connection, e.g. `/path/to/product_ca_cert.pem`. Required when the stcapi endpoint uses HTTPS. |
| `aion_verify` | — | TLS verification for AION platform calls. Set to `False` to disable verification, or provide a path to a CA bundle. Defaults to `True`. |
| `debug_print` | — | Enable debug output. Defaults to `False`. |
| `timeout` | — | HTTP request timeout in seconds. Defaults to `None` (no timeout). |

`aion_url`, `username`, and `password` can be supplied as arguments or via their corresponding environment variables.  The argument takes precedence when both are set.  A `RuntimeError` is raised at construction time if any of the three is missing from both sources.

### Basic Usage

```python
from stcrestclient.aionstchttp import AionStcHttp

stc = AionStcHttp(
    aion_url='https://aion.example.com',
    username='user@example.com',
    password='secret',
    product_ca_cert='/path/to/product_ca_cert.pem',
)
stc.new_session(user_name='myuser', session_name='mysession')
stc.create('port', under='project1', name='myport')
stc.end_session()
```

### Using Environment Variables

Credentials can be supplied entirely via environment variables, keeping them out of source code:

```bash
export AION_URL=https://aion.example.com
export AION_USERNAME=user@example.com
export AION_PASSWORD=secret
```

```python
from stcrestclient.aionstchttp import AionStcHttp

# No credentials in code
stc = AionStcHttp(product_ca_cert='/path/to/product_ca_cert.pem')
stc.new_session(user_name='myuser', session_name='mysession')
```

### Obtaining the AION Cluster Certificate for aion_verify

If the AION platform uses a self-signed certificate, set `aion_verify` to the path of the certificate file.  Use the following command to retrieve and save the certificate from the AION cluster:

```bash
echo | openssl s_client -connect 10.109.120.117:443 2>/dev/null | openssl x509 > aion_cluster.pem
```

Replace `10.109.120.117` with the address of your AION cluster.  Then pass the saved file to `aion_verify`:

```python
stc = AionStcHttp(
    aion_url='https://10.109.120.117',
    username='user@example.com',
    password='secret',
    aion_verify='aion_cluster.pem',
)
```

### Selecting a Specific Instance

When multiple STC LabServer instances are running across AION nodes, use `node_name` and `ui_port` together to uniquely identify the target instance.  The node name and UI port are visible in AION's Product Manager web page.  The matching stcapi port is discovered automatically.

```python
stc = AionStcHttp(
    aion_url='https://aion.example.com',
    username='user@example.com',
    password='secret',
    node_name='10.109.120.117',
    ui_port=64006,
    product_ca_cert='/path/to/product_ca_cert.pem',
)
```



## Using the ReST API Command-line Shell: tccsh

This is an interactive command shell that provides Session Manager and Automation API functionality using a command-line interface.  This command accesses a TestCenter Server over its HTTP interface, so no local BLL installation is needed.  This utility is primarily useful for testing and debugging the ReST API.  It should run on any platform with Python 2.7 or 3.x.

To start the shell, use the following command:
```
tccsh
```
or
```
python -m stcrestclient.tccsh
```

You will be prompted for the server address to connect to.  You can also supply the server address on the command line: `tccsh 10.8.232.105`  To see command line options: `tccsh --help`

    usage: tccsh server [options]
	       python -m stcrestclient.tccsh server [options]

    Command shell that provides STC Automation API functionality using an
    interactive command line interface, or command file.

    positional arguments:
      server                Address of TestCenter server to connect to.

    optional arguments:
      -h, --help
          show this help message and exit

      -c COMMAND_STRING
          Command string. Multiple commands are separated by ";" (semicolon).

      --debug, -d
          Enable debug output.

      --file FILE_PATH, -f FILE_PATH
          Read commands from the specified file.

      --port PORT, -p PORT
          Server TCP port to connect to (default 80).

Commands can be entered from a file (`--file`) or from a command string (`-c`), as an alternative to the normal interactive mode.

### Interactive tccsh

Once started and connected to a server, you will see a prompt that contains the address of the server you are connected to.

Type help to see help info on the available commands.  This displays the help menu:

    Documented commands (type help <topic>):
    ========================================
    chassis       exit           recording_on    stc_disconnectall  
    chassis_info  files          server          stc_get            
    connections   help           set_timeout     stc_help           
    debug_off     info           stc_apply       stc_log            
    debug_on      is_connected   stc_config      stc_perform        
    delete        join           stc_connect     system_info        
    delete_all    kill           stc_connectall  upload             
    download      ls             stc_create      wait_until_complete
    download_all  new            stc_delete    
    end           recording_off  stc_disconnect

To see help for a command, type `help` followed by the command name.  For example, type `help new` to see help on the `new` command.

Use `Tab` for command auto-completion. Command auto-completion may not work on Windows.

The interactive shell has a recording feature that is enabled by the `recording_on` command.  This records commands, entered interactively, to a file that can be played back later through tccsh.  Executing the recorded commands is done by running tccsh and specifying the file containing the recorded commands, using the `--file` command line option.

### Command-line tccsh

The tccsh shell can also be use on the command-line, by specifying a file containing tccsh commands, or by providing a command string.

A file is provided using the `--file` command line option.  A command file contains commands that are executed in order, and each command is on a separate line.  Comment lines (lines starting with "#") and blank lines are ignored.

A command string is provided using the `-c` command line option.  A number of commands can be specified, each separated by a ";" semicolon.  For example:

   `tccsh server -c 'new test1 user=joe; stc_create project; stc_create port project1'`

The above will create a new test session, create a project, and create a port object under the project.  The output looks like this:

```
Created and joined session: test1 - jdoe
created: project1
created: port1
```

## Automation Client ReST API Adapter

This package includes a ReST API client adapter module.  The ReST API client adapter is functionally identical to the legacy StcPython.py module, except that it communicates with the STC ReST API.  Without requiring any code changes, this allows STC automation scripts to communicate over ReST, and not need a local STC installation.  This ReST adapter enables ReST API access if the environment variable `STC_REST_API` is set to a non-empty value.  If `STC_REST_API` is not set, then the non-rest STC client module is loaded if there is a local STC installation.

### Installing Client Adapter module

To enable existing Python automation scripts to use the STC ReST API, run the adapt script:

```
python -m stcrestclient.adapt
```

This installs a new StcPython.py client module, that allows existing automation scripts to work using either the ReST API adapter or the legacy client module. When the above command is run from within the STC installation directory, `StcPython.py` is replaced with a new file that operates using ReST or legacy (non-ReST) mode, depending on whether the `STC_REST_API` environment variable is set.

- Activate ReST adapter: `export STC_REST_API=1; export STC_SERVER_ADDRESS=labserve_addr`
- Deactivate ReST adapter: `unset STC_REST_API`

Set `STC_REST_API` and `STC_SERVER_ADDRESS` in the login profile to avoid having to set these every login. This way automation scripts will use ReST by default.  

Nothing about the Python automation clients needs to change.  They can be run as normal, and can even connect to existing existing TestCenter server sessions.

### Running Without STC Installation

Installing the ReST adapter and setting `STC_REST_API` and `STC_SERVER_ADDRESS` allows existing automation scripts to run on a system where there is no STC installation.  All that is required on the system Python, the stcrestclient package, and the `StcPython.py` file that was replaced when the adapter was installed.

To run your Python automation scripts, have `StcPython.py` in the same directory as your scripts, or its location is in [`PYTHONPATH`](https://docs.python.org/3/using/cmdline.html#envvar-PYTHONPATH), set the `STC_REST_API` and `STC_SERVER_ADDRESS` environment variables, and then run your the automation scripts.  The automation scripts should operate using ReST. 

### Existing STC Sessions

If a session, identified by the specified user and session name, already exists then the adapter raises an exception.  If this is not the desired behavior, then this can be changed by setting the value of the `EXISTING_SESSION` environment variable, or passing the `existing_session` argument into the `new_session()` function.  The value of `existing_session` determines the behavior, and the value may be one of the following: `kill`, `join`

- `kill`: Terminate the existing session, and create a new one.
- `join`: Continue using the existing session.

Any other value results in the default behavior, which is to raise an exception if the specified session already exists, and create a new session otherwise.

### Environment Variables

- `STC_SERVER_ADDRESS` specifies the STC server (Lab Server) addres.
- `STC_SESSION_NAME` specifies the name label part of session ID.
- `EXISTING_SESSION` specifies the behavior when the specified session already exists. Recognized values: "kill", "join"

## TestCenter Server Information.

The stcrestclient package includes a command, `systeminfo`, to retrieve STC and API information from a system running a TestCenter server. This module is provided as a convenient command line tool to get information about a TestCenter server.

To get information about a TestCenter server use the following command:

`stcinfo server_addr` or `python -m stcrestclient.systeminfo server_addr`

## Ending Sessions with stcrestclient

### When using `stchttp` module

A session can be ended in three ways, depending on the value of the end_tcsession parameter of the StcHttp.end_session() method:

1. end_tcsession=None: Stop using session locally, do not contact the server.
1. end_tcsession=False: End client controller, but leave test session on server.
1. end_tcsession=True: End client controller and terminate test session (default).

Specifying end_tcsession=False ends the client controller.  This means that it detaches the ReST API's STC controller from the test session. This is useful to do before attaching an STC GUI or legacy automation script, to prevent having multiple controllers that may interfere with each other. This requires that the server is running version 2.1.5 or later of the STC ReST API.

### When using `tccsh` shell

When using the `tccsh` command shell, the equivalent commands for the above items are:

1. Invoke `join` with no argument: Stop using session locally
1. Invoke `end` and specify "no": End client controller only
1. Invoke `end` and specify "yes": End client controller and test session

## Automation API to ReST API Quick Reference

| Automation API    | StcHttp API                  | ReST Equivalent                                               |
| ----------------- | ---------------------------- | ------------------------------------------------------------- |  
| apply             | `apply()`                    | PUT http://<i></i>host.domain/stcapi/apply                    |
| config            | `config(obj, ..)`            | PUT http://<i></i>host.domain/stcapi/objects/{object}         |
| connect           | `connect([chassis, ..])`     | PUT http://<i></i>host.domain/stcapi/connections/{chassis}    |
| create            | `create(obj_type, ..)`       | POST http://<i></i>host.domain/stcapi/objects/                |
| delete            | `delete(obj)`                | DELETE http://<i></i>host.domain/stcapi/objects/{object}      |
| disconnect        | `disconnect([chassis, ..])`  | DELETE http://<i></i>host.domain/stcapi/connections/{chassis} |
| get               | `get(obj, ..)`               | GET http://<i></i>host.domain/stcapi/objects/{object}         |
| help              | `help(subject)`              | GET http://<i></i>host.domain/stcapi/help/{subject}           |
| help list         | `help('list', ..)`           | GET http://<i></i>host.domain/stcapi/help/list?{search_info}  |
| log               | `log(level, msg)`            | POST http://<i></i>host.domain/stcapi/system/log/             |
| perform           | `perform(command, ..)`       | POST http://<i></i>host.domain/stcapi/perform/{command}       |
| release           | `perform('releasePort', ..)` | See perform |
| reserve           | `perform('reservePort', ..)` | See perform |
| sleep             | N/A                          | NOT SUPPORTED -- client must implement |
| subscribe         | `perform(`<br>`'ResultsSubscribe', ..)` | See perform          |
| unsubscribe       | `perform(`<br>`'ResultDataSetUnsubscribe', ..)` | See perform  |
| waitUntilComplete | `wait_until_complete(timeout)` | Polls sequencer state         |

Note: The STC ReST API supports additional methods, not specified in this table, that perform common STC automation tasks.  For example, the REST API provides methods for connecting or disconnecting all chassis using a POST request.
