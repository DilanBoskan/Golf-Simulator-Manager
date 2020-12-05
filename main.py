from PySide2.QtCore import *
from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtUiTools import QUiLoader
import os
import sys
from collections import defaultdict
from itertools import count
import copy
# Timer logic
from custom_widgets import *
import datetime as dt
import time
from string import Template
# API calling
import requests
import tplinkcloud
# Saving
import atexit
# Debugging
import traceback
import pprint
# Data Saving
import pickle

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


class DataManager:
    """
    Load/Save/Delete Data Manager
    """

    def __init__(self, default_data: dict = {}, file_name: str = 'data'):
        self.default_data = default_data
        self._data = self.default_data
        self._file_name = f'{file_name}.pkl'
        self._load_data()

    @property
    def data(self) -> dict:
        return self._data

    @data.setter
    def data(self, value: dict):
        """
        Update the new saved data
        """
        assert isinstance(value, dict)
        self._data.update(value)
        self._save_data()

    @data.deleter
    def data(self):
        self._data = self.default_data
        self._save_data()

    def _save_data(self):
        """
        Saves given data as a .pkl (pickle) file
        """
        # Open data file, create it if it does not exist
        with open(self._file_name, 'wb') as data_file:
            pickle.dump(self.data, data_file)

    def _load_data(self):
        """
        Loads saved pkl file and sets it to the data variable
        """
        try:
            with open(self._file_name, 'rb') as data_file:  # Open data file
                self._data = pickle.load(data_file)
        except (ValueError, FileNotFoundError):
            # Data File is corrupted or not found so recreate it
            self._data = self.default_data
            self._save_data()
            self._load_data()


data_manager = DataManager(default_data={'username': None,
                                         'password': None,
                                         'data': {}})
current_active_window = None
# Paths
refresh_path = os.path.join(base_path, 'img', 'refresh.png')
# Constants
AVAILABLE_COLOR = (119, 245, 112)
NOT_AVAILABLE_COLOR = (255, 222, 99)
DEACTIVATED_COLOR = (255, 120, 120)


def reconnect(signal, newhandler=None):
    """
    Remove all previous connections and connect
    the newhandler function with the signal
    """
    while True:
        try:
            signal.disconnect()
        except RuntimeError:
            break
    if newhandler is not None:
        signal.connect(newhandler)


def ceil_dt(date, delta):
    return date + (dt.datetime.min - date) % delta


class EventHandler(QObject):
    def __init__(self):
        super(EventHandler, self).__init__()
        self.filters = []

    def addFilter(self, key, callback, parent=None):
        """
        Add a new key to be filered, when the key is
        found the callback funtion will be called
        """
        self.filters.append([key, callback, parent])

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            key = event.key()
            for key_filter_data in self.filters:
                if key_filter_data[2] is not None:
                    if obj.window() != key_filter_data[2]:
                        continue
                if key == key_filter_data[0]:
                    key_filter_data[1]()
            else:
                return True
        else:
            # standard event processing
            try:
                return QObject.eventFilter(self, obj, event)
            except RuntimeError:
                return True


class Device:
    def __init__(self, device=None):
        # -Variables-
        self._device = device
        if self._device is None:
            self.deviceID = -1
            self.state = -1
            self.deviceName = ''
        else:
            global app
            self.deviceID = self._device.device_id
            self.state = 0
            self.deviceName = ''
            # Set threads
            self._turn_on = QThread(app)
            self._turn_off = QThread(app)
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


