###
touchlog.exe changes the timestamp of nest_data.log file. This executable is scheduled
to run at reboot in crontab -e. The watchdo timer monitors the timestamp of this log file.
Updating timestamp of log file at reboot prevents watchdog from entering an infinite reboot
loop if log file is out of date. 