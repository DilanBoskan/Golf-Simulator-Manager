"""
Run the application
"""
from src import app
import sys

if __name__ == "__main__":
    app.run()
    sys.exit(app.app.exec_())
