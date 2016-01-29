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

### Test code
##hum_value = target_humidity(None)
##print hum_value
