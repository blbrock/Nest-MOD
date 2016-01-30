import os
import sys
import ConfigParser
import nest
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

# get number of lines in a file
def getSize(fileobject):
    fileobject.seek(0,2) # move the cursor to the end of the file
    size = fileobject.tell()
    return size

def get_napi(username, password): #might want to change these vars to global later
    global structure
    global data
    structure = None
    try:
        napi = nest.Nest(username, password)
        structure = napi.structures[0]
    except:
        structure = None
    napi = nest.Nest(username, password)
    structure = napi.structures[0]
    return(structure)

### Automatically adjusts RH target for living room thermostat to allow HRV to dehumidify according to outside temperature
def target_humidity(structure):
    if not structure:
        # Import credentials
        import ConfigParser
        Config = ConfigParser.ConfigParser()
        Config.read(sys.path[0] + os.sep + '.secrets')
        username = ConfigSectionMap(Config, 'Credentials')['username']
        password = ConfigSectionMap(Config, 'Credentials')['password']
        #get structure
        structure = get_napi(username, password)

    if structure:
        device = structure.devices[0]
        temperature = nest_utils.c_to_f(structure.weather.current.temperature)
        #calculate linear regression of target humidty and round to base 5 integer
        hum_value = int(5 * round(float((0.55 * temperature) + 31)/5))

        if float(hum_value) != device.target_humidity:
            device.target_humidity = hum_value
    else:
        hum_value = None
    return (hum_value)

# Create temperature log updated each time get_napi() is run
def data_log(structure):
    if not structure:
        # Import credentials
        import ConfigParser
        Config = ConfigParser.ConfigParser()
        Config.read(sys.path[0] + os.sep + '.secrets')
        username = ConfigSectionMap(Config, 'Credentials')['username']
        password = ConfigSectionMap(Config, 'Credentials')['password']
        #get structure
        structure = get_napi(username, password)
        
    if not os.path.isfile(sys.path[0] + os.sep + 'nest_data.log'):
        header = 'Thermostat,Sample_Time,T_room,T_target,T_diff,Humidity_inside,Humidity_target,T_outside,H_stat,Fan,Away\n'
    else:
        header = None

    log = open(sys.path[0] + os.sep + 'nest_data.log', 'a')
    if getSize(log) < 10000:
        if header:
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
            v_list = [Thermostat,Time_s,T_room,T_target,T_diff,humidity,hum_value,T_outside,H_stat,fan,Away]
            line = ''
            for v in v_list:
                line = line + str(v) + ','
            log.write(line + '\n')
        msg = ('Data successfully written to ' + log.name)
    else:
        app_log.warning('Data log file ' + f.name + ' is full. Cannot write new data.')
        msg = ('Data log file ' + log.name + ' is full. Cannot write new data.')
    log.close()
    return(msg)

# Print all parameters
def print_data(structure):
    if not structure:
        # Import credentials
        import ConfigParser
        Config = ConfigParser.ConfigParser()
        Config.read(sys.path[0] + os.sep + '.secrets')
        username = ConfigSectionMap(Config, 'Credentials')['username']
        password = ConfigSectionMap(Config, 'Credentials')['password']
        #get structure
        structure = get_napi(username, password)
        
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
##print data_log(None)

