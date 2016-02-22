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
import datetime
import threading
import nest
##import weakref
from tendo import singleton
from nest_extras import get_parameters, setup_log_handlers
from nest import utils as nest_utils
try:
    import RPi.GPIO as GPIO
except:
    pass
# -------------------- Classes ---------------------------
# --------------------------------------------------------
class thermostat(object):
    
    def __init__(self, name):
        self.name = name
        self.active = False
        self.h_state = None
        self.stage = 0
        self.new = False
        self.t_start = None
        self.thresh_1 = Thresh_Stage_1
##        self._items = []

    def setactive(self, active):
        self.active = active
        return self.active

    def setstage(self, stage):
        self.stage = stage
        if self.stage > 0 and  self.t_start == None:
                    self.t_start = datetime.datetime.now()
        return self.stage, self.t_start

    def seth_state(self, h_state):
        self.h_state = h_state
        return self.h_state
    
    def set_new(self, new):
        self.new = new
        return self.new

    def set_thresh_1(self, thresh):
        self.thresh_1 = thresh
        return self.thresh_1

##    @classmethod
##    def getinstances(cls):
##        dead = set()
##        for ref in cls._instances:
##            obj = ref()
##            if obj is not None:
##                yield obj
##            else:
##                dead.add(ref)
##        cls._instances -= dead

# -------------------- Functions -------------------------
# --------------------------------------------------------

# Get data from nest account
def get_napi():
    global structure
    global data
    structure = None
    data = None
##    global Stage
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

    if i <= 29 and Stage > 0: # change to 29 after testing
        my_handler.setFormatter(log_formatter)
        print('--Unable to connect to Nest server for ' + str(i) + ' minutes. Will retry in 1 minute.--')
        my_handler.setFormatter(log_formatter)
        try:
            app_log.warning('--Unable to connect to Nest server for ' + str(i) + ' minutes. Will retry in 1 minute.--')
        except:
            pass
        i = i + 1
        time.sleep(60) #Change to 60 after testing
        get_napi()
        if not structure == None:
            print('--Nest server connection succeeded--')
            try:
                app_log.info('--Nest server connection succeeded--')
            except:
                pass
            i = 0

    elif i > 29: 
        con_err()
        sys.exit()
    else:
        print('--Unable to connect to Nest server. Will try again on next cycle.--')
        my_handler.setFormatter(blnk_formatter)
        try:
            app_log.info('')
            my_handler.setFormatter(log_formatter)
            app_log.warning('--Unable to connect to Nest server. Will try again on next cycle.--')
        except:
            pass
        sys.exit()
        i = i + 1
    return (i)

# Reset ODR and exit program if connection to Nest Server cannot be made during boost cycle
def con_err():
            
    print('--Unable to connect to Nest server for 30 minutes. Resetting ODR.--')
    try:
        my_handler.setFormatter(blnk_formatter)
        app_log.error('')
        my_handler.setFormatter(log_formatter)
        app_log.error('--Unable to connect to Nest server for 30 minutes. Resetting ODR.--')
    except:
        pass
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
        try:
            app_log.error('*** GPIO pins could not be set to OUT ***')
        except:
            pass

def set_GPIO(pin, state):
    try:
        print ('Trying to set GPIO pin, ' + str(pin) + ' to ' + str(state))
        GPIO.output(pin,state)
    except:
        try:
            app_log.error('*** GPIO pin: ' + str(pin) + ' could not be set to ' + str(state) + ' ***')    
        except:
            pass
        
# Make sure GPIO pin states match boost stage
def GPIO_check(target_states):
    cur_pin_state = []
    try:
        for p in pins:
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
            try:
                app_log.error('*** Current GPIO pin states do not match target pin states - Potential hardware malfunction ***')
            except:
                pass
                 
def make_therm_objects():
    global therm_list
    therm_list = [thermostat(device.where) for device in structure.devices]
    return therm_list

def get_target_stage():
    level_list = []
    for t in therm_list:
        level_list.append(t.stage)
    target_stage = int(max(level_list))
    sum_stage = int(sum(level_list))
    return target_stage, sum_stage

# Measures the temperature differential between the current room temperature and the target setpoint. If room temperature is
# <= 1.25 degrees F of the target temperature for any thermomemter, then relay_trigger is set to 1. HVAC-Stat is also checked to make
# sure a thermostat is actually calling for heat as an additional check.
def ODR_override():

