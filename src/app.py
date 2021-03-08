"""
Main Application
"""
# pylint: disable=no-name-in-module, import-error
# -GUI-
from PySide2.QtCore import (Qt, QThreadPool, QSize, QDir)
from PySide2.QtWidgets import (QApplication, QMainWindow, QMessageBox, QWidget, QPushButton, QFileDialog)
from PySide2.QtGui import (QPixmap, QPalette)
from PySide2.QtUiTools import QUiLoader
# -Root imports-
from .resources.resources_manager import ResourcePaths
from .data.data_manager import DataManager
from .gui_helper.classes import (EventHandler)
from .gui_helper.methods import reconnect
from .kasa.kasa_device import (DeviceRetriever, Device)
from .classes import (Station)
# -Other-
import os
import sys
from itertools import count
from itertools import cycle
from collections import defaultdict
import subprocess  # Restarting application
# Timer logic
import datetime as dt
# Excel file writing
import xlsxwriter
# Code annotation
from typing import (Dict, Union)

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

settingsManager = DataManager(default_data={'username': '',
                                            'password': '',
                                            'window_geometries': {},
                                            'tracked_sessions': {},
                                            'settings': {
                                                'saveLogin': True,
                                            },
                                            'lastExportDir': QDir.homePath(),
                                            })
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
                          #   (3, 3), 16 Stations
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
        self.deviceID_to_stationID = {}

        # -Other-
        self.load_page_stations()
        # Search devices is username and password is stored
        if (settingsManager.value('username') and
                settingsManager.value('password')):
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
        # Refresh
        icon = QPixmap(ResourcePaths.images.refresh)
        self.windows['main'].pushButton_refresh.setIcon(icon)
        # Settings
        icon = QPixmap(ResourcePaths.images.settings)
        self.windows['main'].pushButton_settings.setIcon(icon)
        self.windows['main'].pushButton_settings.setIconSize(QSize(18, 18))

        # -Load saved data-
        if settingsManager.value('settings')['saveLogin']:
            # Load account data
            self.windows['login'].lineEdit_email.setText(settingsManager.value('username'))
            self.windows['login'].lineEdit_password.setText(settingsManager.value('password'))

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
            new_station_path = os.path.join(settingsManager.save_folder,
                                            'generated_ui_files', f'station_{stationID}.ui')
            new_station_ui = open(new_station_path, 'w')
            new_station_ui_lines = station_ui_lines.replace('_1">', f'_{stationID}">')
            new_station_ui_lines = new_station_ui_lines.replace('<class>frame_station_1</class>', f'<class>frame_station_{stationID}</class>')  # nopep8
            new_station_ui.write(new_station_ui_lines)
            new_station_ui.close()
            station = loader.load(new_station_path)
            # Load statistic
            new_statistic_path = os.path.join(settingsManager.save_folder,
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
                                                settingsManager=settingsManager,
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
                  lambda *args: self.clicked_main_openLoginWindow())
        reconnect(self.windows['main'].pushButton_refresh.clicked,
                  lambda *args: self.search_for_devices())
        reconnect(self.windows['main'].pushButton_switch.clicked,
                  lambda *args: self.clicked_main_switchPage())
        reconnect(self.windows['main'].pushButton_settings.clicked,
                  lambda *args: self.clicked_main_openSettingsWindow())

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
                      lambda *args, wig=button: self.clicked_session_createNewSession(wig.property('duration').toPython()))
        # Custom Button
        timeEdit_duration = self.windows['session'].timeEdit_duration
        reconnect(self.windows['session'].pushButton_custom.clicked,
                  lambda *args, wig=timeEdit_duration: self.clicked_session_createNewSession(timeEdit_duration.property('time').toPython()))
        # Radio Buttons
        reconnect(self.windows['session'].radioButton_startAt.clicked,
                  lambda: self.windows['session'].timeEdit_startAt.setEnabled(True))
        reconnect(self.windows['session'].radioButton_append.clicked,
                  lambda: self.windows['session'].timeEdit_startAt.setEnabled(False))
        reconnect(self.windows['session'].radioButton_now.clicked,
                  lambda: self.windows['session'].timeEdit_startAt.setEnabled(False))

        # -Settings Window-
        reconnect(self.windows['settings'].pushButton_apply.clicked,
                  lambda *args: self.clicked_settings_applySettings())
        reconnect(self.windows['settings'].pushButton_resetAll.clicked,
                  lambda *args: self.clicked_settings_resetAllSettings())
        reconnect(self.windows['settings'].pushButton_export.clicked,
                  lambda *args: self.clicked_settings_export())

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

    def clicked_main_openLoginWindow(self):
        """
        Open the login window to enter the
        kasa app account data
        """
        if not settingsManager.value('settings')['saveLogin']:
            # Do not save login information, so
            # clear previously typed data
            self.windows['login'].lineEdit_email.setText('')
            self.windows['login'].lineEdit_password.setText('')
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
        settingsManager.setValue('username', self.windows['login'].lineEdit_email.text())
        settingsManager.setValue('password', self.windows['login'].lineEdit_password.text())

        if not self.search_for_devices():
            # User did not input any data
            return

        self.windows['login'].close()

    def clicked_main_openSettingsWindow(self):
        """
        Open the settings window
        """
        # -Load data-
        settings = settingsManager.value('settings')
        # Get states
        saveLoginCheckedState = Qt.CheckState.Checked if settings['saveLogin'] else Qt.CheckState.Unchecked
        # Update window
        self.windows['settings'].checkBox_saveLogin.setCheckState(saveLoginCheckedState)

        # -Window Setup-
        # Reshow window
        self.windows['settings'].show()
        # Focus window
        self.windows['settings'].activateWindow()
        self.windows['settings'].raise_()

    def clicked_session_createNewSession(self, duration: dt.time):
        """
        Create a session which will either be appended to
        the currently running session or start immediately,
        based on the mode.

        Paramaters:
            duration(dt.time):
                Time length of the session
        """
        # -Get Variables-
        stationID = self.windows['session'].property('stationID')
        customerName = self.windows['session'].lineEdit_customerName.text()
        start_date: Union[dt.datetime, None]
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

    def clicked_settings_applySettings(self):
        """
        Apply the settings entered by the user
        """
        saveLogin = self.windows['settings'].checkBox_saveLogin.isChecked()

        # Update data
        settingsManager.setValue('settings', {
            'saveLogin': saveLogin
        })
        # Close window
        self.windows['settings'].close()

    def clicked_settings_resetAllSettings(self):
        """
        Apply the settings entered by the user
        """
        msg = QMessageBox()
        msg.setWindowTitle('Confirmation')
        msg.setIcon(QMessageBox.Icon.Warning)
        messageBoxText = 'Resetting the application will:\n'
        messageBoxText += '  - Clear all data gathered on customer sessions.\n'
        messageBoxText += '  - Delete the saved login information and window positions.\n'
        messageBoxText += '  - Return to the default settings.\n'
        messageBoxText += 'This action is unrecoverable and will restart the application.'
        msg.setText(messageBoxText)  # nopep8
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        msg.setWindowFlag(Qt.WindowStaysOnTopHint)
        val = msg.exec_()
        if val == QMessageBox.Cancel:
            # Cancel operation
            return

        self.reset_application()

    def clicked_settings_export(self):
        """Export session history"""
        collected_histories: Dict[str, Station] = {}
        for station in self.stations.values():
            sessionTracker_data = station.sessionTracker.extract_data()
            if (sessionTracker_data is None or
                    not sessionTracker_data['tracked_sessions']):
                # No device registered for this station
                # OR no tracked sessions
                continue
            collected_histories[sessionTracker_data['deviceID']] = sessionTracker_data['tracked_sessions']
        # -Get save path-
        defaultName = 'SessionHistoryExport_%s' % dt.datetime.now().strftime(r'%d-%m-%Y')
        filepath = QFileDialog.getSaveFileName(parent=self.windows['settings'],
                                               caption='Save File',
                                               dir=os.path.join(settingsManager.value('lastExportDir'), defaultName),
                                               filter="Excel file (*.xlsx)",
                                               )[0]
        if not filepath:
            # No name specified
            return
        settingsManager.setValue('lastExportDir', os.path.dirname(filepath))
        # --Write to excel file--
        # Create a workbook and add a worksheet.
        workbook = xlsxwriter.Workbook(filepath)
        worksheet = workbook.add_worksheet()
        # -Create style-
        # Cell width and heights
        worksheet.set_column(0, 0, 30)
        worksheet.set_column(1, 1, 15)
        worksheet.set_column(2, 2, 20)
        worksheet.set_column(3, 5, 13.57)
        worksheet.set_column(6, 6, 50)
        worksheet.set_row(0, 30)
        worksheet.set_default_row(18.75)
        # Cell styles
        title_format = workbook.add_format()
        formats_1 = {
            'default': workbook.add_format(),
            'date': workbook.add_format(),
            'time': workbook.add_format(),
            'mergedCell': workbook.add_format(),
        }
        formats_2 = {
            'default': workbook.add_format(),
            'date': workbook.add_format(),
            'time': workbook.add_format(),
            'mergedCell': workbook.add_format(),
        }
        formatCycle = cycle([formats_1, formats_2])
        # ALignement
        title_format.set_align('center')
        title_format.set_align('vcenter')
        for format_1 in formats_1.values():
            format_1.set_align('center')
            format_1.set_align('vcenter')
            format_1.set_bg_color('#FFFFFF')
        for format_2 in formats_2.values():
            format_2.set_align('center')
            format_2.set_align('vcenter')
            format_2.set_bg_color('#DCE6F1')
        # Font
        title_format.set_font_size(12)
        # Borders
        title_format.set_bottom()
        # Cell backgrounds
        title_format.set_bg_color('#DCE6F1')
        # Format
        formats_1['date'].set_num_format('dd.mm.yyyy')
        formats_2['date'].set_num_format('dd.mm.yyyy')
        formats_1['time'].set_num_format('HH:MM')
        formats_2['time'].set_num_format('HH:MM')
        # -Cell Texts-
        # Titles
        titles = ['Device Name', 'Date', 'Customer Name', 'Session Start', 'Session End', 'Duration', 'Device ID']
        for col, title in enumerate(titles):
            worksheet.write(0, col, title, title_format)
        # Content
        row = 1
        for deviceID, tracked_sessions in collected_histories.items():
            # -Device Name-
            formats = next(formatCycle)
            station = self.stations[self.deviceID_to_stationID[deviceID]]
            deviceName = station.device.deviceName
            if len(tracked_sessions) > 1:
                # Merge deviceID cells
                worksheet.merge_range('A%s:A%s' % ((row + 1), (row + 1) + len(tracked_sessions) - 1),
                                      deviceName, formats['mergedCell'])
                worksheet.merge_range('G%s:G%s' % ((row + 1), (row + 1) + len(tracked_sessions) - 1),
                                      deviceID, formats['mergedCell'])
            else:
                # Cant merge one cell
                worksheet.write(row, 0, deviceName, formats['mergedCell'])
                worksheet.write(row, 6, deviceID, formats['mergedCell'])
            # -Device ID-
            # -Session Data-
            for tracked_session in tracked_sessions:
                worksheet.write(row, 1, tracked_session.start_date, formats['date'])
                worksheet.write(row, 2, tracked_session.customerName, formats['default'])
                worksheet.write(row, 3, tracked_session.start_date, formats['time'])
                worksheet.write(row, 4, tracked_session.end_date, formats['time'])
                worksheet.write(row, 5, tracked_session.duration, formats['time'])
                row += 1
        workbook.close()

        # TEMP
        subprocess.Popen(filepath, shell=True)

    # -Key presses-
    def keyPress_edit_deleteSession(self):
        """
        Delete selected queues
        """
        # Find currently open station in edit window
        station = self.stations[self.windows['edit'].property('stationID')]
        # Perform deletion on selection
        station.delete_selection()

    def reset_application(self):
        """Delete data file and restart the application"""
        del settingsManager.data
        os.execl(sys.executable, sys.executable, *sys.argv)

    def search_for_devices(self):
        """
        Refresh the main window by researching for
        devices and setting up the stations
        """
        if not (settingsManager.value('username') and
                settingsManager.value('password')):
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
        # Sort devices by name
        devices = sorted(devices, key=lambda s: s.deviceName)
        tracked_sessions = settingsManager.value('tracked_sessions')
        for i, stationID in enumerate(self.stationIDs):
            station = self.stations[stationID]
            if i < len(devices):
                device = devices[i]
                try:
                    if self.deviceID_to_stationID[device.deviceID] == stationID:
                        # Station at the place same place as before update -> no need for action
                        # Update, in case the plug name was changed
                        new_data = {'device': device}
                    else:
                        raise KeyError('Plug at the same position')
                except KeyError:
                    # See if the plug already existed
                    try:
                        old_stationID = self.deviceID_to_stationID[device.deviceID]
                        # Plug has changed position
                        new_data = self.stations[old_stationID].extract_data()
                    except KeyError:
                        # Plug is completely new
                        new_data = {'device': device,
                                    'state': 'deactivated', }
                        if device.deviceID in tracked_sessions.keys():
                            # Set tracked sessions to the saved ones
                            station.sessionTracker.update(
                                tracked_sessions=tracked_sessions[device.deviceID],
                                override=True
                            )

                self.deviceID_to_stationID[device.deviceID] = stationID
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
        new_tracked_sessions = settingsManager.value('tracked_sessions')
        for station in winManager.stations.values():
            if station.device is not None:
                # Turn off device
                station.device._device.power_off()
                # Save history by deviceID
                deviceID = station.device.deviceID
                new_tracked_sessions[deviceID] = station.sessionTracker.tracked_sessions
        settingsManager.setValue('tracked_sessions', new_tracked_sessions)

        new_geometries = settingsManager.value('window_geometries')
        for win_name, window in winManager.windows.items():
            geometry = window.saveGeometry()
            new_geometries[win_name] = geometry
        settingsManager.setValue('window_geometries', new_geometries)

    if not settingsManager.value('settings')['saveLogin']:
        # Do not save login
        settingsManager.setValue('username', '')
        settingsManager.setValue('password', '')


def load_windows() -> dict:
    """
    Load all windows of this application and return
    a dictionary with their instances
    """
    def load_geometries():
        """Load saved geometries"""
        for win_name, window in windows.items():
            if win_name in settingsManager.value('window_geometries'):
                # Geometry saved -> load saved geometry
                geometry = settingsManager.value('window_geometries')[win_name]
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
                    'settings': ResourcePaths.ui_files.settingswindow,
                    }
    windows: Dict[str, QWidget] = {}
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
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)
    # ...Application settings here...
    app = app(sys.argv)
    windows = load_windows()
    # Create Manager
    winManager = WindowManager(windows)
