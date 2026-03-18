"""
Client Script: This script is activated by mworks io devices (Wheel input) and 
sends 

 - movement direction (up or down) to server.py
 - Receives reward zone trigger from server.py

"""


# libraries
import sys
import socket
import subprocess
import os
import time
import threading
import json
from datetime import datetime

##########################

# Pull in path_hardware_params

##########################
#Get home dir
home_dir = os.path.expanduser("~")

# expected path is /user/documents/vr_exp_params
exp_params_path = home_dir + '/' + 'Documents/' + 'vr_exp_params/'

#Repo path
repo_path = home_dir + '/Repositories/VR_tunnel_paradigms/'

# Expected path for path params json
p_params = repo_path + 'params/path_hardware_params.json'

#Grab path params (json needs to be created in before script can run)
with open(p_params, 'r') as f:
    path_hardware_params = json.load(f)

oddball_tunnel_path = path_hardware_params['python_2_oddball_server_path']
##########################

# json setup (might want to make this yml but need to install via mworks env)

##########################

#Check and see if vr_exp_params path exists 
if os.path.isdir(exp_params_path):
    print('Found exp_params_path')
else:
    print('Did not find exp_params_path')
    #make path
    os.makedirs(exp_params_path)
    print('Created exp_params_path')

#Look if vr_exp_params has any config json files
jsons_configs = os.listdir(exp_params_path)

#If there is not create base config (used for troubleshooting purposes)
if not jsons_configs:
    exp_params = {
        'reward_pause': 5,
        'wall_z_pos': 4,
        'wall_x_pos': 0,
        'wall_scale': 8,
        'cylinder_x_pos': 0,
        'cylinder_z_pos': 10,
        'grating_distortion': 7,
        'lower_bound': -15,
        'upper_bound': 390,
        'photodiode_present': False,
        'photodiode_size_x':0.08,
        'photodiode_size_y':0.03
    }
    #create base
    with open(exp_params_path + '/' + 'base_config.json', 'w') as f:
        json.dump(exp_params, f)
    


def json_create(dict, project_path):
    """
    Function that creates json file for server.py

    input arguments:
    dict: exp params dictionary
    output_path: str path to place yaml (should come from mworks)
    """
    #output datetime (remove punc that is not acceptable for filenames)
    dtime =  datetime.now().strftime('%Y-%m-%d_%H:%M:%S').replace(':', '_').replace('-','_')

    # id of mouse being run
    animal_id = str(getvar('subjectNum')) 

    #Create output path
    json_out_path =  project_path + animal_id + '_' + dtime + '_exp_params.json'


    with open(json_out_path, 'w') as f:
        json.dump(exp_params, f)


def create_params_json():
    exp_params = {
        'reward_pause': getvar('reward_pause'),
        'wall_z_pos': getvar('wall_z_pos'),
        'wall_x_pos': getvar('wall_x_pos'),
        'wall_scale': getvar('wall_scale'),
        'cylinder_x_pos': getvar('cylinder_x_pos'),
        'cylinder_z_pos': getvar('cylinder_z_pos'),
        'grating_distortion': getvar('grating_distortion'),
        'training': getvar('training'),
        'lower_bound': getvar('lower_bound'),
        'upper_bound': getvar('upper_bound'),
        'number_segments': getvar('number_segments'),
        'photodiode_present': getvar('photodiode_present'),
        'photodiode_size_x': getvar('photodiode_size_x'),
        'photodiode_left_right_corner': getvar('photodiode_left_right_corner'),
        'photodiode_size_y': getvar('photodiode_size_y'),
        'photodiode_top_bottom_corner': getvar('photodiode_top_bottom_corner'),
        'gain': getvar('tunnel_gain'),
        'proportion_trials_unexpected': getvar('proportion_trials_unexpected'),
        'expected_trials': getvar('expected_trials'),
        'experimental_flag': getvar('experimental_flag'),
        'session_type': getvar('session_type'),
        'disp_grating': getvar('disp_grating'),
        'passive_paradigm': getvar('passive_paradigm'),
        'cm_from_reward': getvar('cm_from_reward'),
        'random_iti_flag': getvar('random_iti_flag')
    }

    # path to store yaml configs
    project_path = getvar('project_path')

    #output datetime (remove punc that is not acceptable for filenames)
    dtime =  datetime.now().strftime('%Y-%m-%d_%H:%M:%S').replace(':', '_').replace('-','_')

    # id of mouse being run
    animal_id = str(getvar('subjectNum'))

    #Create output path
    json_out_path =  project_path + animal_id + '_' + dtime + '_exp_params.json'
    #/Users/hullglick/Documents/vr_exp_params
    print('starting json creation')

    with open(json_out_path, 'w') as f:
        json.dump(exp_params, f)

    print('finished json created')

