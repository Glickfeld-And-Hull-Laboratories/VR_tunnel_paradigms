
# -*- coding: utf-8 -*-
"""
Created on Sun Jun 22 16:53:26 2014

@author: vision 
"""

# -*- coding: utf-8 -*-
"""
Created on Fri May 30 10:28:18 2014

@author: vision
"""

# -*- coding: utf-8 -*-
"""
Created on Tue Mar 11 17:38:06 2014

@author: fisearis
"""

"""
Edited for Glickfeld and Hull labs

@author: Steven Pilato
"""

#######################################################
#######################################################

# Displays only last portion of tunnel for training

#######################################################
#######################################################

from panda3d.core import FrameBufferProperties, GraphicsPipe, GraphicsOutput, Texture, WindowProperties, loadPrcFileData
from direct.showbase import DirectObject
from direct.showbase.DirectObject import DirectObject 
import string
from panda3d.core import CollisionTraverser,CollisionNode
from panda3d.core import CollisionHandlerQueue,CollisionRay
from panda3d.core import Vec3,Vec4,BitMask32
from pandac.PandaModules import *
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode
from math import pi, sin, cos
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from direct.interval.IntervalGlobal import Sequence
from panda3d.core import Point3
from ConfigParser import SafeConfigParser
import json
import pandas as pd


#import pydaqtools as pdt
import time
import numpy as np
from numpy import *
import ctypes
import random
import math
import os

#Full screen mode on mac
import AppKit
from AppKit import NSApplication, NSWindow, NSMakeRect

#for running app on different thread and placing inputs
import threading
from collections import deque #For generating a queue that stores quadrature input

#For server client
import socket

########################

# Exp params set

########################
#Get home dir
home_dir = os.path.expanduser("~")

# expected path is /user/documents/vr_exp_params
exp_params_path = home_dir + '/' + 'Documents/' + 'vr_exp_params/'

#Repo path
repo_path = home_dir + '/Repositories/VR_tunnel_paradigms/'

# Expected path for path params json
p_params = repo_path + 'params/path_hardware_params.json'

#Path for block assignments
block_assignment_path = repo_path + 'python/block1_trial_assignments.csv'

#Get files in proj dir
files = os.listdir(exp_params_path)

#Get file creation times
files_c_times = [os.path.getctime(exp_params_path  + f) for f in files]

#Get most recent creation time
recent_json_ctime = max(files_c_times)

 #Loop through and find file that was created at that time
recent_ctime_filename = [ fname for fname in files if os.path.getctime(exp_params_path + fname) == recent_json_ctime][0]
with open(exp_params_path + recent_ctime_filename, 'r') as f:
    exp_params = json.load(f)

#Remove unicode characters
def unicode_encode(x):
    try:
        exp_params.update({x[0].encode('ascii', 'ignore'): x[1].encode('ascii', 'ignore')})
    except AttributeError:
        pass

for x in exp_params.items():
    unicode_encode(x)

#Grab path params (json needs to be created in before script can run)
with open(p_params, 'r') as f:
    path_hardware_params = json.load(f)

#Path to tunnel images, libraries, and params (automate this)
path = path_hardware_params['tunnel_images_path']

#Extract screen key words
s1 = path_hardware_params['screen_1']
s2 = path_hardware_params['screen_2']

########################

# monitor setup

########################
# Get total screen size (across dell displays)
screens = AppKit.NSScreen.screens()
total_monitor_width = sum(int(screen.frame().size.width) for screen in screens if  s1 in screen.localizedName().encode('utf-8') or s2 in screen.localizedName().encode('utf-8'))
total_monitor_height = max(int(screen.frame().size.height) for screen in screens if  s1 in screen.localizedName().encode('utf-8') or s2 in screen.localizedName().encode('utf-8'))

#Get names
names = [screen.localizedName().encode('utf-8') for screen in screens]

#get frame pos
frames = [screen.frame() for screen in screens if s1 in screen.localizedName().encode('utf-8')]

#Get x and y pos for each frame (this will be used for telling panda where to set screen)
x_pos = [f.origin.x for f in frames]

#get min pos
min_x_pos = int(min(x_pos))

########################

# Funcions

########################
def nearest_zone(curr_pos):
    """
    Function for finding nearest zone
    #(change this so zone name is just zone position)!!!!!!!!!!!!!!!
    Params: 
        curr_pos: Current camera position
    """
    #Define tunnel seg paramxs
    texture_spacing = 100
    texture_length = texture_spacing/2

    #Define tunnel positions
    tunnel_pos = {
        1: {'position': texture_spacing - texture_length,  'zone': 'A1'},
        2: {'position': 6*texture_spacing - texture_length,  'zone': 'B2'},
        3: {'position': 11*texture_spacing - texture_length, 'zone': 'A3'},
        4: {'position': 16*texture_spacing - texture_length, 'zone': 'B4'},
        5: {'position': 1850, 'zone' : 'reward'}
    }

    #Get nearest value
    near_value = [abs(x['position'] - curr_pos) for x in tunnel_pos.values()]

    # Take min to get integer for pulling from dict
    min_value = min(near_value)

    #Get dictionary index
    nearest_index = [x == min_value for x in near_value] 

    #Combine and extact index value
    ind_value = [x for x,y in zip(tunnel_pos.keys(), nearest_index) if y][0]

    #Get zone
    return tunnel_pos.get(ind_value).get('zone')


def cm2au_from_origin(x, upper_bound, au_unit_cm_factor=0.3239767): #Need to modify this so that I control for user input exceeding bound limits
    """
    function that converts cm to au based on ticks and subtracts from upper boud

    input arguments:
        x float: units to subtract
        upper_bound float/in: upper bound of tunnel
        au_unit_cm_factor: conversion factor to get to au
    """
    #Calculate lower limit from cm input
    res = int(upper_bound - x/au_unit_cm_factor)

    #Set min var (-15 has been the min for every tunnel though there is no specific reason for this)
    min_bound = -15

    #Upper bound for this tunnel is right before the reward zone placement
    upper_bound = int(upper_bound - 30/au_unit_cm_factor)
    #Account for lower bounds
    if res < min_bound:
        res = -15
    elif res > upper_bound:
        res = upper_bound #Place 30cm from reward zone
    return res 


