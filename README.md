# Cleanup Manager for Windows

A native Python desktop app for reviewing files and folders before safely moving selected items to the Windows Recycle Bin.

## Run

Double-click `run_app.cmd`, or run:

```powershell
python -m pip install -r requirements.txt
python -m cleanup_manager
```

Choose a folder, scan it, click the checkbox area beside any item you want to remove, preview it, then use **Move checked to Recycle Bin**. Nothing is deleted automatically.

By default the app lists only the chosen folder's immediate contents. Enable **Show every nested file and folder** for a full recursive inventory.

## Verify

```powershell
python -m unittest discover -s tests
```

The desktop app requires Python 3.10+ with Tkinter installed. Files currently in use may not be recyclable. The Windows UI and native Recycle Bin operation require validation on Windows.

The previously supplied ZIP also contained an older experimental Node/React implementation. This repository initially publishes the supported Python desktop app rather than the unvalidated legacy interface.
