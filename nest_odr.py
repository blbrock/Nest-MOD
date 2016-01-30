# -*- coding: utf-8 -*-
#
# nest_odr.py -- a python interface to the Nest thermometer to provide
# outdoor reset override to boost boiler output to allow faster recovery from
# nightly temperature setbacks.
# ------------------------------------------------------------------------------
#
# Copyright 2016 Brent L. Brock and HoloScene Wildlife Services LLC
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# ---------------------------------------------------------------------------
# Author: Brent L. Brock
# ---------------------------------------------------------------------------
#
# Note: nest-odr requires python-nest developed by Jason Kölker, https://github.com/jkoelker/python-nest/

import os
import sys
import time
import ConfigParser
import datetime
import logging
from logging.handlers import RotatingFileHandler
import threading
import nest
from tendo import singleton
from nest import utils as nest_utils
try:
    import RPi.GPIO as GPIO
except:
    pass
# -------------------- Classes ---------------------------
# --------------------------------------------------------

# Create timing class to bind name with timer object
class cycle(object):
    def __init__(self, name):
        self.name = name
        ##    # Create time stamp for start of boost cycle    
        self.t_start = datetime.datetime.now()

class timer(cycle):
    def __init__(self, name, stage):
        super(timer,self).__init__(name)
#        self.tname = self.name + '_t' + str(stage)
        self.triggered = False
        self.stage = stage

        if stage == 1:
            i_s = 1
        elif stage == 2:
            i_s = i_s2
        elif stage == 3:
            i_s = i_s3
        else:
            raise 'ERROR:timer.stage is out of range...'    
        self.timer = threading.Timer(i_s,Increment_Temp,[self.name, self.stage])
        self.timer.start()

    def settriggered(self, active):
        self.triggered = active
        return self.triggered

# -------------------- Functions -------------------------
# --------------------------------------------------------

# Define Configuration File
def ConfigSectionMap(section):
    dict1 = {}
    options = Config.options(section)
    for option in options:
        try:
            dict1[option] = Config.get(section, option)
            if dict1[option] == -1:
                DebugPrint("skip: %s" % option)
        except:
            print("exception on %s!" % option)
            dict1[option] = None
    return dict1

# Get data from nest account
def get_napi():
    global structure
    global data
    structure = None
    data = None
##    global stage
    d = datetime.datetime.now().time()
    print('napi check @ ' + str(d))

    try:
        napi = nest.Nest(username, password)
        structure = napi.structures[0]
    except:
        structure = None

    return (structure, data)

# Track how long communication with Nest server is down
def check_connection(i):

    if i <= 29 and relay_trigger: # change to 29 after testing
        my_handler.setFormatter(blnk_formatter)
        app_log.info('')
        my_handler.setFormatter(log_formatter)
        print('--Unable to connect to Nest server for ' + str(i) + ' minutes. Will retry in 1 minute.--')
        my_handler.setFormatter(blnk_formatter)
        app_log.info('')
        my_handler.setFormatter(log_formatter)
        app_log.warning('--Unable to connect to Nest server for ' + str(i) + ' minutes. Will retry in 1 minute.--')
        i = i + 1
        time.sleep(60) #Change to 60 after testing
        get_napi()
        if not structure == None:
            print('--Nest server connection succeeded--')
            app_log.info('--Nest server connection succeeded--')
            i = 0

    elif i > 29: 
        con_err()
        sys.exit()
    else:
        print('--Unable to connect to Nest server. Will try again on next cycle.--')
        my_handler.setFormatter(blnk_formatter)
        app_log.info('')
        my_handler.setFormatter(log_formatter)
        app_log.warning('--Unable to connect to Nest server. Will try again on next cycle.--')
        sys.exit()
        i = i + 1
    return (i)

# Reset ODR and exit program if connection to Nest Server cannot be made during boost cycle
def con_err():
            
    print('--Unable to connect to Nest server for 30 minutes. Resetting ODR.--')
    my_handler.setFormatter(blnk_formatter)
    app_log.error('')
    my_handler.setFormatter(log_formatter)
    app_log.error('--Unable to connect to Nest server for 30 minutes. Resetting ODR.--')
    Restore_ODR()
    sys.exit()
    return