def time2str(x):
    """
    Function for converting date-time to string that can be saved as path
    
    x: pandas datatime to be converted
    """
    output = str(x).replace(":","_").replace(" ", "_").replace(".", "_").replace("-","_")
    return output


########################

# Params, ini, functions

########################

#Define quadrature queue
quadrature_queue = deque()

#Define movement queue
movement_queue = deque()

#Tunnel limits
upper_bound = exp_params['upper_bound'] #390 # Not defined for 
lower_bound = exp_params['lower_bound'] #-15.0

#Wall scaling factor (stretch of walls)
wall_scale = exp_params['wall_scale'] #8 

#Wall position
wall_x_pos = exp_params['wall_x_pos'] #0
wall_z_pos = exp_params['wall_z_pos'] #4

#Cylinder position
cylinder_x_pos = exp_params['cylinder_x_pos'] #0
cylinder_z_pos = exp_params['cylinder_z_pos'] #10

#reward pause (in seconds)
reward_pause = exp_params['reward_pause'] #0

#iti flag
random_iti_flag = exp_params['random_iti_flag']

#Define ports (These are used for communicating with client and setting vars in mworks)
quadrature_port = 12345
juice_port =12346
camNP_port = 12347
zone_port = 12348
block_port = 12349
health_port = 54321

#Is photodiode_present present (Will also need to add size params)
photodiode_present = exp_params['photodiode_present']
photodiode_size_x = exp_params['photodiode_size_x']
photodiode_size_y = exp_params['photodiode_size_y']
photodiode_left_right_corner = exp_params['photodiode_left_right_corner']
photodiode_top_bottom_corner = exp_params['photodiode_top_bottom_corner']

#Tunnel gain (Mouse speed)
gain = exp_params['gain']

#Time start
time_start = time.time()

# Reward pause
reward_client_channel_wait = 4 # in seconds

#Dist from finish line for "reward"
finsh_line_offset = 40

#parameters for showing gratings or making paradigm passive (need to pass this to mworks)
disp_grating = exp_params['disp_grating']
passive_paradigm = exp_params['passive_paradigm']

#Pull in experimental flag status from mworks generated json
experimental_flag = exp_params['experimental_flag']

#Get cm from reward
cm_from_reward = exp_params['cm_from_reward']

########################

# Unexpected trials variables/block structure

########################

# unexpected stimulus paramaters (unexpected stimulus)
#proportion_trials_unexpected = exp_params['proportion_trials_unexpected']
block1_start = 1
block1 = 100 #Initial block structure
block2 = 40 #(20 trials are early for unexpected decay and 20 are late for sensory)

if experimental_flag:
    #Import assignment data for block 1 (based on 100 trials with p = .15)
    block1_trial_assignment = pd.read_csv(block_assignment_path) #automate parent directory (Should exist in a particular location regardless of computer)

    #Get number of assignments possibilities
    nrows = block1_trial_assignment.shape[0]

    #Get number of columns to select
    col_select = 1

    #Randomly choose column 
    choose_row = np.random.choice(nrows, col_select)

    #Account for 0 idexing
    if choose_row == nrows:
        choose_row = choose_row - 1

    #Choose column and convert to array
    block1_trial_assignment_ls =  block1_trial_assignment.iloc[choose_row,:].to_numpy().flatten().tolist()

########################

# Create dictionary that contains paths to all stim in tunnel

########################

#Create dictionary that contains stimulus paths
stim_dict = {
    'A1'   : path + 'Aris_VR/final textures/new_textures/mtlb/grat1.egg',
    'B2'   : path + 'verticalgraitng.egg',
    'A3'   : path + 'Aris_VR/final textures/new_textures/mtlb/grat1.egg',
    'A4'   : path + 'Aris_VR/final textures/new_textures/mtlb/grat1.egg',
    'B4'   : path + 'verticalgraitng.egg',
    'C4'   : path + 'Aris_VR/final textures/new_textures/mtlb/grat2.egg',
    'D4'   : path + 'Aris_VR/final textures/new_textures/mtlb/grat2.egg',
    'wall' : path + "Aris_VR/final textures/new_textures/new_random.egg",
    'E4'   : path + 'Aris_VR/final textures/new_textures/horzgrating.egg',
    'L1'   : path + "Aris_VR/final textures/new_textures/mtlb/txt1.egg",
    'L2'   : path + "Aris_VR/final textures/new_textures/mtlb/txt2.egg",
    'L3'   : path + "Aris_VR/final textures/new_textures/mtlb/txt5.egg",
    'L4'   : path + "Aris_VR/final textures/new_textures/mtlb/txt4.egg",
    'finish_line': path + "tunnelModel/objects/cylinder2"
}


########################

# Session type (For imaging sessions)

# Type A4, C4, D4, omission (Other manpiulations can be added here)

########################
if experimental_flag:
    session_type = exp_params['session_type']
possible_session_categories = ['A4', 'C4', 'D4', 'E4', 'omission']

# logic for checking (Should be 1)
if experimental_flag:
    num_cond = sum([x in session_type for x in possible_session_categories]) 
    assert num_cond == 1, 'number of experiment conditions should = 1' #There should be only one session type chosen
    print('Imaging experiment session selected')
    print('  {} session type'.format(session_type))
else:
    #If condition is not selected make it B4 for normal tunnel
    session_type = 'B4'


########################

# ITI randomization

########################
bound = 3
avg_iti = 5
iti_set = [x for x in range(avg_iti - bound, avg_iti + bound + 1)]


########################

# Panda3D app

########################

