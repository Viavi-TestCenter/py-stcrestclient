import datetime
import json
import uuid
import requests
import time
import sys

deployed_instance_info_file = "./deployed_instance_info.txt"
stc_config = "./config/"
VM_IP_file = "./vm_ip_addr.txt"
api_res_queries = "/api/res/queries"
api_test_details = "/api/test-details"
api_objects = "/api/objects"
api_sessions = "/api/sessions"
api_messages = "/api/messages"
api_bulk_perform = "/api/bulk/perform"
api_add_device = "/api/add-device"


#This Funcation will read the deployed instance inof & get the TrafficApp URL with port
def read_aion_url():
    with open(deployed_instance_info_file,'r') as f:
        lines = f.readlines()
        for line in lines:
            if "TestCenter_Plus_IP" in line:
                url = line.split("=")[1].rstrip()
                url = "http://" + url
                return url
    return ""


#This function will read the json file for the config the test
def read_xml_file(stc_config):
    try:
        print("\nReading XML STC Config file {}...".format(json_file_name))
        filename = json_location + stc_config
        print(filename)

        with open(filename,'r') as f:
            json_input = f.read()

        simple_config = json.loads(json_input)
        print(str(datetime.datetime.today()).split()[1].replace(":","").replace(".",""))
        simple_config["id"] = str(datetime.datetime.today()).split()[1].replace(":","").replace(".","")
    except Exception as e:
        print("\n\nERROR: reading json topology file {}...".format(stc_config))
        print(e)
        return None

    return simple_config

#This Funcation will read the STCv port form the VM_IP_List file(vm_ip_addr.txt)
def read_stcvports():
    try:
        print("\n\n Getting STCv Port IP from VM IP file {}...".format(VM_IP_file))
        filename = VM_IP_file
        with open(VM_IP_file, 'r') as f:
            lines = f.readlines()
            for line in lines:
                if "VM_IP1" in line:
                    IP1 = line.split("=")[1].rstrip()
                    break
            for line in lines:
                if "VM_IP2" in line:
                    IP2  = line.split("=")[1].rstrip()
                    break

        ip_list = []
        if "//" in IP1:
            print("HW ports specified??")
            ip_list.append(IP1)
            ip_list.append(IP2)
        else:
            IP1 = "//" + IP1 + "/1/1"
            IP2 = "//" + IP2 + "/1/1"
            ip_list.append(IP1)
            ip_list.append(IP2)
    except Exception as e:
        print("\n\nERROR: reading stcv port file {}...".format(VM_IP_file))
        print(e)
        raise
    return ip_list


#This Funcation will read the "ACCESS_TOKEN" & "REFRESH_TOKEN" from deployed_instance_info.txt file
def get_tokens():
    try:
        with open(deployed_instance_info_file, 'r') as f:
            lines = f.readlines()
            for line in lines:
                if "ACCESS_TOKEN" in line:
                    token = line.split("=")[1].rstrip()
                    break
            access_token = token
            for line in lines:
                if "REFRESH_TOKEN" in line:
                    token = line.split("=")[1].rstrip()
                    break
            refresh_token = token

    except:
        print("ERROR:Unable to open {}".format(deployed_instance_info_file))
        print("Please deploy AION instance using Traffic_deploy script")
        raise

    return access_token,refresh_token

#Upload file
def upload_file(session_id,auth,refresh_token,filename,url):
    headers1 = {
    "X-STC-API-Session":session_id,
    "Authorization":auth,
    "refresh_token":refresh_token,
    }
    testname = filename.strip("./config/")
    print(testname)

    files=[
       ('filename',(testname,open(filename,'rb'),'text/xml'))
    ]
    load=url+api_bulk_perform
    print(load)
    uploadfile = requests.post(url+"/api/files",headers=headers1,data=None,files=files)
    print(uploadfile)
    if uploadfile.status_code != 202:
        delete_session(url,session_id,headers=headers1)
        raise RuntimeError('Unexpected response while uploading file {}: {}'.format(uploadfile.status_code, uploadfile.content))

    session_id=uploadfile.json()['session-id']
    message_id=uploadfile.json()['message-id']
    print("\nMessage-ID is:"+message_id)
    print("\nSession-ID is:"+session_id)
    uploadfile_get = get_message_status(url,headers1,session_id,message_id)
    print(uploadfile_get)

    return testname,load

