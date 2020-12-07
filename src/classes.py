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

    def __init__(self, windows, stationID: int):
        # -Main Variables-
        self.windows = windows
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
        self.windows['main'].findChild(QWidget, f"frame_station_{self.stationID}").setHidden(False)
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
            self.windows['main'].findChild(QWidget, f"frame_station_{self.stationID}").setHidden(True)
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
        self.windows['session'].hide()
        self.windows['session'].setWindowFlag(Qt.WindowStaysOnTopHint)
        self.windows['session'].show()

    def clicked_editSession(self):
        """
        Open the edit sessions window
        """
        # -Window Setup-
        # Reset variable
        # Set stationID
        self.windows['edit'].setProperty('stationID', self.stationID)
        # Reshow window
        self.windows['edit'].hide()
        self.windows['edit'].setWindowFlag(Qt.WindowStaysOnTopHint)
        # Move window to top-left
        # self.windows['edit'].move(self.windows['main'].pos().x(), self.windows['main'].pos().y())
        self.windows['edit'].show()
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
        self.windows['main'].findChild(QLabel, f"label_deviceName_{self.stationID}").setText(self.device.deviceName)
        self.windows['main'].findChild(QLabel, f"label_customerName_{self.stationID}").setText(self.customerName)
        self.windows['main'].findChild(QLabel, f"label_startTimeValue_{self.stationID}").setText(start_date)
        self.windows['main'].findChild(QLabel, f"label_endTimeValue_{self.stationID}").setText(end_date)
        self.windows['main'].findChild(QLabel, f"label_timeLeftValue_{self.stationID}").setText(time_left)
        self.windows['main'].findChild(
            QPushButton, f"pushButton_toggleState_{self.stationID}").setText(toggleState_text)
        self.windows['main'].findChild(
            QPushButton, f"pushButton_newSession_{self.stationID}").setEnabled(newSession_enabled)
        self.windows['main'].findChild(QPushButton, f"pushButton_edit_{self.stationID}").setEnabled(edit_enabled)

    def _update_colors(self):
        """
        Update the indicator colors of the station
        """
        if self.is_activated:
            frame_labels_color = const.AVAILABLE_COLOR
        else:
            frame_labels_color = const.DEACTIVATED_COLOR
        frame_labels_stylesheet = """QFrame { background-color: rgb(%d, %d, %d);}""" % (frame_labels_color[0],
                                                                                        frame_labels_color[1],
                                                                                        frame_labels_color[2])

        # -Update color-
        self.windows['main'].findChild(QFrame, f"frame_labels_{self.stationID}").setStyleSheet(frame_labels_stylesheet)

    def _bind_widgets(self):
        """
        Bind the buttons of this station to
        """
        reconnect(self.windows['main'].findChild(QPushButton, f"pushButton_newSession_{self.stationID}").clicked, self.clicked_newSession)  # nopep8
        reconnect(self.windows['main'].findChild(QPushButton, f"pushButton_edit_{self.stationID}").clicked, self.clicked_editSession)  # nopep8
        reconnect(self.windows['main'].findChild(QPushButton, f"pushButton_toggleState_{self.stationID}").clicked, self.clicked_onOff)  # nopep8
