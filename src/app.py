"""
Main Application
"""
# pylint: disable=no-name-in-module, import-error
# -GUI-
from PySide2.QtCore import (Qt, QThreadPool, QRect, QMargins)
from PySide2.QtWidgets import (QApplication, QMainWindow, QMessageBox, QWidget,)
from PySide2.QtGui import (QPixmap, QPalette)
from PySide2.Qt3DCore import (Qt3DCore)
from PySide2.QtUiTools import QUiLoader
# -Root imports-
from .resources.resources_manager import ResourcePaths
from .data.data_manager import DataManager
from .gui_helper.classes import (QWidgetDelegate, EventHandler)
from .gui_helper.methods import reconnect
from .kasa.kasa_device import (DeviceRetriever, Device)
from .classes import (Station, Station_Tracker)
# -Other-
import os
import sys
from itertools import count
from collections import defaultdict
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
    base_path = sys._MEIPASS  # pylint: disable=no-member
else:
    base_path = os.path.dirname(os.path.abspath(__file__))
os.chdir(base_path)  # Change the current working directory to the base path

data_manager = DataManager(default_data={'username': '',
                                         'password': '',
                                         'window_geometries': {},
                                         'tracked_sessions': {}})
app: QApplication


class WindowManager:
    def __init__(self, windows):
        self.windows = windows
        # -Variables-
        self.threadpool = QThreadPool()
        self.eventHandler = EventHandler()
        self.gridOrder = [(0, 0),
                          (0, 1),
                          (1, 0),
                          (1, 1),
                          (0, 2),
                          (1, 2),
                          (2, 0),
                          (2, 1),
                          (2, 2),
                          #   (0, 3),
                          #   (1, 3),
                          #   (2, 3),
                          #   (3, 0),
                          #   (3, 1),
                          #   (3, 2),
                          #   (3, 3),
                          ]
        self.stationIDs = range(0, len(self.gridOrder))
        # -Setup-
        self.initialize_windows()
        self.initialize_threads()
        self.initialize_binds()
        self.initialize_widgets()
        # Key: stationID
        # Value: Station Class
        self.stations = {x: Station(self.windows, x) for x in self.stationIDs}

        # -Other-
        self.load_page_stations()
        # Search devices is username and password is stored
        if (self.device_retriever.username and
                self.device_retriever.password):
            self.search_for_devices()
        else:
            self._update_stations()
        # Show window
        self.windows['main'].show()
        # Focus window
        self.windows['main'].activateWindow()
        self.windows['main'].raise_()

        self.windows['main'].stackedWidget_mainContents.setStyleSheet("""QWidget[page="true"]{background-image:url(\"%s\"); background-position: center; background-origin: padding;}""" % ResourcePaths.images.golf_icon_png.replace('\\', '/'))  # nopep8

    # -Initialize methods-
    def initialize_windows(self):
        """
        Set up all windows for this application
        """
        # -Event Filter-
        for window in self.windows.values():
            window.installEventFilter(self.eventHandler)
        self.eventHandler.addFilter(Qt.Key_Return, self.clicked_login_connect, parent=self.windows['login'])
        self.eventHandler.addFilter(Qt.Key_Delete, self.keyPress_edit_deleteSession, parent=self.windows['edit'])
        # -Images-
        icon = QPixmap(ResourcePaths.images.refresh)
        self.windows['main'].pushButton_refresh.setIcon(icon)

        # -Load saved data-
        # Load account data
        self.windows['login'].lineEdit_email.setText(data_manager.data['username'])
        self.windows['login'].lineEdit_password.setText(data_manager.data['password'])

    def initialize_widgets(self):
        """Load all widgets for the main window"""
        stationTemplate_path = ResourcePaths.ui_files.stationQWidget
        statisticsTemplate_path = ResourcePaths.ui_files.statisticsQWidget

        # Load stations
        with open(stationTemplate_path) as station_ui:
            station_ui_lines = station_ui.read()
        with open(statisticsTemplate_path) as statistic_ui:
            statistic_ui_lines = statistic_ui.read()

        for i, stationID in enumerate(self.stationIDs):
            # Load station
            new_station_path = os.path.join(data_manager.save_folder, 'generated_ui_files', f'station_{stationID}.ui')
            new_station_ui = open(new_station_path, 'w')
            new_station_ui_lines = station_ui_lines.replace('_1">', f'_{stationID}">')
            new_station_ui_lines = new_station_ui_lines.replace('<class>frame_station_1</class>', f'<class>frame_station_{stationID}</class>')  # nopep8
            new_station_ui.write(new_station_ui_lines)
            new_station_ui.close()
            station = loader.load(new_station_path)
            # Load statistic
            new_statistic_path = os.path.join(data_manager.save_folder,
                                              'generated_ui_files', f'statistic_{stationID}.ui')
            new_statistic_ui = open(new_statistic_path, 'w')
            new_statistic_ui_lines = statistic_ui_lines.replace('_1">', f'_{stationID}">')
            new_statistic_ui_lines = new_statistic_ui_lines.replace('<class>frame_statistic_1</class>', f'<class>frame_statistic_{stationID}</class>')  # nopep8
            new_statistic_ui.write(new_statistic_ui_lines)
            new_statistic_ui.close()
            statistic = loader.load(new_statistic_path)

            self.windows['main'].gridLayout_page_stations.addWidget(station, self.gridOrder[i][0], self.gridOrder[i][1], 1, 1)  # nopep8
            self.windows['main'].gridLayout_page_statistics.addWidget(statistic, self.gridOrder[i][0], self.gridOrder[i][1], 1, 1)  # nopep8

    def initialize_threads(self):
        """
        Setup all threads used for this application
        """
        self.device_retriever = DeviceRetriever(parent=app,
                                                username=data_manager.data['username'],
                                                password=data_manager.data['password'],
                                                disable_widgets=[self.windows['main'].pushButton_refresh,
                                                                 self.windows['login'].pushButton_connect, ],
                                                label_widget=self.windows['main'].label_info)
        # Finished Signal
        reconnect(self.device_retriever.signals.finished, self._update_stations)  # nopep8
        # Error Signal
        reconnect(self.device_retriever.signals.error, self.show_error)  # nopep8

    def initialize_binds(self):
        """
        Bind the widgets to other methods
        """
        # -Main Window-
        reconnect(self.windows['main'].pushButton_login.clicked,
                  lambda *args: self.clicked_main_login())
        reconnect(self.windows['main'].pushButton_refresh.clicked,
                  lambda *args: self.search_for_devices())
        reconnect(self.windows['main'].pushButton_switch.clicked,
                  lambda *args: self.clicked_main_switchPage())

        # -Login Window-
        reconnect(self.windows['login'].pushButton_connect.clicked,
                  lambda *args: self.clicked_login_connect())

        # -Session Window-
        time_buttons = [self.windows['session'].pushButton_30m,
                        self.windows['session'].pushButton_1h,
                        self.windows['session'].pushButton_2h,
                        self.windows['session'].pushButton_3h, ]
        for button in time_buttons:
            reconnect(button.clicked,
                      lambda *args, wig=button: self.clicked_session_submit(wig.property('duration').toPython()))
        # Custom Button
        timeEdit_duration = self.windows['session'].timeEdit_duration
        reconnect(self.windows['session'].pushButton_custom.clicked,
                  lambda *args, wig=timeEdit_duration: self.clicked_session_submit(timeEdit_duration.property('time').toPython()))
        # Radio Buttons
        reconnect(self.windows['session'].radioButton_startAt.clicked,
                  lambda: self.windows['session'].timeEdit_startAt.setEnabled(True))
        reconnect(self.windows['session'].radioButton_append.clicked,
                  lambda: self.windows['session'].timeEdit_startAt.setEnabled(False))
        reconnect(self.windows['session'].radioButton_now.clicked,
                  lambda: self.windows['session'].timeEdit_startAt.setEnabled(False))

        # -Edit Window-

    def refresh(self):
        """
        Refresh all stations and statistics
        """
        for station in self.stations.values():
            station.refresh()
        self.update_stackedWidget_minimumSize()

    # -Page loads-
    def update_stackedWidget_minimumSize(self):
        """
        Update the minimum size of the stacked widget
        """
        stackedWidget = self.windows['main'].stackedWidget_mainContents
        # Get minimum size of currently laoded page
        curPage_minSize = stackedWidget.currentWidget().minimumSizeHint()
        # Set minimum size for stacked widget
        stackedWidget.setMinimumSize(curPage_minSize)

    def load_page_stations(self):
        """
        Load the stations page
        """
        # -Initialize-
        # Load page
        stackedWidget = self.windows['main'].stackedWidget_mainContents
        stackedWidget.setCurrentIndex(0)
        # Change switch button text
        self.windows['main'].pushButton_switch.setText('Statistics')
        # Other
        self.refresh()

    def load_page_statistics(self):
        """
        Load the statistics page
        """
        # -Initialize-
        # Load page
        stackedWidget = self.windows['main'].stackedWidget_mainContents
        stackedWidget.setCurrentIndex(1)
        # Change switch button text
        self.windows['main'].pushButton_switch.setText('Stations')

        # Other
        self.refresh()

    # -Button clicks-
    def clicked_main_switchPage(self):
        """
        Switch page between stations and statistics
        """
        stackedWidget = self.windows['main'].stackedWidget_mainContents
        # 0 -> Station page
        # 1 -> Statistics page
        page_index = stackedWidget.currentIndex()

        if page_index == 0:
            self.load_page_statistics()
        elif page_index == 1:
            self.load_page_stations()

    def clicked_main_login(self):
        """
        Open the login window to enter the
        kasa app account data
        """
        # -Window Setup-
        # Reshow window
        self.windows['login'].show()
        # Focus window
        self.windows['login'].activateWindow()
        self.windows['login'].raise_()

    def clicked_login_connect(self):
        """
        Confirm the entered email and password
        and fill the main window
        """
        self.device_retriever.username = self.windows['login'].lineEdit_email.text()
        self.device_retriever.password = self.windows['login'].lineEdit_password.text()

        if not self.search_for_devices():
            # User did not input any data
            return

        self.windows['login'].hide()

    def clicked_session_submit(self, duration: dt.time):
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
        # -Get Variables-
        stationID = self.windows['session'].property('stationID')
        customerName = self.windows['session'].lineEdit_customerName.text()
        # Get Start Date
        if self.windows['session'].radioButton_startAt.isChecked():
            timeEdit = self.windows['session'].timeEdit_startAt
            time = timeEdit.property('time').toPython()
            start_date = dt.datetime.combine(dt.date.today(), time)
        elif self.windows['session'].radioButton_now.isChecked():
            start_date = dt.datetime.now()
        elif self.windows['session'].radioButton_append.isChecked():
            start_date = None
        # -Add session to station-
        station = self.stations[stationID]
        success = station.add_session(customerName=customerName,
                                      start_date=start_date,
                                      duration=duration,)
        # -Close Window-
        if success:
            self.windows['session'].setProperty('stationID', -1)
            self.windows['session'].close()

    # -Key presses-
    def keyPress_edit_deleteSession(self):
        """
        Delete selected queues
        """
        # Find currently open station in edit window
        station = self.stations[self.windows['edit'].property('stationID')]
        # Perform deletion on selection
        station.delete_selection()

    def search_for_devices(self):
        """
        Refresh the main window by researching for
        devices and setting up the stations
        """
        if not (self.device_retriever.username and
                self.device_retriever.password):
            # No current device manager and username/password
            # was not changed
            msg = QMessageBox()
            msg.setWindowTitle('No Login Information')
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText('Please enter your login data for the Kasa App.')
            msg.setStandardButtons(QMessageBox.Ok)
            msg.setWindowFlag(Qt.WindowStaysOnTopHint)
            msg.exec_()
            return False
        self.threadpool.start(self.device_retriever)
        return True

    def _update_stations(self, devices: list = []):
        """
        Checks if all plugs are still connected, and adds new ones
        if there have been detected new plugs.

        Paramaters:
            devices(list):
                List of devices found
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
        devices = sorted(devices, key=lambda s: s.deviceName)
        for stationID, station in self.stations.items():
            if station.device:
                # Device is registered on this station
                deviceID_to_stationID[station.device.deviceID] = stationID

        for i, stationID in enumerate(self.stationIDs):
            station = self.stations[stationID]
            if i < len(devices):
                device = devices[i]
                try:
                    if deviceID_to_stationID[device.deviceID] == stationID:
                        # Station at the place same place as before update -> no need for action
                        # Update, in case the plug name was changed
                        new_data = {'device': device}
                    else:
                        raise KeyError('Plug at the same position')
                except KeyError:
                    # See if the plug already existed
                    try:
                        old_stationID = deviceID_to_stationID[device.deviceID]
                        new_data = self.stations[old_stationID].extract_data()
                    except KeyError:
                        # Plug is completely new
                        new_data = {'device': device,
                                    'state': 'deactivated',}
                if device.deviceID in data_manager.data['tracked_sessions'].keys():
                    new_data['tracked_sessions'] = data_manager.data['tracked_sessions'][device.deviceID]
                station.show(**new_data)
            else:
                station.reset(hide=True)

        self.refresh()

    def show_error(self, data):
        """
        Show the QMessagebox on this thread
        (Used for threads returning errors)
        """
        msg = QMessageBox()
        msg.setWindowFlag(Qt.WindowStaysOnTopHint)
        contact_creator = '\n\nPlease contact the creator and attach a screenshot of this error (+ expanded details)'

        if data['mode'] == 'untracked_connection_error':
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle('Untracked Connection Error')
            msg.setText(data['message'][0] + contact_creator)
            msg.setDetailedText(data['message'][1])
            msg.setStandardButtons(QMessageBox.Ok)
        elif data['mode'] == 'invalid_login_data':
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle('Invalid Login Data')
            msg.setText('Invalid username and/or password!')
            msg.setStandardButtons(QMessageBox.Ok)
        else:
            msg.setText(f'Invalid Error mode!' + contact_creator)
            msg.setDetailedText(repr(data))
        msg.exec_()


@atexit.register
def closeEvent():
    """Run this method before closing the application"""
    # Turn off all plugs
    if 'winManager' in globals():
        for station in winManager.stations.values():
            if station.device is not None:
                # Turn off device
                station.device._device.power_off()
                # Save history by deviceID
                deviceID = station.device.deviceID
                data_manager.data['tracked_sessions'][deviceID] = station.sessionHistoryTracker.tracked_sessions

        for win_name, window in winManager.windows.items():
            geometry = window.saveGeometry()
            data_manager.data['window_geometries'][win_name] = geometry
    data_manager.save_data()


def load_windows() -> dict:
    """
    Load all windows of this application and return
    a dictionary with their instances
    """
    def load_geometries():
        """Load saved geometries"""
        for win_name, window in windows.items():
            if win_name in data_manager.data['window_geometries']:
                # Geometry saved -> load saved geometry
                geometry = data_manager.data['window_geometries'][win_name]
                window.restoreGeometry(geometry)
            else:
                # Geometry not saved -> center window
                geometry = window.geometry()
                screen = app.desktop().screenNumber(app.desktop().cursor().pos())
                centerPoint = app.desktop().screenGeometry(screen).center()
                geometry.moveCenter(centerPoint)
                window.move(geometry.topLeft())

    global loader
    loader = QUiLoader()
    window_paths = {'main': ResourcePaths.ui_files.mainwindow,
                    'login': ResourcePaths.ui_files.loginwindow,
                    'session': ResourcePaths.ui_files.sessionwindow,
                    'edit': ResourcePaths.ui_files.editwindow,
                    'history': ResourcePaths.ui_files.historywindow,
                    }
    windows = {}
    for win_name, path in window_paths.items():
        window = loader.load(path, None)
        if win_name != 'main':
            # Window is not main
            window.setWindowFlag(Qt.WindowStaysOnTopHint)
        windows[win_name] = window
    load_geometries()

    return windows


def run():
    """Start the application\n
    Run 'sys.exit(app.exec_())' after this method has been called
    """
    global app
    global winManager
    app = QApplication
    # Application settings here...
    app = app(sys.argv)
    windows = load_windows()
    # Create Manager
    winManager = WindowManager(windows)