#Load xml file
def load_file(load,session_id,auth,refresh_token,testname):
    headers2 = {
    "X-STC-API-Session":session_id,
    "Authorization":auth,
    "refresh_token":refresh_token,
    "content-type": "application/json",
    }

    payload = json.dumps([{
         "command": "LoadFromXmlCommand",
         "arguments": {
            "FileName": testname
            }
     }])

    loadfile = requests.post(load, headers=headers2, data=payload)
    print(loadfile)
    url='//'.join(load.split('/')[0:3:2])
    if loadfile.status_code != 202:
        delete_session(url,session_id,headers=headers2)
        raise RuntimeError('Unexpected response while loading config {}: {}'.format(loadfile.status_code, loadfile.content))
    time.sleep(10)

    message_id1=loadfile.json()['message-ids'][0]
    print("\nMessage-ID Load is:"+message_id1)
    loadfile_get = get_message_status(url,headers2,session_id,message_id1)
    print(loadfile_get)

    return headers2,session_id

# Delete session
def delete_session(url,session_id,headers):
    delete=url+"/api/sessions/"+session_id
    sessiondelete = requests.delete(delete, headers=headers, data=None)
    time.sleep(15)
    print(sessiondelete)
    print("Session is deleted")



# Get the message status. Delete session upon FAILURE
def get_message_status(url,headers,session_id,message_id):
    res=requests.get(url+api_messages+"/"+message_id,headers=headers,data=None)
    print(res)
    print(res.json())
    status_code=res.status_code
    state=res.json()['state']
    count=1

    while state!="SUCCESS" and count<=10:
       time.sleep(5)
       res=requests.get(url+api_messages+"/"+message_id,headers=headers,data=None)
       print(res.json())
       state=res.json()['state']
       messages=str(res.json()['messages'])
       count+=1

    if state == "FAILURE":
        print("TEST FAILURE REASON: "+messages)
        delete_session(url,session_id,headers)
        print("Test Verdict: FAIL")
        sys.exit(1)

    return res

#Create new session
def create_new_session(url,headers):
    print(create_new_session)
    new_session = requests.post(url+api_sessions,headers=headers,data=None)
    print(new_session)    
    print(new_session.content)    

    if new_session.status_code != 201:
        raise RuntimeError('Unexpected response while creating session {}: {}'.format(new_session.status_code, new_session.content))
    session_id = new_session.json()['session-id']
    print("\nsession_id is:"+session_id)
        
    return session_id

#Add offline ports
def add_offline_ports(url,headers,session_id,num_ports):
    for i in range(0,int(num_ports)):
        offline_ports_body = json.dumps({
          "operation": "CREATE",
          "create-objects": [
           {
                "object-type": "port",
                "parent-handle": "project1",
                "properties": {
                    "name": "TestPort"+str(i),
                    "location": "//(Offline)/1/1"
                }
            }]
        })

        offlineports = requests.post(url+api_objects, headers=headers, data=offline_ports_body)
        if offlineports.status_code != 202:
            delete_session(url,session_id,headers)
            raise RuntimeError('Unexpected response while adding offline ports {}: {}'.format(offlineports.status_code, offlineports.content))

        print("Get Offline ports Message")
        session_id=offlineports.json()['session-id']
        message_id=offlineports.json()['message-id']
        print("\nSession-ID Offlineports is:"+session_id)
        print("\nMessage-ID Offlineports is:"+message_id)
        offlineports1 = get_message_status(url,headers,session_id,message_id)
        print(offlineports)