class MyApp(ShowBase):

    def __init__(self):

        ShowBase.__init__(self)
              
        #Define window properties
        props = WindowProperties()
        props.setCursorHidden(True)
        props.setSize(total_monitor_width, total_monitor_height) #total_monitor_width, total_monitor_height
        props.setFullscreen(True)
        props.setUndecorated(True)
        self.win.requestProperties(props)
        print(self.win.getProperties())

        # Create left and right camera views
        left_cam = self.makeCamera(self.win)
        right_cam = self.makeCamera(self.win)

        # Set display regions
        left_region = self.win.makeDisplayRegion(0, 0.5, 0, 1)  # Left half
        right_region = self.win.makeDisplayRegion(0.5, 1, 0, 1)  # Right half

        left_region.setCamera(left_cam)
        right_region.setCamera(right_cam)

        #Wait to open window
        self.taskMgr.doMethodLater(0.1, self.resposition_window, 'resposition_window')
        
        self.periodLength = 2

        #generating VE
        base.setBackgroundColor(0, 0, 0, 0)
        base.cam.setPos(0,20,23)
        base.cam.setHpr(0,-90,0)
        self.myscene = NodePath("My Scene")
        self.background = NodePath("Background")
        self.tunnel=[]
        self.trial_no = []
        self.jump = 0  
        self.save = 0
        self.flip = 0
        self.teleport = 0
        self.flash = 0
        self.flip_reg = 0
        self.noflip_trial = 0
        self.randomno = 0
        self.last_lj_pos = 0
        self.curr_trial = 1
        self.last_trial = 1
        self.completion_per_segment = 10 # denots the number of trial completions per segment
           
        # tasks that need to be read from the config file start here
        
        self.F = []
        self.P = []
        self.tunnel_length = 29
        self.visible_tunnel_length = 19
        self.texture_spacing =  100  
        self.texture_length =  self.texture_spacing/2
        self.grating_distortion = 7
        self.wall_x_pos = wall_x_pos
        self.wall_z_pos = wall_z_pos
        self.cylinder_x_pos = cylinder_x_pos
        self.cylinder_z_pos = cylinder_z_pos
        
        #grating dictionary (Applies to non expeirment conditions and experiment conditions, not omission)
        if session_type != 'omission':
            print(session_type)
            self.grating_dict = {
                'grat1': {'pos_index': 1, 'distorted_index': 19, 'non_distorted_index': 20,'grating_y_start': self.texture_spacing, 'file': stim_dict.get('A1'), 'status':None},
                'verticalgraitng1': {'pos_index': 6, 'distorted_index': 21, 'non_distorted_index': 22 ,'grating_y_start': 6*self.texture_spacing, 'file': stim_dict.get('B2'), 'status':None},
                'grat2': {'pos_index': 11,  'distorted_index': 23, 'non_distorted_index': 24,'grating_y_start': 11*self.texture_spacing, 'file': stim_dict.get('A3'), 'status':None},
                'verticalgraitng2': {'pos_index': 16, 'distorted_index': 25, 'non_distorted_index': 26,'grating_y_start': 16*self.texture_spacing, 'file': stim_dict.get('B4'), 'status':None},
                'unexpected_grat': {'pos_index': 16, 'distorted_index': 27, 'non_distorted_index': 28,'grating_y_start': 16*self.texture_spacing, 'file': stim_dict.get(session_type), 'status':None}
            }
        #Make wall unexpected and no distortion    
        else:
            self.grating_dict = {
                'grat1': {'pos_index': 1, 'distorted_index': 19, 'non_distorted_index': 20,'grating_y_start': self.texture_spacing, 'file': stim_dict.get('A1'), 'status':None},
                'verticalgraitng1': {'pos_index': 6, 'distorted_index': 21, 'non_distorted_index': 22 ,'grating_y_start': 6*self.texture_spacing, 'file': stim_dict.get('B2'), 'status':None},
                'grat2': {'pos_index': 11,  'distorted_index': 23, 'non_distorted_index': 24,'grating_y_start': 11*self.texture_spacing, 'file': stim_dict.get('A3'), 'status':None},
                'verticalgraitng2': {'pos_index': 16, 'distorted_index': 25, 'non_distorted_index': 26,'grating_y_start': 16*self.texture_spacing, 'file': stim_dict.get('B4'), 'status':None},
                'unexpected_grat': {'pos_index': 16, 'distorted_index': 27, 'non_distorted_index': 28,'grating_y_start': 16*self.texture_spacing, 'file': stim_dict.get('wall'), 'status':None}
            }            


        #Assign unexpcted trial assignment to object attribute
        if experimental_flag:
            self.trial_binom_assignment = block1_trial_assignment_ls
            
            #Create output path 
            opath_str = time2str(pd.Timestamp.now())

            #Store trial data
            with open('/Users/stevenpilato/Documents/trial_output_{}.txt'.format(opath_str), 'w') as file:
                for item in self.trial_binom_assignment:
                    file.write('{}-'.format(item))

        #Segment type (used in reconfigure_tunnel task)
        self.segment_classification = {
            0:  'gray',
            1:  'grating',
            2:  'gray',
            3:  'gray',
            4:  'landmark',
            5:  'gray',
            6:  'grating',
            7:  'gray',
            8:  'gray',
            9:  'landmark',
            10: 'gray',
            11: 'grating',
            12: 'gray',
            13:  'gray',
            14: 'landmark',
            15: 'gray',
            16: 'grating',
            17: 'gray',
            18: 'landmark'
        }

        # Creates initial tunnel  (This populates gray scene/landmarks/gratings)       
        for i in range(0,self.tunnel_length):  
            if i in [0]:
                self.tunnel.append(loader.loadModel(stim_dict.get('wall')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2, self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, i*self.texture_spacing, self.wall_z_pos)                
                  
            elif i in [1]: #45 grating
                self.tunnel.append(loader.loadModel(stim_dict.get('wall')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, i*self.texture_spacing, self.wall_z_pos)
                  
            elif i in [2]:
                self.tunnel.append(loader.loadModel(stim_dict.get('wall')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, i*self.texture_spacing, self.wall_z_pos)

            elif i in [3]:
                self.tunnel.append(loader.loadModel(stim_dict.get('wall')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, i*self.texture_spacing, self.wall_z_pos)
                    
            elif i in [4]:
                self.tunnel.append(loader.loadModel(stim_dict.get('L1')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (i*self.texture_spacing), self.wall_z_pos)

            elif i in [5]:
                self.tunnel.append(loader.loadModel(stim_dict.get('wall')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (i*self.texture_spacing), self.wall_z_pos)

            elif i in [6]: #vertical grating 
                self.tunnel.append(loader.loadModel(stim_dict.get('wall')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (i*self.texture_spacing), self.wall_z_pos)

            elif i in [7]:
                self.tunnel.append(loader.loadModel(stim_dict.get('wall')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (i*self.texture_spacing), self.wall_z_pos)

            elif i in [8]:
                self.tunnel.append(loader.loadModel(stim_dict.get('wall')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (i*self.texture_spacing), self.wall_z_pos)

            elif i in [9]:
                self.tunnel.append(loader.loadModel(stim_dict.get('L2')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (i*self.texture_spacing), self.wall_z_pos)

            elif i in [10]:
                self.tunnel.append(loader.loadModel(stim_dict.get('wall')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (i*self.texture_spacing), self.wall_z_pos)

            elif i in [11]: #45 grating 
                self.tunnel.append(loader.loadModel(stim_dict.get('wall')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (i*self.texture_spacing), self.wall_z_pos)

            elif i in [12]:
                self.tunnel.append(loader.loadModel(stim_dict.get('wall')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (i*self.texture_spacing), self.wall_z_pos)

            elif i in [13]:
                self.tunnel.append(loader.loadModel(stim_dict.get('wall')))
                self.tunnel[i].reparentTo(self.background)  
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (i*self.texture_spacing), self.wall_z_pos)

            elif i in [14]:
                self.tunnel.append(loader.loadModel(stim_dict.get('L3')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (i*self.texture_spacing), self.wall_z_pos)

            elif i in [15]:
                self.tunnel.append(loader.loadModel(stim_dict.get('wall')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (i*self.texture_spacing), self.wall_z_pos)

            elif i in [16]: #vert grating
                self.tunnel.append(loader.loadModel(stim_dict.get('wall')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (i*self.texture_spacing), self.wall_z_pos)

            elif i in [17]:
                self.tunnel.append(loader.loadModel(stim_dict.get('wall')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (i*self.texture_spacing), self.wall_z_pos)

            elif i in [18]:
                self.tunnel.append(loader.loadModel(stim_dict.get('L4')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (i*self.texture_spacing), self.wall_z_pos)

            #Grating logic ------------------------

            elif i in [19]:
                #Distorted grat1
                self.tunnel.append(loader.loadModel(self.grating_dict.get('grat1').get('file')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length*self.grating_distortion, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (self.grating_dict.get('grat1').get('pos_index')*self.texture_spacing), self.wall_z_pos)
                self.tunnel[i].hide()                
            elif i in [20]:
                #Non-distorted grat1
                self.tunnel.append(loader.loadModel(self.grating_dict.get('grat1').get('file')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (self.grating_dict.get('grat1').get('pos_index')*self.texture_spacing), self.wall_z_pos)
                self.tunnel[i].hide()

            elif i in [21]:
                #Distorted verticalgraitng1
                self.tunnel.append(loader.loadModel(self.grating_dict.get('verticalgraitng1').get('file')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length*self.grating_distortion, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (self.grating_dict.get('verticalgraitng1').get('pos_index')*self.texture_spacing), self.wall_z_pos)
                self.tunnel[i].hide()
            elif i in [22]:
                #Non-distorted verticalgraitng1
                self.tunnel.append(loader.loadModel(self.grating_dict.get('verticalgraitng1').get('file')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (self.grating_dict.get('verticalgraitng1').get('pos_index')*self.texture_spacing), self.wall_z_pos)
                self.tunnel[i].hide()

            elif i in [23]:
                #Distorted grat2
                self.tunnel.append(loader.loadModel(self.grating_dict.get('grat2').get('file')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length*self.grating_distortion, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (self.grating_dict.get('grat2').get('pos_index')*self.texture_spacing), self.wall_z_pos)
                self.tunnel[i].hide()
            elif i in [24]:
                #Non-distorted grat2
                self.tunnel.append(loader.loadModel(self.grating_dict.get('grat2').get('file')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (self.grating_dict.get('grat2').get('pos_index')*self.texture_spacing), self.wall_z_pos)
                self.tunnel[i].hide()

            elif i in [25]:
                #Distorted verticalgraitng2
                self.tunnel.append(loader.loadModel(self.grating_dict.get('verticalgraitng2').get('file')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length*self.grating_distortion, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (self.grating_dict.get('verticalgraitng2').get('pos_index')*self.texture_spacing), self.wall_z_pos)
                self.tunnel[i].hide()
            elif i in [26]:
                #Non-distorted verticalgraitng2
                self.tunnel.append(loader.loadModel(self.grating_dict.get('verticalgraitng2').get('file')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (self.grating_dict.get('verticalgraitng2').get('pos_index')*self.texture_spacing), self.wall_z_pos)
                self.tunnel[i].hide()

        # Unexpected part of tunnel (Will be B4 for omission)
            elif i in [27]:
                #Check if this is omission condition (Do not want stretching)
                if session_type == 'omission':
                    #Distorted unexpected grating
                    self.tunnel.append(loader.loadModel(self.grating_dict.get('unexpected_grat').get('file')))
                    self.tunnel[i].reparentTo(self.background)
                    self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                    self.tunnel[i].setPos(self.wall_x_pos, (self.grating_dict.get('unexpected_grat').get('pos_index')*self.texture_spacing), self.wall_z_pos)
                    self.tunnel[i].hide()
                else:    
                    #Distorted unexpected grating
                    self.tunnel.append(loader.loadModel(self.grating_dict.get('unexpected_grat').get('file')))
                    self.tunnel[i].reparentTo(self.background)
                    self.tunnel[i].setScale(2,self.texture_length*self.grating_distortion, wall_scale)
                    self.tunnel[i].setPos(self.wall_x_pos, (self.grating_dict.get('unexpected_grat').get('pos_index')*self.texture_spacing), self.wall_z_pos)
                    self.tunnel[i].hide()
            elif i in [28]:
                #Non-distorted unexpected grat
                self.tunnel.append(loader.loadModel(self.grating_dict.get('unexpected_grat').get('file')))
                self.tunnel[i].reparentTo(self.background)
                self.tunnel[i].setScale(2,self.texture_length, wall_scale)
                self.tunnel[i].setPos(self.wall_x_pos, (self.grating_dict.get('unexpected_grat').get('pos_index')*self.texture_spacing), self.wall_z_pos)
                self.tunnel[i].hide()     


        #Set cylinder in environment
        self.cylinder = self.loader.loadModel(stim_dict.get('finish_line'))
        self.cylinder.reparentTo(self.myscene)
        self.cylinder.setScale(4,1,2)
        self.cylinder.setPos(self.cylinder_x_pos ,((self.visible_tunnel_length)*self.texture_spacing),self.cylinder_z_pos)        
  

        self.newModel=NodePath('model')
        self.background.getChildren().reparentTo(self.newModel)
        self.newModel.flattenStrong()
        self.newModel.reparentTo(self.myscene)
        

        self.lens2=PerspectiveLens()
        self.lensfovx=30
        self.lensfovy=70
        self.lens2.setFov(self.lensfovx,self.lensfovy)
        self.mybuffer=[] 
        self.mycamera=[]
        self.mytexture=[]
        self.lastPos=0
        self.currPos=0
        
        self.tmp = [0,0,0,0,0]        
        

        for i in range(0,12):
            self.mybuffer.append(base.win.makeTextureBuffer("My Buffer " + str(i), 256, 256))
            self.mytexture.append(self.mybuffer[i].getTexture())
            self.mybuffer[i].setSort(-100)
            self.mycamera.append(base.makeCamera(self.mybuffer[i],lens=self.lens2))
            if i>0:
                self.mycamera[i].reparentTo(self.mycamera[0])
                self.mycamera[i].setHpr(i*self.lensfovx, 0, 0)
#                self.mycamera[i].setPos(0,0,0)


        self.mycamera[0].reparentTo(self.newModel)
        self.mycamera[0].setPos(0, 0, 3)
        self.screen=[]
        self.displayRegion=self.win.makeDisplayRegion()
        self.camNode=Camera('cam')
        self.camNP=NodePath(self.camNode)
        self.displayRegion.setCamera(self.camNP)
        self.camNP.reparentTo(self.myscene)

        #list for storing current positions
        self.camera_y_positions = [self.camNP.getY()] 

        #Define move factor (gain assigned in mworks)
        self.moveFactor= gain 

        #Define attribute that allows for keyboard/labjack input (used for independent movement)
        self.accepting_input = True

        #Upper bound of tunnel
        self.upper_bound = self.visible_tunnel_length*self.texture_spacing - finsh_line_offset

        #Logic for checking how many segments to display
        self.lower_bound = cm2au_from_origin(cm_from_reward, self.upper_bound)
        self.camNP.setPos(self.wall_x_pos, self.lower_bound, self.wall_z_pos)

        # dictionary for passing tunnel segments (initialize to all be false)
        self.tunnel_segment_pass = {i: False for i in range(self.visible_tunnel_length)}

        #reward pase
        self.reward_pause = reward_pause

        #Get current time for reward timer initialization
        self.last_reward_time = time.time()
        self.reward_client_channel_wait = reward_client_channel_wait

        # Initialize start tasks
        self.start()

        #Setup inset screen for photodiode
        if photodiode_present:
            self.inset_dr = self.inset_screen_setup() 
            
    def start(self):
        """
        Function for starting tasks
        """
        taskMgr.add(self.segment_pass_threshold, "segment_pass_threshold", sort=8) #Activates task that checks when cmera passes start of segment
        taskMgr.add(self.camera_positions, "camera_positions", sort = 8) #Activates task that gets current camera position
        if not passive_paradigm:
            taskMgr.add(self.quadrature_input, 'quadrature_input',sort=8)
            taskMgr.add(self.queue_movement, "queue_movement", sort = 10)
        else:
            taskMgr.add(self.passive_independent_moving, "passive_movement", sort = 10)
        #Check if user wants to diplay gratings
        if disp_grating:
            taskMgr.add(self.display_grating, "display_grating", sort = 9)

    def independent_moving(self, task):
        """
        Move camera at a constant rate without input from labjack

        """
        
        #Start timer   
        elapsed_time = task.time

        #How long to move through grating
        duration = 2.4

        #Speed to move through grating
        speed  = 1

        #Stop queue movemnt function so that mouse cannot move through grating
        if not passive_paradigm:
            taskMgr.remove('queue_movement')
        else:
            taskMgr.remove('passive_movement')

        #Check if first corssing occurs so repeat zone threads are not created
        nearest_zone_res = nearest_zone(self.camNP.getY())
        if first_crossing:
            print(nearest_zone_res)
            print(self.camNP.getY())
            global first_crossing
            first_crossing = False
            #Send zone update to client
            threading.Thread(target = self.zone_trigger, args=(nearest_zone_res, True, unexp_status)).start()
 
        if elapsed_time < duration:

            #remove moving input 
            self.accepting_input = False

            #Start self moving
            a=self.camNP.getPos()
            b=a[1]+speed
            self.camNP.setPos(a[0],b,a[2])
            self.mycamera[0].setPos(a[0],b,a[2])

            return task.cont

        else:

            #Add moving input back
            self.accepting_input = True

            if not passive_paradigm:
                #Clear movement queue
                movement_queue.clear()
                #Add back to task manager
                taskMgr.add(self.queue_movement) 
            else:
                taskMgr.add(self.passive_independent_moving, 'passive_movement', sort = 10) 
 
            #Send zone finish message to client
            threading.Thread(target = self.zone_trigger, args=(nearest_zone_res, False, unexp_status)).start()
                
            return task.done

    def passive_independent_moving(self, task):
        """
        Move camera at a constant rate without input from labjack

        """
        #Speed to move through grating
        speed  = gain

        #Start self moving
        a=self.camNP.getPos()
        b=a[1]+speed

        #trial expected/unexpected status
        if self.curr_trial >= block1_start and self.curr_trial <= block1 and experimental_flag:
            if self.trial_binom_assignment[self.curr_trial - 1]:
                global unexp_status
                unexp_status = '- unexpected'
            else:
                global unexp_status
                unexp_status = ''
        else:
            global unexp_status
            unexp_status = ''

        #Check to make movement is not above upper bound
        if b > self.upper_bound:

            #Send message to client the juice should be dispensed
            print(time.time() - self.last_reward_time > self.reward_client_channel_wait)

            if time.time() - self.last_reward_time > self.reward_client_channel_wait:
                #Calculate nearest zone 
                nearest_zone_res = nearest_zone(self.camNP.getY())
                print(nearest_zone_res)
                #update mworks variable
                threading.Thread(target=self.zone_trigger, args=(nearest_zone_res, True)).start()

                #Let solenoid run on seperate thread
                threading.Thread(target = self.reward_juice_trigger).start()

                #set iti
                if random_iti_flag:
                    self.reward_pause = np.random.choice(iti_set)

                #Store last reard time
                self.get_last_reward_time()

                #Logic for checking how many segments to display
                tunnel_reset_start = time.time()

                while time.time() - tunnel_reset_start <= self.reward_pause:
                    print('reward pause')

                #restart at segment
                self.camNP.setPos(self.wall_x_pos, self.lower_bound,self.wall_z_pos)
                a=self.camNP.getPos()
                b=a[1]+speed

                #Send block status update to mworks (If during expeirment)
                if experimental_flag:
                    threading.Thread(target=self.block_status_trigger).start()  
                #Incriment trial              
                self.curr_trial += 1                

                #reset tunnel
                self.start_trial_change_stim_reset()
        else:
            self.camNP.setPos(a[0],b,a[2])
            self.mycamera[0].setPos(a[0],b,a[2])

        return task.cont
            
    def resposition_window(self, task):
        """
        This function repositions window at a lag for origin will move
        """
        app = NSApplication.sharedApplication()
        for window in app.windows():
            if isinstance(window, NSWindow):
                x = min_x_pos
                y = -380

                #Set poition and size
                rect = NSMakeRect(x, y, total_monitor_width, total_monitor_height + 20)
                window.setFrame_display_animate_(rect, True, False)
                break
        return task.done

    def start_independent_movement(self):
        """
        Start the camera movement task (triggered by other methods)
        """
        taskMgr.add(self.independent_moving, "independent_moving")

    def start_trial_change_stim_reset(self):
        """
        increase trial number and reset dictionaries
        """
        taskMgr.add(self.trial_change_stim_reset, "trial_change_stim_reset")

    def start_reconfigure_tunnel(self):
        """
        Start the reconfigure tunnel task (triggered by other methods)
        """
        taskMgr.doMethodLater(2.4,self.reconfigure_tunnel, "reconfigure_tunnel")

    def display_grating(self, task):
        """
        Display extended grating that is movement independent 

        Code will be passed if grating omission condition is present
        """
        # Check current camera y position
        curr_camNP_y = self.camNP.getY()

        # Check if this is regular session (No novel stimuli)
        if not experimental_flag:
            grat_keys = [x for x in self.grating_dict.keys() if 'unexpected_grat' not in x]
            grating_loop = [self.grating_dict.get(x) for x in grat_keys]
        # Check block status and unexpected condition ----
        elif self.curr_trial <= block1: #check if mouse is in block 2
            if self.trial_binom_assignment[self.curr_trial - 1]: 
                #Remove expected grating from loop (Need to add omission logic)
                grat_keys = [x for x in self.grating_dict.keys() if 'verticalgraitng2' not in x]
                grating_loop = [self.grating_dict.get(x) for x in grat_keys]
            else: 
                #remove unexpected grating from loop
                grat_keys = [x for x in self.grating_dict.keys() if 'unexpected_grat' not in x]
                grating_loop = [self.grating_dict.get(x) for x in grat_keys]
        else:
            #Remove expected grating from loop
            grat_keys = [x for x in self.grating_dict.keys() if 'verticalgraitng2' not in x]
            grating_loop = [self.grating_dict.get(x) for x in grat_keys]


        #Loop through gratings
        for wall_pos in grating_loop:
            #Check if camera passes where grating is supposed to be 
            if (curr_camNP_y >= wall_pos.get('grating_y_start') - (self.texture_length)) and wall_pos.get('status') != 'complete' and self.tunnel_segment_pass.get(wall_pos.get('pos_index')):
                #Check if this is an omission trial
                if (wall_pos.get('distorted_index') == wall_pos.get('non_distorted_index')) & (session_type == 'omission'):
                    if photodiode_present:
                        #Change inset color
                        self.inset_dr.setClearColor((1, 1, 1, 1))

                        #delay task to alter photodiode screen
                        taskMgr.doMethodLater(.5, self.inset_screen_stim_off, "inset_screen_stim_off")

                        #start task to change screen inset color
                    #Update dictionary so if mouse goes backward and wont retrigger stimulus    
                    wall_pos.update({'status': 'complete'})
                else: 
                    #Hide tunnels so that only grating is showing
                    for i in range(self.tunnel_length):
                        self.tunnel[i].hide()

                    self.tunnel[wall_pos.get('distorted_index')].show()

                    if photodiode_present:
                        #Change inset color
                        self.inset_dr.setClearColor((1, 1, 1, 1))

                    global first_crossing
                    first_crossing = True # Need this to make sure only 1 thread for zone times is created during independent movement

                    #Hide finish line
                    self.cylinder.hide()

                    #perform independent moving
                    self.start_independent_movement()

                    #Update dictionary so if mouse goes backward and wont retrigger stimulus    
                    wall_pos.update({'status': 'complete'})

                    #reconfigure tunnel (hide grating only tunnel)
                    self.start_reconfigure_tunnel()


        return task.cont

    def segment_pass_threshold(self, task):
        """
        A task that constantly looks where camera is in relation to wall segments start positions

        """

        #Get current y position ------- extract index (subtract 1 for 0 index)
        current_cam_index = len(self.camera_y_positions) - 1

        #Get current y position ------- extract position
        curr_camNP_y = self.camera_y_positions[current_cam_index]

        #Get last camera position
        if current_cam_index > 1:
            last_camNP_y = self.camera_y_positions[current_cam_index - 1]
        else:
            last_camNP_y = curr_camNP_y


        for wall in range(self.visible_tunnel_length):

            wall_y = (wall*self.texture_spacing)  - self.texture_length

            #The below if statement check to make sure that the mouse did cross a wall. This is important because sometimes we have the mouse start out at different positions
            if curr_camNP_y >= wall_y and last_camNP_y <=  wall_y and curr_camNP_y - last_camNP_y > 0:

                self.tunnel_segment_pass.update({wall: True})

            else:

                pass

        return task.cont


    def reconfigure_tunnel(self, task):
        """ 
        Function that show tunnel and hides long grating

        """
        if photodiode_present:
            #Change inset color back
            self.inset_dr.setClearColor((0, 0, 0, 1))

        #Loop through every tunnel segment
        for tunnel_index in range(self.visible_tunnel_length):

            #Loop through all gratings
            for dict_record in self.grating_dict.values():
                #Check if tunnel index matches grating index
                if dict_record.get('pos_index') == tunnel_index:
                    #Check if grating status is complete
                    if  (dict_record.get('status') == 'complete') or (self.tunnel_segment_pass.get(tunnel_index)):

                        #Hide distorted tunnel
                        self.tunnel[dict_record.get('distorted_index')].hide()

                        #Hide gray
                        self.tunnel[tunnel_index].hide()

                        #Show non-distorted
                        self.tunnel[dict_record.get('non_distorted_index')].show()

                        #Reset camera (So queue_movement does not overhsoot position)
                        self.camNP.setPos(0, tunnel_index*self.texture_spacing + self.texture_length, 4)

                        #Show finish line
                        self.cylinder.show()


                # Check if prevous segments were landmarks or gray and display them
                elif (self.segment_classification.get(tunnel_index) in ['landmark', 'gray']) and (self.tunnel_segment_pass.get(tunnel_index)):

                    self .tunnel[tunnel_index].show()
                # if  segments were not passed show them
                else:

                    if not (self.tunnel_segment_pass.get(tunnel_index)):

                        self.tunnel[tunnel_index].show()

        return task.done

    
    def get_last_reward_time(self):
        """

        Assigns time a rward was given

        """
        self.last_reward_time = time.time()


    def queue_movement(self, task):
        """
         Continuously checks the queue for updates and applies changes.
        """
        #print(' \n Current movement queue: {}'.format(str(movement_queue)))
        while movement_queue:

            movement = int(movement_queue.popleft()) # Get oldest movement
            
            #trial expected/unexpected status
            if self.curr_trial >= block1_start and self.curr_trial <= block1 and experimental_flag:
                if self.trial_binom_assignment[self.curr_trial - 1]:
                    global unexp_status
                    unexp_status = '- unexpected'
                else:
                    global unexp_status
                    unexp_status = ''
            else:
                global unexp_status
                unexp_status = ''

            if movement > self.last_lj_pos:

                #Calculate a movement
                a=self.camNP.getPos()

                #Calculate b movement
                b=a[1]+self.moveFactor

                #Check to make movement is not above upper bound
                if a[1] + self.moveFactor > self.upper_bound:

                    #Send message to client the juice should be dispensed
                    print(time.time() - self.last_reward_time > self.reward_client_channel_wait)

                    if time.time() - self.last_reward_time > self.reward_client_channel_wait:
                        #Calculate nearest zone 
                        nearest_zone_res = nearest_zone(self.camNP.getY())
                        print(nearest_zone_res)
                        #update mworks variable
                        threading.Thread(target=self.zone_trigger, args=(nearest_zone_res, True, unexp_status)).start()

                        #Let solenoid run on seperate thread
                        threading.Thread(target = self.reward_juice_trigger).start()
                        #Store last reard time
                        self.get_last_reward_time()

                    #Logic for checking how many segments to display
                    tunnel_reset_start = time.time()

                    taskMgr.remove('queue_movement')
                    taskMgr.remove('quadrature_input')

                    while time.time() - tunnel_reset_start <= self.reward_pause:
                        movement_queue.clear()
                        quadrature_queue.clear()

                    #restart at segment
                    self.camNP.setPos(self.wall_x_pos, self.lower_bound,self.wall_z_pos)

                    #restart tasks
                    taskMgr.add(self.queue_movement, 'queue_movement', sort = 10)
                    taskMgr.add(self.quadrature_input, 'quadrature_input', sort = 8)

                    #Store current trial
                    self.last_trial = self.curr_trial

                    #increment current trial
                    self.curr_trial += 1

                    #Send block status update to mworks
                    if experimental_flag:
                        threading.Thread(target=self.block_status_trigger).start()

                    #reset tunnel
                    self.start_trial_change_stim_reset()

                    #Store last quadrature value
                    self.last_lj_pos = movement

                else:

                    #Set upper bound
                    self.camNP.setPos(a[0],b,a[2])

                    #mocw camera
                    self.mycamera[0].setPos(a[0],b,a[2])  

                    self.last_lj_pos = movement 

               # print("a: {} b: {}".format(a, b))

            elif movement < self.last_lj_pos:

                a=self.camNP.getPos()
                b=a[1]-self.moveFactor

                if b < self.lower_bound:
                    self.last_lj_pos = movement
                    pass

                else:
                    self.camNP.setPos(a[0],b,a[2])
                    self.mycamera[0].setPos(a[0],b,a[2])
                    self.last_lj_pos = movement


        return task.cont

    def trial_change_stim_reset(self, task):
        if self.curr_trial > self.last_trial:

            #reset complete gratings (So they will be triggered for new trial)
            for curr_grat in self.grating_dict.values():
                curr_grat.update({'status':None})        

            #Reset segment threshold (so tunnel just resets)
            self.tunnel_segment_pass = {i: False for i in range(self.visible_tunnel_length)}

            #Go through and reset tunnel to hide gratings
            for curr_tunnel_segment in range(self.tunnel_length):

                if curr_tunnel_segment < self.visible_tunnel_length:

                    self.tunnel[curr_tunnel_segment].show()

                else:

                    self.tunnel[curr_tunnel_segment].hide()

        return task.done


    def camera_positions(self, task):
        """
        get current camera position, store in list, and send to client
        """
        curr_y = self.camNP.getY()
        self.camera_y_positions.append(curr_y)

        try:
            camNP_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            camNP_server.sendto(str(curr_y).encode('utf-8'), ('localhost', camNP_port))
            camNP_server.close()
            print(format("Successfully sent camNP message to client"))
        except socket.error as e:
            print("Error sending message: {}".format(str(e)))

        return task.cont


    def quadrature_input(self, task):
        """
        Function/task that tracks quadrature input

        """
        print('quadrature queue: {}'.format(str(quadrature_queue)))

        while quadrature_queue:

            #Get oldest quadrature_queue value
            movement = int(quadrature_queue.popleft()[0]) # Get oldest quadrature input

            #Append to movement queue
            movement_queue.append(movement)

        return task.cont

    def reward_juice_trigger(self):
        """
        Sends trigger to client
        """
        try:
            juice_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            juice_server.sendto('entered_reward_zone'.encode('utf-8'), ('localhost', juice_port))
            juice_server.close()
            print(format("Successfully sent juice message to client"))
        except socket.error as e:
            print("Error sending message: {}".format(str(e)))

    def zone_trigger(self, zone_name, start_status, unexpected_status):
        """
        Sends zone start and end data to client

        Params:
        zone_name: should be one of A1, B2, A3, B4 or rewared
        start_status:  Boolean
        unexpected_status: str
        """
        try:
            zone_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            if 'unexpected' in unexpected_status and zone_name == 'B4': #(change this so zone name is just zone position)
                if(start_status):
                    print('start {} zone {}'.format(zone_name, unexpected_status))
                    zone_server.sendto('start {} zone {}'.format(session_type, unexpected_status).encode('utf-8'), ('localhost', zone_port))
                    zone_server.close()
                else:
                    print('end {} zone {}'.format(zone_name, unexpected_status))
                    zone_server.sendto('end {} zone {}'.format(session_type, unexpected_status).encode('utf-8'), ('localhost', zone_port))
                    zone_server.close()
            else:   
                if(start_status):
                    print('start {} zone'.format(zone_name))
                    zone_server.sendto('start {} zone'.format(zone_name).encode('utf-8'), ('localhost', zone_port))
                    zone_server.close()
                else:
                    print('end {} zone'.format(zone_name))
                    zone_server.sendto('end {} zone'.format(zone_name).encode('utf-8'), ('localhost', zone_port))
                    zone_server.close()            
            print(format("Successfully sent zone message to client"))
        except socket.error as e:
            print("Error sending zone message: {}".format(str(e)))

    def block_status_trigger(self):
        """
        For each trial -  sends a block identity to mworks
        """
        try:
            block_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            if self.curr_trial <= block1:
                block_server.sendto('block_1', ('localhost', block_port))
            else:
                 block_server.sendto('block_2', ('localhost', block_port))
        except socket.error as e:
            print("Error sending block status message: {}".format(str(e)))


    def inset_screen_setup(self):
        """
        Method that creates inset window that the photodiode will be placed on for 2P
        """
        inset_cam = self.makeCamera(self.win)
        # Set up a new DisplayRegion in the lower-left corner
        #inset_dr = self.win.makeDisplayRegion(.949, 1, 0, .16) 
        inset_dr = self.win.makeDisplayRegion(photodiode_size_x, photodiode_left_right_corner, photodiode_top_bottom_corner, photodiode_size_y)  # (halfway across the window, the right edge of the window, the bottom edge of the window, halfway up the window) in proportions
        inset_dr.setSort(20)  # Render on top of the main display region (not sure if this is needed)
        inset_dr.setCamera(inset_cam)
        # Set color
        inset_dr.setClearColorActive(True)
        #Set black background
        inset_dr.setClearColor((0, 0, 0, 1))
        return inset_dr

    def inset_screen_stim_off(self, task):
        """
        Task for turning inset screen for photodiode to black
        """
        self.inset_dr.setClearColor((0, 0, 0, 1))
        return task.done

#############

# Initialize shared queue for communication and server

#############
#Server ports for client
quadrature_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
quadrature_server.bind(("localhost", quadrature_port))  

health_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
health_server.bind(("localhost", health_port))  # Separate port for health check

#server online check
def health_check_server():
    """
    Runs a lightweight UDP health check server on a separate port.
    """

    while True:
        try:
            data, addr = health_server.recvfrom(1024)
            if data == b"PING":
                health_server.sendto(b"PONG", addr)  # Respond only to health checks
        except socket.error:
            break  # Exit on error (optional for clean shutdown)




# Receives commands from client.py for registering movement in panda3d
def quadrature_input():
    """
    Listens for quadrature input from mworks on 12345

    Time is calculated as time - time_start

    """
    print("Quadrature process (server) is running...")
    while True:
        data, addr = quadrature_server.recvfrom(12345) #input determines chunk size
        obtained_command = data.decode('utf-8').strip()
        quadrature_queue.append((obtained_command, time.time() - time_start))


# Start quadrature_input in a different thread
threading.Thread(target=quadrature_input).start()

#Start pong test for server health on another thread
threading.Thread(target=health_check_server).start()


#############

# run app

#############
app = MyApp()
app.run()
