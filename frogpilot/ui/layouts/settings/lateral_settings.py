from enum import IntEnum

from openpilot.common.conversions import Conversions as CV
from openpilot.common.params import Params
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.hardware import HARDWARE
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.confirm_dialog import ConfirmDialog
from openpilot.system.ui.widgets.list_view import ListItem, ToggleAction
from openpilot.system.ui.widgets.scroller_tici import Scroller

from openpilot.frogpilot.common.frogpilot_variables import nnff_supported, update_frogpilot_toggles
from openpilot.frogpilot.system.ui.widgets.frogpilot_controls import (
  FrogPilotButtonToggleControl,
  FrogPilotConfirmationDialog,
  FrogPilotManageControl,
  FrogPilotParamValueButtonControl,
  FrogPilotParamValueControl,
)

ADVANCED_LATERAL_TUNE_KEYS = {
  "ForceAutoTune",
  "ForceAutoTuneOff",
  "ForceTorqueController",
  "SteerDelay",
  "SteerFriction",
  "SteerKP",
  "SteerLatAccel",
  "SteerRatio",
}

AOL_KEYS = {
  "AlwaysOnLateralLKAS",
  "PauseAOLOnBrake",
}

LANE_CHANGE_KEYS = {
  "LaneChangeTime",
  "LaneDetectionWidth",
  "MinimumLaneChangeSpeed",
  "NudgelessLaneChange",
  "OneLaneChange",
}

LATERAL_TUNE_KEYS = {
  "NNFF",
  "NNFFLite",
  "TurnDesires",
}

QOL_KEYS = {
  "PauseLateralSpeed",
}

FOOT_TO_METER = CV.FOOT_TO_METER
METER_TO_FOOT = CV.METER_TO_FOOT
KM_TO_MILE = 1.0 / CV.MPH_TO_KPH
MILE_TO_KM = CV.MPH_TO_KPH


class SubPanel(IntEnum):
  MAIN = 0
  ADVANCED_LATERAL_TUNE = 1
  AOL = 2
  LANE_CHANGE = 3
  LATERAL_TUNE = 4
  QOL = 5


def build_lane_change_time_labels():
  labels = {}
  for i in range(51):
    val = i / 10.0
    if val == 0:
      labels[val] = "Instant"
    elif val == 1.0:
      labels[val] = "1.0 second"
    else:
      labels[val] = f"{val:.1f} seconds"
  return labels


def build_imperial_speed_labels():
  labels = {}
  for i in range(100):
    labels[i] = "Off" if i == 0 else f"{i} mph"
  return labels


def build_metric_speed_labels():
  labels = {}
  for i in range(151):
    labels[i] = "Off" if i == 0 else f"{i} km/h"
  return labels


def build_imperial_distance_labels():
  labels = {}
  for i in range(151):
    val = i / 10.0
    if val == 0:
      labels[val] = "Off"
    elif i == 1:
      labels[val] = "1 foot"
    else:
      labels[val] = f"{val:.1f} feet"
  return labels


def build_metric_distance_labels():
  labels = {}
  for i in range(51):
    val = i / 10.0
    if val == 0:
      labels[val] = "Off"
    elif i == 1:
      labels[val] = "1 meter"
    else:
      labels[val] = f"{val:.1f} meters"
  return labels


