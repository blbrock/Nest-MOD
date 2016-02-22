# Nest-MOD
Nest-MOD is a hardware and software interface to allow Nest Thermostats to work more efficiently with high efficiency
modulating/condensing boilers and furnaces that incorporate outdoor reset.

![](![hardware image](/images/P1020976.JPG))

Requires python_nest API developed by Jason Kölker:
https://github.com/jkoelker/python-nest/

# Background
Modulating/Condensing (mod/con) boilers with Outdoor Reset (ODR) function are among the most energy 
efficient home heating devices available. However, because mod/con boilers operate at lower output 
temperatures than conventional boilers and furnaces, they do not work well with advanced programable 
and learning thermostats (e.g. Nest) that offer energy savings by programming nightly temperature 
setbacks or when homes are not occupied. Mod/con boilers with ODR adjust their heat output to compensate 
for outdoor temperatures by dialing back heat ouput during warm weather and increasing output when it is 
cold. A properly tuned mod/con ODR boiler will produce just enough heat to compensate for the building's 
heat loss and therefore run at lower output for longer output for longer periods of time.

Because of their lower operating temperatures, mod/con ODR boilers can take many hours to recover from a 
temperature setback, if they recover at all. This is particularly true for radiant floor heating systems 
which are great for maintaining temperatures, but respond slowly to thermostat changes. 
Some boilers include a boost function that increases boiler output to speed recovery from temperature 
setbacks but many do not. 

Using temperature setbacks with radiant floor heating, and particularly with mod/con boilers, is a 
controversial topic. However, a study conducted by the National Renewable Energy Laboratory (NREL) 
indicates that nightly temperature setbacks do save energy in radiant floor, mod/con systems even if the 
boiler has to work harder to recover from those setbacks (http://www.nrel.gov/docs/fy14osti/60200.pdf).

Most networked thermostats do not include support for ODR furnaces and boilers. Nest 3rd 
generation thermostats sold in European markets now provides support for OpenTherm compliant modulating 
boilers which allows the thermostat to communicate with the boiler but currently cannot control boiler 
temperature. Based on discussions with Nest support, there doesn't appear to be any plan to implement 
modulating boiler support of any kind in the US. Therefore, one of the main energy saving advantages of 
programable thermostats is lost on systems that cannot recover from temperature setbacks in a reasonable 
time.

Frustrated by the lack of support for modulating boilers, I decided to build my own interface shield for 
a Raspberry pi. The shield and software are designed for a Munchkin boiler but should work (with appropriate 
modifcation) on any boiler that uses a thermistor to control the ODR curve. 

# Features: 

The software monitors thermostat data and initiates an ODR override cycle when > 1.25F temperature increase 
is called by any thermostat. Three stages of boost are provided depending on the differential between room 
ambient temperature and the target temperature the thermostat is trying to reach. Boost stage (and boiler 
temperature) increases with increasing differentials. Temperature differental threshold for each boost stage 
can be adjusted in the configuration (.secrets) file. Once the differential between target and room temperature 
reaches < 0.25F, ODR override is canceled and the boiler returns to its default ODR state.

The software tracks all thermostats in a Nest account and adjusts boost stages upward or downward according to 
the maximum boost level being requested by all thermostats in the account.

# Extras:

1. boost.py - a simple command line program to provide manual boost if needed. Manual boost cycles are logged (see below).

2. Automatic dehumidifier adjustment:
The software contains an optional routine to adjust the humidity setting for a selected thermostat according 
to outside temperature. This is useful for controlling an HRV or dehumidifier to maintain optimal indoor
humidity in cold climates. This feature does not require the pi to function.

3. Data logging:
Data from nest thermostats may optionally be logged to a file by setting options in the .secrets configuration file. 
This produces a comma delimited file containing data from thermostats and boost conditions. his feature does not require the pi to function.

4. Data Graphing:
In development, comming soon.

# Error checking and logging: 

ODR override events and communication failures are logged to nest_odr.log. If the device loses connection with
the Nest server during an ODR override cycle, it will continue to recheck the connection at 1 minute intervals 
for 30 minutes. If a connection is not made within 30 minutes, the ODR override is aborted and the boiler is 
returned to its default state.


 
 
