import re
import subprocess
import threading

from enum import IntEnum
from pathlib import Path

from openpilot.common.params import Params
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.list_view import ListItem, ToggleAction
from openpilot.system.ui.widgets.scroller_tici import Scroller

from openpilot.frogpilot.common.frogpilot_variables import ACTIVE_THEME_PATH, update_frogpilot_toggles
from openpilot.frogpilot.system.ui.widgets.frogpilot_controls import (
  FrogPilotManageControl,
  FrogPilotParamValueButtonControl,
)

STOCK_SOUNDS_PATH = Path("/data/openpilot/selfdrive/assets/sounds")
THEME_SOUNDS_PATH = ACTIVE_THEME_PATH / "sounds"

ALERT_VOLUME_CONTROL_KEYS = {
  "DisengageVolume",
  "EngageVolume",
  "PromptDistractedVolume",
  "PromptVolume",
  "RefuseVolume",
  "WarningImmediateVolume",
  "WarningSoftVolume",
}

CUSTOM_ALERTS_KEYS = {
  "GoatScream",
  "GreenLightAlert",
  "LeadDepartingAlert",
  "LoudBlindspotAlert",
  "SpeedLimitChangedAlert",
}

# Minimum volume for warning alerts (25%)
WARNING_MIN_VOLUME = 25


class SubPanel(IntEnum):
  MAIN = 0
  ALERT_VOLUME_CONTROL = 1
  CUSTOM_ALERTS = 2


def build_volume_labels() -> dict[int, str]:
  """Build volume labels from 0-101 where 0=Muted, 101=Auto."""
  labels = {}
  for i in range(102):
    if i == 0:
      labels[i] = "Muted"
    elif i == 101:
      labels[i] = "Auto"
    else:
      labels[i] = f"{i}%"
  return labels


def camel_to_snake(name: str) -> str:
  """Convert CamelCase to snake_case."""
  return re.sub(r'([A-Z])', r'_\1', name).lower().lstrip('_')


