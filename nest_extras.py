#!/usr/bin/env python
import os, sys, ConfigParser, logging, nest
from datetime import datetime
from logging.handlers import RotatingFileHandler
from nest import utils as nest_utils

def ConfigSectionMap(Config, section):
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

# Set up logging handlers
def setup_log_handlers(log_dir):
    log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    blnk_formatter = logging.Formatter('%(message)s')

    logFile = dFile = log_dir + 'nest_odr.log'
    my_handler = RotatingFileHandler(logFile, mode='a', maxBytes=5*1024*1024, backupCount=5, encoding=None, delay=0)
    my_handler.setFormatter(log_formatter)
    my_handler.setLevel(logging.INFO)
    app_log = logging.getLogger('root')
    app_log.setLevel(logging.INFO)
    app_log.addHandler(my_handler)
    return(app_log, my_handler, log_formatter, blnk_formatter)

def get_parameters():
    # Import credentials
    Config = ConfigParser.ConfigParser()
    Config.read(sys.path[0] + os.sep + '.secrets')

    username = ConfigSectionMap(Config, 'Credentials')['username']
    password = ConfigSectionMap(Config, 'Credentials')['password']

    # Import parameters
    set_hum = ConfigSectionMap(Config,'Parameters')['set_hum']
    max_hum = ConfigSectionMap(Config,'Parameters')['max_hum']
    exec (ConfigSectionMap(Config,'Parameters')['log_dir']) #creates log_dir variable
    max_log_size = ConfigSectionMap(Config,'Parameters')['max_log_size']
    log_data = ConfigSectionMap(Config,'Parameters')['log_data']
    delay_rechk = float(ConfigSectionMap(Config,'Parameters')['delay_rechk'])
    Thresh_Stage_1 = float(ConfigSectionMap(Config,'Parameters')['thresh_stage_1'])
    Thresh_Stage_2 = ConfigSectionMap(Config,'Parameters')['thresh_stage_2']
    Thresh_Stage_3 = ConfigSectionMap(Config,'Parameters')['thresh_stage_3']
    return locals()

def get_napi(username, password):
    global structure
    global data
    structure = None
    data = None
    d = datetime.now().time()
    print('napi check @ ' + str(d))
    try:
        napi = nest.Nest(username, password)
        structure = napi.structures[0]
    except:
        structure = None
    return(structure, data)

# number of lines in text file
def getSize(fileobject):
    fileobject.seek(0,2) # move the cursor to the end of the file
    size = fileobject.tell()
    return size

# Automatically adjusts RH target allow HRV to dehumidify according to outside temperature.
# NOTE: This sets all thermostats in the structure to the same target humidity. Modify code if this is not desirable.
def target_humidity(structure, max_hum):
    if not structure:
        # Import credentials
        import ConfigParser
        Config = ConfigParser.ConfigParser()
        Config.read(sys.path[0] + os.sep + '.secrets')
        username = ConfigSectionMap(Config, 'Credentials')['username']
        password = ConfigSectionMap(Config, 'Credentials')['password']
        #get structure
        structure = get_napi(username, password)[0]

    if structure:
        for device in structure.devices:
            temperature = nest_utils.c_to_f(structure.weather.current.temperature)
            #calculate linear regression of target humidty and round to base 5 integer
            hum_value = int(5 * round(float(((0.55 * temperature) + 31) - 2.5)/5))
            if hum_value > max_hum:
                hum_value = max_hum

            if float(hum_value) != device.target_humidity:
                device._set('device', {'target_humidity': float(hum_value)})
    else:
        hum_value = None
    return (hum_value)

## Create schedule atttibute
## Creates a list of setpoint lists.  Setpoint lists formatted as [weekday, setpoint_num, time(seconds), temp(C), type]

def get_schedule(device):
    dev_sched = device._nest_api._cache[0]['schedule'][device._device['serial_number']]
    schedule = []
    setpoint = []
    for day in dev_sched['days']:
        for n in range(10):
            try:
                sp = dev_sched['days'][str(day)][str(n)]
                if sp['entry_type'] == 'setpoint':
                    setpoint = [int(day), n, sp['time'], sp['temp'], sp['type']]
                    schedule.append(setpoint)
                    setpoint = []
            except: pass
            
    return schedule

