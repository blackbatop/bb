import json
import threading
import time

from datetime import date, datetime
from enum import IntEnum
from pathlib import Path

from openpilot.common.params import Params
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.confirm_dialog import ConfirmDialog, alert_dialog, DialogResult
from openpilot.system.ui.widgets.keyboard import Keyboard
from openpilot.system.ui.widgets.list_view import ListItem, ToggleAction, ButtonAction, TextAction, ITEM_TEXT_VALUE_COLOR
from openpilot.system.ui.widgets.scroller_tici import Scroller

from openpilot.frogpilot.common.frogpilot_variables import update_frogpilot_toggles
from openpilot.frogpilot.system.ui.widgets.frogpilot_controls import (
  FrogPilotButtonsControl,
  FrogPilotButtonControl,
)


class SubPanel(IntEnum):
  MAIN = 0
  INSTRUCTIONS = 1


class FrogPilotNavigationPanel(Widget):
  def __init__(self):
    super().__init__()

    self._current_panel = SubPanel.MAIN
    self._params = Params()
    self._params_memory = Params("", True)
    self._toggles = {}
    self._tuning_level = 0

    # State tracking
    self._mapbox_public_key_set = False
    self._mapbox_secret_key_set = False
    self._online = False
    self._parked = True
    self._started = False
    self._updating_limits = False

    # Pending dialog action tracking
    self._pending_action = None  # "add_public_key", "remove_public_key", "add_secret_key", "remove_secret_key", "cancel_update", "start_update"
    self._pending_data = {}

    # Keyboard for text input
    self._keyboard = Keyboard()

    self._build_panel()

    ui_state.add_offroad_transition_callback(self._update_toggles)

  def _build_panel(self):
    # IP Label
    self._ip_label_item = ListItem(
      title="Manage Your Settings At",
      action_item=TextAction(lambda: self._get_ip_address(), color=ITEM_TEXT_VALUE_COLOR),
    )

    # Public Mapbox Key Control
    self._public_mapbox_control = FrogPilotButtonsControl(
      "Public Mapbox Key",
      "<b>Manage your Public Mapbox Key.</b>",
      "",
      button_texts=["ADD", "TEST"],
    )
    self._public_mapbox_control.set_click_callback(self._on_public_mapbox_click)

    # Secret Mapbox Key Control
    self._secret_mapbox_control = FrogPilotButtonsControl(
      "Secret Mapbox Key",
      "<b>Manage your Secret Mapbox Key.</b>",
      "",
      button_texts=["ADD", "TEST"],
    )
    self._secret_mapbox_control.set_click_callback(self._on_secret_mapbox_click)

    # Setup Button
    self._setup_button_item = ListItem(
      title="Mapbox Setup Instructions",
      description="<b>Instructions on how to set up Mapbox</b> for \"Primeless Navigation\".",
      action_item=ButtonAction(
        text="VIEW",
        callback=self._on_setup_click,
      ),
    )

    # Speed Limit Filler Control
    self._speed_limit_filler_control = FrogPilotButtonControl(
      "SpeedLimitFiller",
      "Speed Limit Filler",
      "<b>Automatically collect missing or incorrect speed limits while you drive</b> using speeds limits sourced from your dashboard (if supported), "
      "Mapbox, and \"Navigate on openpilot\".<br><br>"
      "When you're parked and connected to Wi-Fi, FrogPilot will automatically processes this data into a file "
      "to be used with the tool located at \"SpeedLimitFiller.frogpilot.com\".<br><br>"
      "You can download this file from \"The Pond\" in the \"Download Speed Limits\" menu.<br><br>"
      "Need a step-by-step guide? Visit <b>#speed-limit-filler</b> in the FrogPilot Discord!",
      "",
      button_texts=["CANCEL", "Manually Update Speed Limits"],
    )
    self._speed_limit_filler_control.set_button_click_callback(self._on_speed_limit_filler_click)
    self._speed_limit_filler_control.set_visible_button(0, False)

    main_items = [
      self._ip_label_item,
      self._public_mapbox_control,
      self._secret_mapbox_control,
      self._setup_button_item,
      self._speed_limit_filler_control,
    ]

    self._toggles["IPLabel"] = self._ip_label_item
    self._toggles["PublicMapboxKey"] = self._public_mapbox_control
    self._toggles["SecretMapboxKey"] = self._secret_mapbox_control
    self._toggles["SetupButton"] = self._setup_button_item
    self._toggles["SpeedLimitFiller"] = self._speed_limit_filler_control

    self._main_scroller = Scroller(main_items, line_separator=True, spacing=0)

  def _get_ip_address(self) -> str:
    """Get current IP address for settings management."""
    # This would need to be wired up to the wifi module
    return "Offline..."

  def _update_buttons(self):
    """Update Mapbox key button states."""
    public_key = self._params.get("MapboxPublicKey", encoding="utf-8") or ""
    secret_key = self._params.get("MapboxSecretKey", encoding="utf-8") or ""

    self._mapbox_public_key_set = public_key.startswith("pk")
    self._mapbox_secret_key_set = secret_key.startswith("sk")

    self._public_mapbox_control.set_text(0, "REMOVE" if self._mapbox_public_key_set else "ADD")
    self._public_mapbox_control.set_visible_button(1, self._mapbox_public_key_set and self._online)

    self._secret_mapbox_control.set_text(0, "REMOVE" if self._mapbox_secret_key_set else "ADD")
    self._secret_mapbox_control.set_visible_button(1, self._mapbox_secret_key_set and self._online)

  def _on_public_mapbox_click(self, button_id: int):
    if button_id == 0:
      # ADD or REMOVE
      if self._mapbox_public_key_set:
        self._pending_action = "remove_public_key"
        gui_app.set_modal_overlay(ConfirmDialog(
          "Remove your Public Mapbox Key?",
          "Remove",
          "Cancel",
        ))
      else:
        self._pending_action = "add_public_key"
        self._keyboard.reset(min_text_size=80)
        self._keyboard.set_title("Enter your Public Mapbox Key")
        gui_app.set_modal_overlay(self._keyboard, callback=self._on_keyboard_result)
    elif button_id == 1:
      # TEST
      self._test_public_key()

  def _on_secret_mapbox_click(self, button_id: int):
    if button_id == 0:
      # ADD or REMOVE
      if self._mapbox_secret_key_set:
        self._pending_action = "remove_secret_key"
        gui_app.set_modal_overlay(ConfirmDialog(
          "Remove your Secret Mapbox Key?",
          "Remove",
          "Cancel",
        ))
      else:
        self._pending_action = "add_secret_key"
        self._keyboard.reset(min_text_size=80)
        self._keyboard.set_title("Enter your Secret Mapbox Key")
        gui_app.set_modal_overlay(self._keyboard, callback=self._on_keyboard_result)
    elif button_id == 1:
      # TEST
      self._test_secret_key()

  def _test_public_key(self):
    """Test the public Mapbox key."""
    self._public_mapbox_control.set_value("Testing...")

    # In a real implementation, this would make an HTTP request
    # For now, we'll just show a placeholder response
    def test_thread():
      time.sleep(1)
      self._public_mapbox_control.set_value("")
      # Would show result dialog here
    threading.Thread(target=test_thread, daemon=True).start()

  def _test_secret_key(self):
    """Test the secret Mapbox key."""
    self._secret_mapbox_control.set_value("Testing...")

    def test_thread():
      time.sleep(1)
      self._secret_mapbox_control.set_value("")
      # Would show result dialog here
    threading.Thread(target=test_thread, daemon=True).start()

  def _on_setup_click(self):
    self._current_panel = SubPanel.INSTRUCTIONS

  def _on_speed_limit_filler_click(self, button_id: int):
    if button_id == 0:
      # CANCEL
      self._pending_action = "cancel_update"
      gui_app.set_modal_overlay(ConfirmDialog(
        "Cancel the speed-limit update?",
        "Yes",
        "No",
      ))
    elif button_id == 1:
      # Manually Update Speed Limits
      # Check request limits
      overpass_requests_str = self._params.get("OverpassRequests", encoding="utf-8") or "{}"
      try:
        overpass_requests = json.loads(overpass_requests_str)
      except json.JSONDecodeError:
        overpass_requests = {}

      total_requests = overpass_requests.get("total_requests", 0)
      max_requests = overpass_requests.get("max_requests", 10000)
      saved_day = overpass_requests.get("day", date.today().day)

      current_day = date.today().day

      if saved_day != current_day:
        total_requests = 0

      if total_requests >= max_requests:
        now = datetime.now()
        seconds_until_midnight = (24 * 3600) - (now.hour * 3600 + now.minute * 60 + now.second)
        hours = seconds_until_midnight // 3600
        minutes = (seconds_until_midnight % 3600) // 60

        gui_app.set_modal_overlay(alert_dialog(
          f"You've hit today's request limit.\n\nIt will reset in {hours} hours and {minutes} minutes."
        ))
        self._speed_limit_filler_control.clear_checked_buttons()
        return

      self._speed_limit_filler_control.set_visible_button(0, True)
      self._speed_limit_filler_control.set_visible_button(1, False)

      self._pending_action = "start_update"
      gui_app.set_modal_overlay(ConfirmDialog(
        "This process takes a while. It's recommended to start when you're done driving and connected to stable Wi-Fi. Continue?",
        "Continue",
        "Cancel",
      ))

  def _on_keyboard_result(self, result: DialogResult):
    """Callback for keyboard modal overlay."""
    self.handle_dialog_result(result, self._keyboard.text)

  def handle_dialog_result(self, result: DialogResult, selection: str = ""):
    """Handle dialog results for pending actions."""
    action = self._pending_action
    self._pending_action = None

    if action == "add_public_key":
      if result == DialogResult.CONFIRM and selection:
        key = selection.strip()
        if not key.startswith("pk."):
          key = "pk." + key
        self._params.put("MapboxPublicKey", key)
        self._update_buttons()

    elif action == "remove_public_key":
      if result == DialogResult.CONFIRM:
        self._params.remove("MapboxPublicKey")
        self._update_buttons()

    elif action == "add_secret_key":
      if result == DialogResult.CONFIRM and selection:
        key = selection.strip()
        if not key.startswith("sk."):
          key = "sk." + key
        self._params.put("MapboxSecretKey", key)
        self._update_buttons()

    elif action == "remove_secret_key":
      if result == DialogResult.CONFIRM:
        self._params.remove("MapboxSecretKey")
        self._update_buttons()

    elif action == "cancel_update":
      if result == DialogResult.CONFIRM:
        self._updating_limits = False
        self._speed_limit_filler_control.set_enabled_button(0, False)
        self._speed_limit_filler_control.set_value("Cancelled...")
        self._params_memory.remove("UpdateSpeedLimits")

        def reset():
          self._speed_limit_filler_control.clear_checked_buttons()
          self._speed_limit_filler_control.set_enabled_button(0, True)
          self._speed_limit_filler_control.set_value("")
          self._speed_limit_filler_control.set_visible_button(0, False)
          self._speed_limit_filler_control.set_visible_button(1, True)
          self._params_memory.remove("UpdateSpeedLimitsStatus")

        threading.Timer(2.5, reset).start()

    elif action == "start_update":
      if result == DialogResult.CONFIRM:
        self._updating_limits = True
        self._speed_limit_filler_control.set_value("Calculating...")
        self._params_memory.put("UpdateSpeedLimitsStatus", "Calculating...")
        self._params_memory.put_bool("UpdateSpeedLimits", True)
      else:
        self._speed_limit_filler_control.set_visible_button(0, False)
        self._speed_limit_filler_control.set_visible_button(1, True)
        self._speed_limit_filler_control.clear_checked_buttons()

  def _update_toggles(self):
    self._tuning_level = self._params.get_int("TuningLevel") or 0
    self._update_buttons()

  def _close_sub_panel(self):
    self._current_panel = SubPanel.MAIN

  def show_event(self):
    super().show_event()
    self._main_scroller.show_event()
    self._update_toggles()
    self._started = ui_state.started

  def hide_event(self):
    super().hide_event()
    self._current_panel = SubPanel.MAIN

  def _render(self, rect):
    self._started = ui_state.started
    self._parked = not self._started

    # Update speed limit filler state
    if self._updating_limits:
      status = self._params_memory.get("UpdateSpeedLimitsStatus", encoding="utf-8") or ""
      if status == "Completed!":
        self._updating_limits = False
        self._speed_limit_filler_control.set_value("Completed!")

        def reset():
          self._speed_limit_filler_control.clear_checked_buttons()
          self._speed_limit_filler_control.set_value("")
          self._speed_limit_filler_control.set_visible_button(0, False)
          self._speed_limit_filler_control.set_visible_button(1, True)
          self._params_memory.remove("UpdateSpeedLimitsStatus")

        threading.Timer(2.5, reset).start()
      else:
        self._speed_limit_filler_control.set_value(status)
    else:
      self._speed_limit_filler_control.set_enabled_button(1, self._online and self._parked)
      if not self._online:
        self._speed_limit_filler_control.set_value("Offline...")
      elif not self._parked:
        self._speed_limit_filler_control.set_value("Not parked")
      else:
        self._speed_limit_filler_control.set_value("")

    if self._current_panel == SubPanel.INSTRUCTIONS:
      # Would render setup instructions image
      self._main_scroller.render(rect)
    else:
      self._main_scroller.render(rect)
