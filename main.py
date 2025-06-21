import wx
from cytolk import tolk
from app_frame import SQLiteEditor

def main():
    """Main function to run the application."""
    app = wx.App(False)
    try:
        tolk.load()
        frame = SQLiteEditor(None)
        frame.Show(True)
        app.MainLoop()
    finally:
        tolk.unload()

if __name__ == '__main__':
    main()