##########################

# IO input/outpus

##########################

#Define port 
quadrature_port = 12345
juice_port = 12346
is_udp_server_running_port = 54321 
camNP_port_sender = 12347

def is_udp_server_running(host="localhost", port=is_udp_server_running_port):
    """
    Checks if the UDP server is running using a ping-pong test.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(1)  # Avoid blocking
    try:
        s.sendto(b"PING", (host, port))  # Send health check request
        data, _ = s.recvfrom(1024)  # Wait for response
        return data == b"PONG"  # Return True if response is correct
    except socket.timeout:
        return False  # No response, assume server is not running
    except socket.error:
        return False  # Socket error
    finally:
        s.close()

def send_command_to_queue(command, port = quadrature_port):
	"""
	Function that connects to socket and sends commands to server

	input arguments:
	command: string of movement command coming from wheel or keyboard
	"""
	client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	client.sendto(str(command).encode('utf-8'), ("localhost", port))
	client.close()


#################################

# Check if quadrature server is running

#################################

devnull = open(os.devnull, 'w')

def start_server():
   """
   Create subprocess that opens up panda3d tunnel

   This allows for control over client while server runs
   """
   if is_udp_server_running():
        print("A Python instance is running on the specified port.")
   else:
        print("No Python instance detected.")
        process = subprocess.Popen([
        path_hardware_params['python_2_bin_path'],
        path_hardware_params['python_2_oddball_server_path']],
        stdout=devnull,
        stderr=devnull,
        stdin=devnull,
        preexec_fn=os.setsid )
        return process

def close_server():
    """
    stop subprocess from running (Assumes process is defined)

    """
    try:
        process.kill()
        print("Server closed")
    except e:
        print(e)


#################################

# Logic for juice port

#################################
juice_port_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
juice_port_server.settimeout(1)
juice_port_server.bind(("localhost", juice_port))

def reward_juice_trigger_check():
    print('Juice trigger check process is running')
    while True:
        try:
            data, addr = juice_port_server.recvfrom(12345) #input determines chunk size
            juice_command = data.decode('utf-8').strip()
            if (juice_command == 'entered_reward_zone'):
                setvar('py_juice_trigger','True')
        except socket.timeout:
            setvar('py_juice_trigger','False')

threading.Thread(target = reward_juice_trigger_check).start()


#################################

# Logic for mouse position (camNP)

#################################
camNP_port_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
camNP_port_server.settimeout(1)
camNP_port_server.bind(("localhost", camNP_port_sender))


def mouse_position_check():
    print('Mouse position check process is running')
    while True:
        try:
            data, addr = camNP_port_server.recvfrom(40000) #input determines chunk size
            camNP_pos = data.decode('utf-8').strip()
            setvar('mouse_pos',camNP_pos)
        except socket.timeout:
            setvar('mouse_pos', 'Error')
            pass

threading.Thread(target = mouse_position_check).start()

#################################

# Logic for zone port

#################################
zone_port = 12348
zone_port_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
zone_port_server.settimeout(1)
zone_port_server.bind(("localhost", zone_port))

def zone_check():
    print('Zone entry/exit check process is running')
    error_count = 0
    while True:
        try:
            data, addr = zone_port_server.recvfrom(1234500) #input determines chunk size
            zone_status = data.decode('utf-8').strip()
            setvar('zone_entry_exit_status', zone_status)
            print(zone_status)
        except socket.timeout:
            setvar('zone_entry_exit_status', 'Error')

threading.Thread(target = zone_check).start()

#################################

# Logic for block identities

#################################
block_port = 12349
block_port_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
block_port_server.settimeout(1)
block_port_server.bind(("localhost", block_port))

def block_check():
    print('Block check process is running')
    while True:
        try:
            data, addr = block_port_server.recvfrom(1234500) #input determines chunk size
            block_status = data.decode('utf-8').strip()
            setvar('block_status', block_status)
            print(block_status)
        except socket.timeout:
            pass
#Check if this is an experimental session (Allows for block signals to be sent)
if getvar('experimental_flag'):
    threading.Thread(target = block_check).start()
