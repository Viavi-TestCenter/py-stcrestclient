from __future__ import print_function
import sys
from stcrestclient.aionstchttp import AionStcHttp

session_name = 'aion-example'
user_name = 'aionuser'

if len(sys.argv) < 4:
    print('usage: python', sys.argv[0], '<aion_url> <username> <password>',
          file=sys.stderr)
    sys.exit(1)

aion_url, username, password = sys.argv[1], sys.argv[2], sys.argv[3]

try:
    stc = AionStcHttp(
        aion_url=aion_url,
        username=username,
        password=password,
    )

    sid = stc.new_session(user_name=user_name, session_name=session_name)
    print('Created session:', sid)

    info = stc.system_info()
    print('System info:', info)

    project = stc.create('project')
    print('Project handle:', project)

    port1 = stc.create('port', project)
    print('Port 1 handle:', port1)

    port2 = stc.create('port', project)
    print('Port 2 handle:', port2)

    stc.end_session()
    print('Session ended.')

except Exception as e:
    print(e, file=sys.stderr)
    sys.exit(1)
