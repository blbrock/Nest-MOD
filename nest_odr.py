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

# sys.exit(-1) if other instance is running
me = singleton.SingleInstance() 
#sys.stdout.flush()
#sys.stderr.flush()

## Use the following pin map:
##   Pin     GPIO
##   13       27
##   16       23
##   18       24

try:
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(13, GPIO.IN)
    GPIO.setup(16, GPIO.IN)
    GPIO.setup(18, GPIO.IN)
except:
    pass

# define variables
global relay_trigger
relay_trigger = False
stage = 0
global dev_list
dev_list = []
timer_list = []
timer_dict = {}
T_start = datetime.datetime.now()
cur_dir = sys.path[0] + os.sep
i = 0
structure = None

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

        if stage == 2:
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

username = ConfigSectionMap('Credentials')['username']
password = ConfigSectionMap('Credentials')['password']
set_hum = ConfigSectionMap('Parameters')['set_hum']
delay_rechk = float(ConfigSectionMap('Parameters')['delay_rechk'])
i_s2 = float(ConfigSectionMap('Parameters')['delay_s2'])
i_s3 = float(ConfigSectionMap('Parameters')['delay_s3'])


##my_handler.setFormatter(blnk_formatter)
##app_log.info('')
##my_handler.setFormatter(log_formatter)
##
## remove this after intial testing
## app_log.info("-------- ODR Check Started --------")

# Get data from nest account
def get_napi():
    global structure
    global stage
    d = datetime.datetime.now().time()
    print('napi check @ ' + str(d))

    try:
        napi = nest.Nest(username, password)
        structure = napi.structures[0]
        
##        ############
##        if stage > 2:
##            structure = None
    except:
        structure = None

    return
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
    app_log.info('')
    my_handler.setFormatter(log_formatter)
    app_log.warning('--Unable to connect to Nest server for 30 minutes. Resetting ODR.--')
    Restore_ODR()
    sys.exit()
    return

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
                my_handler.setFormatter(blnk_formatter)
                app_log.info('')
                my_handler.setFormatter(log_formatter)
                app_log.info('******** [ODR Override Initiated] ********')
                app_log.info('\tRequesting_Thermostat    : %s' % Thermostat)
                app_log.info('\tTemp_Differential        : %s' % str(T_diff))
                app_log.info('\tTemp_Room                : %s' % str(T_room))
                app_log.info('\tTemp_Target              : %s' % str(T_target))
                app_log.info('\tTemp_Outside             : %s' % str(T_outside))
                print('\n******** [ODR override initiated] ********')
                print('\tRequesting_Thermostat    : %s' % Thermostat)
                dev_list.append(Thermostat)
            
                # create timers and boost cycle for thermostat staging
                
                create_timers(Thermostat)
            gpio = True
            
##            elif float(T_diff) < float(T_thresh) and H_stat == False:
##                if relay_trigger == False:
##                    my_handler.setFormatter(blnk_formatter)
##                    app_log.info('')
##                    my_handler.setFormatter(log_formatter)
##                    app_log.warning('*** Temperature Differential Detected But No Call For HEAT ***')
##                    app_log.warning('\tRequesting_Thermostat    : %s' % Thermostat)
##                    app_log.warning('\tTemp_Differential        : %s' % str(T_diff))
##                    app_log.warning('\tTemp_Room                : %s' % str(T_room))
##                    app_log.warning('\tTemp_Target               : %s' % str(T_target))
##                    print('Temperature low but no call for heat')
##                gpio = False

        else:
            gpio = False

# Add devices calling for boost to list and remove devices no longer calling for boost.

        if gpio == True and not Thermostat in dev_list:
            dev_list.append(Thermostat)
            app_log.info('\tDevice: ' + Thermostat + ' is requesting a new boost call and has been added to the queue')
            print('Device: ' + Thermostat + ' is requesting a new boost call and has been added to the queue.')
            # create timers for thermostat staging            
            create_timers(Thermostat)

        elif (not gpio or not H_stat) and Thermostat in dev_list:
            if not H_stat:
                app_log.info('*** Nest call for heat on Device: ' + Thermostat + ' has ended. Removing ' + Thermostat + ' from the boost queue')
                print('\tNest call for heat on Device: ' + Thermostat + ' has ended. Removing ' + Thermostat + ' from the boost queue')   

            # Cancel timers for deleted thermostat
            for t in timer_list[:]:
                if t.name == Thermostat:
                    t.timer.cancel()
                    print('timer ' + str(t.name) + ' cancelled.')
                    timer_list.remove(t)
                    t_start = t.t_start
                    Increment_Temp(Thermostat, None)

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
    try:
        print 'Pin 13 : %s' % str(GPIO.input(13))
        print 'Pin 16 : %s' % str(GPIO.input(16))
        print 'Pin 18 : %s' % str(GPIO.input(18))
        print '\n'
    except:
        pass
    gpio = max(gpio_list)

    if gpio == True:
        rchk = threading.Timer(delay_rechk, main)
        rchk.start()

    else:
        rchk = None
        
    return (gpio, rchk)

