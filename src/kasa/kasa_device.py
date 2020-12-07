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

    def __init__(self, disable_widgets: list = None, label_widget: QLabel = None):
        super(DeviceRetriever, self).__init__()
        self.signals = WorkerSignals()
        self.disable_widgets = disable_widgets
        self.label_widget = label_widget
        self.device_manager = None
        self.setAutoDelete(False)

        self.username = None
        self.password = None

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

            device_manager = TPLinkDeviceManager(self.username, self.password)
            if device_manager._auth_token is not None:
                # Valid username or password
                found_devices = device_manager.get_devices()
                for found_device in found_devices:
                    # Append devices to the devices list
                    devices.append({'device_name': found_device.get_alias(),
                                    'device': found_device})
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
    def __init__(self, parent: QApplication = None, device: hs100.HS100 = None):
        self.parent = parent
        # -Variables-
        self._device = device
        if self._device is None:
            self.deviceID = -1
            self.state = None
            self.deviceName = ''
        else:
            self.deviceID = self._device.device_id
            self.state = 0
            self.deviceName = ''
            # Set threads
            self._turn_on = QThread(self.parent)
            self._turn_off = QThread(self.parent)
            self._turn_on.run = self._device.power_on
            self._turn_off.run = self._device.power_off
        self.refresh()

    def refresh(self):
        """
        Refresh the data of this station:
            - Update device name
            - Update state
        """
        if self._device is None:
            return
        self._update_deviceName()

    def turn_on(self):
        """Turn on the device"""
        if self._device is None:
            return
        self._turn_on.start()

    def turn_off(self):
        """Turn off the device"""
        if self._device is None:
            return
        self._turn_off.start()

    def _update_deviceName(self, callback=None):
        """
        Update the device name
        """
        if self._device is None:
            return
        self._set_deviceName('Test Device Name')

    def _set_deviceName(self, value: str):
        assert isinstance(value, str), "deviceName has to be str"
        self.deviceName = value
