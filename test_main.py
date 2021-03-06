"""
Test the application
"""
# pylint: disable=no-name-in-module
from src.classes import (Session)
from src import app
from PySide2.QtCore import (Slot)
import time
import datetime as dt
# Debugging
import sys
import traceback
NUM_DEVICES = 3  # MAX: 9
PRINT_STATE_CHANGE = False
DEVICE_0_HISTORY = [
    Session(customerName='Customer 1',
            start_date=dt.datetime.combine(dt.datetime.today() - dt.timedelta(days=10), dt.time(8, 00)),
            duration=dt.time(1, 0),
            ),
    Session(customerName='Customer 2',
            start_date=dt.datetime.combine(dt.datetime.today() - dt.timedelta(days=5), dt.time(8, 15)),
            duration=dt.time(1, 30),
            ),
    Session(customerName='Customer 3',
            start_date=dt.datetime.combine(dt.datetime.today() - dt.timedelta(days=3), dt.time(10, 00)),
            duration=dt.time(0, 30),
            ),
    Session(customerName='Customer 4',
            start_date=dt.datetime.combine(dt.datetime.today() - dt.timedelta(days=1), dt.time(10, 30)),
            duration=dt.time(1, 30),
            ),
    Session(customerName='Customer 5',
            start_date=dt.datetime.combine(dt.datetime.today() - dt.timedelta(days=1), dt.time(12, 15)),
            duration=dt.time(0, 45),
            ),
]
DEVICE_1_HISTORY = [
    Session(customerName='Customer 1',
            start_date=dt.datetime.combine(dt.datetime.today() - dt.timedelta(days=2), dt.time(9, 00)),
            duration=dt.time(1, 0),
            ),
    Session(customerName='Customer 2',
            start_date=dt.datetime.combine(dt.datetime.today() - dt.timedelta(days=1), dt.time(8, 15)),
            duration=dt.time(0, 30),
            ),
    Session(customerName='Customer 3',
            start_date=dt.datetime.combine(dt.datetime.today() - dt.timedelta(days=1), dt.time(10, 15)),
            duration=dt.time(1, 45),
            ),
    Session(customerName='Customer 4',
            start_date=dt.datetime.combine(dt.datetime.today() - dt.timedelta(days=1), dt.time(16, 15)),
            duration=dt.time(1, 30),
            ),
]
DEVICE_2_HISTORY = DEVICE_0_HISTORY.copy()


class HS100Device:
    def __init__(self, x):
        self.x = x

    def power_on(self):
        """Turn on device"""
        if PRINT_STATE_CHANGE:
            print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] Device {self.x}: ON")

    def power_off(self):
        """Turn on device"""
        if PRINT_STATE_CHANGE:
            print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] Device {self.x}: OFF")


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
    new_tracked_sessions = app.settingsManager.value('tracked_sessions')
    new_tracked_sessions[0] = DEVICE_0_HISTORY
    new_tracked_sessions[1] = DEVICE_1_HISTORY
    new_tracked_sessions[2] = DEVICE_2_HISTORY
    app.settingsManager.setValue('tracked_sessions', new_tracked_sessions)
    sys.exit(app.app.exec_())
