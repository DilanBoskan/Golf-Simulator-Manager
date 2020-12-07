"""
Main Application
"""
# -GUI-
from PySide2.QtCore import *
from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtUiTools import QUiLoader
# -Root imports-
from resources.resources_manager import ResourcePaths
from data.data_manager import DataManager
from gui_helper.classes import (QWidgetDelegate, EventHandler)
from gui_helper.methods import reconnect
from kasa.kasa_device import (DeviceRetriever, Device)
from classes import Station
import constants as const
# ! Make device retriever return 'Device' classes
# -Other-
import os
import sys
from itertools import count
# Timer logic
import datetime as dt

# Saving
import atexit

# Change the current working directory to the directory
# this file sits in
if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the PyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))
os.chdir(base_path)  # Change the current working directory to the base path


data_manager = DataManager(default_data={'username': None,
                                         'password': None,
                                         'data': {}})


class WindowManager:
    def __init__(self):
        global windows
        # -Variables-
        self.stationIDs = [x for x in range(1, 9 + 1, 1)]
        self.load_stations()
        self.setup_windows()
        self.setup_threads()
        # Key: stationID
        # Value: Station Class
        self.all_stations = {x: Station(windows, x) for x in self.stationIDs}
        # Update login data
        self.device_retriever.username = data_manager.data['username']
        self.device_retriever.password = data_manager.data['password']
        # -Setup-
        self.bind_widgets()

        # -Other-
        self.update_stations()
        windows['main'].show()
        if (self.device_retriever.username and
                self.device_retriever.password):
            self.search_for_devices()

    def load_stations(self):
        """Load all stations for the main window"""
        global windows
        # ! Check if station file has been already created
        # ! Beware what if station 1 is updated, the rest will not be updated!
        stationTemplate_path = ResourcePaths.ui_files.stationQWidget
        self.gridOrder = [
            (0, 0),
            (0, 1),
            (1, 0),
            (1, 1),
            (0, 2),
            (1, 2),
            (2, 0),
            (2, 1),
            (2, 2),
            (0, 3),
            (1, 3),
            (2, 3),
            (3, 0),
            (3, 1),
            (3, 2),
            (3, 3),
        ]

        with open(stationTemplate_path) as station_ui:
            station_ui_lines = station_ui.read()
            for i, stationID in enumerate(self.stationIDs):
                new_station_path = os.path.join(data_manager.save_folder, f'station_{stationID}.ui')
                new_station_ui = open(new_station_path, 'w')
                new_station_ui_lines = station_ui_lines.replace('_1">', f'_{stationID}">')
                new_station_ui_lines = new_station_ui_lines.replace('<class>frame_station_1</class>', f'<class>frame_station_{stationID}</class>')  # nopep8
                new_station_ui.write(new_station_ui_lines)
                new_station_ui.close()

                station = loader.load(new_station_path)
                windows['main'].gridLayout_page_1.addWidget(station, self.gridOrder[i][0], self.gridOrder[i][1], 1, 1)

    def bind_widgets(self):
        """
        Bind the widgets to other methods
        """
        global windows
        # -Main Window-
        reconnect(windows['main'].pushButton_login.clicked,
                  lambda *args: self.main_clicked_login())
        reconnect(windows['main'].pushButton_refresh.clicked,
                  lambda *args: self.search_for_devices())

        # -Login Window-
        reconnect(windows['login'].pushButton_connect.clicked,
                  lambda *args: self.login_clicked_connect())

        # -Session Window-
        time_buttons = [windows['session'].pushButton_30m,
                        windows['session'].pushButton_1h,
                        windows['session'].pushButton_2h,
                        windows['session'].pushButton_3h, ]
        for button in time_buttons:
            reconnect(button.clicked,
                      lambda *args, wig=button: self.session_clicked_start(wig.property('duration').toPython()))
        # Custom Button
        timeEdit_duration = windows['session'].timeEdit_duration
        reconnect(windows['session'].pushButton_custom.clicked,
                  lambda *args, wig=timeEdit_duration: self.session_clicked_start(timeEdit_duration.property('time').toPython()))
        # Radio Buttons
        reconnect(windows['session'].radioButton_startAt.clicked,
                  lambda: windows['session'].timeEdit_startAt.setEnabled(True))
        reconnect(windows['session'].radioButton_append.clicked,
                  lambda: windows['session'].timeEdit_startAt.setEnabled(False))
        reconnect(windows['session'].radioButton_now.clicked,
                  lambda: windows['session'].timeEdit_startAt.setEnabled(False))

        # -Edit Window-

    def setup_windows(self):
        """
        Set up all windows for this application
        """
        global windows
        # -Event Filter-
        eventHandler.addFilter(Qt.Key_Return, self.login_clicked_connect, parent=windows['login'])
        eventHandler.addFilter(Qt.Key_Delete, self.edit_pressed_delete, parent=windows['edit'])
        # -Images-
        icon = QPixmap(ResourcePaths.images.refresh)
        windows['main'].pushButton_refresh.setIcon(icon)

    def setup_threads(self):
        """
        Setup all threads used for this application
        """
        global windows
        self.device_retriever = DeviceRetriever(disable_widgets=[windows['main'].pushButton_refresh,
                                                                 windows['login'].pushButton_connect,
                                                                 ],
                                                label_widget=windows['main'].label_info)
        # Finished Signal
        reconnect(self.device_retriever.signals.finished, self.update_stations)  # nopep8
        reconnect(self.device_retriever.signals.finished, self.update_stations)  # nopep8
        # Error Signal
        reconnect(self.device_retriever.signals.error, self.show_error)  # nopep8

    def update_stations(self, devices: list = []):
        """
        This method has to be called in a loop.\n
        Checks if all plugs are still connected, and adds new ones
        if there have been detected new plugs.

        Paramaters:
            devices(list):
                List of dictionaries for each device, holding two values:
                    1. device_name
                    2. device
        """
        if not devices:
            # No device registered on account (or no devices on remote control)
            pass
        else:
            # Save Login Data
            data_manager.data = {'username': self.device_retriever.username,
                                 'password': self.device_retriever.password}
        # Retrieve deviceIDs for each station
        deviceID_to_stationID = {}
        # Sort devices by name
        devices = sorted(devices, key=lambda s: s['device_name'])
        for stationID, station in self.all_stations.items():
            if station.device:
                # Device is registered on this station
                deviceID_to_stationID[station.device.deviceID] = stationID

        for i, stationID in enumerate(self.stationIDs):
            station = self.all_stations[stationID]
            if i < len(devices):
                device = Device(parent=app,
                                device=devices[i]['device'])
                device_name = devices[i]['device_name']
                try:
                    if deviceID_to_stationID[device.deviceID] == stationID:
                        # Station at the place same place as before update -> no need for action
                        # Update, in case the plug name was changed
                        new_data = {'device_name': device_name,
                                    'device': device}
                    else:
                        raise KeyError('Plug at the same position')
                except KeyError:
                    # See if the plug already existed
                    try:
                        old_stationID = deviceID_to_stationID[device.deviceID]
                        new_data = self.all_stations[old_stationID].extract_data()
                    except KeyError:
                        # Plug is completely new
                        new_data = {'device_name': device_name,
                                    'device': device,
                                    'state': 'deactivated',
                                    }

                station.show(**new_data)
            else:
                station.reset(hide=True)

        # -Detect disconnected plugs-
        # disconnected_stations = []
        # plugIDs = [device['plugID'] for device in devices]
        # for stationID, station_data in prev_station_data.items():
        #     print(station_data)
        #     if station_data['plugID'] in plugIDs:
        #         plugIDs.remove(station_data['plugID'])
        #     else:
        #         disconnected_stations.append(stationID)

        # for stationID in disconnected_stations:
        #     self.updateState_station(stationID=stationID,
        #                             state='disconnected')

    def main_clicked_edit(self, stationID: int):
        """
        Edit the current session
            (Feature request: View all current sessions pending,
             and be able to edit them)

        Paramaters:
            stationID(int):
                Identifier for the station
        """
        global windows
        # -Window SetUp-
        # Re-create window
        windows['edit'] = loader.load(window_paths['edit'], None)
        # Bind Widgets in this window

        # Show window
        windows['edit'].show()

    def main_clicked_login(self):
        """
        Open the login window to enter the
        kasa app account data
        """
        global windows
        # -Window Setup-
        # Load account data
        windows['login'].lineEdit_email.setText(self.device_retriever.username)
        windows['login'].lineEdit_password.setText(self.device_retriever.password)
        # Reshow window
        windows['login'].hide()
        windows['login'].setWindowFlag(Qt.WindowStaysOnTopHint)
        windows['login'].show()

    def edit_pressed_delete(self):
        """
        Delete selected queues
        """
        global windows
        widget = windows['edit'].tableWidget_queue
        selection = widget.selectionModel().selectedRows()
        station = self.all_stations[windows['edit'].property('stationID')]
        station.editWindow_deleteSelection(selection)

    def search_for_devices(self):
        """
        This method has to be called in a loop.\n

        Refresh the main window by researching for
        devices and setting up the stations
        """
        if not (self.device_retriever.username and
                self.device_retriever.password):
            # No current device manager and username/password
            # was not changed
            global windows
            msg = QMessageBox()
            msg.setWindowTitle('No Login Information')
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText('Please enter your login data for the Kasa App.')
            msg.setStandardButtons(QMessageBox.Ok)
            msg.setWindowFlag(Qt.WindowStaysOnTopHint)
            msg.exec_()
            return

        threadpool.start(self.device_retriever)

    # Login Window
    def login_clicked_connect(self):
        """
        Confirm the entered email and password
        and fill the main window
        """
        global windows
        self.device_retriever.username = windows['login'].lineEdit_email.text()
        self.device_retriever.password = windows['login'].lineEdit_password.text()

        self.search_for_devices()

        windows['login'].hide()

    # New Session Window
    def session_clicked_start(self, duration: dt.time):
        """
        Create a session which will either be appended to
        the currently running session or start immediately,
        based on the mode.

        Paramaters:
            stationID(int):
                Identifier for the station
            customerName(str):
                Name of customer for this session
            startDate(dt.datetime or None):
                If None, the End Time of the last queue item will be taken
            duration(dt.time):
                Time length of the session
        """
        global windows
        # -Get Variables-
        stationID = windows['session'].property('stationID')
        customerName = windows['session'].lineEdit_customerName.text()
        # Get Start Date
        if windows['session'].radioButton_startAt.isChecked():
            timeEdit = windows['session'].timeEdit_startAt
            time = timeEdit.property('time').toPython()
            start_date = dt.datetime.combine(dt.date.today(), time)
        elif windows['session'].radioButton_now.isChecked():
            start_date = dt.datetime.now()
        elif windows['session'].radioButton_append.isChecked():
            start_date = None
        # -Add session to station-
        station = self.all_stations[stationID]
        success = station.add_session(customerName=customerName,
                                      start_date=start_date,
                                      duration=duration,)
        # -Close Window-
        if success:
            windows['session'].setProperty('stationID', -1)
            windows['session'].close()

    def show_error(self, data):
        """
        Show the QMessagebox on this thread
        (Used for threads returning errors)
        """
        global windows
        msg = QMessageBox()
        msg.setWindowFlag(Qt.WindowStaysOnTopHint)

        if data['mode'] == 'untracked_connection_error':
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle('Untracked Connection Error')
            msg.setText(data['message'][0] +
                        '\n\nPlease contact the creator and attach a screenshot of this error (+ details)')
            msg.setDetailedText(data['message'][1])
            msg.setStandardButtons(QMessageBox.Ok)
        elif data['mode'] == 'invalid_login_data':
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle('Invalid Login Data')
            msg.setText('Invalid username and/or password!')
            msg.setStandardButtons(QMessageBox.Ok)
        else:
            msg.setText(f'Invalid Error mode!{contact_creator_text}')
            msg.setDetailedText(repr(data))
        msg.exec_()


@atexit.register
def closeEvent():
    """Run this method before closing the application"""
    # Turn off all plugs
    if 'winManager' in globals():
        for station in winManager.all_stations.values():
            if station.device._device is not None:
                station.device._device.power_off()

def load_windows() -> dict:
    """
    Load all windows of this application and return
    a dictionary with their instances
    """
    global loader
    loader = QUiLoader()
    window_paths = {'main': ResourcePaths.ui_files.mainwindow,
                    'login': ResourcePaths.ui_files.loginwindow,
                    'session': ResourcePaths.ui_files.sessionwindow,
                    'edit': ResourcePaths.ui_files.editwindow,
                    }
    windows = {}
    for key, path in window_paths.items():
        windows[key] = loader.load(path, None)
        windows[key].installEventFilter(eventHandler)
    
    return windows

if __name__ == "__main__":
    app = QApplication
    # Application settings here...
    app = app(sys.argv)
    threadpool = QThreadPool()
    eventHandler = EventHandler()
    windows = load_windows()
    # Create Manager
    winManager = WindowManager()
    # Create stations
    sys.exit(app.exec_())
