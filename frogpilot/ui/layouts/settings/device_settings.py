from enum import IntEnum
from pathlib import Path

import os

from openpilot.common.params import Params
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.hardware import HARDWARE
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.confirm_dialog import ConfirmDialog, alert_dialog, DialogResult
from openpilot.system.ui.widgets.list_view import ListItem, ToggleAction, ButtonAction, TextAction, ITEM_TEXT_VALUE_COLOR
from openpilot.system.ui.widgets.scroller_tici import Scroller

from openpilot.frogpilot.common.frogpilot_variables import update_frogpilot_toggles
from openpilot.frogpilot.system.ui.widgets.frogpilot_controls import (
  FrogPilotButtonControl,
  FrogPilotButtonToggleControl,
  FrogPilotConfirmationDialog,
  FrogPilotManageControl,
  FrogPilotParamValueControl,
)

DEVICE_MANAGEMENT_KEYS = {
  "DeviceShutdown",
  "HigherBitrate",
  "IncreaseThermalLimits",
  "LowVoltageShutdown",
  "NoLogging",
  "NoUploads",
  "UseKonikServer",
}

SCREEN_KEYS = {
  "ScreenBrightness",
  "ScreenBrightnessOnroad",
  "ScreenRecorder",
  "ScreenTimeout",
  "ScreenTimeoutOnroad",
  "StandbyMode",
}

NOT_VETTED_PATH = Path("/data/openpilot/not_vetted")
USE_HD_PATH = Path("/cache/use_HD")
USE_KONIK_PATH = Path("/cache/use_konik")


class SubPanel(IntEnum):
  MAIN = 0
  DEVICE_MANAGEMENT = 1
  SCREEN = 2


def build_shutdown_labels():
  labels = {}
  for i in range(34):
    if i == 0:
      labels[i] = "5 mins"
    elif i <= 3:
      labels[i] = f"{i * 15} mins"
    elif i == 4:
      labels[i] = "1 hour"
    else:
      labels[i] = f"{i - 3} hours"
  return labels


def build_brightness_labels(include_off=False):
  labels = {}
  if include_off:
    labels[0] = "Screen Off"
  for i in range(1, 101):
    labels[i] = f"{i}%"
  labels[101] = "Auto"
  return labels