# Set GPIO pins to output
def GPIO_out(pins):
    print 'Running GPIO_out...'
    try:
        GPIO.setmode(GPIO.BOARD)
        for p in pins:
            GPIO.setup(p, GPIO.OUT)
            GPIO.output(p, False)
            print 'Pin ' + str(p) + ' set to OUT'
    except:
        app_log.error('*** GPIO pins could not be set to OUT ***')

# Make sure GPIO pin states match boost stage
def GPIO_check(target_states):
    cur_pin_state = []
    try:
        for p in pins:
            s = GPIO.input(p)
            if s:
                s = True
            elif not s:
                s = False       
            cur_pin_state.append(s)
            print 'Pin: ' + str(p) + ' is ' + str(s)
        GPIO_out(pins)
        print 'GPIO check successful'
    except:
        if not cur_pin_state == target_states:
            app_log.error('*** Current GPIO pin states do not match target pin states - Potential hardware malfunction ***')

# Send thermostat and weather data to log file
def log_data(thermostats):
    Away = structure.away
    devices = structure.devices
    Time_s = structure.weather.current.datetime.strftime('%H:%M:%S')

    for device in devices:
        Thermostat = device.where
        if Thermostat in thermostats:
            T_room = nest_utils.c_to_f(device.temperature)
            if Away:
                T_target = nest_utils.c_to_f(device.away_temperature[0])
                app_log.info('-- Away mode enabled --')
                print('-- Away mode enabled --')
            else:
                T_target = nest_utils.c_to_f(device.target)   
            H_stat = device.hvac_heater_state
            T_diff = T_room - T_target
            T_outside = nest_utils.c_to_f(structure.weather.current.temperature)
            app_log.info('\tSample Time              : %s' % Time_s)
            app_log.info('\tRequesting_Thermostat    : %s' % Thermostat)
            app_log.info('\tTemp_Differential        : %s' % str(T_diff))
            app_log.info('\tTemp_Room                : %s' % str(T_room))
            app_log.info('\tTemp_Target              : %s' % str(T_target))
            app_log.info('\tTemp_Outside             : %s' % str(T_outside))
            my_handler.setFormatter(blnk_formatter)
            app_log.info('')
            my_handler.setFormatter(log_formatter)

# Measures the temperature differential between the current room temperature and the target setpoint. If room temperature is
# <= 1.25 degrees F of the target temperature for any thermomemter, then relay_trigger is set to 1. HVAC-Stat is also checked to make
# sure a thermostat is actually calling for heat as an additional check.
def ODR_override():
    gpio_list = []

# Make sure connection with Nest server was established before continuing.
    Away = structure.away
    
    for device in structure.devices:
        Thermostat = device.where
        T_room = nest_utils.c_to_f(device.temperature)
        if Away:
            T_target = nest_utils.c_to_f(device.away_temperature[0])
            app_log.info('-- Away mode enabled --')
            print('-- Away mode enabled --')
        else:
            T_target = nest_utils.c_to_f(device.target)
            
        H_stat = device.hvac_heater_state
        T_diff = T_room - T_target
        T_outside = nest_utils.c_to_f(structure.weather.current.temperature)         

# Check if thermostat was calling for recovery in previous loop and sets threashold temp to -0.75F to
# maintain boost cycle until call for heat on device is satisfied.
        if Thermostat in dev_list:
            T_thresh = -0.75
        else:
            T_thresh = -1.25 # Adjust this value to increase or decrease the threshold tolerance
        if float(T_diff) < float(T_thresh) and H_stat == True:
            if stage == 0:
                GPIO_out(pins)
                my_handler.setFormatter(blnk_formatter)
                app_log.info('')
                my_handler.setFormatter(log_formatter)
                app_log.info('******** [ODR Override Initiated] ********')
                print('\n******** [ODR override initiated] ********')
                print('\tRequesting_Thermostat    : %s' % Thermostat)
                dev_list.append(Thermostat)
            
                # create timers and boost cycle for thermostat staging
                create_timers(Thermostat)
            gpio = True
        else:
            gpio = False