class FrogPilotSoundsPanel(Widget):
  def __init__(self):
    super().__init__()

    self._current_panel = SubPanel.MAIN
    self._params = Params()
    self._params_memory = Params("", True)
    self._sound_player_process: subprocess.Popen | None = None
    self._started = False
    self._toggles = {}
    self._tuning_level = 0

    # Car capabilities (will be loaded from frogpilot_variables)
    self._has_bsm = False
    self._has_openpilot_longitudinal = False

    self._build_main_panel()
    self._build_alert_volume_panel()
    self._build_custom_alerts_panel()

    self._initialize_sound_player()

    ui_state.add_offroad_transition_callback(self._update_toggles)

  def _build_main_panel(self):
    self._alert_volume_control = FrogPilotManageControl(
      "AlertVolumeControl",
      "Alert Volume Controller",
      "<b>Set how loud each type of openpilot alert is</b> to keep routine prompts from becoming distracting.",
      "../../frogpilot/assets/toggle_icons/icon_mute.png",
    )
    self._alert_volume_control.set_manage_callback(self._open_alert_volume_panel)

    self._custom_alerts_control = FrogPilotManageControl(
      "CustomAlerts",
      "FrogPilot Alerts",
      "<b>Optional FrogPilot alerts</b> that highlight driving events in a more noticeable way.",
      "../../frogpilot/assets/toggle_icons/icon_green_light.png",
    )
    self._custom_alerts_control.set_manage_callback(self._open_custom_alerts_panel)

    main_items = [
      self._alert_volume_control,
      self._custom_alerts_control,
    ]

    self._toggles["AlertVolumeControl"] = self._alert_volume_control
    self._toggles["CustomAlerts"] = self._custom_alerts_control

    self._main_scroller = Scroller(main_items, line_separator=True, spacing=0)

  def _build_alert_volume_panel(self):
    volume_labels = build_volume_labels()

    # Disengage Volume (0-101)
    self._disengage_volume_control = FrogPilotParamValueButtonControl(
      "DisengageVolume",
      "Disengage Volume",
      "<b>Set the volume for alerts when openpilot disengages.</b><br><br>Examples include: \"Cruise Fault: Restart the Car\", \"Parking Brake Engaged\", \"Pedal Pressed\".",
      "",
      min_value=0,
      max_value=101,
      value_labels=volume_labels,
      fast_increase=True,
      button_texts=["Test"],
      checkable=False,
    )
    self._disengage_volume_control.set_button_click_callback(lambda _: self._test_sound("DisengageVolume"))

    # Engage Volume (0-101)
    self._engage_volume_control = FrogPilotParamValueButtonControl(
      "EngageVolume",
      "Engage Volume",
      "<b>Set the volume for the chime when openpilot engages</b>, such as after pressing the \"RESUME\" or \"SET\" steering wheel buttons.",
      "",
      min_value=0,
      max_value=101,
      value_labels=volume_labels,
      fast_increase=True,
      button_texts=["Test"],
      checkable=False,
    )
    self._engage_volume_control.set_button_click_callback(lambda _: self._test_sound("EngageVolume"))

    # Prompt Volume (0-101)
    self._prompt_volume_control = FrogPilotParamValueButtonControl(
      "PromptVolume",
      "Prompt Volume",
      "<b>Set the volume for prompts that need attention.</b><br><br>Examples include: \"Car Detected in Blindspot\", \"Steering Temporarily Unavailable\", \"Turn Exceeds Steering Limit\".",
      "",
      min_value=0,
      max_value=101,
      value_labels=volume_labels,
      fast_increase=True,
      button_texts=["Test"],
      checkable=False,
    )
    self._prompt_volume_control.set_button_click_callback(lambda _: self._test_sound("PromptVolume"))

    # Prompt Distracted Volume (0-101)
    self._prompt_distracted_volume_control = FrogPilotParamValueButtonControl(
      "PromptDistractedVolume",
      "Prompt Distracted Volume",
      "<b>Set the volume for prompts when openpilot detects driver distraction or unresponsiveness.</b><br><br>Examples include: \"Pay Attention\", \"Touch Steering Wheel\".",
      "",
      min_value=0,
      max_value=101,
      value_labels=volume_labels,
      fast_increase=True,
      button_texts=["Test"],
      checkable=False,
    )
    self._prompt_distracted_volume_control.set_button_click_callback(lambda _: self._test_sound("PromptDistractedVolume"))

    # Refuse Volume (0-101)
    self._refuse_volume_control = FrogPilotParamValueButtonControl(
      "RefuseVolume",
      "Refuse Volume",
      "<b>Set the volume for alerts when openpilot refuses to engage.</b><br><br>Examples include: \"Brake Hold Active\", \"Door Open\", \"Seatbelt Unlatched\".",
      "",
      min_value=0,
      max_value=101,
      value_labels=volume_labels,
      fast_increase=True,
      button_texts=["Test"],
      checkable=False,
    )
    self._refuse_volume_control.set_button_click_callback(lambda _: self._test_sound("RefuseVolume"))

    # Warning Soft Volume (25-101, minimum 25%)
    self._warning_soft_volume_control = FrogPilotParamValueButtonControl(
      "WarningSoftVolume",
      "Warning Soft Volume",
      "<b>Set the volume for softer warnings about potential risks.</b><br><br>Examples include: \"BRAKE! Risk of Collision\", \"Steering Temporarily Unavailable\".",
      "",
      min_value=WARNING_MIN_VOLUME,
      max_value=101,
      value_labels=volume_labels,
      fast_increase=True,
      button_texts=["Test"],
      checkable=False,
    )
    self._warning_soft_volume_control.set_button_click_callback(lambda _: self._test_sound("WarningSoftVolume"))

    # Warning Immediate Volume (25-101, minimum 25%)
    self._warning_immediate_volume_control = FrogPilotParamValueButtonControl(
      "WarningImmediateVolume",
      "Warning Immediate Volume",
      "<b>Set the volume for the loudest warnings that require urgent attention.</b><br><br>Examples include: \"DISENGAGE IMMEDIATELY — Driver Distracted\", \"DISENGAGE IMMEDIATELY — Driver Unresponsive\".",
      "",
      min_value=WARNING_MIN_VOLUME,
      max_value=101,
      value_labels=volume_labels,
      fast_increase=True,
      button_texts=["Test"],
      checkable=False,
    )
    self._warning_immediate_volume_control.set_button_click_callback(lambda _: self._test_sound("WarningImmediateVolume"))

    alert_volume_items = [
      self._disengage_volume_control,
      self._engage_volume_control,
      self._prompt_volume_control,
      self._prompt_distracted_volume_control,
      self._refuse_volume_control,
      self._warning_soft_volume_control,
      self._warning_immediate_volume_control,
    ]

    self._toggles["DisengageVolume"] = self._disengage_volume_control
    self._toggles["EngageVolume"] = self._engage_volume_control
    self._toggles["PromptVolume"] = self._prompt_volume_control
    self._toggles["PromptDistractedVolume"] = self._prompt_distracted_volume_control
    self._toggles["RefuseVolume"] = self._refuse_volume_control
    self._toggles["WarningSoftVolume"] = self._warning_soft_volume_control
    self._toggles["WarningImmediateVolume"] = self._warning_immediate_volume_control

    self._alert_volume_scroller = Scroller(alert_volume_items, line_separator=True, spacing=0)

  def _build_custom_alerts_panel(self):
    self._goat_scream_item = ListItem(
      title="Goat Scream",
      description="<b>Play the infamous \"Goat Scream\" when the steering controller reaches its limit.</b> Based on the \"Turn Exceeds Steering Limit\" event.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("GoatScream"),
        callback=lambda state: self._simple_toggle("GoatScream", state),
      ),
    )

    self._green_light_alert_item = ListItem(
      title="Green Light Alert",
      description="<b>Play an alert when the model predicts a red light has turned green.</b><br><br><i><b>Disclaimer</b>: openpilot does not explicitly detect traffic lights. This alert is based on end-to-end model predictions from camera input and may trigger even when the light has not changed.</i>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("GreenLightAlert"),
        callback=lambda state: self._simple_toggle("GreenLightAlert", state),
      ),
    )

    self._lead_departing_alert_item = ListItem(
      title="Lead Departing Alert",
      description="<b>Play an alert when the lead vehicle departs from a stop.</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("LeadDepartingAlert"),
        callback=lambda state: self._simple_toggle("LeadDepartingAlert", state),
      ),
    )

    self._loud_blindspot_alert_item = ListItem(
      title="Loud \"Car Detected in Blindspot\" Alert",
      description="<b>Play a louder alert if a vehicle is in the blind spot when attempting to change lanes.</b> Based on the \"Car Detected in Blindspot\" event.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("LoudBlindspotAlert"),
        callback=lambda state: self._simple_toggle("LoudBlindspotAlert", state),
      ),
    )

    self._speed_limit_changed_alert_item = ListItem(
      title="Speed Limit Changed Alert",
      description="<b>Play an alert when the posted speed limit changes.</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("SpeedLimitChangedAlert"),
        callback=lambda state: self._simple_toggle("SpeedLimitChangedAlert", state),
      ),
    )

    custom_alerts_items = [
      self._goat_scream_item,
      self._green_light_alert_item,
      self._lead_departing_alert_item,
      self._loud_blindspot_alert_item,
      self._speed_limit_changed_alert_item,
    ]

    self._toggles["GoatScream"] = self._goat_scream_item
    self._toggles["GreenLightAlert"] = self._green_light_alert_item
    self._toggles["LeadDepartingAlert"] = self._lead_departing_alert_item
    self._toggles["LoudBlindspotAlert"] = self._loud_blindspot_alert_item
    self._toggles["SpeedLimitChangedAlert"] = self._speed_limit_changed_alert_item

    self._custom_alerts_scroller = Scroller(custom_alerts_items, line_separator=True, spacing=0)

  def _simple_toggle(self, param: str, state: bool):
    self._params.put_bool(param, state)
    update_frogpilot_toggles()

  def _initialize_sound_player(self):
    """Initialize a Python subprocess for playing test sounds."""
    program = '''
import numpy as np
import sounddevice as sd
import sys
import wave

while True:
  try:
    line = sys.stdin.readline()
    if not line:
      break
    path, volume = line.strip().split('|')

    sound_file = wave.open(path, 'rb')
    audio = np.frombuffer(sound_file.readframes(sound_file.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0

    sd.play(audio * float(volume), sound_file.getframerate())
    sd.wait()
  except Exception:
    pass
'''

    try:
      self._sound_player_process = subprocess.Popen(
        ["python3", "-u", "-c", program],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
      )
    except Exception:
      self._sound_player_process = None

  def _test_sound(self, key: str):
    """Test a sound by playing it or triggering via params."""
    # Remove "Volume" suffix to get base alert name
    base_name = key.replace("Volume", "")

    if self._started:
      # If driving, trigger via TestAlert param (handled by openpilot)
      update_frogpilot_toggles()

      # Convert to camelCase for TestAlert param
      camel_case_alert = base_name[0].lower() + base_name[1:]
      self._params_memory.put("TestAlert", camel_case_alert)
    else:
      # If parked, play directly via sound player process
      snake_case_alert = camel_to_snake(base_name)

      # Check for custom theme sound first, then fall back to stock
      theme_path = THEME_SOUNDS_PATH / f"{snake_case_alert}.wav"
      stock_path = STOCK_SOUNDS_PATH / f"{snake_case_alert}.wav"

      sound_path = theme_path if theme_path.exists() else stock_path

      if not sound_path.exists():
        return

      # Get volume from param (0-101, where 101 is auto)
      volume_param = self._params.get_float(key)
      if volume_param is None:
        volume_param = self._params.get_int(key) or 100

      # Auto (101) defaults to 50%
      volume = volume_param / 100.0 if volume_param <= 100 else 0.5

      self._play_sound(str(sound_path), volume)

  def _play_sound(self, path: str, volume: float):
    """Play a sound file at the specified volume."""
    if self._sound_player_process is None or self._sound_player_process.poll() is not None:
      self._initialize_sound_player()

    if self._sound_player_process and self._sound_player_process.stdin:
      try:
        message = f"{path}|{volume}\n"
        self._sound_player_process.stdin.write(message.encode())
        self._sound_player_process.stdin.flush()
      except Exception:
        pass

  def _open_alert_volume_panel(self):
    self._current_panel = SubPanel.ALERT_VOLUME_CONTROL

  def _open_custom_alerts_panel(self):
    self._current_panel = SubPanel.CUSTOM_ALERTS

  def _close_sub_panel(self):
    self._current_panel = SubPanel.MAIN

  def _update_toggles(self):
    self._tuning_level = self._params.get_int("TuningLevel") or 0

    # Check visibility conditions for specific toggles
    # LoudBlindspotAlert only visible if car has BSM
    if hasattr(self._loud_blindspot_alert_item, "set_visible"):
      self._loud_blindspot_alert_item.set_visible(self._has_bsm)

    # SpeedLimitChangedAlert visible if ShowSpeedLimits OR (hasOpenpilotLongitudinal AND SpeedLimitController)
    show_speed_limits = self._params.get_bool("ShowSpeedLimits")
    speed_limit_controller = self._params.get_bool("SpeedLimitController")
    slc_visible = show_speed_limits or (self._has_openpilot_longitudinal and speed_limit_controller)
    if hasattr(self._speed_limit_changed_alert_item, "set_visible"):
      self._speed_limit_changed_alert_item.set_visible(slc_visible)

  def _load_car_capabilities(self):
    """Load car capabilities from frogpilot variables."""
    try:
      from openpilot.frogpilot.common.frogpilot_variables import get_frogpilot_toggles
      toggles = get_frogpilot_toggles()
      self._has_bsm = getattr(toggles, "has_bsm", False)
      self._has_openpilot_longitudinal = getattr(toggles, "has_openpilot_longitudinal", False)
    except Exception:
      self._has_bsm = False
      self._has_openpilot_longitudinal = False

  def show_event(self):
    super().show_event()
    self._main_scroller.show_event()
    self._load_car_capabilities()
    self._update_toggles()
    self._started = ui_state.started

  def hide_event(self):
    super().hide_event()
    self._current_panel = SubPanel.MAIN

    # Clean up sound player process
    if self._sound_player_process:
      try:
        self._sound_player_process.terminate()
      except Exception:
        pass
      self._sound_player_process = None

  def _render(self, rect):
    self._started = ui_state.started

    if self._current_panel == SubPanel.ALERT_VOLUME_CONTROL:
      self._alert_volume_scroller.render(rect)
    elif self._current_panel == SubPanel.CUSTOM_ALERTS:
      self._custom_alerts_scroller.render(rect)
    else:
      self._main_scroller.render(rect)