#Modify port location
def modify_port_loc(url,headers,session_id,num_ports,slot_list):
    if int(num_ports) != len(slot_list):
        print("num_ports {} and slots in slot_list {} does not match".format(num_ports,len(slot_list)))
        delete_session(url,session_id,headers)
        raise RuntimeError('Unexpected response while modify_port_loc {}: {}'.format(modify_port_loc.status_code, modify_port_loc.content))

    i = 1
    while i <= int(num_ports):
        modify_port_loc_body = json.dumps({
            "operation": "UPDATE",
            "update-objects": [
            {
                "handle": "port"+str(i),
                "properties": {
                    "location": slot_list[int(i) - 1]
                }
            } ]
        })
        modify_port_loc = requests.post(url+api_objects, headers=headers, data=modify_port_loc_body)
        if modify_port_loc.status_code != 202:
            delete_session(url,session_id,headers)
            raise RuntimeError('Unexpected response while modify_port_loc {}: {}'.format(modify_port_loc.status_code, modify_port_loc.content))

        print("Get Modify port location Message")
        session_id=modify_port_loc.json()['session-id']
        message_id=modify_port_loc.json()['message-id']
        print("\nSession-ID Modify port location is:"+session_id)
        print("\nMessage-ID Modify port location is:"+message_id)
        modify_port_loc1 =get_message_status(url,headers,session_id,message_id)
        print(modify_port_loc1)
        i = i + 1

# Function to run commands using /api/bulk/perform api
def perform(url,headers,session_id,cmd):
    req_body = json.dumps([{ "command": cmd}])
    cmd_out = requests.post(url+api_bulk_perform,headers=headers,data=req_body)

    if cmd_out.status_code != 202:
        delete_session(url,session_id,headers)
        raise RuntimeError('Unexpected response while delete_session {}: {}'.format(cmd_out.status_code,cmd_out.content))

    message_id = cmd_out.json()['message-ids'][0]
    message_status = get_message_status(url,headers,session_id,message_id)
    return message_status

# Return PassFailstate result value from the payload of arpndresultcommand
def verify_arp_pass_fail(payload):
    out = json.loads(payload.content)
    out2 = json.loads(out['messages'][0]['payload'])
    print(out2['PassFailState'])

    return out2['PassFailState']


#Add device
def add_device(url,headers,session_id,encap):
    add_device_body = json.dumps({
        "port-handles": [
            "port1","port2"
        ],
        "device-blocks-per-port": 1,
        "vlan-count": 0,
        "lower-level-encap": "EthernetII",
        "upper-level-encap": encap,
        "supported-protocol": [
            "None"
        ]
    })

    add_device = requests.post(url+api_add_device, headers=headers, data=add_device_body)
    print(add_device)
    if add_device.status_code != 202:
        delete_session(url,session_id,headers)
        raise RuntimeError('Unexpected response while adding devices {}: {}'.format(add_device.status_code, add_device.content))
    print("Get add device Message")
    session_id=add_device.json()['session-id']
    message_id=add_device.json()['message-id']
    print("\nSession-ID add_device is:"+session_id)
    print("\nMessage-ID add_device is:"+message_id)
    add_device1 =get_message_status(url,headers,session_id,message_id)
    print(add_device1)

#Modify ip's B2B
def modify_ip_b2b(url,headers,session_id):
    modify_ip_b2b_out = requests.post(url+api_objects, headers=headers, data=modify_ip_b2b_body)
    if modify_ip_b2b_out.status_code != 202:
        delete_session(url,session_id,headers)
        raise RuntimeError('Unexpected response while adding offline ports {}: {}'.format(modify_ip_b2b_out.status_code, modify_ip_b2b_out.content))

    message_id=modify_ip_b2b_out.json()['message-id']
    print("\nSession-ID modify_ip_b2b is:"+session_id)
    print("\nMessage-ID modify_ip_b2b is:"+message_id)
    modify_ip_b2b1 =get_message_status(url,headers,session_id,message_id)
    print(modify_ip_b2b1)