# Make sure connection with Nest server was established before continuing.
    Away = structure.away
    
    for device in structure.devices:
        T_name = device.where
        T_room = nest_utils.c_to_f(device.temperature)
        if Away:
            T_target = nest_utils.c_to_f(device.away_temperature[0])
            try:
                app_log.info('-- Away mode enabled --')
            except:
                pass
            print('-- Away mode enabled --')
        else:
            T_target = nest_utils.c_to_f(device.target)
            
        H_stat = device.hvac_heater_state
        T_diff = T_room - T_target
        T_outside = nest_utils.c_to_f(structure.weather.current.temperature)
        for th in therm_list:
            if th.name == T_name:
                t = th
                
        t.seth_state(H_stat)

# Check if thermostat was calling for recovery in previous loop and sets threashold temp to -0.75F to
# maintain boost cycle until call for heat on device is satisfied.
        if t.active:
            t.set_thresh_1(-0.75)
    
        if float(T_diff) < float(Thresh_Stage_3) and H_stat == True:
            t.setstage(3)
        elif float(T_diff) < float(Thresh_Stage_2) and H_stat == True:
            t.setstage(2)
        elif float(T_diff) < float(t.thresh_1) and H_stat == True:
            t.setstage(1)
        else:
            t.setstage(0)

        if t.stage > 0:
            t.setactive(True)
##            gpio = True
        else:
            t.setactive(False)
##            gpio = False

        print 'Thermostat    : %s' % T_name
        print 'Away Status   : %s' % str(Away)
        print 'T_room        : %s' % str(T_room)
        print 'T_target      : %s' % str(T_target)
        print 'HVAC State    : %s' % str(H_stat)
        print 'T_diff        : %s' % str(T_diff)
        print 'T_thresh      : %s' % str(t.thresh_1)
        print 'Device List   : %s' % dev_list
        print '\n'
        
        update_status(t)

    # Write data to log file if option is set
    if log_data:
        d_log = data_log(structure, Stage, log_dir, max_log_size)
        if d_log[1]:
            try:
                app_log.warning(d_log[0])
            except:
                pass
        print d_log[0]

    if get_target_stage()[0] > 0:
        rchk = threading.Timer(delay_rechk, main)
        rchk.start()
    else:
        rchk = None

    if dev_list:
        Increment_Temp()

# Log initaiaton of new boost cycle
def update_status(t):

    ## Report new boost initiated
    if t.active and Stage == 0 and not t.name in dev_list:
        t.set_new(True)
        my_handler.setFormatter(log_formatter)
        try:
            app_log.info('******** [ODR Override Initiated] ********')
        except:
            pass
        print('\n******** [ODR override initiated] ********')
        print('\tRequesting_Thermostat    : %s' % t.name)
        GPIO_out(pins)

        dev_list.append(t.name)

# Add devices calling for boost to list and remove devices no longer calling for boost.
    if t.active and t.h_state == True and not t.name in dev_list:
        t.set_new(True)
        dev_list.append(t.name)
        try:
            app_log.info('\t-- Device: ' + t.name + ' is requesting a new boost call and has been added to the queue')
        except:
            pass
        print('Device: ' + t.name + ' is requesting a new boost call and has been added to the queue.')
        report_data(dev_list)

    elif (t.stage == 0 or not t.h_state) and t.name in dev_list:
        if not t.h_state:
            try:
                app_log.info('\t-- Nest call for heat on Device: ' + t.name + ' has ended. Removing ' + t.name + ' from the boost queue')
            except:
                pass
            print('\tNest call for heat on Device: ' + t.name + ' has ended. Removing ' + t.name + ' from the boost queue')   

        T_delta = datetime.datetime.now() - t.t_start
        m, s = divmod(T_delta.total_seconds(), 60)
        h, m = divmod(m, 60)
        disp = "%d:%02d:%02d" % (h, m, s)
        try:
            app_log.info('\tBoost call for Device: ' + t.name + ' ended after ' + disp + '  H:MM:SS')
        except:
            pass
        print('*** Boost call for Device: ' + t.name + ' ended after ' + disp + '  H:MM:SS ***')
        t.setactive(False)
        dev_list.remove(t.name)

        if not dev_list:
            print('\nDevice list is empty...\n')
            Restore_ODR()
        else:
            try:
                app_log.info('\tBoost call continues for Device(s): ' + '[%s]' % ', '.join(map(str, dev_list)))
            except:
                pass
            print('*** Boost call continues for Device(s): [%s]' % ', '.join(map(str, dev_list)) + ' ***')

# Controls GPIO pins 13,16, & 18 on raspberry pi. 
#
#           Water Temp    PIN13  PIN16  PIN18
#           Stage1         On     Off     Off
#           Stage2         On     On      Off
#           Stage3         On     On      On