# Add devices calling for boost to list and remove devices no longer calling for boost.

        if gpio == True and not Thermostat in dev_list:
            dev_list.append(Thermostat)
            app_log.info('\t-- Device: ' + Thermostat + ' is requesting a new boost call and has been added to the queue --')
            print('Device: ' + Thermostat + ' is requesting a new boost call and has been added to the queue.')

            # create timers for thermostat staging            
            create_timers(Thermostat)

        elif (not gpio or not H_stat) and Thermostat in dev_list:
            if not H_stat:
                app_log.info('\t-- Nest call for heat on Device: ' + Thermostat + ' has ended. Removing ' + Thermostat + ' from the boost queue')
                print('\tNest call for heat on Device: ' + Thermostat + ' has ended. Removing ' + Thermostat + ' from the boost queue')   

            # Cancel timers for deleted thermostat
            for t in timer_list[:]:
                if t.name == Thermostat:
                    t.timer.cancel()
                    print('timer ' + str(t.name) + ' cancelled.')
                    timer_list.remove(t)
                    t_start = t.t_start

            T_delta = datetime.datetime.now() - t_start
            m, s = divmod(T_delta.total_seconds(), 60)
            h, m = divmod(m, 60)
            disp = "%d:%02d:%02d" % (h, m, s)
            app_log.info('\tBoost call for Device: ' + Thermostat + ' ended after ' + disp + '  H:MM:SS')
            print('*** Boost call for Device: ' + Thermostat + ' ended after ' + disp + '  H:MM:SS ***')
            dev_list.remove(Thermostat)

            if not dev_list:
                print('\nDevice list is empty...\n')
                Restore_ODR()
            else:
                app_log.info('\tBoost call continues for Device(s): ' + '[%s]' % ', '.join(map(str, dev_list)))
                print('*** Boost call continues for Device(s): [%s]' % ', '.join(map(str, dev_list)) + ' ***')
                Increment_Temp(Thermostat, None)

        gpio_list.append(gpio)
        print 'Thermostat    : %s' % Thermostat
        print 'Away Status   : %s' % str(Away)
        print 'T_room        : %s' % str(T_room)
        print 'T_target      : %s' % str(T_target)
        print 'HVAC State    : %s' % str(H_stat)
        print 'T_diff        : %s' % str(T_diff)
        print 'Device List   : %s' % dev_list
        print 'T_thresh      : %s' % str(T_thresh)
        print '\n'

    gpio = max(gpio_list)

    # Write data to log file if option is set
    if data_log:
        try:
            print data_log(structure)
        except:
            app_log.error('*** An error occured trying to write to data log ***')
            print '*** An error occured trying to write to data log ***'
            
    if gpio == True:
        rchk = threading.Timer(delay_rechk, main)
        rchk.start()

    else:
        rchk = None                      
    return (gpio, rchk)

# Create 3 boost stage timers whenever a new boost call is detected
def create_timers(Thermostat):
    t = timer(Thermostat, 1)
    timer_list.append(t)
    t = timer(Thermostat, 2)
    timer_list.append(t)
    t = timer(Thermostat, 3)
    timer_list.append(t)
    return(timer_list)

# Controls GPIO pins 13,16, & 18 on raspberry pi. 
#
#           Water Temp    PIN13  PIN16  PIN18
#           Stage1         On     Off     Off
#           Stage2         On     On      Off
#           Stage3         On     On      On

# Adjust boost stage according to active calls
def Increment_Temp(name, level):
    i_s = 0
    global stage
    print 'Running Increment_Temp...'

#    if not level == 1:
    # Set triggered state of current timer to True
    for t in timer_list:
        if t.name == name and t.stage == level:
            t.settriggered(True)
    # Get stage values of all timers that have triggered
    active_list = []
    for t in timer_list:
        if t.triggered == True:
            active_list.append(t.stage)
    if not active_list:
        level = 1
    else:
        level = max(active_list)

    # Set GPIO pins to target boost level        
    if level == 1:
        state = [True, False, False] # 22K Resistance
    elif level == 2:
        state = [True, True, False]  # 22K + 47K = 69K Resistance
    else:
        state = [True, True, True]  # Infinite Resistance (circuit open)

    #  Change GPIO pin states on pi to trigger appropriate boost stage and check to make sure pins were set as instructed    
    if stage <> level:
        for p in pins:
            try:
                print ('Trying to set GPIO pin, ' + str(p) + ' to ' + str(state[i_s]))
                GPIO.output(p,state[i_s])
            except:
                app_log.error('*** GPIO pin: ' + str(p) + ' could not be set ' + str(state[i_s]) + '***')        
            i_s = i_s + 1
        try:
            GPIO_check(state)
        except:
            pass

