import json
import os
import shutil
import subprocess
import threading
import time

from datetime import datetime
from pathlib import Path

from openpilot.common.params import Params
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.hardware import HARDWARE
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets import Widget, DialogResult
from openpilot.system.ui.widgets.confirm_dialog import ConfirmDialog, alert_dialog
from openpilot.system.ui.widgets.keyboard import Keyboard
from openpilot.system.ui.widgets.list_view import ListItem, TextAction, ITEM_TEXT_VALUE_COLOR
from openpilot.system.ui.widgets.option_dialog import MultiOptionDialog
from openpilot.system.ui.widgets.scroller_tici import Scroller

from openpilot.frogpilot.common.frogpilot_utilities import clean_model_name
from openpilot.frogpilot.common.frogpilot_variables import (
  BACKUP_PATH,
  ERROR_LOGS_PATH,
  FROGPILOT_BACKUPS,
  SCREEN_RECORDINGS_PATH,
  TOGGLE_BACKUPS,
  update_frogpilot_toggles,
)
from openpilot.frogpilot.system.ui.widgets.frogpilot_controls import (
  FrogPilotButtonsControl,
  FrogPilotConfirmationDialog,
)

DRIVING_DATA_PATHS = [
  Path("/data/media/0/realdata"),
  Path("/data/media/0/realdata_HD"),
  Path("/data/media/0/realdata_konik"),
]

METER_TO_MILE = 0.000621371
MS_TO_KPH = 3.6
MS_TO_MPH = 2.23694

KEY_MAP = {
  "AEBEvents": ("Total Emergency Brake Alerts", "count"),
  "AOLTime": ("Time Using \"Always On Lateral\"", "timePercent"),
  "CruiseSpeedTimes": ("Favorite Set Speed", "speed"),
  "CurrentMonthsMeters": ("Distance Driven This Month", "distance"),
  "DayTime": ("Time Driving (Daytime)", "timePercent"),
  "Disengages": ("Total Disengagements", "count"),
  "Engages": ("Total Engagements", "count"),
  "ExperimentalModeTime": ("Time Using \"Experimental Mode\"", "timePercent"),
  "FrogChirps": ("Total Frog Chirps", "count"),
  "FrogHops": ("Total Frog Hops", "count"),
  "FrogPilotDrives": ("Total Drives", "count"),
  "FrogPilotMeters": ("Total Distance Driven", "distance"),
  "FrogPilotSeconds": ("Total Driving Time", "time"),
  "FrogSqueaks": ("Total Frog Squeaks", "count"),
  "GoatScreams": ("Total Goat Screams", "count"),
  "HighestAcceleration": ("Highest Acceleration Rate", "accel"),
  "LateralTime": ("Time Using Lateral Control", "timePercent"),
  "LongestDistanceWithoutOverride": ("Longest Distance Without an Override", "distance"),
  "LongitudinalTime": ("Time Using Longitudinal Control", "timePercent"),
  "ModelTimes": ("Driving Models:", "parent"),
  "Month": ("Month", "other"),
  "NightTime": ("Time Driving (Nighttime)", "timePercent"),
  "Overrides": ("Total Overrides", "count"),
  "OverrideTime": ("Time Overriding openpilot", "timePercent"),
  "PersonalityTimes": ("Driving Personalities:", "parent"),
  "RandomEvents": ("Random Events:", "parent"),
  "StandstillTime": ("Time Stopped", "timePercent"),
  "StopLightTime": ("Time Spent at Stoplights", "timePercent"),
  "TrackedTime": ("Total Time Tracked", "time"),
  "WeatherTimes": ("Time Driven (Weather):", "parent"),
}

RANDOM_EVENTS_MAP = {
  "accel30": "UwUs",
  "accel35": "Loch Ness Encounters",
  "accel40": "Visits to 1955",
  "dejaVuCurve": "Deja Vu Moments",
  "firefoxSteerSaturated": "Internet Explorer Weeeeeeees",
  "hal9000": "HAL 9000 Denials",
  "openpilotCrashedRandomEvent": "openpilot Crashes",
  "thisIsFineSteerSaturated": "This Is Fine Moments",
  "toBeContinued": "To Be Continued Moments",
  "vCruise69": "Noices",
  "yourFrogTriedToKillMe": "Attempted Frog Murders",
  "youveGotMail": "Total Mail Received",
}

IGNORED_KEYS = {"Month"}


def format_ordinal(day):
  if 11 <= day <= 13:
    suffix = "th"
  elif day % 10 == 1:
    suffix = "st"
  elif day % 10 == 2:
    suffix = "nd"
  elif day % 10 == 3:
    suffix = "rd"
  else:
    suffix = "th"
  return f"{day}{suffix}"


def format_friendly_date(dt):
  day = dt.day
  return f"{dt.strftime('%B')} {format_ordinal(day)}, {dt.year} ({dt.strftime('%I:%M %p').lstrip('0')})"


