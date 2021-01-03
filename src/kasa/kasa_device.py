"""
Classes associated with TP-Link
"""
# pylint: disable=no-name-in-module, import-error
# -GUI-
from PySide2.QtCore import (QRunnable, QThread, QObject, Signal, Slot)
from PySide2.QtWidgets import (QApplication, QLabel)
# -Other-
# TP-Link
from tplinkcloud import (hs100, TPLinkDeviceManager)
# Debugging
import traceback
import sys


class WorkerSignals(QObject):
    '''
    Defines the signals available from a running worker thread.

    Supported signals are:

    finished
        No data

    error
        `tuple` (exctype, value, traceback.format_exc() )

    result
        `object` data returned from processing, anything

    '''
    finished = Signal(object)
    error = Signal(dict)


class DeviceRetriever(QRunnable):
    '''
    Worker thread

    Paramaters:
        disable_widgets(list):
            List of widgets to be disabled when this
            thread runs
        label_widget:
            List of widgets to be disabled when this
            thread runs
    '''

    def __init__(self, parent: QApplication, settingsManager, disable_widgets: list = None, label_widget: QLabel = None):
        super(DeviceRetriever, self).__init__()
        self.parent = parent
        self.signals = WorkerSignals()
        self.disable_widgets = disable_widgets
        self.label_widget = label_widget
        self.device_manager = None
        self.setAutoDelete(False)

    @Slot()
    def run(self):
        """
        Connect to the Kasa app and extract all available
        devices
        """
        devices = []
        try:
            # Disable widgets
            if self.label_widget:
                self.label_widget.setText('Searching for devices...')
            for widget in self.disable_widgets:
                widget.setEnabled(False)

            device_manager = TPLinkDeviceManager(settingsManager.value('username'),
                                                 settingsManager.value('password'))
            if device_manager._auth_token is not None:
                # Valid username or password
                found_devices = device_manager.get_devices()
                for found_device in found_devices:
                    # Create device instance
                    device = Device(device=found_device,
                                    deviceID=found_device.device_id,
                                    deviceName=found_device.get_alias())
                    # Append devices to the devices list
                    devices.append(device)
            else:
                # Invalid username or password
                self.signals.error.emit({'mode': 'invalid_login_data'})
            # Enable widgets
            if self.label_widget:
                self.label_widget.setText('')
            for widget in self.disable_widgets:
                widget.setEnabled(True)
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


class Device:
    def __init__(self, device: hs100.HS100, deviceID: str, deviceName: str):
        # -Variables-
        self._device = device
        self.state = 0
        self.deviceID = deviceID
        self.deviceName = deviceName
        # Set threads
        self._turn_on = QThread()
        self._turn_off = QThread()
        self._turn_on.run = self._device.power_on
        self._turn_off.run = self._device.power_off
        self.refresh()

    def refresh(self):
        """
        Refresh the data of this station:
            - Update state
        """
        if self._device is None:
            return
        pass

    def turn_on(self):
        """Turn on the device"""
        self._turn_on.start()

    def turn_off(self):
        """Turn off the device"""
        self._turn_off.start()