# Log output
    if not level == stage:

        if level > stage:
            app_log.info('\t-- Stage ' + str(level) + ' Boost engaged --')
            print('--Stage ' + str(level) + ' Boost engaged--')
        elif level < stage:
            app_log.info('\t-- Calling thermostat queue has changed. Reducing boost to Stage ' + str(level) + ' --')
            print('\t-- Calling thermostat queue has changed. Reducing boost to Stage ' + str(level) + ' --')
        log_data(dev_list)
        stage = level
    return()

# Kill timers, cleanup pins, and exit program            
def Restore_ODR():
    try:
        rchk.cancel()
        print('recheck cancelled')
    except:
        pass
    try:
        for t in timers:
            t.cancel()
            print('timer ' + str(t) + ' cancelled.')
    except:
        pass
    try:
        GPIO.cleanup()
    except:
        pass

    T_delta = datetime.datetime.now() - T_start
    m, s = divmod(T_delta.total_seconds(), 60)
    h, m = divmod(m, 60)
    disp = "%d:%02d:%02d" % (h, m, s)
    app_log.info('\t-- ODR Override Cycle Complete --')
    app_log.info('\t-- Total duration:  ' + disp + '  H:MM:SS --')
    print('**** ODR Override Cycle Complete ***** \n**** Total duration:  ' + disp + '  H:MM:SS ***\n')
    sys.exit()
    
def main():
    global i
    get_napi()
    while structure == None:
        i = check_connection(i)
    odr = ODR_override()
    relay_trigger = odr[0]
    rchk = odr[1]
    return (relay_trigger)

# ---------------------- PROGRAM STARTS HERE---------------------------- #

# sys.exit(-1) if other instance is running
me = singleton.SingleInstance() 

# define variables
global structure
global relay_trigger
global dev_list
global data
relay_trigger = False
stage = 0
dev_list = []
timer_list = []
timer_dict = {}
T_start = datetime.datetime.now()
cur_dir = sys.path[0] + os.sep
i = 0
pins = [13,16,18]

# Set up logging handlers
## log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')
log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
blnk_formatter = logging.Formatter('%(message)s')

logFile = dFile = sys.path[0] + os.sep + 'nest_odr.log'
#logfile.flush()
my_handler = RotatingFileHandler(logFile, mode='a', maxBytes=5*1024*1024, backupCount=5, encoding=None, delay=0)
my_handler.setFormatter(log_formatter)
my_handler.setLevel(logging.INFO)

app_log = logging.getLogger('root')
app_log.setLevel(logging.INFO)

app_log.addHandler(my_handler)

# Import credentials
Config = ConfigParser.ConfigParser()
Config.read(sys.path[0] + os.sep + '.secrets')

username = ConfigSectionMap('Credentials')['username']
password = ConfigSectionMap('Credentials')['password']
set_hum = ConfigSectionMap('Parameters')['set_hum']
data_log = ConfigSectionMap('Parameters')['log_data']

delay_rechk = float(ConfigSectionMap('Parameters')['delay_rechk'])
i_s2 = float(ConfigSectionMap('Parameters')['delay_s2'])
i_s3 = float(ConfigSectionMap('Parameters')['delay_s3'])

if data_log:
    from nest_extras import data_log

relay_trigger = main()

# Set target humidity according to outside temperature
if set_hum:
    from nest_extras import target_humidity
    hum_value = target_humidity(structure)
    print 'Outside Temp    : %s' % str(nest_utils.c_to_f(structure.weather.current.temperature))
    print 'Outside Humidity: %s' % str(structure.weather.current.humidity)
    print 'Humidity Target : %s' % str(hum_value)

#Print additonal information
print 'GPIO            : %s' % str(relay_trigger)

   