# Adjust boost stage according to active calls
def Increment_Temp():
    i_s = 0
    global Stage
    level_list = []

    level, sum_stage = get_target_stage()

# Increase boost stage if cumulative boost call is large
    if sum_stage > 5:
        level = 3

    # Set GPIO pins to target boost level
    if Stage <> level:
        if level >= 1:
            set_GPIO(13, True) # 22K Resistance
        else:
            set_GPIO(13, False)
            
        if level >= 2:
                set_GPIO(16, True) # 22K + 47K = 69K Resistance
        else:
            set_GPIO(16, False)
            
        if level == 3:
            set_GPIO(18,True) # Infinite Resistance (circuit open)
        else:
            set_GPIO(18,False)

# Log output
    if not level == Stage:
            
        if level > Stage and Stage > 0:
            try:
                app_log.info('\t-- Calling thermostat queue status has changed. Increasing boost to Stage ' + str(level) + ' --')
            except:
                pass
            print('\t-- Calling thermostat status has changed. Increasing boost to Stage ' + str(level) + ' --')

        elif level < Stage:
            try:
                app_log.info('\t-- Calling thermostat queue status has changed. Reducing boost to Stage ' + str(level) + ' --')
            except:
                pass
            print('\t-- Calling thermostat status has changed. Reducing boost to Stage ' + str(level) + ' --')

        try:
            app_log.info('\t-- Stage ' + str(level) + ' Boost engaged --')
        except:
            pass
        print('--Stage ' + str(level) + ' Boost engaged--')

        report_data(dev_list)
    Stage = level

# Send thermostat and weather data to log file
def report_data(thermostats):
    Away = structure.away
    devices = structure.devices
    Time_s = structure.weather.current.datetime.strftime('%H:%M:%S')

    for device in devices:
        try:
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
        except:
            pass


# Kill timers, cleanup pins, and exit program            
def Restore_ODR():
    try:
        rchk.cancel()
        print('recheck cancelled')
    except:
        pass
    
    try:
        GPIO.cleanup()
    except:
        pass
    try:
        T_delta = datetime.datetime.now() - T_start
        m, s = divmod(T_delta.total_seconds(), 60)
        h, m = divmod(m, 60)
        disp = "%d:%02d:%02d" % (h, m, s)
        app_log.info('\t-- ODR Override Cycle Complete --')
        app_log.info('\t-- Total duration:  ' + disp + '  H:MM:SS --')
        my_handler.setFormatter(blnk_formatter)
        app_log.info('')
        print('**** ODR Override Cycle Complete ***** \n**** Total duration:  ' + disp + '  H:MM:SS ***\n')
    except:
        pass
    sys.exit()
    
def main():
    global i
    get_napi()
    while structure == None:
        i = check_connection(i)
    if not therm_list:
        make_therm_objects()
        print('Thermostat objects created...')
    ODR_override()

# ---------------------- PROGRAM STARTS HERE---------------------------- #

# sys.exit(-1) if other instance is running
me = singleton.SingleInstance() 

# define variables
global structure
global therm_list
global dev_list
global data
relay_trigger = False
Stage = 0
dev_list = []
therm_list = []
T_start = datetime.datetime.now()
i = 0
pins = [13,16,18]

# Import configuration parameters
p = get_parameters()
for key,val in p.items():
    exec(key + '=val')

# set up log file
# Wrap all logging operation in try statements to prevent lost connection to remote logging directory
# from causing the program to crash.
try:
    log_object = setup_log_handlers(log_dir)
    app_log = log_object[0]
    my_handler = log_object[1]
    log_formatter = log_object[2]
    blnk_formatter = log_object[3]

    if log_data:
        from nest_extras import data_log
        from subproccess import call

except:
    pass

main()

# Set target humidity according to outside temperature
if set_hum:
    from nest_extras import target_humidity
    hum_value = target_humidity(structure)
    print 'Outside Temp    : %s' % str(nest_utils.c_to_f(structure.weather.current.temperature))
    print 'Outside Humidity: %s' % str(structure.weather.current.humidity)
    print 'Humidity Target : %s' % str(hum_value)

# Remove duplicate lines from data log without changing sort order
if log_data:
    try:
        dfile = log_dir + 'nest_data.log'
        tmpfile = log_dir + 'temp.log'
        call("awk '!x[$0]++' '%s' > '%s' && mv '%s' '%s'" % (dfile, tmpfile, tmpfile, dfile), shell=True)
    except:
        pass
