#!/usr/bin/env python3
"""this script listenes for a shutdown command (3 second hold of power button)

it shuts down the pi if and only if there are no external drives mounted at /media/pi
when the shutdown button command is recieved.

Note: this script used to control LEDs, but that caused conflicts with other scripts controlling
LEDs so that functionality was removed.
"""

import subprocess
from datetime import datetime
from gpiozero import Button
from time import sleep
import os
from pathlib import Path

sleep_time = 0.1  # run loop 10x/sec
button_hold_time = 3  # require 3 second hold to shut down pi
power_button = Button(3, hold_time=3)


def shutdown():
    """attempts shutdown
    - if any external drives mounted, does not shutdown
    - returns True if shutdown happens, false otherwise"""
    # if any external drives are mounted, do not shut down
    # (/media/pi might not exist of no external drives!)
    if Path("/media/pi").exists():
        num_external_drives = len(os.listdir("/media/pi"))
    else:
        num_external_drives = 0

    if num_external_drives > 0:
        # do not shut down.
        # add event to the log.
        with open("/home/pi/shutdown_log.txt", "a+") as f:
            f.write(f"{datetime.now()}: Shutdown blocked due to mounted drives.\n")
            # don't continue checking and writing log until button is released
            while power_button.is_held:
                sleep(sleep_time)
        return False

    else:  # shutdown

        # write to log file
        with open("/home/pi/shutdown_log.txt", "a+") as f:
            f.write(f"{datetime.now()}: Shutting down.\n")

        # force shutdown
        subprocess.call(["sudo", "shutdown", "-h", "now"], shell=False)

        return True


shutting_down = False
while not shutting_down:
    sleep(sleep_time)
    if power_button.is_held:
        shutting_down = shutdown()
