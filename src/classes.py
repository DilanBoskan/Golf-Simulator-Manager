"""
Classes
"""
# pylint: disable=no-name-in-module, import-error
# -GUI-
from PySide2.QtCore import (Qt, QTimer)
from PySide2.QtWidgets import (QMessageBox, QTableWidgetItem, QHeaderView, QPushButton,
                               QFrame, QLabel, QWidget)
# -Root imports-
from .gui_helper.classes import (EventHandler, QWidgetDelegate)
from .gui_helper.methods import (reconnect)
from .kasa.kasa_device import (Device)
from . import constants as const
# -Other-
from itertools import count
import datetime as dt
from string import Template
# Code annotation
from typing import (Dict, List, Union, MutableSequence)


class Session:
    _id_counter = count()

    def __init__(self, customerName: str, start_date: dt.datetime, duration: dt.time, sessionID: Union[int, None] = None):
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
            msg = QMessageBox()
            msg.setWindowTitle("Invalid Input")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText("Please set a valid end time!\nYour end time is before your start time.")  # nopep8
            msg.setStandardButtons(QMessageBox.Ok)
            msg.setWindowFlags(Qt.WindowStaysOnTopHint)
            msg.exec_()
            return

        self.duration = (dt.datetime.min + new_duration).time()

    def range_contains(self, datetime: dt.datetime) -> bool:
        """
        Returns whether the given datetime is contained inside the
        range of this session
        """
        return self.start_date <= datetime <= self.end_date

    def range_conflicts(self, start_date: dt.datetime, end_date: dt.datetime) -> bool:
        """
        Returns whether the given range conflicts with the range
        of this session
        """
        return (self.start_date < end_date) and (start_date < self.end_date)

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
    DEFAULT_DEVICE = None
    DEFAULT_CUSTOMERNAME = ''
    DEFAULT_ACTIVATION = False
    DEFAULT_SESSIONS = []

    def __init__(self, windows, stationID: int, tracked_sessions: List[Session] = []):
        self.windows = windows
        # -Main Variables-
        # Static Paramaters
        self.stationID = stationID
        self.device: Union[Device, None] = self.DEFAULT_DEVICE
        self.sessionTracker = SessionTracker(self,
                                             tracked_sessions)
        # Dynamic Paramaters
        self._customerName: str = self.DEFAULT_CUSTOMERNAME
        self._is_activated: bool = self.DEFAULT_ACTIVATION
        self.sessions: List[Session] = self.DEFAULT_SESSIONS
        # Helper Variables
        self._editWindow_shownSessions: List[Session] = []
        self.rowTranslator: Dict[int, int] = {}  # Connect edit row to sessionID

        # -Setup-
        self._initialize_timers()
        self._initialize_binds()
        self.hide()
        self.refresh()

    @property
    def is_activated(self):
        return self._is_activated

    @is_activated.setter
    def is_activated(self, value: bool):
        assert isinstance(value, bool), "is_activated has to be bool"
        self._is_activated = value

        if not self.is_activated:
            # Deactivate station
            if self.device is not None:
                # Device is registered
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

    # -Initialize methods-
    def _initialize_timers(self):
        """
        Set up timers here
        """
        # Refresh timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2500)

    def _initialize_binds(self):
        """
        Bind the buttons of this station to
        """
        reconnect(self.windows['main'].findChild(QPushButton, f"pushButton_newSession_{self.stationID}").clicked, self.clicked_newSession)  # nopep8
        reconnect(self.windows['main'].findChild(QPushButton, f"pushButton_edit_{self.stationID}").clicked, self.clicked_editSession)  # nopep8
        reconnect(self.windows['main'].findChild(QPushButton, f"pushButton_toggleState_{self.stationID}").clicked, self.clicked_onOff)  # nopep8

    # -Station methods-
    def refresh(self):
        """
        Refresh this station:
            - Update sessions
            - Update texts
            - Update colors
            - Update Edit Window
            - Update Statistics Tracker
        """
        self._update_sessions()
        self._update_texts()
        self._update_colors()
        self._editWindow_refresh()
        self.sessionTracker.refresh()

    def update(self, **kwargs):
        """Update the data of this station

        Paramaters:
            **kwargs:
                Data to update the station on
        """
        if 'device' in kwargs:
            assert (isinstance(kwargs['device'], Device) or kwargs['device'] is None)
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
        self.windows['main'].findChild(QWidget, f"frame_station_{self.stationID}").setHidden(False)
        if kwargs:
            self.update(**kwargs)

        self.refresh()

    def hide(self):
        """Hide the station"""
        self.windows['main'].findChild(QWidget, f"frame_station_{self.stationID}").setHidden(True)

    def reset(self, hide: bool = False):
        """Reset the data of this station

        Paramaters:
            hide(bool):
                Hide the station
        """
        if hide:
            self.hide()
        self.update(**{
            'device': self.DEFAULT_DEVICE,
            'customerName': self.DEFAULT_CUSTOMERNAME,
            'is_activated': self.DEFAULT_ACTIVATION,
            'sessions': self.DEFAULT_SESSIONS,
        })

    # -Session methods-
    def add_session(self, customerName: str, start_date: Union[dt.datetime, None], duration: dt.time, sessionID: Union[int, None] = None) -> bool:
        """
        Add a new session

        Paramaters:
            customerName(str):
                Name of customer for this session
            start_date(dt.datetime or None):
                If None, the end_date of the last queue item will be taken
            duration(dt.time):
                Time length of the session
            sessionID(int or None):
                ID of session, if None a new session is created, otherwise
                it may replace a session if a session already has that sessionID (no warning)
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
            if new_session.range_conflicts(queued_session.start_date, queued_session.end_date):
                # Ranges conflict
                if queued_session.sessionID == new_session.sessionID:
                    # Ignore the session as it is the one being replaced
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
                # Remove all conflicting sessions
                for conflicting_session in conflicting_sessions:
                    self.delete_session(session=conflicting_session,
                                        track=None)
                # Add the session again
                session_data = new_session.extract_data()
                del session_data['sessionID']
                return self.add_session(**session_data)
            else:
                # User pressed cancel -> unsuccessful
                return False

        if sessionID is not None:
            # Delete old session
            self.delete_session(session=sessionID,
                                track=False)
        self.sessions.append(new_session)
        self.refresh()
        return True

    def delete_session(self, session: Union[int, Session] = None, track: Union[bool, None] = None):
        """
        Delete the session

        Paramaters:
            session(int or Session):
                ID of the session to delete OR
                Session class to delete
            track(bool):
                Whether to track the session
                If track is None, the session is only tracked if its range is in the current date.
                If that condition is true, the session is tracked up until the current date
        """
        deleted_session: Session
        if isinstance(session, int):
            deleted_session = self._find_session(session)
        elif isinstance(session, Session):
            deleted_session = session

        if track is None:
            datetime_now = dt.datetime.now()
            if deleted_session.range_contains(datetime_now):
                deleted_session.end_date = datetime_now
                track = True
            else:
                track = False
        if track:
            self.sessionTracker.add_session_to_history(deleted_session)
        self.sessions.remove(deleted_session)

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
        first_session = self.sessions[0]

        datetime_now = dt.datetime.now()
        # Current time inside the sessions range
        return first_session.range_contains(datetime_now)

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
                self.delete_session(session=queue_session,
                                    track=True)

        # -Determine Text shown and states-
        if not self.running_session():
            # No session running
            self.customerName = self.DEFAULT_CUSTOMERNAME
            # Check for an upcoming session
            if self.sessions:
                upcoming_session = self.sessions[0]
                if upcoming_session.start_date > datetime_now:
                    customerName = f"{upcoming_session.customerName}"
                    self.customerName = customerName + f" <span style=\" font-size:8pt; font-style:italic; color:#333;\" >starts at {upcoming_session.start_date.strftime('%H:%M')}</span>"  # nopep8
            if self.is_activated:
                # Station is activated
                if self.device is not None:
                    # Device is registered
                    self.device.turn_off()
        else:
            # Session running
            self.customerName = self.sessions[0].customerName
            if self.device is not None:
                # Device is registered
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
                msg = QMessageBox()
                msg.setWindowTitle("Confirmation")
                msg.setIcon(QMessageBox.Warning)
                msg.setText("Deactivating this station will close the current customer session and all sessions queued.\nDo you wish to proceed?")  # nopep8
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msg.setWindowFlag(Qt.WindowStaysOnTopHint)
                val = msg.exec_()

                if val != QMessageBox.Yes:  # Not Continue
                    return

            for session in self.sessions:
                self.delete_session(session=session,
                                    track=None)
            self.is_activated = False
        else:
            self.is_activated = True

    def clicked_newSession(self):
        """
        Open the session window
        """
        # -Window Setup-
        if self.sessions:
            time = self.sessions[-1].end_date
        else:
            time = dt.datetime.now()
        time = self.ceil_dt(time,
                            dt.timedelta(minutes=30))

        # Time is over the current day
        if time.day > dt.date.today().day:
            time = dt.time(23, 59)
        else:
            time = time.time()

        # Reset variable
        self.windows['session'].lineEdit_customerName.setText('')
        self.windows['session'].timeEdit_startAt.setTime(time)
        # Set dynamic properties
        self.windows['session'].setProperty('stationID', self.stationID)
        # Reshow window
        self.windows['session'].setWindowFlag(Qt.WindowStaysOnTopHint)
        self.windows['session'].show()
        # Focus window
        self.windows['session'].activateWindow()
        self.windows['session'].raise_()

    def clicked_editSession(self):
        """
        Open the edit sessions window
        """
        # -Window Setup-
        # Reset variable
        # Set stationID
        self.windows['edit'].setProperty('stationID', self.stationID)
        # Reshow window
        self.windows['edit'].setWindowFlag(Qt.WindowStaysOnTopHint)
        self.windows['edit'].show()
        # Focus window
        self.windows['edit'].activateWindow()
        self.windows['edit'].raise_()
        # -Fill List-
        self._editWindow_updateTable()
        self.refresh()

    # -Edit Window-
    def delete_selection(self):
        """
        Delete all session selected
        """
        assert self.windows['edit'].property('stationID') == self.stationID, "stationID in edit window does not equal stationID deletion is being performed on"  # nopep8

        # Get selection
        widget = self.windows['edit'].tableWidget_queue
        selection = widget.selectionModel().selectedRows()
        # Perform deletion
        datetime_now = dt.datetime.now()
        for item in selection:
            session = self._find_session(self.rowTranslator[item.row()])
            if session.range_contains(datetime_now):
                # Current time inside the sessions range
                msg = QMessageBox()
                msg.setWindowTitle('Confirmation')
                msg.setIcon(QMessageBox.Icon.Information)
                msg.setText('You are deleting a session that is currently active. Do you wish to proceed?')
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
                msg.setWindowFlag(Qt.WindowStaysOnTopHint)
                val = msg.exec_()
                if val == QMessageBox.Cancel:
                    # Skip this session deletion
                    continue
            self.delete_session(session=session,
                                track=None)
        self.refresh()

    @staticmethod
    def ceil_dt(date, delta) -> dt.datetime:
        """
        Round up datetime
        """
        return date + (dt.datetime.min - date) % delta

    def _editWindow_refresh(self):
        """
        Check if the table in the edit window needs an update
        Is being checked as a refill of the table results in an
        unselection
        """
        if self.windows['edit'].property('stationID') == self.stationID:
            if self.sessions != self._editWindow_shownSessions:
                self._editWindow_updateTable()

    def _editWindow_updateTable(self):
        """
        Fill the table in the edit sessions window
        """
        headers = ['Customer Name', 'Start Time', 'End Time', 'Total Time']
        headerTranslator = {
            'Customer Name': 'customerName',
            'Start Time': 'start_date',
            'End Time': 'end_date',
            'Total Time': 'duration',
        }
        self.rowTranslator = {}

        tableWidget = self.windows['edit'].tableWidget_queue
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
        tableWidget.setItemDelegate(QWidgetDelegate(self.windows['edit'], station=self))
        self._editWindow_shownSessions = self.sessions.copy()

    def _update_texts(self):
        """
        Update the text elements of the station
        """
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
        self.windows['main'].findChild(QLabel, f"label_customerName_{self.stationID}").setText(self.customerName)
        self.windows['main'].findChild(QLabel, f"label_startTimeValue_{self.stationID}").setText(start_date)
        self.windows['main'].findChild(QLabel, f"label_endTimeValue_{self.stationID}").setText(end_date)
        self.windows['main'].findChild(QLabel, f"label_timeLeftValue_{self.stationID}").setText(time_left)
        self.windows['main'].findChild(QPushButton, f"pushButton_toggleState_{self.stationID}").setText(toggleState_text)  # nopep8
        self.windows['main'].findChild(QPushButton, f"pushButton_newSession_{self.stationID}").setEnabled(newSession_enabled)  # nopep8
        self.windows['main'].findChild(QPushButton, f"pushButton_edit_{self.stationID}").setEnabled(edit_enabled)
        if self.device is not None:
            # Device is registered
            self.windows['main'].findChild(QLabel, f"label_deviceName_{self.stationID}").setText(self.device.deviceName)
        else:
            self.windows['main'].findChild(QLabel, f"label_deviceName_{self.stationID}").setText('N/A')

    def _update_colors(self):
        """
        Update the indicator colors of the station
        """
        if self.running_session():
            frame_labels_color = const.NOT_AVAILABLE_COLOR
        elif self.is_activated:
            frame_labels_color = const.AVAILABLE_COLOR
        else:
            frame_labels_color = const.DEACTIVATED_COLOR
        frame_labels_stylesheet = """QFrame { background-color: rgb(%d, %d, %d);}""" % (frame_labels_color[0],
                                                                                        frame_labels_color[1],
                                                                                        frame_labels_color[2])

        # -Update color-
        self.windows['main'].findChild(QFrame, f"frame_labels_{self.stationID}").setStyleSheet(frame_labels_stylesheet)


class SessionTracker:
    """Class containing the necessary data to track
    a stations sessions

    Paramaters:
        station(Station):
            Station to track the times on
    """

    def __init__(self, station: Station, tracked_sessions: List[Session] = []):
        self.station = station
        self.windows = self.station.windows
        self.stationID = self.station.stationID
        self.tracked_sessions = tracked_sessions
        # -Setup-
        self._initialize_timers()
        self._initialize_binds()
        self.refresh()

    # -Initialize methods-
    def _initialize_timers(self):
        """
        Set up timers here
        """
        # Refresh timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2500)

    def _initialize_binds(self):
        """
        Bind the buttons of this station to
        """
        reconnect(self.windows['main'].findChild(QPushButton, f"pushButton_statistics_showSessions_{self.stationID}").clicked, self.clicked_showSessions)  # nopep8

    def refresh(self):
        """
        Refresh this statistics tracker:
            - Sort tracked sessions
            - Update visibility
            - Update texts
            - Update table
        """
        self.tracked_sessions = sorted(self.tracked_sessions, key=lambda s: s.start_date)
        self._update_visibility()
        self._update_texts(sessions=self.tracked_sessions)
        if self.windows['history'].property('stationID') == self.stationID:
            self._historyWindow_updateTable(sessions=self.tracked_sessions)

    def update(self, tracked_sessions: list, override: bool):
        """Update the data of this sessionTracker"""
        new_tracked_sessions = tracked_sessions
        if not override:
            # Do not override existing data
            new_tracked_sessions.append(self.tracked_sessions)

        self.tracked_sessions = new_tracked_sessions
        self.refresh()

    def extract_data(self) -> Union[dict, None]:
        """
        Extract the data of this tracker

        Returns(dict or None):
            Full data of the session history or None if the
            parent station does not have a registered device
        """
        if self.station.device is None:
            # No device registered for this station
            return None
        data = {
            'deviceID': self.station.device.deviceID,
            'tracked_sessions': self.tracked_sessions
        }
        return data

    # -Session tracking-
    def add_session_to_history(self, session: Session):
        """
        Add a session to the session history of this station
        """
        # Search for conflicting sessions
        for tracked_session in self.tracked_sessions:
            if tracked_session.range_conflicts(start_date=session.start_date,
                                               end_date=session.end_date):
                # Two tracked sessions might conflict if the user
                # finished one session and then set up a session that
                # happened during that previous sessions time range
                # Action: Override old session
                self.tracked_sessions.remove(tracked_session)
        self.tracked_sessions.append(session)
        self.refresh()

    def calculate_stats(self, sessions: list) -> dict:
        """
        Return the stats displayed on the application
        """
        if not len(sessions):
            # No tracked sessions
            session_history = {
                'total_time': dt.time(hour=0, minute=0),
                'average_time': dt.time(hour=0, minute=0),
                'total_sessions': 0,
                'average_sessions': 0,
            }
            return session_history
        session_history = {}
        total_minutes = 0

        # -Total time-
        for session in sessions:
            total_minutes += session.duration.hour * 60
            total_minutes += session.duration.minute

        hours, minutes = divmod(total_minutes, 60)
        session_history['total_time'] = dt.time(hour=hours,
                                                minute=minutes)
        # -Average session time-
        average_minutes = int(total_minutes / len(sessions))
        hours, minutes = divmod(average_minutes, 60)
        session_history['average_time'] = dt.time(hour=hours,
                                                  minute=minutes)
        # -Total sessions-
        session_history['total_sessions'] = len(sessions)
        # -Average sessions/day-
        dates = []
        for session in sessions:
            start_date = session.start_date.date()
            if start_date in dates:
                continue
            else:
                dates.append(start_date)
        average_sessions = round(len(sessions) / len(dates), 1)
        if average_sessions.is_integer():
            average_sessions = int(average_sessions)
        session_history['average_sessions'] = average_sessions

        return session_history

    # -Button clicks-
    def clicked_showSessions(self):
        """
        Show a table of the sessions history
        """
        # -Window Setup-
        # Set variable
        if self.station.device is not None:
            # Device is registered
            self.windows['history'].label.setText(f'{self.station.device.deviceName} Session History')
        else:
            self.windows['history'].label.setText(f'N/A Session History')
        # Set stationID
        self.windows['history'].setProperty('stationID', self.stationID)
        # Reshow window
        self.windows['history'].setWindowFlag(Qt.WindowStaysOnTopHint)
        self.windows['history'].show()
        # Focus window
        self.windows['history'].activateWindow()
        self.windows['history'].raise_()
        # -Fill List-

        self.refresh()

    def _historyWindow_updateTable(self, sessions: list):
        """
        Update the history table
        """
        headers = ['Date', 'Customer Name', 'Start Time', 'End Time']
        headerTranslator = {
            'Date': 'date',
            'Customer Name': 'customerName',
            'Start Time': 'start_date',
            'End Time': 'end_date',
            'Total Time': 'duration',
        }
        tableWidget = self.windows['history'].tableWidget_history
        tableWidget.setRowCount(0)
        # Base widget settings
        tableWidget.setRowCount(len(sessions))
        tableWidget.setColumnCount(len(headers))
        tableWidget.setHorizontalHeaderLabels(headers)
        # -Set column widths-
        column_width = 90
        tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        tableWidget.setColumnWidth(0, column_width + 20)
        tableWidget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        tableWidget.setColumnWidth(2, column_width)
        tableWidget.setColumnWidth(3, column_width)
        # -Fill table-
        for row in range(tableWidget.rowCount()):
            session = sessions[row]
            session_data = session.extract_data()
            session_data['end_date'] = session.end_date
            for col, header_key in enumerate(headers):
                key = headerTranslator[header_key]
                if key == 'date':
                    data = session_data['start_date'].strftime(r'%d.%m.%Y')
                else:
                    data = session_data[key]
                    if type(data) in (dt, dt.date, dt.datetime, dt.time):
                        data = data.strftime('%H:%M')
                item = QTableWidgetItem(str(data))
                item.setTextAlignment(Qt.AlignCenter)
                tableWidget.setItem(row, col, item)

    def _update_visibility(self):
        """
        Check whether to hide or show this station
        """
        station_frame = self.windows['main'].findChild(QWidget, f"frame_station_{self.stationID}")
        statistic_frame = self.windows['main'].findChild(QWidget, f"frame_statistics_{self.stationID}")
        if station_frame.isHidden():
            # Parent station is hidden
            # Hide the tracker as well
            statistic_frame.setHidden(True)
        else:
            statistic_frame.setHidden(False)

    def _update_texts(self, sessions: list):
        """
        Update the text elements of the statistics
        """
        # -Get Values-
        session_history = self.calculate_stats(sessions)
        total_time = session_history['total_time'].strftime('%H:%M')
        average_time = session_history['average_time'].strftime('%H:%M')
        total_sessions = str(session_history['total_sessions'])
        average_sessions = str(session_history['average_sessions'])
        # -Update texts-
        self.windows['main'].findChild(QLabel, f"label_statistics_totalTimeValue_{self.stationID}").setText(total_time)
        self.windows['main'].findChild(QLabel, f"label_statistics_avgSessionTimeValue_{self.stationID}").setText(average_time)  # nopep8
        self.windows['main'].findChild(QLabel, f"label_statistics_totalSessionsValue_{self.stationID}").setText(total_sessions)  # nopep8
        self.windows['main'].findChild(QLabel, f"label_statistics_avgSessionDayValue_{self.stationID}").setText(average_sessions)  # nopep8
        if self.station.device is not None:
            # Device is registered
            self.windows['main'].findChild(QLabel, f"label_statistics_deviceName_{self.stationID}").setText(self.station.device.deviceName)  # nopep8
        else:
            self.windows['main'].findChild(QLabel, f"label_statistics_deviceName_{self.stationID}").setText('N/A')