class Session:
    _id_counter = count()

    def __init__(self, customerName: str, start_date: dt.datetime, duration: dt.time, sessionID: int = None):
        if sessionID is None:
            sessionID = next(self._id_counter)

        self.sessionID = sessionID
        self.customerName = customerName
        self.start_date = start_date
        self.duration = duration

    @property
    def end_date(self):
        return self.start_date + dt.timedelta(hours=self.duration.hour,
                                              minutes=self.duration.minute)

    @end_date.setter
    def end_date(self, value: dt.datetime):
        assert isinstance(value, dt.datetime), "end_date has to be dt.datetime"
        new_duration = value - self.start_date

        if value <= self.start_date:
            # Invalid new end_date
            global current_active_window
            msg = QMessageBox()
            msg.setWindowTitle("Invalid Input")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText("Please set a valid end time!\nYour end time is before your start time.")  # nopep8
            msg.setStandardButtons(QMessageBox.Ok)
            msg.setWindowFlags(Qt.WindowStaysOnTopHint)
            msg.exec_()
            return

        self.duration = (dt.datetime.min + new_duration).time()

    def extract_data(self) -> dict:
        """
        Extract the data of this session

        Returns(dict):
            Full data of the session
        """
        data = {
            'sessionID': self.sessionID,
            'customerName': self.customerName,
            'start_date': self.start_date,
            'duration': self.duration,
        }
        return data

    def copy(self):
        """Create a copy of this session"""
        return Session(**self.extract_data())


