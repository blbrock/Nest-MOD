import time
import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BOARD)
GPIO.setup(13, GPIO.OUT)
GPIO.setup(16, GPIO.OUT)
GPIO.setup(18, GPIO.OUT)
GPIO.output(13, True)
GPIO.output(16, True)
GPIO.output(18, True)



i = 50

while i < 50:
    time.sleep(0.5)
    GPIO.output(11,True)