class FrogPilotDevicePanel(Widget):
  def __init__(self):
    super().__init__()

    self._current_panel = SubPanel.MAIN
    self._is_recording = False
    self._params = Params()
    self._params_memory = Params("", True)
    self._started = False
    self._toggles = {}
    self._tuning_level = 0

    # Pending dialog action tracking
    self._pending_action = None  # "warning_toggle", "reboot_toggle"
    self._pending_data = {}

    self._build_main_panel()
    self._build_device_management_panel()
    self._build_screen_panel()

    ui_state.add_offroad_transition_callback(self._update_toggles)

  def _build_main_panel(self):
    self._device_management_control = FrogPilotManageControl(
      "DeviceManagement",
      "Device Settings",
      "<b>Settings that control how the device runs, powers off, and manages driving data.</b>",
      "../../frogpilot/assets/toggle_icons/icon_device.png",
    )
    self._device_management_control.set_manage_callback(self._open_device_management)

    self._screen_management_control = FrogPilotManageControl(
      "ScreenManagement",
      "Screen Settings",
      "<b>Settings that control screen brightness, screen recording, and timeout duration.</b>",
      "../../frogpilot/assets/toggle_icons/icon_light.png",
    )
    self._screen_management_control.set_manage_callback(self._open_screen_panel)

    main_items = [
      self._device_management_control,
      self._screen_management_control,
    ]

    self._main_scroller = Scroller(main_items, line_separator=True, spacing=0)

  def _build_device_management_panel(self):
    shutdown_labels = build_shutdown_labels()
    self._device_shutdown_control = FrogPilotParamValueControl(
      "DeviceShutdown",
      "Device Shutdown Timer",
      "<b>Keep the device on for the set amount of time after a drive</b> before it shuts down automatically.",
      "",
      min_value=0,
      max_value=33,
      value_labels=shutdown_labels,
    )

    self._no_logging_item = ListItem(
      title="Disable Logging",
      description="<b>WARNING: This will prevent your drives from being recorded and all data will be unobtainable!</b><br><br><b>Prevent the device from saving driving data.</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("NoLogging"),
        callback=lambda state: self._on_warning_toggle("NoLogging", state, "This will prevent your drives from being recorded. Are you sure?"),
      ),
    )

    self._no_uploads_control = FrogPilotButtonToggleControl(
      "NoUploads",
      "Disable Uploads",
      "<b>WARNING: This will prevent your drives from being uploaded to comma connect which will impact debugging and official support from comma!</b><br><br><b>Prevent the device from uploading driving data.</b>",
      "",
      button_params=["DisableOnroadUploads"],
      button_texts=["Disable Onroad Only"],
    )
    self._no_uploads_control.set_toggle_callback(lambda state: self._on_warning_toggle("NoUploads", state, "This will prevent uploads to comma connect. Are you sure?"))
    self._no_uploads_control.set_button_click_callback(lambda _: self._update_toggles())

    self._higher_bitrate_item = ListItem(
      title="High-Quality Recording",
      description="<b>Save drive footage in higher video quality.</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("HigherBitrate"),
        callback=lambda state: self._on_reboot_toggle("HigherBitrate", state, USE_HD_PATH),
      ),
    )

    self._low_voltage_control = FrogPilotParamValueControl(
      "LowVoltageShutdown",
      "Low-Voltage Cutoff",
      "<b>While parked, if the battery voltage falls below the set level, the device shuts down</b> to prevent excessive battery drain.",
      "",
      min_value=11.8,
      max_value=12.5,
      label=" volts",
      interval=0.1,
    )

    self._thermal_limits_item = ListItem(
      title="Raise Temperature Limits",
      description="<b>WARNING: Running at higher temperatures may damage your device!</b><br><br><b>Allow the device to run at higher temperatures</b> before throttling or shutting down. Use only if you understand the risks!",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("IncreaseThermalLimits"),
        callback=lambda state: self._on_warning_toggle("IncreaseThermalLimits", state, "This may damage your device. Are you sure?"),
      ),
    )

    self._use_konik_item = ListItem(
      title="Use Konik Server",
      description="<b>Upload driving data to \"stable.konik.ai\" instead of \"connect.comma.ai\".</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("UseKonikServer") or NOT_VETTED_PATH.is_file(),
        callback=lambda state: self._on_reboot_toggle("UseKonikServer", state, USE_KONIK_PATH),
        enabled=lambda: not NOT_VETTED_PATH.is_file(),
      ),
    )

    device_items = [
      self._device_shutdown_control,
      self._no_logging_item,
      self._no_uploads_control,
      self._higher_bitrate_item,
      self._low_voltage_control,
      self._thermal_limits_item,
      self._use_konik_item,
    ]

    self._toggles["DeviceShutdown"] = self._device_shutdown_control
    self._toggles["NoLogging"] = self._no_logging_item
    self._toggles["NoUploads"] = self._no_uploads_control
    self._toggles["HigherBitrate"] = self._higher_bitrate_item
    self._toggles["LowVoltageShutdown"] = self._low_voltage_control
    self._toggles["IncreaseThermalLimits"] = self._thermal_limits_item
    self._toggles["UseKonikServer"] = self._use_konik_item

    self._device_management_scroller = Scroller(device_items, line_separator=True, spacing=0)

  def _build_screen_panel(self):
    offroad_brightness_labels = build_brightness_labels(include_off=False)
    self._screen_brightness_control = FrogPilotParamValueControl(
      "ScreenBrightness",
      "Screen Brightness (Offroad)",
      "<b>The screen brightness while not driving.</b>",
      "",
      min_value=1,
      max_value=101,
      value_labels=offroad_brightness_labels,
      fast_increase=True,
    )
    self._screen_brightness_control.set_value_changed_callback(self._on_offroad_brightness_changed)

    onroad_brightness_labels = build_brightness_labels(include_off=True)
    self._screen_brightness_onroad_control = FrogPilotParamValueControl(
      "ScreenBrightnessOnroad",
      "Screen Brightness (Onroad)",
      "<b>The screen brightness while driving.</b>",
      "",
      min_value=0,
      max_value=101,
      value_labels=onroad_brightness_labels,
      fast_increase=True,
    )
    self._screen_brightness_onroad_control.set_value_changed_callback(self._on_onroad_brightness_changed)

    self._screen_recorder_control = FrogPilotButtonControl(
      "ScreenRecorder",
      "Screen Recorder",
      "<b>Add a button to the driving screen to record the display.</b>",
      "",
      button_texts=["Start Recording", "Stop Recording"],
      checkable=True,
    )
    self._screen_recorder_control.set_button_click_callback(self._on_screen_recorder_click)
    self._screen_recorder_control.set_visible_button(1, False)

    self._screen_timeout_control = FrogPilotParamValueControl(
      "ScreenTimeout",
      "Screen Timeout (Offroad)",
      "<b>How long the screen stays on after being tapped while not driving.</b>",
      "",
      min_value=5,
      max_value=60,
      label=" seconds",
      interval=5,
    )

    self._screen_timeout_onroad_control = FrogPilotParamValueControl(
      "ScreenTimeoutOnroad",
      "Screen Timeout (Onroad)",
      "<b>How long the screen stays on after being tapped while driving.</b>",
      "",
      min_value=5,
      max_value=60,
      label=" seconds",
      interval=5,
    )

    self._standby_mode_item = ListItem(
      title="Standby Mode",
      description="<b>Turn the screen off while driving and automatically wake it up for alerts or engagement state changes.</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("StandbyMode"),
        callback=lambda state: self._simple_toggle("StandbyMode", state),
      ),
    )

    screen_items = [
      self._screen_brightness_control,
      self._screen_brightness_onroad_control,
      self._screen_recorder_control,
      self._screen_timeout_control,
      self._screen_timeout_onroad_control,
      self._standby_mode_item,
    ]

    self._toggles["ScreenBrightness"] = self._screen_brightness_control
    self._toggles["ScreenBrightnessOnroad"] = self._screen_brightness_onroad_control
    self._toggles["ScreenRecorder"] = self._screen_recorder_control
    self._toggles["ScreenTimeout"] = self._screen_timeout_control
    self._toggles["ScreenTimeoutOnroad"] = self._screen_timeout_onroad_control
    self._toggles["StandbyMode"] = self._standby_mode_item

    self._screen_scroller = Scroller(screen_items, line_separator=True, spacing=0)

  def _simple_toggle(self, param: str, state: bool):
    self._params.put_bool(param, state)
    update_frogpilot_toggles()

  def _on_warning_toggle(self, param: str, state: bool, warning_message: str):
    if state:
      self._pending_action = "warning_toggle"
      self._pending_data = {"param": param}
      gui_app.set_modal_overlay(ConfirmDialog(warning_message, "Confirm", "Cancel"))
    else:
      self._params.put_bool(param, False)
      update_frogpilot_toggles()
      self._update_toggles()

  def _on_reboot_toggle(self, param: str, state: bool, cache_path: Path):
    self._params.put_bool(param, state)

    if state:
      cache_path.touch(exist_ok=True)
    else:
      if cache_path.exists():
        cache_path.unlink()

    update_frogpilot_toggles()

    self._pending_action = "reboot_toggle"
    self._pending_data = {}
    gui_app.set_modal_overlay(ConfirmDialog(
      "Reboot required to take effect.",
      "Reboot Now",
      "Reboot Later",
    ))

  def handle_dialog_result(self, result: DialogResult, selection: str = ""):
    """Handle dialog results for pending actions."""
    action = self._pending_action
    self._pending_action = None

    if action == "warning_toggle":
      if result == DialogResult.CONFIRM:
        param = self._pending_data.get("param")
        if param:
          self._params.put_bool(param, True)
          update_frogpilot_toggles()
          self._update_toggles()
      self._pending_data = {}

    elif action == "reboot_toggle":
      if result == DialogResult.CONFIRM:
        HARDWARE.reboot()
      self._pending_data = {}

  def _on_offroad_brightness_changed(self, value: float):
    if not self._started:
      brightness = int(value) if value <= 100 else 50
      HARDWARE.set_brightness(brightness)

  def _on_onroad_brightness_changed(self, value: float):
    if self._started:
      brightness = int(value) if value <= 100 else 50
      HARDWARE.set_brightness(brightness)

  def _on_screen_recorder_click(self, button_id: int):
    if button_id == 0:
      # Start Recording - enable the screen recording environment variable
      self._is_recording = True
      self._screen_recorder_control.set_checked_button(1)
      self._screen_recorder_control.set_visible_button(0, False)
      self._screen_recorder_control.set_visible_button(1, True)

      # Set params to trigger screen recording
      self._params_memory.put_bool("RecordScreen", True)
    else:
      # Stop Recording - disable the screen recording
      self._is_recording = False
      self._screen_recorder_control.clear_checked_buttons()
      self._screen_recorder_control.set_visible_button(0, True)
      self._screen_recorder_control.set_visible_button(1, False)

      # Clear params to stop screen recording
      self._params_memory.put_bool("RecordScreen", False)

  def _open_device_management(self):
    self._current_panel = SubPanel.DEVICE_MANAGEMENT

  def _open_screen_panel(self):
    self._current_panel = SubPanel.SCREEN

  def _close_sub_panel(self):
    self._current_panel = SubPanel.MAIN

  def _update_toggles(self):
    self._tuning_level = self._params.get_int("TuningLevel") or 0

    device_management_enabled = self._params.get_bool("DeviceManagement")
    no_uploads_enabled = self._params.get_bool("NoUploads")
    disable_onroad_only = self._params.get_bool("DisableOnroadUploads")

    higher_bitrate_visible = device_management_enabled and no_uploads_enabled and not disable_onroad_only
    if hasattr(self._higher_bitrate_item, 'set_visible'):
      self._higher_bitrate_item.set_visible(higher_bitrate_visible)

    if NOT_VETTED_PATH.is_file():
      self._params.put_bool("UseKonikServer", True)

  def _update_state(self):
    self._started = ui_state.started

  def show_event(self):
    super().show_event()
    self._main_scroller.show_event()
    self._update_toggles()

  def hide_event(self):
    super().hide_event()
    self._current_panel = SubPanel.MAIN

  def _render(self, rect):
    if self._current_panel == SubPanel.DEVICE_MANAGEMENT:
      self._device_management_scroller.render(rect)
    elif self._current_panel == SubPanel.SCREEN:
      self._screen_scroller.render(rect)
    else:
      self._main_scroller.render(rect)