def calc_setpoint(thermostat):
    now = datetime.now()
    seconds = (now - now.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
    day = datetime.today().weekday()
    dev_sched = get_schedule(thermostat)
    day_sched = [x for x in dev_sched if x[0] == day]
    sp_first = 0
    sp_last = len(day_sched) - 1
    for sp in day_sched:
       # sp_next = None
        sp_next = day_sched.index(sp) + 1
        if sp_next <= sp_last:
            if seconds >= sp[2] and seconds < day_sched[sp_next][2]:
                setpoint = sp[3]
        elif seconds < day_sched[sp_first][2] or seconds >= day_sched[sp_last][2]:
            setpoint = day_sched[sp_last][3]

    setpoint = round(nest_utils.c_to_f(setpoint), 0)
#    print("Setpoint: %s" %(setpoint))
    return setpoint
    
# Create temperature log updated each time get_napi() is run
#def data_log(napi, stage, log_dir, max_log_size):
def data_log(structure, stage, log_dir, max_log_size):
##    try:
##        structure = napi.structures[0]
##    except:
##        structure = None
    if not structure:
        p = get_parameters()
        for key,val in p.items():
            exec(key + '=val')

        #get structure
        structure = get_napi(username, password)[0]
        
    if not os.path.isfile(log_dir + 'nest_data.log'):
        header = 'Thermostat,Sample_Time,T_room,T_target,T_diff,Humidity_inside,Humidity_target,T_outside,H_stat,Fan,Away,Stage, T_setpoint\n'
    else:
        header = None

    log = open(log_dir + 'nest_data.log', 'a')

    if getSize(log) < max_log_size: # Limit log file size to 100 Mb
        warning = False
        if not header == None:
            log.write(header)
            
        Away = structure.away
        Time_s = structure.weather.current.datetime.strftime('%Y-%m-%d %H:%M:%S')
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
            hum_value = device.target_humidity
            humidity = device.humidity
            fan = device.fan
            #######
            T_setpoint = calc_setpoint(device)
            v_list = [Thermostat,Time_s,T_room,T_target,T_diff,humidity,hum_value,T_outside,H_stat,fan,Away,stage,T_setpoint]
            line = ''
            for v in v_list:
                line = line + str(v) + ','
            line = line[:-1]
            log.write(line + '\n')
        msg = ('Data successfully written to ' + log.name)
    else:
        warning = True
        msg = ('Data log file ' + log.name + ' is full. Cannot write new data.')
    log.close()
    return(msg, warning)

# Print all parameters
def print_data(structure):
    if not structure:
        # Import credentials
        p = get_parameters()
        for key,val in p.items():
            exec(key + '=val')
            
        #get structure
        structure = get_napi(username, password)[0]
        
    print 'Structure %s' % structure.name
    print '    Away: %s' % structure.away
    print '    Devices:'

    for device in structure.devices:
        print '        Device: %s' % device.name
        print '            Temp: %0.1f' % device.temperature

##    # Access advanced structure properties:
##    print 'Structure   : %s' % structure.name
##    print ' Postal Code                    : %s' % structure.postal_code
##    print ' Country                        : %s' % structure.country_code
##    print ' dr_reminder_enabled            : %s' % structure.dr_reminder_enabled
##    print ' emergency_contact_description  : %s' % structure.emergency_contact_description
##    print ' emergency_contact_type         : %s' % structure.emergency_contact_type
##    print ' emergency_contact_phone        : %s' % structure.emergency_contact_phone
##    print ' enhanced_auto_away_enabled     : %s' % structure.enhanced_auto_away_enabled
##    print ' eta_preconditioning_active     : %s' % structure.eta_preconditioning_active
##    print ' house_type                     : %s' % structure.house_type
##    print ' hvac_safety_shutoff_enabled    : %s' % structure.hvac_safety_shutoff_enabled
##    print ' num_thermostats                : %s' % structure.num_thermostats
##    print ' measurement_scale              : %s' % structure.measurement_scale
##    print ' renovation_date                : %s' % structure.renovation_date
##    print ' structure_area                 : %s' % structure.structure_area

    # Access advanced device properties:
    for device in structure.devices:
        print '        Device: %s' % device.name
        print '        Where: %s' % device.where
        print '            Mode     : %s' % device.mode
        print '            Fan      : %s' % device.fan
        print '            Temp     : %0.1fC' % device.temperature
        print '            Humidity : %0.1f%%' % device.humidity
        print '            Target   : %0.1fC' % device.target
        print '            Away Heat: %0.1fC' % device.away_temperature[0]
##        print '            Away Cool: %0.1fC' % device.away_temperature[1]

        print '            hvac_ac_state         : %s' % device.hvac_ac_state
        print '            hvac_cool_x2_state    : %s' % device.hvac_cool_x2_state
        print '            hvac_heater_state     : %s' % device.hvac_heater_state
        print '            hvac_aux_heater_state : %s' % device.hvac_aux_heater_state
        print '            hvac_heat_x2_state    : %s' % device.hvac_heat_x2_state
        print '            hvac_heat_x3_state    : %s' % device.hvac_heat_x3_state
        print '            hvac_alt_heat_state   : %s' % device.hvac_alt_heat_state
        print '            hvac_alt_heat_x2_state: %s' % device.hvac_alt_heat_x2_state
        print '            hvac_emer_heat_state  : %s' % device.hvac_emer_heat_state

        print '            online                : %s' % device.online
        print '            last_ip               : %s' % device.last_ip
        print '            local_ip              : %s' % device.local_ip
        print '            last_connection       : %s' % device.last_connection

        print '            error_code            : %s' % device.error_code
        print '            battery_level         : %s' % device.battery_level


    time_str = structure.weather.current.datetime.strftime('%Y-%m-%d %H:%M:%S')
    print 'Current Weather at %s:' % time_str
    print '    Condition: %s' % structure.weather.current.condition
    print '    Temperature: %s' % structure.weather.current.temperature
    print '    Humidity: %s' % structure.weather.current.humidity
    print '    Wind Dir: %s' % structure.weather.current.wind.direction
    print '    Wind Azimuth: %s' % structure.weather.current.wind.azimuth
    print '    Wind Speed: %s' % structure.weather.current.wind.kph

    # NOTE: Hourly forecasts do not contain a "contidion" its value is `None`
    #       Wind Speed is likwise `None` as its generally not reported
    print 'Hourly Forcast:'
    for f in structure.weather.hourly:
        print '    %s:' % f.datetime.strftime('%Y-%m-%d %H:%M:%S')
        print '        Temperature: %s' % f.temperature
        print '        Humidity: %s' % f.humidity
        print '        Wind Dir: %s' % f.wind.direction
        print '        Wind Azimuth: %s' % f.wind.azimuth


    # NOTE: Daily forecasts temperature is a tuple of (low, high)
    print 'Daily Forcast:'
    for f in structure.weather.daily:
        print '    %s:' % f.datetime.strftime('%Y-%m-%d %H:%M:%S')
        print '    Condition: %s' % structure.weather.current.condition
        print '        Low: %s' % f.temperature[0]
        print '        High: %s' % f.temperature[1]
        print '        Humidity: %s' % f.humidity
        print '        Wind Dir: %s' % f.wind.direction
        print '        Wind Azimuth: %s' % f.wind.azimuth
        print '        Wind Speed: %s' % structure.weather.current.wind.kph


    # NOTE: By default all datetime objects are timezone unaware (UTC)
    #       By passing `local_time=True` to the `Nest` object datetime objects
    #       will be converted to the timezone reported by nest. If the `pytz`
    #       module is installed those timezone objects are used, else one is
    #       synthesized from the nest data


### Test code
##hum_value = target_humidity(None)
##print hum_value
##    
##print_data(None)
##
##print data_log(None, None, None, 0)

# Import configuration parameters
##p = get_parameters()
##for key,val in p.items():
##    exec(key + '=val')
##    
##st = get_napi(username, password)
##print str(st)
##print ("getting humidity target value...")
##hum_value = target_humidity(st)
##print ('hum_value = ' + str(hum_value))
##print ('max_hum = ' + str(max_hum))

##sp = calc_setpoint('master bedroom', datetime.now().replace(hour=0, minute=22, second=0, microsecond=0))
##sp = calc_setpoint('master bedroom', datetime(2016, 2, 22, 15, 0, 0))
##print str(sp)

##import csv
##output = ""
##log_dir = r'\\SAGEDISK\home\nest'
##
##file_name = log_dir + os.sep + 'nest_data.log'
##outfile = log_dir + os.sep + 'nest_data_new.log'
##
##
##with open(file_name, 'r') as f, open (outfile,'wb') as fout:
##    reader = csv.reader(f, delimiter=',', skipinitialspace=True)
##    writer = csv.writer(fout, delimiter=',')
##    next(reader, None)  # skip the headers
##    for x in reader:
####        if  not x[13]:
##        therm = x[0]
##        samp_time = x[1]
##        string_to_add = calc_setpoint(therm,samp_time)
##        x[12] = (string_to_add)
##        print x
##        writer.writerow(x)