class FrogPilotLateralPanel(Widget):
  def __init__(self, parent=None):
    super().__init__()

    self._current_panel = SubPanel.MAIN
    self._is_metric = False
    self._params = Params()
    self._parent = parent
    self._started = False
    self._toggles = {}

    self._car_model = ""
    self._friction = 0.0
    self._has_auto_tune = True
    self._has_nnff_log = False
    self._is_angle_car = False
    self._is_torque_car = False
    self._lat_accel_factor = 0.0
    self._lkas_allowed_for_aol = False
    self._steer_actuator_delay = 0.0
    self._steer_kp = 1.0
    self._steer_ratio = 0.0
    self._tuning_level = 0

    self._build_main_panel()
    self._build_advanced_lateral_tune_panel()
    self._build_aol_panel()
    self._build_lane_change_panel()
    self._build_lateral_tune_panel()
    self._build_qol_panel()

    ui_state.add_offroad_transition_callback(self._on_offroad_transition)

  def _on_offroad_transition(self):
    self._is_metric = self._params.get_bool("IsMetric")
    self._update_metric()
    self._update_car_params()
    self._update_toggles()

  def _build_main_panel(self):
    self._advanced_lateral_tune_control = FrogPilotManageControl(
      "AdvancedLateralTune",
      "Advanced Lateral Tuning",
      "<b>Advanced steering control changes to fine-tune how openpilot drives.</b>",
      "../../frogpilot/assets/toggle_icons/icon_advanced_lateral_tune.png",
    )
    self._advanced_lateral_tune_control.set_manage_callback(self._open_advanced_lateral_tune)

    self._aol_control = FrogPilotManageControl(
      "AlwaysOnLateral",
      "Always On Lateral",
      "<b>openpilot's steering remains active even when the accelerator or brake pedals are pressed.</b>",
      "../../frogpilot/assets/toggle_icons/icon_always_on_lateral.png",
    )
    self._aol_control.set_manage_callback(self._open_aol_panel)

    self._lane_changes_control = FrogPilotManageControl(
      "LaneChanges",
      "Lane Changes",
      "<b>Allow openpilot to change lanes.</b>",
      "../../frogpilot/assets/toggle_icons/icon_lane.png",
    )
    self._lane_changes_control.set_manage_callback(self._open_lane_change_panel)

    self._lateral_tune_control = FrogPilotManageControl(
      "LateralTune",
      "Lateral Tuning",
      "<b>Miscellaneous steering control changes</b> to fine-tune how openpilot drives.",
      "../../frogpilot/assets/toggle_icons/icon_lateral_tune.png",
    )
    self._lateral_tune_control.set_manage_callback(self._open_lateral_tune_panel)

    self._qol_lateral_control = FrogPilotManageControl(
      "QOLLateral",
      "Quality of Life",
      "<b>Steering control changes to fine-tune how openpilot drives.</b>",
      "../../frogpilot/assets/toggle_icons/icon_quality_of_life.png",
    )
    self._qol_lateral_control.set_manage_callback(self._open_qol_panel)

    main_items = [
      self._advanced_lateral_tune_control,
      self._aol_control,
      self._lane_changes_control,
      self._lateral_tune_control,
      self._qol_lateral_control,
    ]

    self._toggles["AdvancedLateralTune"] = self._advanced_lateral_tune_control
    self._toggles["AlwaysOnLateral"] = self._aol_control
    self._toggles["LaneChanges"] = self._lane_changes_control
    self._toggles["LateralTune"] = self._lateral_tune_control
    self._toggles["QOLLateral"] = self._qol_lateral_control

    self._main_scroller = Scroller(main_items, line_separator=True, spacing=0)

  def _build_advanced_lateral_tune_panel(self):
    self._steer_delay_control = FrogPilotParamValueButtonControl(
      "SteerDelay",
      "Actuator Delay",
      "<b>The time between openpilot's steering command and the vehicle's response.</b> Increase if the vehicle reacts late; decrease if it feels jumpy. Auto-learned by default.",
      "",
      min_value=0.01,
      max_value=1.0,
      interval=0.01,
      button_texts=["Reset"],
    )
    self._steer_delay_control.set_button_click_callback(lambda _: self._reset_param("SteerDelay", self._steer_actuator_delay))

    self._steer_friction_control = FrogPilotParamValueButtonControl(
      "SteerFriction",
      "Friction",
      "<b>Compensates for steering friction.</b> Increase if the wheel sticks near center; decrease if it jitters. Auto-learned by default.",
      "",
      min_value=0.0,
      max_value=1.0,
      interval=0.01,
      button_texts=["Reset"],
    )
    self._steer_friction_control.set_button_click_callback(lambda _: self._reset_param("SteerFriction", self._friction))

    self._steer_kp_control = FrogPilotParamValueButtonControl(
      "SteerKP",
      "Kp Factor",
      "<b>How strongly openpilot corrects lane position.</b> Higher is tighter but twitchier; lower is smoother but slower. Auto-learned by default.",
      "",
      min_value=0.5,
      max_value=1.5,
      interval=0.01,
      button_texts=["Reset"],
    )
    self._steer_kp_control.set_button_click_callback(lambda _: self._reset_param("SteerKP", self._steer_kp))

    self._steer_lat_accel_control = FrogPilotParamValueButtonControl(
      "SteerLatAccel",
      "Lateral Acceleration",
      "<b>Maps steering torque to turning response.</b> Increase for sharper turns; decrease for gentler steering. Auto-learned by default.",
      "",
      min_value=0.5,
      max_value=1.5,
      interval=0.01,
      button_texts=["Reset"],
    )
    self._steer_lat_accel_control.set_button_click_callback(lambda _: self._reset_param("SteerLatAccel", self._lat_accel_factor))

    self._steer_ratio_control = FrogPilotParamValueButtonControl(
      "SteerRatio",
      "Steer Ratio",
      "<b>The relationship between steering wheel rotation and road wheel angle.</b> Increase if steering feels too quick or twitchy; decrease if it feels too slow or weak. Auto-learned by default.",
      "",
      min_value=5.0,
      max_value=25.0,
      interval=0.01,
      button_texts=["Reset"],
    )
    self._steer_ratio_control.set_button_click_callback(lambda _: self._reset_param("SteerRatio", self._steer_ratio))

    self._force_auto_tune_item = ListItem(
      title="Force Auto-Tune On",
      description="<b>Force-enable openpilot's live auto-tuning for \"Friction\" and \"Lateral Acceleration\".</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("ForceAutoTune"),
        callback=lambda state: self._on_toggle("ForceAutoTune", state),
      ),
    )

    self._force_auto_tune_off_item = ListItem(
      title="Force Auto-Tune Off",
      description="<b>Force-disable openpilot's live auto-tuning for \"Friction\" and \"Lateral Acceleration\" and use the set value instead.</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("ForceAutoTuneOff"),
        callback=lambda state: self._on_toggle("ForceAutoTuneOff", state),
      ),
    )

    self._force_torque_controller_item = ListItem(
      title="Force Torque Controller",
      description="<b>Use torque-based steering control instead of angle-based control for smoother lane keeping, especially in curves.</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("ForceTorqueController"),
        callback=lambda state: self._on_reboot_toggle("ForceTorqueController", state),
      ),
    )

    advanced_items = [
      self._steer_delay_control,
      self._steer_friction_control,
      self._steer_kp_control,
      self._steer_lat_accel_control,
      self._steer_ratio_control,
      self._force_auto_tune_item,
      self._force_auto_tune_off_item,
      self._force_torque_controller_item,
    ]

    self._toggles["SteerDelay"] = self._steer_delay_control
    self._toggles["SteerFriction"] = self._steer_friction_control
    self._toggles["SteerKP"] = self._steer_kp_control
    self._toggles["SteerLatAccel"] = self._steer_lat_accel_control
    self._toggles["SteerRatio"] = self._steer_ratio_control
    self._toggles["ForceAutoTune"] = self._force_auto_tune_item
    self._toggles["ForceAutoTuneOff"] = self._force_auto_tune_off_item
    self._toggles["ForceTorqueController"] = self._force_torque_controller_item

    self._advanced_lateral_tune_scroller = Scroller(advanced_items, line_separator=True, spacing=0)

  def _build_aol_panel(self):
    self._aol_lkas_item = ListItem(
      title="Enable With LKAS",
      description="<b>Enable \"Always On Lateral\" whenever \"LKAS\" is on, even when openpilot is not engaged.</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("AlwaysOnLateralLKAS"),
        callback=lambda state: self._on_toggle("AlwaysOnLateralLKAS", state),
      ),
    )

    self._pause_aol_on_brake_control = FrogPilotParamValueControl(
      "PauseAOLOnBrake",
      "Pause on Brake Press Below",
      "<b>Pause \"Always On Lateral\" below the set speed while the brake pedal is pressed.</b>",
      "",
      min_value=0,
      max_value=99,
      fast_increase=True,
    )

    aol_items = [
      self._aol_lkas_item,
      self._pause_aol_on_brake_control,
    ]

    self._toggles["AlwaysOnLateralLKAS"] = self._aol_lkas_item
    self._toggles["PauseAOLOnBrake"] = self._pause_aol_on_brake_control

    self._aol_scroller = Scroller(aol_items, line_separator=True, spacing=0)

  def _build_lane_change_panel(self):
    self._nudgeless_lane_change_item = ListItem(
      title="Automatic Lane Changes",
      description="<b>When the turn signal is on, openpilot will automatically change lanes.</b> No steering-wheel nudge required!",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("NudgelessLaneChange"),
        callback=lambda state: self._on_toggle("NudgelessLaneChange", state),
      ),
    )

    lane_change_time_labels = build_lane_change_time_labels()
    self._lane_change_time_control = FrogPilotParamValueControl(
      "LaneChangeTime",
      "Lane Change Delay",
      "<b>Delay between turn signal activation and the start of an automatic lane change.</b>",
      "",
      min_value=0,
      max_value=5,
      value_labels=lane_change_time_labels,
      interval=0.1,
    )

    self._minimum_lane_change_speed_control = FrogPilotParamValueControl(
      "MinimumLaneChangeSpeed",
      "Minimum Lane Change Speed",
      "<b>Lowest speed at which openpilot will change lanes.</b>",
      "",
      min_value=0,
      max_value=99,
      fast_increase=True,
    )

    self._lane_detection_width_control = FrogPilotParamValueControl(
      "LaneDetectionWidth",
      "Minimum Lane Width",
      "<b>Prevent automatic lane changes into lanes narrower than the set width.</b>",
      "",
      min_value=0,
      max_value=15,
      interval=0.1,
      fast_increase=True,
    )

    self._one_lane_change_item = ListItem(
      title="One Lane Change Per Signal",
      description="<b>Limit automatic lane changes to one per turn-signal activation.</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("OneLaneChange"),
        callback=lambda state: self._on_toggle("OneLaneChange", state),
      ),
    )

    lane_change_items = [
      self._nudgeless_lane_change_item,
      self._lane_change_time_control,
      self._minimum_lane_change_speed_control,
      self._lane_detection_width_control,
      self._one_lane_change_item,
    ]

    self._toggles["NudgelessLaneChange"] = self._nudgeless_lane_change_item
    self._toggles["LaneChangeTime"] = self._lane_change_time_control
    self._toggles["MinimumLaneChangeSpeed"] = self._minimum_lane_change_speed_control
    self._toggles["LaneDetectionWidth"] = self._lane_detection_width_control
    self._toggles["OneLaneChange"] = self._one_lane_change_item

    self._lane_change_scroller = Scroller(lane_change_items, line_separator=True, spacing=0)

  def _build_lateral_tune_panel(self):
    self._turn_desires_item = ListItem(
      title="Force Turn Desires Below Lane Change Speed",
      description="<b>While driving below the minimum lane change speed with an active turn signal, instruct openpilot to turn left/right.</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("TurnDesires"),
        callback=lambda state: self._on_toggle("TurnDesires", state),
      ),
    )

    self._nnff_item = ListItem(
      title="Neural Network Feedforward (NNFF)",
      description="<b>Twilsonco's \"Neural Network FeedForward\" controller.</b> Uses a trained neural network model to predict steering torque based on vehicle speed, roll, and past/future planned path data for smoother, model-based steering.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("NNFF"),
        callback=lambda state: self._on_reboot_toggle("NNFF", state),
      ),
    )

    self._nnff_lite_item = ListItem(
      title="Neural Network Feedforward (NNFF) Lite",
      description="<b>A lightweight version of Twilsonco's \"Neural Network FeedForward\" controller.</b> Uses the \"look-ahead\" planned lateral jerk logic from the full model to help smoothen steering adjustments in curves, but does not use the full neural network for torque calculation.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("NNFFLite"),
        callback=lambda state: self._on_reboot_toggle("NNFFLite", state),
      ),
    )

    lateral_tune_items = [
      self._turn_desires_item,
      self._nnff_item,
      self._nnff_lite_item,
    ]

    self._toggles["TurnDesires"] = self._turn_desires_item
    self._toggles["NNFF"] = self._nnff_item
    self._toggles["NNFFLite"] = self._nnff_lite_item

    self._lateral_tune_scroller = Scroller(lateral_tune_items, line_separator=True, spacing=0)

  def _build_qol_panel(self):
    self._pause_lateral_speed_control = FrogPilotParamValueButtonControl(
      "PauseLateralSpeed",
      "Pause Steering Below",
      "<b>Pause steering below the set speed.</b>",
      "",
      min_value=0,
      max_value=99,
      fast_increase=True,
      button_params=["PauseLateralOnSignal"],
      button_texts=["Turn Signal Only"],
    )

    qol_items = [
      self._pause_lateral_speed_control,
    ]

    self._toggles["PauseLateralSpeed"] = self._pause_lateral_speed_control

    self._qol_scroller = Scroller(qol_items, line_separator=True, spacing=0)

  def _on_toggle(self, param: str, state: bool):
    self._params.put_bool(param, state)
    update_frogpilot_toggles()
    self._update_toggles()

  def _on_reboot_toggle(self, param: str, state: bool):
    self._params.put_bool(param, state)
    update_frogpilot_toggles()
    self._update_toggles()

    if self._started:
      gui_app.set_modal_overlay(ConfirmDialog(
        "Reboot required to take effect.",
        "Reboot Now",
        "Reboot Later",
      ))

  def _reset_param(self, param: str, default_value: float):
    def on_confirm():
      self._params.put_float(param, default_value)
      if param == "SteerDelay":
        self._steer_delay_control.refresh()
      elif param == "SteerFriction":
        self._steer_friction_control.refresh()
      elif param == "SteerKP":
        self._steer_kp_control.refresh()
      elif param == "SteerLatAccel":
        self._steer_lat_accel_control.refresh()
      elif param == "SteerRatio":
        self._steer_ratio_control.refresh()

    gui_app.set_modal_overlay(ConfirmDialog(
      f"Reset to its default value ({default_value:.2f})?",
      "Reset",
      "Cancel",
    ))

  def _open_advanced_lateral_tune(self):
    self._current_panel = SubPanel.ADVANCED_LATERAL_TUNE

  def _open_aol_panel(self):
    self._current_panel = SubPanel.AOL

  def _open_lane_change_panel(self):
    self._current_panel = SubPanel.LANE_CHANGE

  def _open_lateral_tune_panel(self):
    self._current_panel = SubPanel.LATERAL_TUNE

  def _open_qol_panel(self):
    self._current_panel = SubPanel.QOL

  def _close_sub_panel(self):
    self._current_panel = SubPanel.MAIN

  def _update_car_params(self):
    try:
      from cereal import car, messaging
      car_params_bytes = self._params.get("CarParamsPersistent")
      if car_params_bytes:
        CP = messaging.log_from_bytes(car_params_bytes, car.CarParams)

        self._car_model = CP.carFingerprint
        self._friction = CP.lateralTuning.torque.friction
        self._has_nnff_log = nnff_supported(self._car_model)
        self._is_angle_car = CP.steerControlType == car.CarParams.SteerControlType.angle
        self._is_torque_car = CP.lateralTuning.which() == "torque"
        self._lat_accel_factor = CP.lateralTuning.torque.latAccelFactor
        self._steer_actuator_delay = CP.steerActuatorDelay
        self._steer_ratio = CP.steerRatio

        self._update_steering_control_titles()
        self._update_steering_control_ranges()
    except Exception:
      pass

    try:
      from cereal import log
      ltp_bytes = self._params.get("LiveTorqueParameters")
      if ltp_bytes:
        from cereal import messaging
        LTP = messaging.log_from_bytes(ltp_bytes, log.LiveTorqueParametersData)
        self._has_auto_tune = LTP.useParams
    except Exception:
      pass

  def _update_steering_control_titles(self):
    if self._steer_actuator_delay != 0:
      self._steer_delay_control.set_title(f"Actuator Delay (Default: {self._steer_actuator_delay:.2f})")
    if self._friction != 0:
      self._steer_friction_control.set_title(f"Friction (Default: {self._friction:.2f})")
    if self._steer_kp != 0:
      self._steer_kp_control.set_title(f"Kp Factor (Default: {self._steer_kp:.2f})")
    if self._lat_accel_factor != 0:
      self._steer_lat_accel_control.set_title(f"Lateral Acceleration (Default: {self._lat_accel_factor:.2f})")
    if self._steer_ratio != 0:
      self._steer_ratio_control.set_title(f"Steer Ratio (Default: {self._steer_ratio:.2f})")

  def _update_steering_control_ranges(self):
    if self._steer_kp > 0:
      self._steer_kp_control.update_control(self._steer_kp * 0.5, self._steer_kp * 1.5)
    if self._lat_accel_factor > 0:
      self._steer_lat_accel_control.update_control(self._lat_accel_factor * 0.5, self._lat_accel_factor * 1.5)
    if self._steer_ratio > 0:
      self._steer_ratio_control.update_control(self._steer_ratio * 0.5, self._steer_ratio * 1.5)

  def _update_metric(self):
    if self._is_metric:
      speed_labels = build_metric_speed_labels()
      distance_labels = build_metric_distance_labels()
      max_speed = 150
      max_distance = 5.0
    else:
      speed_labels = build_imperial_speed_labels()
      distance_labels = build_imperial_distance_labels()
      max_speed = 99
      max_distance = 15.0

    self._minimum_lane_change_speed_control.update_control(0, max_speed, speed_labels)
    self._pause_aol_on_brake_control.update_control(0, max_speed, speed_labels)
    self._pause_lateral_speed_control.update_control(0, max_speed, speed_labels)
    self._lane_detection_width_control.update_control(0, max_distance, distance_labels)

  def _update_toggles(self):
    self._tuning_level = self._params.get_int("TuningLevel") or 0

    forcing_auto_tune = not self._has_auto_tune and self._params.get_bool("ForceAutoTune")
    forcing_auto_tune_off = self._has_auto_tune and self._params.get_bool("ForceAutoTuneOff")
    forcing_torque_controller = not self._is_angle_car and self._params.get_bool("ForceTorqueController")
    using_nnff = self._has_nnff_log and self._params.get_bool("LateralTune") and self._params.get_bool("NNFF")
    nudgeless_enabled = self._params.get_bool("LaneChanges") and self._params.get_bool("NudgelessLaneChange")

    if hasattr(self._aol_lkas_item, 'set_visible'):
      self._aol_lkas_item.set_visible(self._lkas_allowed_for_aol)

    if hasattr(self._force_auto_tune_item, 'set_visible'):
      visible = not self._has_auto_tune and not self._is_angle_car
      visible = visible and (self._is_torque_car or forcing_torque_controller or using_nnff)
      self._force_auto_tune_item.set_visible(visible)

    if hasattr(self._force_auto_tune_off_item, 'set_visible'):
      self._force_auto_tune_off_item.set_visible(self._has_auto_tune)

    if hasattr(self._force_torque_controller_item, 'set_visible'):
      visible = not self._is_angle_car and not self._is_torque_car
      self._force_torque_controller_item.set_visible(visible)

    if hasattr(self._lane_change_time_control, 'set_visible'):
      self._lane_change_time_control.set_visible(nudgeless_enabled)

    if hasattr(self._lane_detection_width_control, 'set_visible'):
      self._lane_detection_width_control.set_visible(nudgeless_enabled)

    if hasattr(self._nnff_item, 'set_visible'):
      visible = self._has_nnff_log and not self._is_angle_car
      self._nnff_item.set_visible(visible)

    if hasattr(self._nnff_lite_item, 'set_visible'):
      visible = not using_nnff and not self._is_angle_car
      self._nnff_lite_item.set_visible(visible)

    if hasattr(self._steer_delay_control, 'set_visible'):
      self._steer_delay_control.set_visible(self._steer_actuator_delay != 0)

    if hasattr(self._steer_friction_control, 'set_visible'):
      visible = self._friction != 0
      visible = visible and (self._has_auto_tune if forcing_auto_tune_off else not forcing_auto_tune)
      visible = visible and (self._is_torque_car or forcing_torque_controller or using_nnff)
      visible = visible and not using_nnff
      self._steer_friction_control.set_visible(visible)

    if hasattr(self._steer_kp_control, 'set_visible'):
      visible = self._steer_kp != 0
      visible = visible and (self._is_torque_car or forcing_torque_controller or using_nnff)
      visible = visible and not self._is_angle_car
      self._steer_kp_control.set_visible(visible)

    if hasattr(self._steer_lat_accel_control, 'set_visible'):
      visible = self._lat_accel_factor != 0
      visible = visible and (self._has_auto_tune if forcing_auto_tune_off else not forcing_auto_tune)
      visible = visible and (self._is_torque_car or forcing_torque_controller or using_nnff)
      visible = visible and not using_nnff
      self._steer_lat_accel_control.set_visible(visible)

    if hasattr(self._steer_ratio_control, 'set_visible'):
      visible = self._steer_ratio != 0
      visible = visible and (self._has_auto_tune if forcing_auto_tune_off else not forcing_auto_tune)
      self._steer_ratio_control.set_visible(visible)

  def show_event(self):
    super().show_event()
    self._main_scroller.show_event()
    self._is_metric = self._params.get_bool("IsMetric")
    self._update_car_params()
    self._update_metric()
    self._update_toggles()

  def hide_event(self):
    super().hide_event()
    self._current_panel = SubPanel.MAIN

  def _render(self, rect):
    if self._current_panel == SubPanel.ADVANCED_LATERAL_TUNE:
      self._advanced_lateral_tune_scroller.render(rect)
    elif self._current_panel == SubPanel.AOL:
      self._aol_scroller.render(rect)
    elif self._current_panel == SubPanel.LANE_CHANGE:
      self._lane_change_scroller.render(rect)
    elif self._current_panel == SubPanel.LATERAL_TUNE:
      self._lateral_tune_scroller.render(rect)
    elif self._current_panel == SubPanel.QOL:
      self._qol_scroller.render(rect)
    else:
      self._main_scroller.render(rect)
