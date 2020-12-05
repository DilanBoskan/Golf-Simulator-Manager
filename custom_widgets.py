from PySide2.QtCore import *
from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtUiTools import QUiLoader
import time
import datetime as dt
# Debugging
import traceback
import sys
# Plug Retriever
from tplinkcloud import TPLinkDeviceManager

# -Threads-


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


class KasaAppRetriever(QRunnable):
    '''
    Worker thread

    Paramaters:
        disable_widgets(list):
            List of widgets to be disabled when this
            thread runs
    '''

    def __init__(self, win: dict, disable_widgets: list = None, label_widget=None):
        super(KasaAppRetriever, self).__init__()
        self.win = win
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


class QWidgetDelegate(QStyledItemDelegate):
    def __init__(self, parent, station):
        super(QWidgetDelegate, self).__init__(parent)
        self.parent = parent
        self.station = station

    def createEditor(self, parent, option, index):
        """
        Create the editor widget for the table
        """
        if index.column() == 0:
            # Customer Name Column
            cellWidget = QLineEdit(parent=parent)
            cellWidget.setText(index.data())
            cellWidget.selectAll()
        else:
            # Time Column
            cellWidget = QTimeEdit(parent=parent)
            cellWidget.setTime(dt.datetime.strptime(index.data(), '%H:%M').time())

        cellWidget.setAlignment(Qt.AlignCenter)
        return cellWidget

    def destroyEditor(self, editor, index):
        """
        User exits out of edit mode
        """
        # -Check which option was edited and edit session accordingly-
        if index.column() == 0:
            key = 'new_customerName'
            value = index.data()
        elif index.column() == 1:
            key = 'new_start_date'
            value = editor.property('time').toPython()
        elif index.column() == 2:
            key = 'new_end_date'
            value = editor.property('time').toPython()
        elif index.column() == 3:
            key = 'new_duration'
            value = editor.property('time').toPython()
        
        if isinstance(value, dt.time):
            # Value is start or end date
            date_now = dt.date.today()
            value = dt.datetime.combine(date=date_now,
                                        time=editor.property('time').toPython())
        self.station.replace_session(self.station.rowTranslator[index.row()],
                                     **{key: value})
        # Destroy edit widget
        editor.destroy()


if __name__ == "__main__":
    # Testing
    username = 'boskan.dilan@gmail.com'
    password = 'dilan848k'

    device_manager = TPLinkDeviceManager(username, password)
    devices = device_manager.get_devices()
    if devices:
        for device in devices:
            print(d)
            print(f'{device.model_type.name} device called {device.get_alias()}')

# {
#     'stationName': 'TEST 1',
#     'plugID': 0,
# },
# {
#     'stationName': 'TEST 2',
#     'plugID': 1,
# },
# {
#     'stationName': 'TEST 3',
#     'plugID': 2,
# },
# {
#     'stationName': 'TEST 4',
#     'plugID': 3,
# },
# {
#     'stationName': 'TEST 5',
#     'plugID': 4,
# },
# {
#     'stationName': 'TEST 6',
#     'plugID': 5,
# },
# {
#     'stationName': 'TEST 7',
#     'plugID': 6,
# },
# {
#     'stationName': 'TEST 8',
#     'plugID': 7,
# },
# {
#     'stationName': 'TEST 9',
#     'plugID': 8,
# },
# {
#     'stationName': 'TEST 10',
#     'plugID': 9,
# },
# {
#     'stationName': 'TEST 11',
#     'plugID': 10,
# },
# {
#     'stationName': 'TEST 12',
#     'plugID': 11,
# },
# {
#     'stationName': 'TEST 13',
#     'plugID': 12,
# },
# {
#     'stationName': 'TEST 14',
#     'plugID': 13,
# },
# {
#     'stationName': 'TEST 15',
#     'plugID': 14,
# },
# {
#     'stationName': 'TEST 16',
#     'plugID': 15,
# },
# {
#     'stationName': 'TEST 17',
#     'plugID': 16,
# },