def parse_recording_name(filename):
  if not filename.endswith(".mp4"):
    return None, None

  clean_name = filename[:-4]
  separator = "--" if "--" in clean_name else "_"
  parts = clean_name.split(separator)

  if len(parts) >= 2:
    try:
      date = datetime.strptime(parts[0], "%Y-%m-%d")
      time_part = datetime.strptime(parts[1], "%H-%M-%S")
      dt = datetime.combine(date.date(), time_part.time())
      return format_friendly_date(dt), filename
    except ValueError:
      pass

  friendly = clean_name.replace("_", " ")
  return friendly, filename


def parse_backup_name(filename, mod_time=None):
  friendly = filename

  if filename.endswith("_auto.tar.zst") and mod_time:
    parts = filename.replace(".tar.zst", "").split("_")
    if len(parts) >= 3:
      friendly = format_friendly_date(mod_time).rsplit(" (", 1)[0] + f" ({parts[1]})"

  if friendly == filename:
    friendly = filename.replace(".tar.zst", "").replace("_", " ")

  return friendly, filename


def parse_toggle_backup_name(dirname):
  friendly = dirname

  if dirname.endswith("_auto"):
    parts = dirname.replace("_auto", "").split("_")
    if len(parts) >= 2:
      try:
        date = datetime.strptime(parts[0], "%Y-%m-%d")
        time_part = datetime.strptime(parts[1], "%H-%M-%S")
        dt = datetime.combine(date.date(), time_part.time())
        friendly = format_friendly_date(dt)
      except ValueError:
        pass

  if friendly == dirname:
    friendly = dirname.replace("_", " ")

  return friendly, dirname