# Load handle_name object ex: emulateddevice1 & 2
def get_handle(url,headers,session_id,handle_name):
    print("get_handle")
    device_name = json.dumps({
        "operation": "GET",
        "get-objects": [
            {
                "handle": handle_name
            }
        ]
    })

    get_handle = requests.post(url+api_objects, headers=headers, data=device_name)
    print(get_handle)
    if get_handle.status_code != 200 and get_handle.status_code != 202:
        delete_session(url,session_id,headers)
        raise RuntimeError('Unexpected response while get handle{}: {}'.format(get_handle.status_code, get_handle.content))

# Add x number of RAW stream blocks on the ports specified
def add_raw_streamblock(url,headers,session_id,port_handles,num_ports):

    for port_handle in port_handles:
        for i in range(0,int(num_ports)):
            raw_streamblock_body = json.dumps({
                "operation": "CREATE",
                "create-objects": [
                {
                    "object-type": "StreamBlock",
                    "parent-handle": port_handle,
                    "properties": {
                        "name": "Raw-"+port_handle+"-stream-"+str(i)
                    }
                 }
                ]
            })

            add_raw_streamblock = requests.post(url+api_objects, headers=headers, data=raw_streamblock_body)

            if add_raw_streamblock.status_code != 202:
                delete_session(url,session_id,headers)
                raise RuntimeError('Unexpected response while add_raw_streamblock {}: {}'.format(add_raw_streamblock.status_code, add_raw_streamblock.content))
    
            session_id1 = add_raw_streamblock.json()['session-id']
            message_id1 = add_raw_streamblock.json()['message-id']
            print("Session-ID add stream block is:"+session_id1)
            print("Message-ID add stream block is:"+message_id1)
            add_raw_streamblock1 =get_message_status(url,headers,session_id,message_id1)
            print("added stream block {} on port {}".format(i,port_handle))

#get result id and verify TC IQ Results
def verify_iq_results(url,headers,json_file,num_rows):
    req6=requests.get(url+api_test_details,headers=headers,data=None)
    print(req6)
    print(req6.text)
    result_id=req6.json()['db-id']
    print(result_id)

    json_location = "./IQresults/"
    filename = json_location + json_file
    with open(filename,'r') as f:
        json_input = f.read()
    body = json.loads(json_input)
    body['database']['id']=result_id
    req6=requests.post(url+api_res_queries,headers=headers,json=body)
    print(req6)
    iq_result_obtained=req6.json()
    print(iq_result_obtained['result']['rows'])
    actual_num_rows=len(iq_result_obtained['result']['rows'])
    print(actual_num_rows)
    if (int(num_rows)==int(actual_num_rows) and iq_result_obtained['result']['rows']!='None'):
        print("IQ verification passed")
        return(iq_result_obtained['result']['rows'])
    else:
        print("IQ verification failed")

## Req body 
modify_ip_b2b_body = json.dumps({
  "operation": "UPDATE",
  "update-objects": [
    {
      "handle": "ipv4if1",
      "properties":{
        "Address": "192.168.2.3",
        "Gateway": "192.168.2.4",
        "ResolveGatewayMac": "TRUE"
      }
    },
      {
      "handle": "ipv4if2",
      "properties":{
        "Address": "192.168.2.4",
        "Gateway": "192.168.2.3",
        "ResolveGatewayMac": "TRUE"
      }
    }
  ]
})

raw_streamblock_body = json.dumps({ 
        "operation": "CREATE", 
        "create-objects": [ 
        { 
            "object-type": "StreamBlock", 
            "parent-handle": "port1", 
            "properties": { 
                "name": "Raw1" 
            } 
         } 
        ] 
})