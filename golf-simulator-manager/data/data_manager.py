import pickle
import os
import sys

# Get the absolute path to this file
if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the PyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    abs_path = sys._MEIPASS
else:
    abs_path = os.path.dirname(os.path.abspath(__file__))


class DataManager:
    """
    Load/Save/Delete Data Manager
    """

    def __init__(self, default_data: dict = {}, file_path: str = None):
        self.default_data = default_data
        self._data = self.default_data
        self.file_path = os.path.join(abs_path, 'data', 'data.pkl') if file_path is None else file_path
        self.save_folder = os.path.dirname(self.file_path)
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
        with open(self.file_path, 'wb') as data_file:
            pickle.dump(self.data, data_file)

    def _load_data(self):
        """
        Loads saved pkl file and sets it to the data variable
        """
        try:
            with open(self.file_path, 'rb') as data_file:  # Open data file
                self._data = pickle.load(data_file)
        except (ValueError, FileNotFoundError):
            # Data File is corrupted or not found so recreate it
            self._data = self.default_data
            self._save_data()
            self._load_data()