class Station:
    """Station class containing the necessary data to control
    a single station

    Paramaters:
        stationID(int):
            ID identifier for the station and suffix for
            all widget names
    """
    DEFAULT_DATA = {
        'device': Device(),
        'customerName': '',
        'is_activated': True,
        'sessions': [],
    }

    def __init__(self, stationID: int):
        # -Main Variables-
        # Static Paramaters
        self.stationID = stationID
        self.device = self.DEFAULT_DATA['device']
        # Dynamic Paramaters
        self._customerName = self.DEFAULT_DATA['customerName']
        self._is_activated = self.DEFAULT_DATA['is_activated']
        self.sessions = self.DEFAULT_DATA['sessions']
        # -Helper Variables-
        self._editWindow_shownSessions = []
        # Edit window row to sessionID
        self.rowTranslator = {}

        # -Other-
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh())
        self.timer.start(2500)
        self._bind_widgets()
        self._update_sessions()

    @property
    def is_activated(self):
        return self._is_activated

    @is_activated.setter
    def is_activated(self, value: str):
        assert isinstance(value, bool), "is_activated has to be bool"
        self._is_activated = value

        if not self.is_activated:
            self.device.turn_off()
        self.refresh()

    @property
    def customerName(self):
        return self._customerName

    @customerName.setter
    def customerName(self, value: str):
        assert isinstance(value, str), "customerName has to be str"
        self._customerName = value
        self._update_texts()

    # -Station methods-
    def refresh(self):
        """
        Refresh this station:
            - Update sessions
            - Update texts
            - Update colors
            - Update Edit Window
        """
        self._update_sessions()
        self._update_texts()
        self._update_colors()
        self._editWindow_refresh()

    def update(self, **kwargs):
        """Update the data of this station

        Paramaters:
            **kwargs:
                Data to update the station on
        """
        if 'device' in kwargs:
            assert isinstance(kwargs['device'], Device)
            self.device = kwargs['device']
        if 'customerName' in kwargs:
            assert isinstance(kwargs['customerName'], str)
            self._customerName = kwargs['customerName']
        if 'is_activated' in kwargs:
            assert isinstance(kwargs['is_activated'], bool)
            self._is_activated = kwargs['is_activated']
        if 'sessions' in kwargs:
            assert isinstance(kwargs['sessions'], list)
            self.sessions = kwargs['sessions'].copy()
        self.refresh()

    def extract_data(self) -> dict:
        """
        Extract the data of this station

        Returns(dict):
            Full data of the station
        """
        data = {
            'device': self.device,
            'customerName': self.customerName,
            'is_activated': self.is_activated,
            'sessions': self.sessions,
        }
        return data

    def show(self, **kwargs):
        """Display the station

        Paramaters:
            **kwargs:
                Data to update the station on
        """
        global windows
        windows['main'].findChild(QWidget, f"frame_station_{self.stationID}").setHidden(False)
        if kwargs:
            self.update(**kwargs)

        self.refresh()

    def reset(self, hide: bool = False):
        """Reset the data of this station

        Paramaters:
            hide(bool):
                Hide the station
        """
        if hide:
            windows['main'].findChild(QWidget, f"frame_station_{self.stationID}").setHidden(True)
        self.update(**self.DEFAULT_DATA.copy())

    # -Session methods-
    def add_session(self, customerName: str, start_date: dt.datetime, duration: dt.time, sessionID: int = None) -> bool:
        """
        Add a new session

        Paramaters:
            customerName(str):
                Name of customer for this session
            start_date(dt.datetime or None):
                If None, the end_date of the last queue item will be taken
            duration(dt.time):
                Time length of the session
            sessionID(int):
                ID of session that is to be replaced
        Returns(bool):
            Succesfully added session
        """
        # -Determine session paramaters-
        if start_date is None:
            if self.sessions:
                start_date = self.sessions[-1].end_date
            else:
                start_date = dt.datetime.now()
        new_session = Session(customerName=customerName,
                              start_date=start_date,
                              duration=duration,
                              sessionID=sessionID)

        # -Check for conflicting sessions-
        conflicting_sessions = []
        for queued_session in self.sessions:
            if (new_session.start_date < queued_session.end_date) and (queued_session.start_date < new_session.end_date):
                if queued_session.sessionID == new_session.sessionID:
                    # Ignore the session that is being replaced
                    continue
                conflicting_sessions.append(queued_session)
        # Ask for confirmation on deletion of overlapping sessions
        if conflicting_sessions:
            # Create messagebox
            msg = QMessageBox()
            msg.setWindowTitle("Conflicting Sessions")
            msg.setIcon(QMessageBox.Warning)
            msg.setText(f"Your session is conflicting with {len(conflicting_sessions)} already registered session(s).\nDo you wish to delete the overlapping sessions?")  # nopep8
            detailedText = f"Your sessions start: {new_session.start_date.strftime('%H:%M')}\nYour sessions end: {new_session.end_date.strftime('%H:%M')}"
            detailedText += '\n\nConflicting session(s):\n\n'
            for conflicting_data in conflicting_sessions:
                conflicting_session = conflicting_data
                detailedText += f"{conflicting_session.customerName}´s session start: {conflicting_session.start_date.strftime('%H:%M')}"
                detailedText += f"\n{conflicting_session.customerName}´s session end: {conflicting_session.end_date.strftime('%H:%M')}"
                detailedText += '\n\n'
            msg.setDetailedText(detailedText)
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setWindowFlag(Qt.WindowStaysOnTopHint)
            val = msg.exec_()

            # User pressed continue
            if val == QMessageBox.Yes:
                # ! Use filter method
                # Remove all conflicting sessions
                for conflicting_session in conflicting_sessions:
                    for queued_session in self.sessions:
                        if conflicting_session.sessionID == queued_session.sessionID:
                            self.sessions.remove(queued_session)
                # Add the session again
                session_data = new_session.extract_data()
                del session_data['sessionID']
                return self.add_session(**session_data)
            else:
                # User pressed cancel -> unsuccessful
                return False

        if sessionID is not None:
            # Delete old session
            self.delete_session(sessionID)
        self.sessions.append(new_session)
        self.refresh()
        return True

    def delete_session(self, sessionID: int):
        """
        Delete the session

        Paramaters:
            sessionID(int):
                ID of the session to delete
        """
        session = self._find_session(sessionID)
        self.sessions.remove(session)

    def replace_session(self, sessionID: int, new_customerName: str = None, new_start_date: dt.datetime = None,
                        new_end_date: dt.datetime = None, new_duration: dt.time = None):
        """
        Update the session with the given session id with the
        newly given session data

        Paramaters:
            sessionID(int):
                ID of the session to delete
            new_customerName(str):
                The new customer name
            new_start_date(dt.datetime):
                New start date (end date will change)
            new_end_date(dt.datetime):
                New end date (duration will change)
            new_duration(dt.time):
                New duration (end date will change)
        """
        session = self._find_session(sessionID).copy()
        if new_customerName is not None:
            session.customerName = new_customerName
        if new_start_date is not None:
            session.start_date = new_start_date
        if new_end_date is not None:
            session.end_date = new_end_date
        if new_duration is not None:
            session.duration = new_duration

        self.add_session(**session.extract_data())

    def running_session(self) -> bool:
        """
        Check if a session is currently running
        Returns(bool):

            Currently running a session
        """
        if (not self.sessions or
                not self.is_activated):
            return False
        # Sort session by start date
        self.sessions = sorted(self.sessions, key=lambda s: s.start_date)
        datetime_now = dt.datetime.now()
        if self.sessions[0].start_date <= datetime_now <= self.sessions[0].end_date:
            # Current time inside the sessions range
            return True
        else:
            return False

    def _update_sessions(self):
        """
        Update the session queue
        """
        datetime_now = dt.datetime.now()
        # Sort session by start date
        self.sessions = sorted(self.sessions, key=lambda s: s.start_date)
        # Clear out expired sessions (already past sessions; includes the most recent active session)
        for queue_session in self.sessions:
            if queue_session.end_date <= datetime_now:
                # Session is done
                self.delete_session(queue_session['id'])

        # -Determine Text shown and states-
        if not self.running_session():
            # No session running
            self.customerName = self.DEFAULT_DATA['customerName']
            # Check for an upcoming session
            if self.sessions:
                if self.sessions[0].start_date > datetime_now:
                    customerName = f"{self.sessions[0].customerName}"
                    self.customerName = customerName + f" <span style=\" font-size:8pt; font-style:italic; color:#333;\" >starts at {self.sessions[0].start_date.strftime('%H:%M')}</span>"  # nopep8
            if self.is_activated:
                self.device.turn_off()
        else:
            self.customerName = self.sessions[0].customerName
            # Update time left
            self.device.turn_on()

    def _find_session(self, sessionID: int) -> Session:
        """
        Find a session by its id

        Paramaters:
            sessionID(int):
                ID of the session to delete

        Returns(Session):
            Session instance with that id
        """
        for session in self.sessions:
            if session.sessionID == sessionID:
                return session
        else:
            raise KeyError('No session found with id', sessionID)

    # -Button clicks-
    def clicked_onOff(self):
        """
        Toggle between activated and deactivated
        """
        if self.is_activated:
            if self.sessions:
                global windows
                msg = QMessageBox()
                msg.setWindowTitle("Confirmation")
                msg.setIcon(QMessageBox.Warning)
                msg.setText("Deactivating this station will close the current customer session and all sessions queued.\nDo you wish to proceed?")  # nopep8
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msg.setWindowFlag(Qt.WindowStaysOnTopHint)
                val = msg.exec_()

                if val != QMessageBox.Yes:  # Not Continue
                    return

            self.sessions.clear()
            self.is_activated = False
        else:
            self.is_activated = True

    def clicked_newSession(self):
        """
        Open the session window
        """
        global windows
        # -Window Setup-
        if self.sessions:
            time = self.sessions[-1].end_date
        else:
            time = dt.datetime.now()
        time = ceil_dt(time,
                       dt.timedelta(minutes=30))

        # Time is over the current day
        if time.day > dt.date.today().day:
            time = dt.time(23, 59)
        else:
            time = time.time()

        # Reset variable
        windows['session'].lineEdit_customerName.setText('')
        windows['session'].timeEdit_startAt.setTime(time)
        # Set dynamic properties
        windows['session'].setProperty('stationID', self.stationID)
        # Reshow window
        windows['session'].hide()
        windows['session'].setWindowFlag(Qt.WindowStaysOnTopHint)
        windows['session'].show()

    def clicked_editSession(self):
        """
        Open the edit sessions window
        """
        global windows
        # -Window Setup-
        # Reset variable
        # Set stationID
        windows['edit'].setProperty('stationID', self.stationID)
        # Reshow window
        windows['edit'].hide()
        windows['edit'].setWindowFlag(Qt.WindowStaysOnTopHint)
        # Move window to top-left
        # windows['edit'].move(windows['main'].pos().x(), windows['main'].pos().y())
        windows['edit'].show()
        # -Fill List-
        self.refresh()

    # -Edit Window-
    def editWindow_deleteSelection(self, selection):
        """
        Delete all session in the given selection
        """
        for item in selection:
            self.delete_session(self.rowTranslator[item.row()])
        self.refresh()

    def _editWindow_refresh(self):
        """
        Check if the table in the edit window needs an update
        Is being checked as a refill of the table results in an
        unselection
        """
        global windows
        if windows['edit'].property('stationID') == self.stationID:
            if self.sessions != self._editWindow_shownSessions:
                self._editWindow_updateTable()

    def _editWindow_updateTable(self):
        """
        Fill the table in the edit sessions window
        """
        global windows
        headers = ['Customer Name', 'Start Time', 'End Time', 'Total Time']
        headerTranslator = {
            'Customer Name': 'customerName',
            'Start Time': 'start_date',
            'End Time': 'end_date',
            'Total Time': 'duration',
        }
        self.rowTranslator = {}

        tableWidget: QTableWidget = windows['edit'].findChild(QTableWidget, f"tableWidget_queue")
        tableWidget.setRowCount(0)
        # Base widget settings
        tableWidget.setRowCount(len(self.sessions))
        tableWidget.setColumnCount(len(headers))
        tableWidget.setHorizontalHeaderLabels(headers)
        # -Set column widths-
        tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        column_width = max(tableWidget.columnWidth(1), tableWidget.columnWidth(2), tableWidget.columnWidth(3))
        tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        tableWidget.setColumnWidth(1, column_width)
        tableWidget.setColumnWidth(2, column_width)
        tableWidget.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        # -Fill table-
        for row in range(tableWidget.rowCount()):
            self.rowTranslator[row] = self.sessions[row].sessionID
            datas = self.sessions[row].extract_data()
            datas['end_date'] = self.sessions[row].end_date
            for col, header_key in enumerate(headers):
                data = datas[headerTranslator[header_key]]
                if type(data) in (dt, dt.date, dt.datetime, dt.time):
                    data = data.strftime('%H:%M')
                item = QTableWidgetItem(str(data))
                item.setTextAlignment(Qt.AlignCenter)

                tableWidget.setItem(row, col, item)
        tableWidget.setItemDelegate(QWidgetDelegate(windows['edit'], station=self))
        self._editWindow_shownSessions = self.sessions.copy()

    def _update_texts(self):
        """
        Update the text elements of the station
        """
        global windows

        def strfdelta(tdelta, fmt):
            """
            Stringify timedelta
            """
            class DeltaTemplate(Template):
                delimiter = "%"
            d = {"D": tdelta.days}
            d["H"], rem = divmod(tdelta.seconds, 3600)
            d["M"], d["S"] = divmod(rem, 60)
            for key in d.keys():
                d[key] = str(d[key]).zfill(2)

            t = DeltaTemplate(fmt)
            return t.substitute(**d)

        # -Update station name and customer name-

        # -Update start date, end date and time left-
        if not self.running_session():
            # Station is either deactivated, or has no session running
            start_date = ''
            end_date = ''
            time_left = ''
        else:
            # Stringify the time formats
            datetime_now = dt.datetime.now()
            start_date = self.sessions[0].start_date.strftime('%H:%M')
            end_date = self.sessions[0].end_date.strftime('%H:%M')
            time_left = strfdelta(self.sessions[0].end_date - datetime_now, '%H:%M')

        # -Push Buttons-
        if not self.is_activated:
            toggleState_text = 'Take Control'
            newSession_enabled = False
            edit_enabled = False
        else:
            toggleState_text = 'Release Control'
            newSession_enabled = True
            edit_enabled = True

        # -Update texts-
        windows['main'].findChild(QLabel, f"label_deviceName_{self.stationID}").setText(self.device.deviceName)
        windows['main'].findChild(QLabel, f"label_customerName_{self.stationID}").setText(self.customerName)
        windows['main'].findChild(QLabel, f"label_startTimeValue_{self.stationID}").setText(start_date)
        windows['main'].findChild(QLabel, f"label_endTimeValue_{self.stationID}").setText(end_date)
        windows['main'].findChild(QLabel, f"label_timeLeftValue_{self.stationID}").setText(time_left)
        windows['main'].findChild(QPushButton, f"pushButton_toggleState_{self.stationID}").setText(toggleState_text)
        windows['main'].findChild(QPushButton, f"pushButton_newSession_{self.stationID}").setEnabled(newSession_enabled)
        windows['main'].findChild(QPushButton, f"pushButton_edit_{self.stationID}").setEnabled(edit_enabled)

    def _update_colors(self):
        """
        Update the indicator colors of the station
        """
        global windows
        if self.is_activated:
            frame_labels_color = AVAILABLE_COLOR
        else:
            frame_labels_color = DEACTIVATED_COLOR
        frame_labels_stylesheet = """QFrame { background-color: rgb(%d, %d, %d);}""" % (frame_labels_color[0],
                                                                                        frame_labels_color[1],
                                                                                        frame_labels_color[2])

        # -Update color-
        windows['main'].findChild(QFrame, f"frame_labels_{self.stationID}").setStyleSheet(frame_labels_stylesheet)

    def _bind_widgets(self):
        """
        Bind the buttons of this station to
        """
        global windows
        reconnect(windows['main'].findChild(QPushButton, f"pushButton_newSession_{self.stationID}").clicked, self.clicked_newSession)  # nopep8
        reconnect(windows['main'].findChild(QPushButton, f"pushButton_edit_{self.stationID}").clicked, self.clicked_editSession)  # nopep8
        reconnect(windows['main'].findChild(QPushButton, f"pushButton_toggleState_{self.stationID}").clicked, self.clicked_onOff)  # nopep8


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
        self.all_stations = {x: Station(x) for x in self.stationIDs}
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
        stationTemplate_path = os.path.join(ui_folder, 'stationQWidget.ui')
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
                new_station_path = os.path.join(ui_folder, 'Stations', f'station_{stationID}.ui')
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
        icon = QPixmap(refresh_path)
        windows['main'].pushButton_refresh.setIcon(icon)

    def setup_threads(self):
        """
        Setup all threads used for this application
        """
        global windows
        self.device_retriever = KasaAppRetriever(win=windows,
                                                 disable_widgets=[windows['main'].pushButton_refresh,
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
                device = Device(devices[i]['device'])
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
        widget = windows['edit'].findChild(QTableWidget, f"tableWidget_queue")
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


if __name__ == "__main__":
    global windows
    global app
    app = QApplication
    # Application settings here...
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app = app(sys.argv)
    threadpool = QThreadPool()
    eventHandler = EventHandler()

    # Load Windows
    loader = QUiLoader()
    ui_folder = 'UI Files'
    window_paths = {'main': os.path.join(ui_folder, 'mainwindow.ui'),
                    'login': os.path.join(ui_folder, 'loginwindow.ui'),
                    'session': os.path.join(ui_folder, 'sessionwindow.ui'),
                    'edit': os.path.join(ui_folder, 'editwindow.ui'),
                    }
    windows = {}
    for key, path in window_paths.items():
        windows[key] = loader.load(path, None)
        windows[key].installEventFilter(eventHandler)
    current_active_window = app
    # Create Manager
    winManager = WindowManager()

    # Create stations
    sys.exit(app.exec_())
