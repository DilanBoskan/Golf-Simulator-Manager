"""
Test the application
"""
from src import app
from PySide2.QtCore import (Slot)
import time
import datetime
# Debugging
import sys
import traceback
NUM_DEVICES = 7
PRINT_STATE_CHANGE = False


class HS100Device:
    def __init__(self, x):
        self.x = x

    def power_on(self):
        """Turn on device"""
        if PRINT_STATE_CHANGE:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Device {self.x}: ON")

    def power_off(self):
        """Turn on device"""
        if PRINT_STATE_CHANGE:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Device {self.x}: OFF")


@Slot()
def run(self):
    """
    New Device Retriever
    """
    devices = []
    try:
        for x in range(NUM_DEVICES):
            devices.append(app.Device(device=HS100Device(x),
                                      deviceID=x,
                                      deviceName=f'Device {x}'))
    except:
        # Get Variables
        value, the_traceback = sys.exc_info()[1:]
        traceback_text = ''.join(traceback.format_tb(the_traceback))
        # Create a messagebox to inform the user
        # of an occured error
        self.signals.error.emit({'mode': 'untracked_connection_error',
                                 'message': [str(value), traceback_text]})
        return
    finally:
        self.signals.finished.emit(devices)  # Done
        return


if __name__ == "__main__":
    setattr(app.DeviceRetriever, 'run', run)
    app.run()