"""
Custom methods helping with the gui logic are here
"""

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
