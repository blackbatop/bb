import json
import threading
import time

from pathlib import Path

from openpilot.common.params import Params
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.hardware import HARDWARE
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.confirm_dialog import ConfirmDialog, alert_dialog, DialogResult
from openpilot.system.ui.widgets.keyboard import Keyboard
from openpilot.system.ui.widgets.list_view import ListItem, ToggleAction, ButtonAction, TextAction, ITEM_TEXT_VALUE_COLOR
from openpilot.system.ui.widgets.option_dialog import MultiOptionDialog
from openpilot.system.ui.widgets.scroller_tici import Scroller

from openpilot.frogpilot.common.frogpilot_variables import update_frogpilot_toggles
from openpilot.frogpilot.system.ui.widgets.frogpilot_controls import (
  FrogPilotButtonsControl,
)

ERROR_LOG_PATH = Path("/data/error_logs/error.txt")

# Keys that should NOT be reset
EXCLUDED_KEYS = {
  "AvailableModels",
  "AvailableModelNames",
  "FrogPilotStats",
  "GithubSshKeys",
  "GithubUsername",
  "MapBoxRequests",
  "ModelDrivesAndScores",
  "OverpassRequests",
  "SpeedLimits",
  "SpeedLimitsFiltered",
  "UpdaterAvailableBranches",
}

REPORT_MESSAGES = [
  "Acceleration feels harsh or jerky",
  "An alert was unclear and I'm not sure what it meant",
  "Braking is too sudden or uncomfortable",
  "I'm not sure if this is normal or a bug:",
  "My steering wheel buttons aren't working",
  "openpilot disengages when I don't expect it",
  "openpilot feels sluggish or slow to respond",
  "Something else (please describe)",
]


