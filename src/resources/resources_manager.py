import enum
import os
import sys

# Get the absolute path to this file
if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the PyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    abs_path = sys._MEIPASS # pylint: disable=no-member
else:
    abs_path = os.path.dirname(os.path.abspath(__file__))


class ResourcePaths:
    """
    Get access to all resources used in the application
    through this class
    """
    class images:
        IMAGE_FOLDER = 'images'
        golf_icon_ico = os.path.join(abs_path, IMAGE_FOLDER, 'golf-icon.ico')
        golf_icon_png = os.path.join(abs_path, IMAGE_FOLDER, 'golf-icon.png')
        refresh = os.path.join(abs_path, IMAGE_FOLDER, 'refresh.png')

    class ui_files:
        UI_FOLDER = 'ui_files'
        editwindow = os.path.join(abs_path, UI_FOLDER, 'editwindow.ui')
        loginwindow = os.path.join(abs_path, UI_FOLDER, 'loginwindow.ui')
        mainwindow = os.path.join(abs_path, UI_FOLDER, 'mainwindow.ui')
        sessionwindow = os.path.join(abs_path, UI_FOLDER, 'sessionwindow.ui')
        stationQWidget = os.path.join(abs_path, UI_FOLDER, 'stationQWidget.ui')


if __name__ == "__main__":
    """Print all resources"""

    print('-- Images --')
    for img, img_path in vars(ResourcePaths.images).items():
        if os.path.isfile(str(img_path)):
            print(f'{img} -> {img_path}')
    print('-- UI Files --')
    for ui, ui_path in vars(ResourcePaths.ui_files).items():
        if os.path.isfile(str(ui_path)):
            print(f'{ui} -> {ui_path}')
