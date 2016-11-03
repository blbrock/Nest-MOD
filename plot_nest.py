import os
import matplotlib as mpl
#mpl.use('WXAgg')
#matplotlib.use('Agg')
import numpy as np
import matplotlib.pyplot as plt
#import matplotlib.cbook as cbook
from matplotlib.dates import MO, TU, WE, TH, FR, SA, SU
from datetime import datetime, timedelta
from nest_extras import get_parameters
from subprocess import call
import csv


##-------------------------------- Classes --------------------------------------
class data_file(object):
    
    def __init__(self, name, fname):
        self.name = name
        self.file = fname
        self.array = None
        self.plot = None

    def setarray(self, data):
        self.array = data
        return self.array

##------------------------------ Functions ---------------------------------------
def get_thermostat_list(infile):
    thermostats = []
    with open(infile, 'r') as f:
        reader = csv.reader(f, delimiter=',', skipinitialspace=True)
        next(reader, None)  # skip the headers
        for row in reader:
            if row[0] not in thermostats:
                thermostats.append(row[0])
    return(thermostats)

def subset_data(infile, thermostat):    
    outfile = infile.rsplit(os.sep,1)[0] + os.sep + thermostat.replace(' ', '_') + '.csv'
    with open(infile,'r') as fin, open (outfile,'w') as fout:
        writer = csv.writer(fout, delimiter=',')
        rownum = 0
        for row in csv.reader(fin, delimiter=','):
            if row[0] == thermostat or rownum == 0:
                 writer.writerow(row)
            rownum += 1
    return (outfile)

def gen_array(data_file):
    datestr2num = lambda x: datetime.strptime(x, '%Y-%m-%d %H:%M:%S')

    array = np.genfromtxt(data_file.file, names=True, converters={'Sample_Time': datestr2num},
                         delimiter=',', dtype=None, skip_header=0, skip_footer=0)
    return array

def plot_thermostat(array, thermostat):
    time, t_room, t_target = array['Sample_Time'], array['T_room'], array['T_target']
    fig = plt.figure()
    ax1 = fig.add_subplot(311, axisbg='dimgray')
    plt.plot_date(x=time, y=t_target, fmt='-', color='red')
    plt.plot_date(x=time, y=t_room, fmt='-')
    plt.gcf().autofmt_xdate()
    plt.title(thermostat)
    plt.ylabel('Temp_room')
    plt.xlabel('Date')
    plt.show()
    return(array)

def plot_thermostats(data_file_list):
    i = 1
    fig = plt.figure()
    # get datetime of one week ago
    xlim = datetime.now() - timedelta(days=7)
    for d in data_file_list:
        time, t_room, t_target, t_setpoint = d.array['Sample_Time'], d.array['T_room'], d.array['T_target'], d.array['T_setpoint']
        d.plot = fig.add_subplot(310 + i, axisbg='white')
        plt.plot_date(x=time, y=t_room, fmt='-', color='blue', label='Room Temp F')
        plt.plot_date(x=time, y=t_target, fmt='-', color='orange', label ='Target Temp F')
        plt.plot_date(x=time, y=t_setpoint, fmt='-', color='gray', label = 'Setpoint Temp F')
        plt.gcf().autofmt_xdate()
        plt.title(d.name)
        plt.ylabel('Temp F')
      #  plt.xlabel('Date')
        d.plot.set_xlim([xlim, datetime.now()])
        
        i = i + 1

        if d == data_file_list[0]:

            legend = plt.legend(loc='upper right', shadow=False)
            # The frame is matplotlib.patches.Rectangle instance surrounding the legend.
            frame = legend.get_frame()
            frame.set_facecolor('white')
            frame.set_edgecolor('black')
            # Set the fontsize
            for label in legend.get_texts():
                label.set_color('black')
                label.set_fontsize('medium')

    loc = d.plot.xaxis.set_major_locator(mpl.dates.WeekdayLocator(byweekday=(MO, TU, WE, TH, FR, SA, SU)))
    loc2 = d.plot.xaxis.set_minor_locator(mpl.dates.HourLocator(byhour=(12)))
    d.plot.xaxis.set_major_formatter(mpl.dates.DateFormatter('%a %d %b\n%H:%M'))
  #  d.plot.xaxis.set_major_formatter(mpl.dates.DateFormatter('%a %d\n%b %Y\n%H:%M'))
  #  d.plot.xaxis.set_minor_formatter(mpl.dates.DateFormatter("%H:%M"))


    mng = plt.get_current_fig_manager()
##    mng.frame.Maximize(True)

    ### for 'TkAgg' backend
    mng.window.state('zoomed')

    plt.show()

p = get_parameters()
for key,val in p.items():
    if key == 'log_dir':
        exec(key + '=val')

csv_file = log_dir + os.sep + 'nest_data.log'

thermostats = get_thermostat_list(csv_file)
data_file_list = []
for t in thermostats:
##    data_file(t, subset_data(csv_file, t))
    data_file_list.append(data_file(t, subset_data(csv_file, t)))

##zip_list = zip(thermostats,data_file_list)

for z in data_file_list:
    z.setarray(gen_array(z))
#    data = plot_thermostat(z.array, z.name)
plot_thermostats(data_file_list)
# Clean up temp files
for d in data_file_list:
    os.remove(d.file)



