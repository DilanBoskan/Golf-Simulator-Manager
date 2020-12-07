"""
Test the kasa plug retrieving
"""
from tplinkcloud import TPLinkDeviceManager

if __name__ == "__main__":
    # Kasa-App credentials
    username = ''
    password = ''

    device_manager = TPLinkDeviceManager(username, password)
    devices = device_manager.get_devices()
    if devices:
        for device in devices:
            print(f'{device.model_type.name} device called {device.get_alias()} (State: {1 if device.is_on() else 0})')