def create_timers(Thermostat):
    global stage
    if stage == 0:
        Increment_Temp(Thermostat, 1)

    t = timer(Thermostat, 2)
    timer_list.append(t)
    t = timer(Thermostat, 3)
    timer_list.append(t)
    return(timer_list)


# Controls GPIO pin #18 on raspberry pi. If relay_trigger = 1, then pins 4 and 5 are energized.
# If temperature not satisfied after %i_s% time, stage 2 is initiated by energizing pin 6 and deenergizing pin 5.
# If temperature not satisfied after 2 * %i_s% time, stage 3 is initiated by deenergizing pins 5 and 6.
#
#           Water Temp    PIN13  PIN16  PIN18
#           Stage1         On     Off     Off
#           Stage2         On     On      Off
#           Stage3         On     On      On
def Increment_Temp(name, level):
    i_s = 0
    global stage
    global structure
    pins = [13,16,18]

    if not level == 1:
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
        
    if stage <> level:
        for p in pins:
            if state[i_s] == True:
                Sname = 'HIGH'
            else:
                Sname = 'LOW'
            
            try:
                GPIO.output(p,state[i_s])
            except:
                pass
            i_s = i_s + 1
            print('\t--Pin ' + str(p) + ' set - ' + Sname)

# Log output
    if level > stage:
        app_log.info('\t-- Stage ' + str(level) + ' Boost engaged --')
        print('--Stage ' + str(level) + ' Boost engaged--')
    elif level < stage:
        app_log.info('\t-- Calling thermostat queue has changed. Reducing boost to Stage ' + str(level) + ' --')
        print('\t-- Calling thermostat queue has changed. Reducing boost to Stage ' + str(level) + ' --')
    stage = level
#    structure = get_napi()
    if structure == None:
        app_log.info('\tThermostat data not available at this time')
    else:
        for device in structure.devices:
            if device.where in dev_list:
                Thermostat = device.where
                T_room = nest_utils.c_to_f(device.temperature)
                T_target = nest_utils.c_to_f(device.target)
                T_diff = T_room - T_target
                app_log.info('\tRequesting_Thermostat    : %s' % Thermostat)
                app_log.info('\tTemp_Differential        : %s' % str(T_diff))
                app_log.info('\tTemp_Room                : %s' % str(T_room))
                app_log.info('\tTemp_Target              : %s' % str(T_target))

    return()
            
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
    
### Automatically adjusts RH target for living room thermostat to allow HRV to dehumidify according to outside temperature
def target_humidity(device):
    temperature = nest_utils.c_to_f(structure.weather.current.temperature)

    if temperature >= 50:
        hum_value = 55
    elif temperature >= 35:
        hum_value = 50
    elif temperature >= 30:
        hum_value = 45
    elif temperature >= 23:
        hum_value = 40
    elif temperature >= 14:
        hum_value = 35
    elif temperature >= -4:
        hum_value = 30
    elif temperature >= -13:
        hum_value = 25

    if float(hum_value) != device.target_humidity:
        device.target_humidity = hum_value

    return hum_value

def main():
    global i
    get_napi()
    while structure == None:
        i = check_connection(i)
    odr = ODR_override()
    relay_trigger = odr[0]
    rchk = odr[1]
    return (relay_trigger)
# PROGRAM STARTS HERE #
relay_trigger = main()
##if relay_trigger == True and stage == 1:
##    timers = GPIO_trigger()
##elif relay_trigger == True and stage > 1:
##    print('Boost already initiated, do nothing')

# Set target humidity according to outside temperature
if set_hum:
    hum_value = target_humidity(structure.devices[0])
    print 'Outside Temp    : %s' % str(nest_utils.c_to_f(structure.weather.current.temperature))
    print 'Outside Humidity: %s' % str(structure.weather.current.humidity)
    print 'Humidity Target : %s' % str(hum_value)

#Print additonal information
print 'GPIO            : %s' % str(relay_trigger)

   
