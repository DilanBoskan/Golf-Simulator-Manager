"""
Custom classes helping with the gui logic are here
"""
# pylint: disable=no-name-in-module, import-error
from PySide2.QtWidgets import (QStyledItemDelegate, QLineEdit, QTimeEdit)
from PySide2.QtCore import (Qt, QObject, QEvent)
import datetime as dt

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