class FrogPilotUtilitiesPanel(Widget):
  def __init__(self):
    super().__init__()

    self._params = Params()
    self._params_memory = Params("", True)
    self._toggles = {}

    # State tracking
    self._flash_status = ""
    self._reset_status = ""
    self._online = False

    # Pending dialog action tracking
    self._pending_action = None  # "flash_panda", "report_select", "report_extra", "report_discord", "reset_default", "reset_stock"
    self._pending_data = {}

    # Keyboard for text input
    self._keyboard = Keyboard()

    self._build_panel()

    ui_state.add_offroad_transition_callback(self._update_toggles)

  def _build_panel(self):
    # Debug Mode Toggle
    self._debug_mode_item = ListItem(
      title="Debug Mode",
      description="<b>Use all of FrogPilot's developer metrics on your next drive</b> to diagnose issues and improve bug reports.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("DebugMode"),
        callback=lambda state: self._simple_toggle("DebugMode", state),
      ),
    )

    # Flash Panda Button
    self._flash_panda_control = FrogPilotButtonsControl(
      "Flash Panda",
      "<b>Flash the latest, official firmware onto your Panda device</b> to restore core functionality, fix bugs, or ensure you have the most up-to-date software.",
      "",
      button_texts=["FLASH"],
    )
    self._flash_panda_control.set_click_callback(self._on_flash_panda_click)

    # Force Drive State Buttons
    self._force_drive_state_control = FrogPilotButtonsControl(
      "Force Drive State",
      "<b>Force openpilot to be offroad or onroad.</b>",
      "",
      button_texts=["OFFROAD", "ONROAD", "OFF"],
    )
    self._force_drive_state_control.set_click_callback(self._on_force_drive_state_click)
    self._force_drive_state_control.set_checked_button(2)

    # Report Issue Button
    self._report_issue_control = FrogPilotButtonsControl(
      "Report a Bug or an Issue",
      "<b>Send a bug report</b> so we can help fix the problem!",
      "",
      button_texts=["REPORT"],
    )
    self._report_issue_control.set_click_callback(self._on_report_issue_click)

    # Reset Toggles to Default Button
    self._reset_default_control = FrogPilotButtonsControl(
      "Reset Toggles to Default",
      "<b>Reset all toggles to their default values.</b>",
      "",
      button_texts=["RESET"],
    )
    self._reset_default_control.set_click_callback(self._on_reset_default_click)

    # Reset Toggles to Stock Button
    self._reset_stock_control = FrogPilotButtonsControl(
      "Reset Toggles to Stock openpilot",
      "<b>Reset all toggles to match stock openpilot.</b>",
      "",
      button_texts=["RESET"],
    )
    self._reset_stock_control.set_click_callback(self._on_reset_stock_click)

    items = [
      self._debug_mode_item,
      self._flash_panda_control,
      self._force_drive_state_control,
      self._report_issue_control,
      self._reset_default_control,
      self._reset_stock_control,
    ]

    self._toggles["DebugMode"] = self._debug_mode_item
    self._toggles["FlashPanda"] = self._flash_panda_control
    self._toggles["ForceDriveState"] = self._force_drive_state_control
    self._toggles["ReportIssue"] = self._report_issue_control
    self._toggles["ResetDefault"] = self._reset_default_control
    self._toggles["ResetStock"] = self._reset_stock_control

    self._scroller = Scroller(items, line_separator=True, spacing=0)

  def _simple_toggle(self, param: str, state: bool):
    self._params.put_bool(param, state)
    update_frogpilot_toggles()

  def _on_flash_panda_click(self, button_id: int):
    self._pending_action = "flash_panda"
    gui_app.set_modal_overlay(ConfirmDialog(
      "Are you sure you want to flash the Panda firmware?",
      "Flash",
      "Cancel",
    ))

  def _do_flash_panda(self):
    """Flash panda firmware in a background thread."""
    def flash_thread():
      self._flash_panda_control.set_enabled(False)
      self._flash_panda_control.set_value("Flashing...")

      self._params_memory.put_bool("FlashPanda", True)

      # Wait for flash to complete
      while self._params_memory.get_bool("FlashPanda"):
        time.sleep(0.05)  # UI_FREQ equivalent

      self._flash_panda_control.set_value("Flashed!")
      time.sleep(2.5)

      self._flash_panda_control.set_value("Rebooting...")
      time.sleep(2.5)

      HARDWARE.reboot()

    threading.Thread(target=flash_thread, daemon=True).start()

  def _on_force_drive_state_click(self, button_id: int):
    if button_id == 0:
      # OFFROAD
      self._params.put_bool("ForceOffroad", True)
      self._params.put_bool("ForceOnroad", False)
    elif button_id == 1:
      # ONROAD - copy persistent car params
      car_params = self._params.get("CarParamsPersistent")
      if car_params:
        self._params.put("CarParams", car_params)

      frogpilot_car_params = self._params.get("FrogPilotCarParamsPersistent")
      if frogpilot_car_params:
        self._params.put("FrogPilotCarParams", frogpilot_car_params)

      self._params.put_bool("ForceOffroad", False)
      self._params.put_bool("ForceOnroad", True)
    elif button_id == 2:
      # OFF
      self._params.put_bool("ForceOffroad", False)
      self._params.put_bool("ForceOnroad", False)

    update_frogpilot_toggles()

  def _on_report_issue_click(self, button_id: int):
    # Check if online (would need to be wired up properly to frogpilot_scene.online)
    # For now, we'll proceed with the report flow

    # Build report messages list
    messages = list(REPORT_MESSAGES)

    # Add crash option if error log exists
    if ERROR_LOG_PATH.exists():
      messages.insert(0, "I saw an alert that said \"openpilot crashed\"")

    self._pending_action = "report_select"
    self._pending_data = {}
    gui_app.set_modal_overlay(MultiOptionDialog(
      "What's going on?",
      messages,
    ))

  def _on_reset_default_click(self, button_id: int):
    self._pending_action = "reset_default"
    gui_app.set_modal_overlay(ConfirmDialog(
      "Are you sure you want to reset all toggles to their default values?",
      "Reset",
      "Cancel",
    ))

  def _on_reset_stock_click(self, button_id: int):
    self._pending_action = "reset_stock"
    gui_app.set_modal_overlay(ConfirmDialog(
      "Are you sure you want to reset all toggles to match stock openpilot?",
      "Reset",
      "Cancel",
    ))

  def _do_reset_toggles(self, use_stock: bool):
    """Reset toggles in a background thread."""
    control = self._reset_stock_control if use_stock else self._reset_default_control

    def reset_thread():
      control.set_enabled(False)
      control.set_value("Resetting...")

      all_keys = self._params.all_keys()

      for key in all_keys:
        if key in EXCLUDED_KEYS:
          continue

        try:
          if use_stock:
            stock_value = self._params.get_stock_value(key)
            if stock_value is not None:
              self._params.put(key, stock_value)
          else:
            default_value = self._params.get_key_default_value(key)
            if default_value is not None:
              self._params.put(key, default_value)
        except Exception:
          # Skip keys that don't have default/stock values
          pass

      update_frogpilot_toggles()

      control.set_value("Reset!")
      time.sleep(2.5)

      control.set_value("")
      control.set_enabled(True)

    threading.Thread(target=reset_thread, daemon=True).start()

  def _on_keyboard_result(self, result: DialogResult):
    """Callback for keyboard modal overlay."""
    self.handle_dialog_result(result, self._keyboard.text)

  def handle_dialog_result(self, result: DialogResult, selection: str = ""):
    """Handle dialog results for all pending actions."""
    action = self._pending_action
    self._pending_action = None

    if action == "flash_panda":
      if result == DialogResult.CONFIRM:
        self._do_flash_panda()

    elif action == "report_select":
      # Report issue - first dialog (issue selection)
      if result != DialogResult.CONFIRM or not selection:
        self._pending_data = {}
        return

      self._pending_data["selected_issue"] = selection

      # Check if we need extra input
      if "crashed" in selection.lower() or "not sure" in selection.lower() or "something else" in selection.lower():
        self._pending_action = "report_extra"
        self._keyboard.reset()
        self._keyboard.set_title("Please describe what's happening")
        gui_app.set_modal_overlay(self._keyboard, callback=self._on_keyboard_result)
      else:
        # Skip to discord username
        self._pending_action = "report_discord"
        current_discord = self._params.get("DiscordUsername", encoding="utf-8") or ""
        self._keyboard.reset()
        self._keyboard.set_title("What's your Discord username?")
        self._keyboard.set_text(current_discord)
        gui_app.set_modal_overlay(self._keyboard, callback=self._on_keyboard_result)

    elif action == "report_extra":
      # Extra description for the issue
      if result != DialogResult.CONFIRM or not selection:
        self._pending_data = {}
        return

      # Append extra description to selected issue
      self._pending_data["selected_issue"] += " \u2014 " + selection.strip()

      # Now get discord username
      self._pending_action = "report_discord"
      current_discord = self._params.get("DiscordUsername", encoding="utf-8") or ""
      self._keyboard.reset()
      self._keyboard.set_title("What's your Discord username?")
      self._keyboard.set_text(current_discord)
      gui_app.set_modal_overlay(self._keyboard, callback=self._on_keyboard_result)

    elif action == "report_discord":
      # Discord username input
      discord_user = selection.strip() if result == DialogResult.CONFIRM else ""

      # Create report data
      report_data = {
        "DiscordUser": discord_user,
        "Issue": self._pending_data.get("selected_issue", ""),
      }

      # Save discord username and report
      if discord_user:
        self._params.put_nonblocking("DiscordUsername", discord_user)
      self._params_memory.put("IssueReported", json.dumps(report_data))

      self._pending_data = {}

      # Show confirmation
      gui_app.set_modal_overlay(alert_dialog(
        "Report Sent! Thanks for letting us know!"
      ))

    elif action == "reset_default":
      if result == DialogResult.CONFIRM:
        self._do_reset_toggles(use_stock=False)

    elif action == "reset_stock":
      if result == DialogResult.CONFIRM:
        self._do_reset_toggles(use_stock=True)

  def _update_toggles(self):
    # Report Issue button only visible for FrogAI repo
    git_remote = self._params.get("GitRemote", encoding="utf-8") or ""
    is_frogai = git_remote.lower() == "https://github.com/frogai/openpilot.git"
    if hasattr(self._report_issue_control, "set_visible"):
      self._report_issue_control.set_visible(is_frogai)

  def show_event(self):
    super().show_event()
    self._scroller.show_event()
    self._update_toggles()

  def _render(self, rect):
    self._scroller.render(rect)
