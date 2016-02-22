# -*- coding: utf-8 -*-
#
# boost.py -- a command line utility to manually increase boiler output temperature
# using raspberry pi interface.
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
# Usage: python boost.py [stage]            (stage must be an integer value 0-3)

import sys
try:
    import RPi.GPIO as GPIO
except:
    pass
from nest_extras import get_parameters, setup_log_handlers
# from nest_extras.py import *

stage = int(sys.argv[1])
if not 0 <= stage <= 3:
    print('variable stage = ' + str(stage) + ' is out of range. Select a value 0-3')
    sys.exit()

def main(stage):
    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(13, GPIO.OUT)
        GPIO.setup(16, GPIO.OUT)
        GPIO.setup(18, GPIO.OUT)
        GPIO.output(13, False)
        GPIO.output(16, False)
        GPIO.output(18, False)

        if stage > 0:
            GPIO.output(13, True)
        if stage > 1:
            GPIO.output(16, True)
        if stage > 2:
            GPIO.output(18, True)
    except:
        pass
    print ('Boiler temperature has been set to: Stage ' + str(stage))
    return()

main(stage)
# Import configuration parameters
p = get_parameters()
for key,val in p.items():
    exec(key + '=val')

# set up log file
log_object = setup_log_handlers(log_dir)
app_log = log_object[0]
my_handler = log_object[1]
log_formatter = log_object[2]
blnk_formatter = log_object[3]

# Log manual request
if stage > 0:
    app_log.info('** Manual boost requested -- Stage ' + str(stage) + ' Boost engaged **')
else:
    app_log.info('** Manual boost canceled -- ODR has been reset **')

        