class FrogPilotDataPanel(Widget):
  def __init__(self):
    super().__init__()

    self._is_metric = False
    self._params = Params()
    self._show_stats = False

    # State for dialogs and operations
    self._pending_dialog = None
    self._pending_action = None
    self._pending_data = {}

    # Screen recordings data
    self._recordings_map = {}
    self._recordings_list = []

    # FrogPilot backups data
    self._fp_backups_map = {}
    self._fp_backups_list = []

    # Toggle backups data
    self._toggle_backups_map = {}
    self._toggle_backups_list = []

    # Keyboard for text input
    self._keyboard = Keyboard()

    # Delete Driving Data Button
    self._delete_driving_data_control = FrogPilotButtonsControl(
      "DeleteDrivingData",
      "Delete Driving Data",
      "<b>Delete all stored driving footage and data</b> to free up storage space or to simply just erase driving data.",
      "",
      button_texts=["DELETE"],
    )
    self._delete_driving_data_control.set_click_callback(self._on_delete_driving_data_click)

    # Delete Error Logs Button
    self._delete_error_logs_control = FrogPilotButtonsControl(
      "DeleteErrorLogs",
      "Delete Error Logs",
      "<b>Delete collected error logs</b> to free up space and clear old crash records.",
      "",
      button_texts=["DELETE"],
    )
    self._delete_error_logs_control.set_click_callback(self._on_delete_error_logs_click)

    # Screen Recordings Buttons
    self._screen_recordings_control = FrogPilotButtonsControl(
      "ScreenRecordings",
      "Screen Recordings",
      "<b>Delete or rename screen recordings.</b>",
      "",
      button_texts=["DELETE", "DELETE ALL", "RENAME"],
    )
    self._screen_recordings_control.set_click_callback(self._on_screen_recordings_click)

    # FrogPilot Backups Buttons
    self._frogpilot_backups_control = FrogPilotButtonsControl(
      "FrogPilotBackups",
      "FrogPilot Backups",
      "<b>Create, delete, or restore FrogPilot backups.</b>",
      "",
      button_texts=["BACKUP", "DELETE", "DELETE ALL", "RESTORE"],
    )
    self._frogpilot_backups_control.set_click_callback(self._on_frogpilot_backups_click)

    # Toggle Backups Buttons
    self._toggle_backups_control = FrogPilotButtonsControl(
      "ToggleBackups",
      "Toggle Backups",
      "<b>Create, delete, or restore toggle backups.</b>",
      "",
      button_texts=["BACKUP", "DELETE", "DELETE ALL", "RESTORE"],
    )
    self._toggle_backups_control.set_click_callback(self._on_toggle_backups_click)

    # FrogPilot Stats Buttons
    self._stats_control = FrogPilotButtonsControl(
      "FrogPilotStats",
      "FrogPilot Stats",
      "<b>View your collected FrogPilot stats.</b>",
      "",
      button_texts=["RESET", "VIEW"],
    )
    self._stats_control.set_click_callback(self._on_stats_click)

    main_items = [
      self._delete_driving_data_control,
      self._delete_error_logs_control,
      self._screen_recordings_control,
      self._frogpilot_backups_control,
      self._toggle_backups_control,
      self._stats_control,
    ]

    self._main_scroller = Scroller(main_items, line_separator=True, spacing=0)
    self._stats_scroller = None
    self._stats_items = []

    ui_state.add_offroad_transition_callback(self._on_offroad_transition)

  def _on_offroad_transition(self):
    self._is_metric = self._params.get_bool("IsMetric")
    if self._show_stats:
      self._update_stats_labels()

  # ==================== DELETE DRIVING DATA ====================
  def _on_delete_driving_data_click(self, button_id: int):
    self._pending_action = "delete_driving_data"
    gui_app.set_modal_overlay(ConfirmDialog(
      "Delete all driving data and footage?",
      "Delete",
      "Cancel",
    ))

  def _do_delete_driving_data(self):
    def delete_thread():
      self._delete_driving_data_control.set_enabled(False)
      self._delete_driving_data_control.set_value("Deleting...")

      for path in DRIVING_DATA_PATHS:
        if not path.exists():
          continue

        for entry in path.iterdir():
          if entry.is_dir():
            try:
              preserve = os.getxattr(str(entry), b"user.preserve") == b"1"
            except OSError:
              preserve = False

            if not preserve:
              shutil.rmtree(entry, ignore_errors=True)

      self._delete_driving_data_control.set_value("Deleted!")
      time.sleep(2.5)

      self._delete_driving_data_control.set_value("")
      self._delete_driving_data_control.set_enabled(True)

    threading.Thread(target=delete_thread, daemon=True).start()

  # ==================== DELETE ERROR LOGS ====================
  def _on_delete_error_logs_click(self, button_id: int):
    self._pending_action = "delete_error_logs"
    gui_app.set_modal_overlay(ConfirmDialog(
      "Delete all error logs?",
      "Delete",
      "Cancel",
    ))

  def _do_delete_error_logs(self):
    def delete_thread():
      self._delete_error_logs_control.set_enabled(False)
      self._delete_error_logs_control.set_value("Deleting...")

      if ERROR_LOGS_PATH.exists():
        shutil.rmtree(ERROR_LOGS_PATH, ignore_errors=True)
      ERROR_LOGS_PATH.mkdir(parents=True, exist_ok=True)

      self._delete_error_logs_control.set_value("Deleted!")
      time.sleep(2.5)

      self._delete_error_logs_control.set_value("")
      self._delete_error_logs_control.set_enabled(True)

    threading.Thread(target=delete_thread, daemon=True).start()

  # ==================== SCREEN RECORDINGS ====================
  def _on_screen_recordings_click(self, button_id: int):
    SCREEN_RECORDINGS_PATH.mkdir(parents=True, exist_ok=True)

    recordings = []
    self._recordings_map = {}

    if SCREEN_RECORDINGS_PATH.exists():
      for f in SCREEN_RECORDINGS_PATH.iterdir():
        if f.is_file() and f.suffix.lower() == ".mp4":
          friendly, original = parse_recording_name(f.name)
          if friendly:
            recordings.append((friendly, original))
            self._recordings_map[friendly] = original

    recordings.sort(key=lambda x: x[1], reverse=True)
    self._recordings_list = [r[0] for r in recordings]

    if not self._recordings_list:
      gui_app.set_modal_overlay(alert_dialog("No screen recordings found."))
      return

    if button_id == 0:
      # DELETE single recording
      self._pending_action = "recording_delete_select"
      gui_app.set_modal_overlay(MultiOptionDialog(
        "Choose a screen recording to delete",
        self._recordings_list,
      ))

    elif button_id == 1:
      # DELETE ALL recordings
      self._pending_action = "recording_delete_all"
      gui_app.set_modal_overlay(ConfirmDialog(
        "Delete all screen recordings?",
        "Delete All",
        "Cancel",
      ))

    elif button_id == 2:
      # RENAME recording
      self._pending_action = "recording_rename_select"
      gui_app.set_modal_overlay(MultiOptionDialog(
        "Choose a screen recording to rename",
        self._recordings_list,
      ))

  def _do_delete_recording(self, selection: str):
    def delete_thread():
      self._screen_recordings_control.set_enabled(False)
      self._screen_recordings_control.set_value("Deleting...")
      self._screen_recordings_control.set_visible_button(1, False)
      self._screen_recordings_control.set_visible_button(2, False)

      filename = self._recordings_map.get(selection, "")
      if filename:
        filepath = SCREEN_RECORDINGS_PATH / filename
        if filepath.exists():
          filepath.unlink()

      self._screen_recordings_control.set_value("Deleted!")
      time.sleep(2.5)

      self._screen_recordings_control.set_value("")
      self._screen_recordings_control.set_enabled(True)
      self._screen_recordings_control.set_visible_button(1, True)
      self._screen_recordings_control.set_visible_button(2, True)

    threading.Thread(target=delete_thread, daemon=True).start()

  def _do_delete_all_recordings(self):
    def delete_thread():
      self._screen_recordings_control.set_enabled(False)
      self._screen_recordings_control.set_value("Deleting...")
      self._screen_recordings_control.set_visible_button(0, False)
      self._screen_recordings_control.set_visible_button(2, False)

      if SCREEN_RECORDINGS_PATH.exists():
        shutil.rmtree(SCREEN_RECORDINGS_PATH, ignore_errors=True)
      SCREEN_RECORDINGS_PATH.mkdir(parents=True, exist_ok=True)

      self._screen_recordings_control.set_value("Deleted!")
      time.sleep(2.5)

      self._screen_recordings_control.set_value("")
      self._screen_recordings_control.set_enabled(True)
      self._screen_recordings_control.set_visible_button(0, True)
      self._screen_recordings_control.set_visible_button(2, True)

    threading.Thread(target=delete_thread, daemon=True).start()

  def _do_rename_recording(self, selection: str, new_name: str):
    def rename_thread():
      self._screen_recordings_control.set_enabled(False)
      self._screen_recordings_control.set_value("Renaming...")
      self._screen_recordings_control.set_visible_button(0, False)
      self._screen_recordings_control.set_visible_button(1, False)

      old_filename = self._recordings_map.get(selection, "")
      new_filename = new_name.replace(" ", "_") + ".mp4"

      if old_filename:
        old_path = SCREEN_RECORDINGS_PATH / old_filename
        new_path = SCREEN_RECORDINGS_PATH / new_filename
        if old_path.exists() and not new_path.exists():
          old_path.rename(new_path)

      self._screen_recordings_control.set_value("Renamed!")
      time.sleep(2.5)

      self._screen_recordings_control.set_value("")
      self._screen_recordings_control.set_enabled(True)
      self._screen_recordings_control.set_visible_button(0, True)
      self._screen_recordings_control.set_visible_button(1, True)

    threading.Thread(target=rename_thread, daemon=True).start()

  # ==================== FROGPILOT BACKUPS ====================
  def _on_frogpilot_backups_click(self, button_id: int):
    FROGPILOT_BACKUPS.mkdir(parents=True, exist_ok=True)

    backups = []
    self._fp_backups_map = {}

    for f in FROGPILOT_BACKUPS.iterdir():
      if f.is_file() and f.name.endswith(".tar.zst") and "in_progress" not in f.name:
        mod_time = datetime.fromtimestamp(f.stat().st_mtime)
        friendly, original = parse_backup_name(f.name, mod_time)
        backups.append((friendly, original, mod_time))
        self._fp_backups_map[friendly] = original

    backups.sort(key=lambda x: x[2], reverse=True)
    self._fp_backups_list = [b[0] for b in backups]

    if button_id == 0:
      # CREATE BACKUP
      self._pending_action = "fp_backup_create"
      self._keyboard.reset()
      self._keyboard.set_title("Name your backup", "Backup Name")
      gui_app.set_modal_overlay(self._keyboard, callback=self._on_keyboard_result)

    elif button_id == 1:
      # DELETE backup
      if not self._fp_backups_list:
        gui_app.set_modal_overlay(alert_dialog("No backups found."))
        return
      self._pending_action = "fp_backup_delete_select"
      gui_app.set_modal_overlay(MultiOptionDialog(
        "Choose a backup to delete",
        self._fp_backups_list,
      ))

    elif button_id == 2:
      # DELETE ALL backups
      self._pending_action = "fp_backup_delete_all"
      gui_app.set_modal_overlay(ConfirmDialog(
        "Delete all FrogPilot backups?",
        "Delete All",
        "Cancel",
      ))

    elif button_id == 3:
      # RESTORE backup
      if not self._fp_backups_list:
        gui_app.set_modal_overlay(alert_dialog("No backups found."))
        return
      self._pending_action = "fp_backup_restore_select"
      gui_app.set_modal_overlay(MultiOptionDialog(
        "Choose a backup to restore",
        self._fp_backups_list,
      ))

  def _do_create_fp_backup(self, name: str):
    def backup_thread():
      self._frogpilot_backups_control.set_enabled(False)
      self._frogpilot_backups_control.set_value("Backing up...")
      self._frogpilot_backups_control.set_visible_button(1, False)
      self._frogpilot_backups_control.set_visible_button(2, False)
      self._frogpilot_backups_control.set_visible_button(3, False)

      backup_name = name.replace(" ", "_") + ".tar.zst"
      backup_path = FROGPILOT_BACKUPS / backup_name

      subprocess.run(
        f"tar --use-compress-program=zstd -cf {backup_path} /data/openpilot",
        shell=True,
        capture_output=True
      )

      self._frogpilot_backups_control.set_value("Backup created!")
      time.sleep(2.5)

      self._frogpilot_backups_control.set_value("")
      self._frogpilot_backups_control.set_enabled(True)
      self._frogpilot_backups_control.set_visible_button(1, True)
      self._frogpilot_backups_control.set_visible_button(2, True)
      self._frogpilot_backups_control.set_visible_button(3, True)

    threading.Thread(target=backup_thread, daemon=True).start()

  def _do_delete_fp_backup(self, selection: str):
    def delete_thread():
      self._frogpilot_backups_control.set_enabled(False)
      self._frogpilot_backups_control.set_value("Deleting...")
      self._frogpilot_backups_control.set_visible_button(0, False)
      self._frogpilot_backups_control.set_visible_button(2, False)
      self._frogpilot_backups_control.set_visible_button(3, False)

      filename = self._fp_backups_map.get(selection, "")
      if filename:
        filepath = FROGPILOT_BACKUPS / filename
        if filepath.exists():
          filepath.unlink()

      self._frogpilot_backups_control.set_value("Deleted!")
      time.sleep(2.5)

      self._frogpilot_backups_control.set_value("")
      self._frogpilot_backups_control.set_enabled(True)
      self._frogpilot_backups_control.set_visible_button(0, True)
      self._frogpilot_backups_control.set_visible_button(2, True)
      self._frogpilot_backups_control.set_visible_button(3, True)

    threading.Thread(target=delete_thread, daemon=True).start()

  def _do_delete_all_fp_backups(self):
    def delete_thread():
      self._frogpilot_backups_control.set_enabled(False)
      self._frogpilot_backups_control.set_value("Deleting...")
      self._frogpilot_backups_control.set_visible_button(0, False)
      self._frogpilot_backups_control.set_visible_button(1, False)
      self._frogpilot_backups_control.set_visible_button(3, False)

      if FROGPILOT_BACKUPS.exists():
        shutil.rmtree(FROGPILOT_BACKUPS, ignore_errors=True)
      FROGPILOT_BACKUPS.mkdir(parents=True, exist_ok=True)

      self._frogpilot_backups_control.set_value("Deleted!")
      time.sleep(2.5)

      self._frogpilot_backups_control.set_value("")
      self._frogpilot_backups_control.set_enabled(True)
      self._frogpilot_backups_control.set_visible_button(0, True)
      self._frogpilot_backups_control.set_visible_button(1, True)
      self._frogpilot_backups_control.set_visible_button(3, True)

    threading.Thread(target=delete_thread, daemon=True).start()

  def _do_restore_fp_backup(self, selection: str):
    def restore_thread():
      self._frogpilot_backups_control.set_enabled(False)
      self._frogpilot_backups_control.set_value("Restoring...")
      self._frogpilot_backups_control.set_visible_button(0, False)
      self._frogpilot_backups_control.set_visible_button(1, False)
      self._frogpilot_backups_control.set_visible_button(2, False)

      filename = self._fp_backups_map.get(selection, "")
      if filename:
        backup_path = FROGPILOT_BACKUPS / filename
        subprocess.run(
          f"rm -rf /data/openpilot/* && tar --use-compress-program=zstd -xf {backup_path} -C /",
          shell=True,
          capture_output=True
        )
        # Create marker file for backup restore
        Path("/cache/on_backup").touch()

      self._frogpilot_backups_control.set_value("Restored!")
      time.sleep(2.5)

      self._frogpilot_backups_control.set_value("Rebooting...")
      time.sleep(2.5)

      HARDWARE.reboot()

    threading.Thread(target=restore_thread, daemon=True).start()

  # ==================== TOGGLE BACKUPS ====================
  def _on_toggle_backups_click(self, button_id: int):
    TOGGLE_BACKUPS.mkdir(parents=True, exist_ok=True)

    backups = []
    self._toggle_backups_map = {}

    for d in TOGGLE_BACKUPS.iterdir():
      if d.is_dir() and "in_progress" not in d.name:
        friendly, original = parse_toggle_backup_name(d.name)
        backups.append((friendly, original))
        self._toggle_backups_map[friendly] = original

    backups.sort(key=lambda x: x[1], reverse=True)
    self._toggle_backups_list = [b[0] for b in backups]

    if button_id == 0:
      # CREATE BACKUP
      self._pending_action = "toggle_backup_create"
      self._keyboard.reset()
      self._keyboard.set_title("Name your backup", "Backup Name")
      gui_app.set_modal_overlay(self._keyboard, callback=self._on_keyboard_result)

    elif button_id == 1:
      # DELETE backup
      if not self._toggle_backups_list:
        gui_app.set_modal_overlay(alert_dialog("No backups found."))
        return
      self._pending_action = "toggle_backup_delete_select"
      gui_app.set_modal_overlay(MultiOptionDialog(
        "Choose a backup to delete",
        self._toggle_backups_list,
      ))

    elif button_id == 2:
      # DELETE ALL backups
      self._pending_action = "toggle_backup_delete_all"
      gui_app.set_modal_overlay(ConfirmDialog(
        "Delete all toggle backups?",
        "Delete All",
        "Cancel",
      ))

    elif button_id == 3:
      # RESTORE backup
      if not self._toggle_backups_list:
        gui_app.set_modal_overlay(alert_dialog("No backups found."))
        return
      self._pending_action = "toggle_backup_restore_select"
      gui_app.set_modal_overlay(MultiOptionDialog(
        "Choose a backup to restore",
        self._toggle_backups_list,
      ))

  def _do_create_toggle_backup(self, name: str):
    def backup_thread():
      self._toggle_backups_control.set_enabled(False)
      self._toggle_backups_control.set_value("Backing up...")
      self._toggle_backups_control.set_visible_button(1, False)
      self._toggle_backups_control.set_visible_button(2, False)
      self._toggle_backups_control.set_visible_button(3, False)

      backup_name = name.replace(" ", "_")
      backup_path = TOGGLE_BACKUPS / backup_name

      subprocess.run(
        f"cp -r /data/params/d/ {backup_path}",
        shell=True,
        capture_output=True
      )

      self._toggle_backups_control.set_value("Backup created!")
      time.sleep(2.5)

      self._toggle_backups_control.set_value("")
      self._toggle_backups_control.set_enabled(True)
      self._toggle_backups_control.set_visible_button(1, True)
      self._toggle_backups_control.set_visible_button(2, True)
      self._toggle_backups_control.set_visible_button(3, True)

    threading.Thread(target=backup_thread, daemon=True).start()

  def _do_delete_toggle_backup(self, selection: str):
    def delete_thread():
      self._toggle_backups_control.set_enabled(False)
      self._toggle_backups_control.set_value("Deleting...")
      self._toggle_backups_control.set_visible_button(0, False)
      self._toggle_backups_control.set_visible_button(2, False)
      self._toggle_backups_control.set_visible_button(3, False)

      dirname = self._toggle_backups_map.get(selection, "")
      if dirname:
        dirpath = TOGGLE_BACKUPS / dirname
        if dirpath.exists():
          shutil.rmtree(dirpath, ignore_errors=True)

      self._toggle_backups_control.set_value("Deleted!")
      time.sleep(2.5)

      self._toggle_backups_control.set_value("")
      self._toggle_backups_control.set_enabled(True)
      self._toggle_backups_control.set_visible_button(0, True)
      self._toggle_backups_control.set_visible_button(2, True)
      self._toggle_backups_control.set_visible_button(3, True)

    threading.Thread(target=delete_thread, daemon=True).start()

  def _do_delete_all_toggle_backups(self):
    def delete_thread():
      self._toggle_backups_control.set_enabled(False)
      self._toggle_backups_control.set_value("Deleting...")
      self._toggle_backups_control.set_visible_button(0, False)
      self._toggle_backups_control.set_visible_button(1, False)
      self._toggle_backups_control.set_visible_button(3, False)

      if TOGGLE_BACKUPS.exists():
        shutil.rmtree(TOGGLE_BACKUPS, ignore_errors=True)
      TOGGLE_BACKUPS.mkdir(parents=True, exist_ok=True)

      self._toggle_backups_control.set_value("Deleted!")
      time.sleep(2.5)

      self._toggle_backups_control.set_value("")
      self._toggle_backups_control.set_enabled(True)
      self._toggle_backups_control.set_visible_button(0, True)
      self._toggle_backups_control.set_visible_button(1, True)
      self._toggle_backups_control.set_visible_button(3, True)

    threading.Thread(target=delete_thread, daemon=True).start()

  def _do_restore_toggle_backup(self, selection: str):
    def restore_thread():
      self._toggle_backups_control.set_enabled(False)
      self._toggle_backups_control.set_value("Restoring...")
      self._toggle_backups_control.set_visible_button(0, False)
      self._toggle_backups_control.set_visible_button(1, False)
      self._toggle_backups_control.set_visible_button(2, False)

      dirname = self._toggle_backups_map.get(selection, "")
      if dirname:
        backup_path = TOGGLE_BACKUPS / dirname
        subprocess.run(
          f"cp -r {backup_path}/* /data/params/d/",
          shell=True,
          capture_output=True
        )
        update_frogpilot_toggles()

      self._toggle_backups_control.set_value("Restored!")
      time.sleep(2.5)

      self._toggle_backups_control.set_value("")
      self._toggle_backups_control.set_enabled(True)
      self._toggle_backups_control.set_visible_button(0, True)
      self._toggle_backups_control.set_visible_button(1, True)
      self._toggle_backups_control.set_visible_button(2, True)

    threading.Thread(target=restore_thread, daemon=True).start()

  # ==================== STATS ====================
  def _on_stats_click(self, button_id: int):
    if button_id == 0:
      # RESET stats
      self._pending_action = "stats_reset"
      gui_app.set_modal_overlay(ConfirmDialog(
        "Are you sure you want to reset all of your FrogPilot stats?",
        "Reset",
        "Cancel",
      ))
    elif button_id == 1:
      # VIEW stats
      self._show_stats = True
      self._update_stats_labels()

  def _do_reset_stats(self):
    self._params.remove("FrogPilotStats")
    if self._show_stats:
      self._update_stats_labels()

  def _close_stats(self):
    self._show_stats = False

  # ==================== DIALOG RESULT HANDLING ====================
  def _on_keyboard_result(self, result: DialogResult):
    """Callback for keyboard modal overlay."""
    self.handle_dialog_result(result, self._keyboard.text)

  def handle_dialog_result(self, result: DialogResult, selection: str = ""):
    """Handle dialog results from modal overlays."""
    action = self._pending_action
    self._pending_action = None

    if result != DialogResult.CONFIRM:
      return

    # Delete driving data
    if action == "delete_driving_data":
      self._do_delete_driving_data()

    # Delete error logs
    elif action == "delete_error_logs":
      self._do_delete_error_logs()

    # Screen recordings - delete single
    elif action == "recording_delete_select" and selection:
      self._pending_data["recording_selection"] = selection
      self._pending_action = "recording_delete_confirm"
      gui_app.set_modal_overlay(ConfirmDialog(
        "Delete this screen recording?",
        "Delete",
        "Cancel",
      ))
    elif action == "recording_delete_confirm":
      selection = self._pending_data.pop("recording_selection", "")
      if selection:
        self._do_delete_recording(selection)

    # Screen recordings - delete all
    elif action == "recording_delete_all":
      self._do_delete_all_recordings()

    # Screen recordings - rename
    elif action == "recording_rename_select" and selection:
      self._pending_data["recording_selection"] = selection
      self._pending_action = "recording_rename_input"
      self._keyboard.reset()
      self._keyboard.set_title("Enter a new name", "Rename Screen Recording")
      gui_app.set_modal_overlay(self._keyboard, callback=self._on_keyboard_result)
    elif action == "recording_rename_input" and selection:
      old_selection = self._pending_data.pop("recording_selection", "")
      new_name = selection.strip()
      if old_selection and new_name:
        # Check for duplicate name
        new_filename = new_name.replace(" ", "_") + ".mp4"
        existing_files = [f.name for f in SCREEN_RECORDINGS_PATH.iterdir() if f.is_file()]
        if new_filename in existing_files:
          gui_app.set_modal_overlay(alert_dialog("Name already in use. Please choose a different name!"))
        else:
          self._do_rename_recording(old_selection, new_name)

    # FrogPilot backups - create
    elif action == "fp_backup_create" and selection:
      backup_name = selection.strip().replace(" ", "_")
      if backup_name:
        existing_files = [f.name for f in FROGPILOT_BACKUPS.iterdir() if f.is_file()]
        if backup_name + ".tar.zst" in existing_files:
          gui_app.set_modal_overlay(alert_dialog("Name already in use. Please choose a different name!"))
        else:
          self._do_create_fp_backup(backup_name)

    # FrogPilot backups - delete single
    elif action == "fp_backup_delete_select" and selection:
      self._pending_data["fp_backup_selection"] = selection
      self._pending_action = "fp_backup_delete_confirm"
      gui_app.set_modal_overlay(ConfirmDialog(
        "Delete this backup?",
        "Delete",
        "Cancel",
      ))
    elif action == "fp_backup_delete_confirm":
      selection = self._pending_data.pop("fp_backup_selection", "")
      if selection:
        self._do_delete_fp_backup(selection)

    # FrogPilot backups - delete all
    elif action == "fp_backup_delete_all":
      self._do_delete_all_fp_backups()

    # FrogPilot backups - restore
    elif action == "fp_backup_restore_select" and selection:
      self._pending_data["fp_backup_selection"] = selection
      self._pending_action = "fp_backup_restore_confirm"
      gui_app.set_modal_overlay(ConfirmDialog(
        "Restore this backup? This will overwrite your current installation and reboot the device.",
        "Restore",
        "Cancel",
      ))
    elif action == "fp_backup_restore_confirm":
      selection = self._pending_data.pop("fp_backup_selection", "")
      if selection:
        self._do_restore_fp_backup(selection)

    # Toggle backups - create
    elif action == "toggle_backup_create" and selection:
      backup_name = selection.strip().replace(" ", "_")
      if backup_name:
        existing_dirs = [d.name for d in TOGGLE_BACKUPS.iterdir() if d.is_dir()]
        if backup_name in existing_dirs:
          gui_app.set_modal_overlay(alert_dialog("Name already in use. Please choose a different name!"))
        else:
          self._do_create_toggle_backup(backup_name)

    # Toggle backups - delete single
    elif action == "toggle_backup_delete_select" and selection:
      self._pending_data["toggle_backup_selection"] = selection
      self._pending_action = "toggle_backup_delete_confirm"
      gui_app.set_modal_overlay(ConfirmDialog(
        "Delete this backup?",
        "Delete",
        "Cancel",
      ))
    elif action == "toggle_backup_delete_confirm":
      selection = self._pending_data.pop("toggle_backup_selection", "")
      if selection:
        self._do_delete_toggle_backup(selection)

    # Toggle backups - delete all
    elif action == "toggle_backup_delete_all":
      self._do_delete_all_toggle_backups()

    # Toggle backups - restore
    elif action == "toggle_backup_restore_select" and selection:
      self._pending_data["toggle_backup_selection"] = selection
      self._pending_action = "toggle_backup_restore_confirm"
      gui_app.set_modal_overlay(ConfirmDialog(
        "Restore this backup? This will overwrite your current settings!",
        "Restore",
        "Cancel",
      ))
    elif action == "toggle_backup_restore_confirm":
      selection = self._pending_data.pop("toggle_backup_selection", "")
      if selection:
        self._do_restore_toggle_backup(selection)

    # Stats reset
    elif action == "stats_reset":
      self._do_reset_stats()

  # ==================== STATS DISPLAY ====================
  def _format_number(self, number):
    return f"{number:,.0f}" if isinstance(number, float) else f"{number:,}"

  def _format_distance(self, meters):
    if self._is_metric:
      value = meters / 1000.0
      unit = "kilometer" if value == 1.0 else "kilometers"
    else:
      value = meters * METER_TO_MILE
      unit = "mile" if value == 1.0 else "miles"
    return f"{self._format_number(round(value))} {unit}"

  def _format_time(self, seconds):
    seconds = int(seconds)
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60

    parts = []
    if days > 0:
      parts.append(f"{self._format_number(days)} {'day' if days == 1 else 'days'}")
    if hours > 0 or days > 0:
      parts.append(f"{self._format_number(hours)} {'hour' if hours == 1 else 'hours'}")
    parts.append(f"{self._format_number(minutes)} {'minute' if minutes == 1 else 'minutes'}")

    return " ".join(parts)

  def _update_stats_labels(self):
    self._stats_items = []

    try:
      stats_data = self._params.get("FrogPilotStats")
      stats = json.loads(stats_data) if stats_data else {}
    except (json.JSONDecodeError, TypeError):
      stats = {}

    tracked_time = stats.get("TrackedTime", 0.0)

    sorted_keys = sorted(KEY_MAP.keys(), key=lambda k: KEY_MAP[k][0].lower())

    for key in sorted_keys:
      if key in IGNORED_KEYS:
        continue

      label_text, stat_type = KEY_MAP[key]
      value = stats.get(key, 0)

      if key == "AEBEvents":
        total_events = stats.get("TotalEvents", {})
        count = total_events.get("stockAeb", 0) + total_events.get("fcw", 0)
        trimmed = label_text.replace("Total ", "", 1) if label_text.startswith("Total ") else label_text
        display = f"{self._format_number(count)} {trimmed}"
        self._stats_items.append(ListItem(title=label_text, action_item=TextAction(display, color=ITEM_TEXT_VALUE_COLOR)))

      elif key == "CruiseSpeedTimes" and isinstance(value, dict):
        max_time = -1
        best_speed = ""
        for speed_key, time_val in value.items():
          if time_val > max_time:
            best_speed = speed_key
            max_time = time_val

        if best_speed:
          speed_val = float(best_speed)
          if self._is_metric:
            display_speed = f"{round(speed_val * MS_TO_KPH)} km/h"
          else:
            display_speed = f"{round(speed_val * MS_TO_MPH)} mph"
          display = f"{display_speed} ({self._format_time(max_time)})"
          self._stats_items.append(ListItem(title=label_text, action_item=TextAction(display, color=ITEM_TEXT_VALUE_COLOR)))

      elif stat_type == "parent" and isinstance(value, dict):
        self._stats_items.append(ListItem(title=label_text))

        if key == "RandomEvents":
          sub_keys = sorted(RANDOM_EVENTS_MAP.keys(), key=lambda k: RANDOM_EVENTS_MAP.get(k, k).lower())
        else:
          sub_keys = sorted(value.keys(), key=lambda k: k.lower())

        for subkey in sub_keys:
          if subkey == "Unknown":
            continue

          if key == "ModelTimes":
            display_subkey = clean_model_name(subkey)
          elif key == "RandomEvents":
            display_subkey = RANDOM_EVENTS_MAP.get(subkey, subkey)
          elif key == "WeatherTimes":
            display_subkey = subkey.capitalize()
          else:
            display_subkey = subkey

          if key.endswith("Times"):
            subvalue = self._format_time(value.get(subkey, 0))
          else:
            subvalue = self._format_number(value.get(subkey, 0))

          self._stats_items.append(ListItem(title=f"     {display_subkey}", action_item=TextAction(subvalue, color=ITEM_TEXT_VALUE_COLOR)))

      else:
        if stat_type == "accel":
          display = f"{value:.2f} m/s²"
        elif stat_type == "count":
          trimmed = label_text.replace("Total ", "", 1) if label_text.startswith("Total ") else label_text
          display = f"{self._format_number(int(value))} {trimmed}"
        elif stat_type == "distance":
          display = self._format_distance(float(value))
        elif stat_type in ("time", "timePercent"):
          display = self._format_time(float(value))
        else:
          display = str(value) if value else "0"

        self._stats_items.append(ListItem(title=label_text, action_item=TextAction(display, color=ITEM_TEXT_VALUE_COLOR)))

        if stat_type == "timePercent" and tracked_time > 0:
          percent = int((float(value) * 100.0) / tracked_time)
          self._stats_items.append(ListItem(title=f"% of {label_text}", action_item=TextAction(f"{self._format_number(percent)}%", color=ITEM_TEXT_VALUE_COLOR)))

    self._stats_scroller = Scroller(self._stats_items, line_separator=True, spacing=0)

  # ==================== LIFECYCLE ====================
  def show_event(self):
    super().show_event()
    self._main_scroller.show_event()
    self._is_metric = self._params.get_bool("IsMetric")
    self._show_stats = False

  def hide_event(self):
    super().hide_event()
    self._show_stats = False

  def _render(self, rect):
    if self._show_stats and self._stats_scroller:
      self._stats_scroller.render(rect)
    else:
      self._main_scroller.render(rect)
