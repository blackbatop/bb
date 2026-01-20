from enum import IntEnum

from openpilot.common.conversions import Conversions as CV
from openpilot.common.params import Params
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.confirm_dialog import ConfirmDialog
from openpilot.system.ui.widgets.list_view import ListItem, ToggleAction, ButtonAction
from openpilot.system.ui.widgets.scroller_tici import Scroller

from openpilot.frogpilot.common.frogpilot_variables import update_frogpilot_toggles
from openpilot.frogpilot.system.ui.widgets.frogpilot_controls import (
  FrogPilotButtonsControl,
  FrogPilotButtonToggleControl,
  FrogPilotConfirmationDialog,
  FrogPilotDualParamValueControl,
  FrogPilotManageControl,
  FrogPilotParamValueButtonControl,
  FrogPilotParamValueControl,
)

ADVANCED_LONGITUDINAL_TUNE_KEYS = {
  "LongitudinalActuatorDelay",
  "MaxDesiredAcceleration",
  "StartAccel",
  "StopAccel",
  "StoppingDecelRate",
  "VEgoStarting",
  "VEgoStopping",
}

AGGRESSIVE_PERSONALITY_KEYS = {
  "AggressiveFollow",
  "AggressiveJerkAcceleration",
  "AggressiveJerkDeceleration",
  "AggressiveJerkDanger",
  "AggressiveJerkSpeed",
  "AggressiveJerkSpeedDecrease",
  "ResetAggressivePersonality",
}

CONDITIONAL_EXPERIMENTAL_KEYS = {
  "CESpeed",
  "CESpeedLead",
  "CECurves",
  "CELead",
  "CEModelStopTime",
  "CESignalSpeed",
  "CEStopLights",
  "ShowCEMStatus",
}

CURVE_SPEED_KEYS = {
  "CalibratedLateralAcceleration",
  "CalibrationProgress",
  "ResetCurveData",
  "ShowCSCStatus",
}

CUSTOM_DRIVING_PERSONALITY_KEYS = {
  "AggressivePersonalityProfile",
  "RelaxedPersonalityProfile",
  "StandardPersonalityProfile",
  "TrafficPersonalityProfile",
}

LONGITUDINAL_TUNE_KEYS = {
  "AccelerationProfile",
  "DecelerationProfile",
  "HumanAcceleration",
  "HumanFollowing",
  "HumanLaneChanges",
  "LeadDetectionThreshold",
  "TacoTune",
}

QOL_KEYS = {
  "CustomCruise",
  "CustomCruiseLong",
  "ForceStops",
  "IncreasedStoppedDistance",
  "MapGears",
  "ReverseCruise",
  "SetSpeedOffset",
  "WeatherPresets",
}

RELAXED_PERSONALITY_KEYS = {
  "RelaxedFollow",
  "RelaxedJerkAcceleration",
  "RelaxedJerkDeceleration",
  "RelaxedJerkDanger",
  "RelaxedJerkSpeed",
  "RelaxedJerkSpeedDecrease",
  "ResetRelaxedPersonality",
}

SPEED_LIMIT_CONTROLLER_KEYS = {
  "SLCOffsets",
  "SLCFallback",
  "SLCOverride",
  "SLCPriority",
  "SLCQOL",
  "SLCVisuals",
}

SPEED_LIMIT_CONTROLLER_OFFSETS_KEYS = {
  "Offset1",
  "Offset2",
  "Offset3",
  "Offset4",
  "Offset5",
  "Offset6",
  "Offset7",
}

SPEED_LIMIT_CONTROLLER_QOL_KEYS = {
  "SetSpeedLimit",
  "SLCConfirmation",
  "SLCLookaheadHigher",
  "SLCLookaheadLower",
  "SLCMapboxFiller",
}

SPEED_LIMIT_CONTROLLER_VISUAL_KEYS = {
  "ShowSLCOffset",
  "SpeedLimitSources",
}

STANDARD_PERSONALITY_KEYS = {
  "StandardFollow",
  "StandardJerkAcceleration",
  "StandardJerkDeceleration",
  "StandardJerkDanger",
  "StandardJerkSpeed",
  "StandardJerkSpeedDecrease",
  "ResetStandardPersonality",
}

TRAFFIC_PERSONALITY_KEYS = {
  "TrafficFollow",
  "TrafficJerkAcceleration",
  "TrafficJerkDeceleration",
  "TrafficJerkDanger",
  "TrafficJerkSpeed",
  "TrafficJerkSpeedDecrease",
  "ResetTrafficPersonality",
}

WEATHER_KEYS = {
  "LowVisibilityOffsets",
  "RainOffsets",
  "RainStormOffsets",
  "SetWeatherKey",
  "SnowOffsets",
}

WEATHER_LOW_VISIBILITY_KEYS = {
  "IncreaseFollowingLowVisibility",
  "IncreasedStoppedDistanceLowVisibility",
  "ReduceAccelerationLowVisibility",
  "ReduceLateralAccelerationLowVisibility",
}

WEATHER_RAIN_KEYS = {
  "IncreaseFollowingRain",
  "IncreasedStoppedDistanceRain",
  "ReduceAccelerationRain",
  "ReduceLateralAccelerationRain",
}

WEATHER_RAIN_STORM_KEYS = {
  "IncreaseFollowingRainStorm",
  "IncreasedStoppedDistanceRainStorm",
  "ReduceAccelerationRainStorm",
  "ReduceLateralAccelerationRainStorm",
}

WEATHER_SNOW_KEYS = {
  "IncreaseFollowingSnow",
  "IncreasedStoppedDistanceSnow",
  "ReduceAccelerationSnow",
  "ReduceLateralAccelerationSnow",
}

FOOT_TO_METER = CV.FOOT_TO_METER
METER_TO_FOOT = CV.METER_TO_FOOT
KM_TO_MILE = 1.0 / CV.MPH_TO_KPH
MILE_TO_KM = CV.MPH_TO_KPH


class SubPanel(IntEnum):
  MAIN = 0
  ADVANCED_LONGITUDINAL_TUNE = 1
  AGGRESSIVE_PERSONALITY = 2
  CONDITIONAL_EXPERIMENTAL = 3
  CURVE_SPEED = 4
  CUSTOM_DRIVING_PERSONALITY = 5
  LONGITUDINAL_TUNE = 6
  QOL = 7
  RELAXED_PERSONALITY = 8
  SPEED_LIMIT_CONTROLLER = 9
  SPEED_LIMIT_CONTROLLER_OFFSETS = 10
  SPEED_LIMIT_CONTROLLER_QOL = 11
  SPEED_LIMIT_CONTROLLER_VISUALS = 12
  STANDARD_PERSONALITY = 13
  TRAFFIC_PERSONALITY = 14
  WEATHER = 15
  WEATHER_LOW_VISIBILITY = 16
  WEATHER_RAIN = 17
  WEATHER_RAIN_STORM = 18
  WEATHER_SNOW = 19


def build_stop_time_labels():
  labels = {}
  for i in range(10):
    if i == 0:
      labels[i] = "Off"
    elif i == 1:
      labels[i] = "1 second"
    else:
      labels[i] = f"{i} seconds"
  return labels


def build_follow_time_labels():
  labels = {}
  for i in range(301):
    val = i / 100.0
    if round(val * 100) == 100:
      labels[val] = f"{val:.2f} second"
    else:
      labels[val] = f"{val:.2f} seconds"
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
  for i in range(11):
    if i == 0:
      labels[i] = "Off"
    elif i == 1:
      labels[i] = "1 foot"
    else:
      labels[i] = f"{i} feet"
  return labels


def build_metric_distance_labels():
  labels = {}
  for i in range(4):
    if i == 0:
      labels[i] = "Off"
    elif i == 1:
      labels[i] = "1 meter"
    else:
      labels[i] = f"{i} meters"
  return labels


class FrogPilotLongitudinalPanel(Widget):
  def __init__(self, parent=None):
    super().__init__()

    self._current_panel = SubPanel.MAIN
    self._custom_personality_open = False
    self._is_metric = False
    self._params = Params()
    self._parent = parent
    self._qol_open = False
    self._slc_open = False
    self._started = False
    self._toggles = {}
    self._tuning_level = 0
    self._weather_open = False

    self._has_dash_speed_limits = False
    self._has_pcm_cruise = False
    self._has_radar = False
    self._is_gm = False
    self._is_toyota = False
    self._is_tsk = False

    self._longitudinal_actuator_delay = 0.0
    self._start_accel = 0.0
    self._stop_accel = 0.0
    self._stopping_decel_rate = 0.0
    self._v_ego_starting = 0.0
    self._v_ego_stopping = 0.0

    self._build_main_panel()
    self._build_advanced_longitudinal_tune_panel()
    self._build_conditional_experimental_panel()
    self._build_curve_speed_panel()
    self._build_custom_driving_personality_panel()
    self._build_traffic_personality_panel()
    self._build_aggressive_personality_panel()
    self._build_standard_personality_panel()
    self._build_relaxed_personality_panel()
    self._build_longitudinal_tune_panel()
    self._build_qol_panel()
    self._build_weather_panel()
    self._build_weather_low_visibility_panel()
    self._build_weather_rain_panel()
    self._build_weather_rain_storm_panel()
    self._build_weather_snow_panel()
    self._build_speed_limit_controller_panel()
    self._build_slc_offsets_panel()
    self._build_slc_qol_panel()
    self._build_slc_visuals_panel()

    ui_state.add_offroad_transition_callback(self._on_offroad_transition)

  def _on_offroad_transition(self):
    self._is_metric = self._params.get_bool("IsMetric")
    self._update_metric()
    self._update_car_params()
    self._update_toggles()

  def _build_main_panel(self):
    self._advanced_longitudinal_tune_control = FrogPilotManageControl(
      "AdvancedLongitudinalTune",
      "Advanced Longitudinal Tuning",
      "<b>Advanced acceleration and braking control changes</b> to fine-tune how openpilot drives.",
      "../../frogpilot/assets/toggle_icons/icon_advanced_longitudinal_tune.png",
    )
    self._advanced_longitudinal_tune_control.set_manage_callback(self._open_advanced_longitudinal_tune)

    self._conditional_experimental_control = FrogPilotManageControl(
      "ConditionalExperimental",
      "Conditional Experimental Mode",
      "<b>Automatically switch to \"Experimental Mode\" when set conditions are met.</b> Allows the model to handle challenging situations with smarter decision making.",
      "../../frogpilot/assets/toggle_icons/icon_conditional.png",
    )
    self._conditional_experimental_control.set_manage_callback(self._open_conditional_experimental)

    self._curve_speed_controller_control = FrogPilotManageControl(
      "CurveSpeedController",
      "Curve Speed Controller",
      "<b>Automatically slow down for upcoming curves</b> using data learned from your driving style, adapting to curves as you would.",
      "../../frogpilot/assets/toggle_icons/icon_speed_map.png",
    )
    self._curve_speed_controller_control.set_manage_callback(self._open_curve_speed)

    self._custom_personalities_control = FrogPilotManageControl(
      "CustomPersonalities",
      "Driving Personalities",
      "<b>Customize the \"Driving Personalities\"</b> to better match your driving style.",
      "../../frogpilot/assets/toggle_icons/icon_personality.png",
    )
    self._custom_personalities_control.set_manage_callback(self._open_custom_driving_personality)

    self._longitudinal_tune_control = FrogPilotManageControl(
      "LongitudinalTune",
      "Longitudinal Tuning",
      "<b>Acceleration and braking control changes</b> to fine-tune how openpilot drives.",
      "../../frogpilot/assets/toggle_icons/icon_longitudinal_tune.png",
    )
    self._longitudinal_tune_control.set_manage_callback(self._open_longitudinal_tune)

    self._qol_longitudinal_control = FrogPilotManageControl(
      "QOLLongitudinal",
      "Quality of Life",
      "<b>Miscellaneous acceleration and braking control changes</b> to fine-tune how openpilot drives.",
      "../../frogpilot/assets/toggle_icons/icon_quality_of_life.png",
    )
    self._qol_longitudinal_control.set_manage_callback(self._open_qol)

    self._speed_limit_controller_control = FrogPilotManageControl(
      "SpeedLimitController",
      "Speed Limit Controller",
      "<b>Limit openpilot's maximum driving speed to the current speed limit</b> obtained from downloaded maps, Mapbox, or the dashboard for supported vehicles (Ford, Genesis, Hyundai, Kia, Lexus, Toyota).",
      "../../frogpilot/assets/toggle_icons/icon_speed_limit.png",
    )
    self._speed_limit_controller_control.set_manage_callback(self._open_speed_limit_controller)

    main_items = [
      self._advanced_longitudinal_tune_control,
      self._conditional_experimental_control,
      self._curve_speed_controller_control,
      self._custom_personalities_control,
      self._longitudinal_tune_control,
      self._qol_longitudinal_control,
      self._speed_limit_controller_control,
    ]

    self._toggles["AdvancedLongitudinalTune"] = self._advanced_longitudinal_tune_control
    self._toggles["ConditionalExperimental"] = self._conditional_experimental_control
    self._toggles["CurveSpeedController"] = self._curve_speed_controller_control
    self._toggles["CustomPersonalities"] = self._custom_personalities_control
    self._toggles["LongitudinalTune"] = self._longitudinal_tune_control
    self._toggles["QOLLongitudinal"] = self._qol_longitudinal_control
    self._toggles["SpeedLimitController"] = self._speed_limit_controller_control

    self._main_scroller = Scroller(main_items, line_separator=True, spacing=0)

  def _build_advanced_longitudinal_tune_panel(self):
    self._longitudinal_actuator_delay_control = FrogPilotParamValueControl(
      "LongitudinalActuatorDelay",
      "Actuator Delay",
      "<b>The time between openpilot's throttle or brake command and the vehicle's response.</b> Increase if the vehicle feels slow to react; decrease if it feels too eager or overshoots.",
      "",
      min_value=0,
      max_value=1,
      label=" seconds",
      interval=0.01,
    )

    self._max_desired_acceleration_control = FrogPilotParamValueControl(
      "MaxDesiredAcceleration",
      "Maximum Acceleration",
      "<b>Limit the strongest acceleration</b> openpilot can command.",
      "",
      min_value=0.1,
      max_value=4.0,
      label=" m/s²",
      interval=0.1,
    )

    self._start_accel_control = FrogPilotParamValueControl(
      "StartAccel",
      "Start Acceleration",
      "<b>Extra acceleration applied when starting from a stop.</b> Increase for quicker takeoffs; decrease for smoother, gentler starts.",
      "",
      min_value=0,
      max_value=4,
      label=" m/s²",
      interval=0.01,
      fast_increase=True,
    )

    self._v_ego_starting_control = FrogPilotParamValueControl(
      "VEgoStarting",
      "Start Speed",
      "<b>The speed at which openpilot exits the stopped state.</b> Increase to reduce creeping; decrease to move sooner after stopping.",
      "",
      min_value=0.01,
      max_value=1,
      label=" m/s²",
      interval=0.01,
    )

    self._stop_accel_control = FrogPilotParamValueControl(
      "StopAccel",
      "Stop Acceleration",
      "<b>Brake force applied to hold the vehicle at a standstill.</b> Increase to prevent rolling on hills; decrease for smoother, softer stops.",
      "",
      min_value=-4,
      max_value=0,
      label=" m/s²",
      interval=0.01,
      fast_increase=True,
    )

    self._stopping_decel_rate_control = FrogPilotParamValueControl(
      "StoppingDecelRate",
      "Stopping Rate",
      "<b>How quickly braking ramps up when stopping.</b> Increase for shorter, firmer stops; decrease for smoother, longer stops.",
      "",
      min_value=0.001,
      max_value=1,
      label=" m/s²",
      interval=0.001,
      fast_increase=True,
    )

    self._v_ego_stopping_control = FrogPilotParamValueControl(
      "VEgoStopping",
      "Stop Speed",
      "<b>The speed at which openpilot considers the vehicle stopped.</b> Increase to brake earlier and stop smoothly; decrease to wait longer but risk overshooting.",
      "",
      min_value=0.01,
      max_value=1,
      label=" m/s²",
      interval=0.01,
    )

    advanced_items = [
      self._longitudinal_actuator_delay_control,
      self._max_desired_acceleration_control,
      self._start_accel_control,
      self._v_ego_starting_control,
      self._stop_accel_control,
      self._stopping_decel_rate_control,
      self._v_ego_stopping_control,
    ]

    self._toggles["LongitudinalActuatorDelay"] = self._longitudinal_actuator_delay_control
    self._toggles["MaxDesiredAcceleration"] = self._max_desired_acceleration_control
    self._toggles["StartAccel"] = self._start_accel_control
    self._toggles["VEgoStarting"] = self._v_ego_starting_control
    self._toggles["StopAccel"] = self._stop_accel_control
    self._toggles["StoppingDecelRate"] = self._stopping_decel_rate_control
    self._toggles["VEgoStopping"] = self._v_ego_stopping_control

    self._advanced_longitudinal_tune_scroller = Scroller(advanced_items, line_separator=True, spacing=0)

  def _build_conditional_experimental_panel(self):
    self._ce_speed_control = FrogPilotParamValueControl(
      "CESpeed",
      "Below",
      "<b>Switch to \"Experimental Mode\" when driving below this speed without a lead</b> to help openpilot handle low-speed situations more smoothly.",
      "",
      min_value=0,
      max_value=99,
      label=" mph",
      fast_increase=True,
    )

    self._ce_speed_lead_control = FrogPilotParamValueControl(
      "CESpeedLead",
      "With Lead",
      "<b>Switch to \"Experimental Mode\" when driving below this speed with a lead</b> to help openpilot handle low-speed situations more smoothly.",
      "",
      min_value=0,
      max_value=99,
      label=" mph",
      fast_increase=True,
    )

    self._ce_speed_dual_control = FrogPilotDualParamValueControl(self._ce_speed_control, self._ce_speed_lead_control)

    self._ce_curves_control = FrogPilotButtonToggleControl(
      "CECurves",
      "Curve Detected Ahead",
      "<b>Switch to \"Experimental Mode\" when a curve is detected</b> to allow the model to set an appropriate speed for the curve.",
      "",
      button_params=["CECurvesLead"],
      button_texts=["With Lead"],
    )

    self._ce_stop_lights_item = ListItem(
      title="\"Detected\" Stop Lights/Signs",
      description="<b>Switch to \"Experimental Mode\" whenever the driving model \"detects\" a red light or stop sign.</b><br><br><i><b>Disclaimer</b>: openpilot does not explicitly detect traffic lights or stop signs. In \"Experimental Mode\", openpilot makes end-to-end driving decisions from camera input, which means it may stop even when there's no clear reason!</i>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("CEStopLights"),
        callback=lambda state: self._on_toggle("CEStopLights", state),
      ),
    )

    self._ce_lead_control = FrogPilotButtonToggleControl(
      "CELead",
      "Lead Detected Ahead",
      "<b>Switch to \"Experimental Mode\" when a slower or stopped vehicle is detected.</b> Can make braking smoother and more reliable on some vehicles.",
      "",
      button_params=["CESlowerLead", "CEStoppedLead"],
      button_texts=["Slower Lead", "Stopped Lead"],
    )

    stop_time_labels = build_stop_time_labels()
    self._ce_model_stop_time_control = FrogPilotParamValueControl(
      "CEModelStopTime",
      "Predicted Stop In",
      "<b>Switch to \"Experimental Mode\" when openpilot predicts a stop within the set time.</b> This is usually triggered when the model \"sees\" a red light or stop sign ahead.<br><br><i><b>Disclaimer</b>: openpilot does not explicitly detect traffic lights or stop signs. In \"Experimental Mode\", openpilot makes end-to-end driving decisions from camera input, which means it may stop even when there's no clear reason!</i>",
      "",
      min_value=0,
      max_value=9,
      value_labels=stop_time_labels,
    )

    self._ce_signal_speed_control = FrogPilotParamValueButtonControl(
      "CESignalSpeed",
      "Turn Signal Below",
      "<b>Switch to \"Experimental Mode\" when using a turn signal below the set speed</b> to allow the model to choose an appropriate speed for smoother left and right turns.",
      "",
      min_value=0,
      max_value=99,
      label=" mph",
      fast_increase=True,
      button_params=["CESignalLaneDetection"],
      button_texts=["Not For Detected Lanes"],
      left_button=True,
    )

    self._show_cem_status_item = ListItem(
      title="Status Widget",
      description="<b>Show which condition triggered \"Experimental Mode\"</b> on the driving screen.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("ShowCEMStatus"),
        callback=lambda state: self._on_toggle("ShowCEMStatus", state),
      ),
    )

    conditional_items = [
      self._ce_speed_dual_control,
      self._ce_curves_control,
      self._ce_stop_lights_item,
      self._ce_lead_control,
      self._ce_model_stop_time_control,
      self._ce_signal_speed_control,
      self._show_cem_status_item,
    ]

    self._toggles["CESpeed"] = self._ce_speed_dual_control
    self._toggles["CECurves"] = self._ce_curves_control
    self._toggles["CEStopLights"] = self._ce_stop_lights_item
    self._toggles["CELead"] = self._ce_lead_control
    self._toggles["CEModelStopTime"] = self._ce_model_stop_time_control
    self._toggles["CESignalSpeed"] = self._ce_signal_speed_control
    self._toggles["ShowCEMStatus"] = self._show_cem_status_item

    self._conditional_experimental_scroller = Scroller(conditional_items, line_separator=True, spacing=0)

  def _build_curve_speed_panel(self):
    self._calibrated_lateral_acceleration_item = ListItem(
      title="Calibrated Lateral Acceleration",
      description="<b>The learned lateral acceleration from collected driving data.</b> This sets how fast openpilot will take curves. Higher values allow faster cornering; lower values slow the vehicle for gentler turns.",
      action_item=ButtonAction(
        initial_text=f"{self._params.get_float('CalibratedLateralAcceleration'):.2f} m/s²",
      ),
    )

    self._calibration_progress_item = ListItem(
      title="Calibration Progress",
      description="<b>How much curve data has been collected.</b> This is a progress meter; it is normal for the value to stay low and rarely reach 100%.",
      action_item=ButtonAction(
        initial_text=f"{self._params.get_float('CalibrationProgress'):.2f}%",
      ),
    )

    self._reset_curve_data_item = ListItem(
      title="Reset Curve Data",
      description="<b>Reset collected user data for \"Curve Speed Controller\".</b>",
      action_item=ButtonAction(
        initial_text="RESET",
        callback=self._on_reset_curve_data,
      ),
    )

    self._show_csc_status_item = ListItem(
      title="Status Widget",
      description="<b>Show the \"Curve Speed Controller\" target speed on the driving screen.</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("ShowCSCStatus"),
        callback=lambda state: self._on_toggle("ShowCSCStatus", state),
      ),
    )

    curve_speed_items = [
      self._calibrated_lateral_acceleration_item,
      self._calibration_progress_item,
      self._reset_curve_data_item,
      self._show_csc_status_item,
    ]

    self._toggles["CalibratedLateralAcceleration"] = self._calibrated_lateral_acceleration_item
    self._toggles["CalibrationProgress"] = self._calibration_progress_item
    self._toggles["ResetCurveData"] = self._reset_curve_data_item
    self._toggles["ShowCSCStatus"] = self._show_csc_status_item

    self._curve_speed_scroller = Scroller(curve_speed_items, line_separator=True, spacing=0)

  def _build_custom_driving_personality_panel(self):
    self._traffic_personality_control = FrogPilotButtonsControl(
      "Traffic Mode",
      "<b>Customize the \"Traffic Mode\" personality profile.</b> Designed for stop-and-go driving.",
      "../../frogpilot/assets/stock_theme/distance_icons/traffic.png",
      button_texts=["MANAGE"],
    )
    self._traffic_personality_control.set_click_callback(lambda _: self._open_traffic_personality())

    self._aggressive_personality_control = FrogPilotButtonsControl(
      "Aggressive",
      "<b>Customize the \"Aggressive\" personality profile.</b> Designed for assertive driving with tighter gaps.",
      "../../frogpilot/assets/stock_theme/distance_icons/aggressive.png",
      button_texts=["MANAGE"],
    )
    self._aggressive_personality_control.set_click_callback(lambda _: self._open_aggressive_personality())

    self._standard_personality_control = FrogPilotButtonsControl(
      "Standard",
      "<b>Customize the \"Standard\" personality profile.</b> Designed for balanced driving with moderate gaps.",
      "../../frogpilot/assets/stock_theme/distance_icons/standard.png",
      button_texts=["MANAGE"],
    )
    self._standard_personality_control.set_click_callback(lambda _: self._open_standard_personality())

    self._relaxed_personality_control = FrogPilotButtonsControl(
      "Relaxed",
      "<b>Customize the \"Relaxed\" personality profile.</b> Designed for smoother, more comfortable driving with larger gaps.",
      "../../frogpilot/assets/stock_theme/distance_icons/relaxed.png",
      button_texts=["MANAGE"],
    )
    self._relaxed_personality_control.set_click_callback(lambda _: self._open_relaxed_personality())

    custom_personality_items = [
      self._traffic_personality_control,
      self._aggressive_personality_control,
      self._standard_personality_control,
      self._relaxed_personality_control,
    ]

    self._toggles["TrafficPersonalityProfile"] = self._traffic_personality_control
    self._toggles["AggressivePersonalityProfile"] = self._aggressive_personality_control
    self._toggles["StandardPersonalityProfile"] = self._standard_personality_control
    self._toggles["RelaxedPersonalityProfile"] = self._relaxed_personality_control

    self._custom_driving_personality_scroller = Scroller(custom_personality_items, line_separator=True, spacing=0)

  def _build_traffic_personality_panel(self):
    follow_time_labels = build_follow_time_labels()

    self._traffic_follow_control = FrogPilotParamValueControl(
      "TrafficFollow",
      "Following Distance",
      "<b>The minimum following distance to the lead vehicle in \"Traffic Mode\".</b> openpilot blends between this value and the \"Aggressive\" profile as speed increases. Increase for more space; decrease for tighter gaps.",
      "",
      min_value=0.5,
      max_value=3,
      value_labels=follow_time_labels,
      interval=0.01,
      fast_increase=True,
    )

    self._traffic_jerk_acceleration_control = FrogPilotParamValueControl(
      "TrafficJerkAcceleration",
      "Acceleration Smoothness",
      "<b>How smoothly openpilot accelerates in \"Traffic Mode\".</b> Increase for gentler starts; decrease for faster but more abrupt takeoffs.",
      "",
      min_value=25,
      max_value=200,
      label="%",
    )

    self._traffic_jerk_deceleration_control = FrogPilotParamValueControl(
      "TrafficJerkDeceleration",
      "Braking Smoothness",
      "<b>How smoothly openpilot brakes in \"Traffic Mode\".</b> Increase for gentler stops; decrease for quicker but sharper braking.",
      "",
      min_value=25,
      max_value=200,
      label="%",
    )

    self._traffic_jerk_danger_control = FrogPilotParamValueControl(
      "TrafficJerkDanger",
      "Safety Gap Bias",
      "<b>How much extra space openpilot keeps from the vehicle ahead in \"Traffic Mode\".</b> Increase for larger gaps and more cautious following; decrease for tighter gaps and closer following.",
      "",
      min_value=25,
      max_value=200,
      label="%",
    )

    self._traffic_jerk_speed_decrease_control = FrogPilotParamValueControl(
      "TrafficJerkSpeedDecrease",
      "Slowdown Response",
      "<b>How smoothly openpilot slows down in \"Traffic Mode\".</b> Increase for more gradual deceleration; decrease for faster but sharper slowdowns.",
      "",
      min_value=25,
      max_value=200,
      label="%",
    )

    self._traffic_jerk_speed_control = FrogPilotParamValueControl(
      "TrafficJerkSpeed",
      "Speed-Up Response",
      "<b>How smoothly openpilot speeds up in \"Traffic Mode\".</b> Increase for more gradual acceleration; decrease for quicker but more jolting acceleration.",
      "",
      min_value=25,
      max_value=200,
      label="%",
    )

    self._reset_traffic_personality_item = ListItem(
      title="Reset to Defaults",
      description="<b>Reset \"Traffic Mode\" settings to defaults.</b>",
      action_item=ButtonAction(
        initial_text="RESET",
        callback=self._on_reset_traffic_personality,
      ),
    )

    traffic_items = [
      self._traffic_follow_control,
      self._traffic_jerk_acceleration_control,
      self._traffic_jerk_deceleration_control,
      self._traffic_jerk_danger_control,
      self._traffic_jerk_speed_decrease_control,
      self._traffic_jerk_speed_control,
      self._reset_traffic_personality_item,
    ]

    self._toggles["TrafficFollow"] = self._traffic_follow_control
    self._toggles["TrafficJerkAcceleration"] = self._traffic_jerk_acceleration_control
    self._toggles["TrafficJerkDeceleration"] = self._traffic_jerk_deceleration_control
    self._toggles["TrafficJerkDanger"] = self._traffic_jerk_danger_control
    self._toggles["TrafficJerkSpeedDecrease"] = self._traffic_jerk_speed_decrease_control
    self._toggles["TrafficJerkSpeed"] = self._traffic_jerk_speed_control
    self._toggles["ResetTrafficPersonality"] = self._reset_traffic_personality_item

    self._traffic_personality_scroller = Scroller(traffic_items, line_separator=True, spacing=0)

  def _build_aggressive_personality_panel(self):
    follow_time_labels = build_follow_time_labels()

    self._aggressive_follow_control = FrogPilotParamValueControl(
      "AggressiveFollow",
      "Following Distance",
      "<b>How many seconds openpilot follows behind lead vehicles when using the \"Aggressive\" profile.</b> Increase for more space; decrease for tighter gaps.<br><br>Default: 1.25 seconds.",
      "",
      min_value=1,
      max_value=3,
      value_labels=follow_time_labels,
      interval=0.01,
      fast_increase=True,
    )

    self._aggressive_jerk_acceleration_control = FrogPilotParamValueControl(
      "AggressiveJerkAcceleration",
      "Acceleration Smoothness",
      "<b>How smoothly openpilot accelerates with the \"Aggressive\" profile.</b> Increase for gentler starts; decrease for faster but more abrupt takeoffs.",
      "",
      min_value=25,
      max_value=200,
      label="%",
    )

    self._aggressive_jerk_deceleration_control = FrogPilotParamValueControl(
      "AggressiveJerkDeceleration",
      "Braking Smoothness",
      "<b>How smoothly openpilot brakes with the \"Aggressive\" profile.</b> Increase for gentler stops; decrease for quicker but sharper braking.",
      "",
      min_value=25,
      max_value=200,
      label="%",
    )

    self._aggressive_jerk_danger_control = FrogPilotParamValueControl(
      "AggressiveJerkDanger",
      "Safety Gap Bias",
      "<b>How much extra space openpilot keeps from the vehicle ahead with the \"Aggressive\" profile.</b> Increase for larger gaps and more cautious following; decrease for tighter gaps and closer following.",
      "",
      min_value=25,
      max_value=200,
      label="%",
    )

    self._aggressive_jerk_speed_decrease_control = FrogPilotParamValueControl(
      "AggressiveJerkSpeedDecrease",
      "Slowdown Response",
      "<b>How smoothly openpilot slows down with the \"Aggressive\" profile.</b> Increase for more gradual deceleration; decrease for faster but sharper slowdowns.",
      "",
      min_value=25,
      max_value=200,
      label="%",
    )

    self._aggressive_jerk_speed_control = FrogPilotParamValueControl(
      "AggressiveJerkSpeed",
      "Speed-Up Response",
      "<b>How smoothly openpilot speeds up with the \"Aggressive\" profile.</b> Increase for more gradual acceleration; decrease for quicker but more jolting acceleration.",
      "",
      min_value=25,
      max_value=200,
      label="%",
    )

    self._reset_aggressive_personality_item = ListItem(
      title="Reset to Defaults",
      description="<b>Reset the \"Aggressive\" profile to defaults.</b>",
      action_item=ButtonAction(
        initial_text="RESET",
        callback=self._on_reset_aggressive_personality,
      ),
    )

    aggressive_items = [
      self._aggressive_follow_control,
      self._aggressive_jerk_acceleration_control,
      self._aggressive_jerk_deceleration_control,
      self._aggressive_jerk_danger_control,
      self._aggressive_jerk_speed_decrease_control,
      self._aggressive_jerk_speed_control,
      self._reset_aggressive_personality_item,
    ]

    self._toggles["AggressiveFollow"] = self._aggressive_follow_control
    self._toggles["AggressiveJerkAcceleration"] = self._aggressive_jerk_acceleration_control
    self._toggles["AggressiveJerkDeceleration"] = self._aggressive_jerk_deceleration_control
    self._toggles["AggressiveJerkDanger"] = self._aggressive_jerk_danger_control
    self._toggles["AggressiveJerkSpeedDecrease"] = self._aggressive_jerk_speed_decrease_control
    self._toggles["AggressiveJerkSpeed"] = self._aggressive_jerk_speed_control
    self._toggles["ResetAggressivePersonality"] = self._reset_aggressive_personality_item

    self._aggressive_personality_scroller = Scroller(aggressive_items, line_separator=True, spacing=0)

  def _build_standard_personality_panel(self):
    follow_time_labels = build_follow_time_labels()

    self._standard_follow_control = FrogPilotParamValueControl(
      "StandardFollow",
      "Following Distance",
      "<b>How many seconds openpilot follows behind lead vehicles when using the \"Standard\" profile.</b> Increase for more space; decrease for tighter gaps.<br><br>Default: 1.45 seconds.",
      "",
      min_value=1,
      max_value=3,
      value_labels=follow_time_labels,
      interval=0.01,
      fast_increase=True,
    )

    self._standard_jerk_acceleration_control = FrogPilotParamValueControl(
      "StandardJerkAcceleration",
      "Acceleration Smoothness",
      "<b>How smoothly openpilot accelerates with the \"Standard\" profile.</b> Increase for gentler starts; decrease for faster but more abrupt takeoffs.",
      "",
      min_value=25,
      max_value=200,
      label="%",
    )

    self._standard_jerk_deceleration_control = FrogPilotParamValueControl(
      "StandardJerkDeceleration",
      "Braking Smoothness",
      "<b>How smoothly openpilot brakes with the \"Standard\" profile.</b> Increase for gentler stops; decrease for quicker but sharper braking.",
      "",
      min_value=25,
      max_value=200,
      label="%",
    )

    self._standard_jerk_danger_control = FrogPilotParamValueControl(
      "StandardJerkDanger",
      "Safety Gap Bias",
      "<b>How much extra space openpilot keeps from the vehicle ahead with the \"Standard\" profile.</b> Increase for larger gaps and more cautious following; decrease for tighter gaps and closer following.",
      "",
      min_value=25,
      max_value=200,
      label="%",
    )

    self._standard_jerk_speed_decrease_control = FrogPilotParamValueControl(
      "StandardJerkSpeedDecrease",
      "Slowdown Response",
      "<b>How smoothly openpilot slows down with the \"Standard\" profile.</b> Increase for more gradual deceleration; decrease for faster but sharper slowdowns.",
      "",
      min_value=25,
      max_value=200,
      label="%",
    )

    self._standard_jerk_speed_control = FrogPilotParamValueControl(
      "StandardJerkSpeed",
      "Speed-Up Response",
      "<b>How smoothly openpilot speeds up with the \"Standard\" profile.</b> Increase for more gradual acceleration; decrease for quicker but more jolting acceleration.",
      "",
      min_value=25,
      max_value=200,
      label="%",
    )

    self._reset_standard_personality_item = ListItem(
      title="Reset to Defaults",
      description="<b>Reset the \"Standard\" profile to defaults.</b>",
      action_item=ButtonAction(
        initial_text="RESET",
        callback=self._on_reset_standard_personality,
      ),
    )

    standard_items = [
      self._standard_follow_control,
      self._standard_jerk_acceleration_control,
      self._standard_jerk_deceleration_control,
      self._standard_jerk_danger_control,
      self._standard_jerk_speed_decrease_control,
      self._standard_jerk_speed_control,
      self._reset_standard_personality_item,
    ]

    self._toggles["StandardFollow"] = self._standard_follow_control
    self._toggles["StandardJerkAcceleration"] = self._standard_jerk_acceleration_control
    self._toggles["StandardJerkDeceleration"] = self._standard_jerk_deceleration_control
    self._toggles["StandardJerkDanger"] = self._standard_jerk_danger_control
    self._toggles["StandardJerkSpeedDecrease"] = self._standard_jerk_speed_decrease_control
    self._toggles["StandardJerkSpeed"] = self._standard_jerk_speed_control
    self._toggles["ResetStandardPersonality"] = self._reset_standard_personality_item

    self._standard_personality_scroller = Scroller(standard_items, line_separator=True, spacing=0)

  def _build_relaxed_personality_panel(self):
    follow_time_labels = build_follow_time_labels()

    self._relaxed_follow_control = FrogPilotParamValueControl(
      "RelaxedFollow",
      "Following Distance",
      "<b>How many seconds openpilot follows behind lead vehicles when using the \"Relaxed\" profile.</b> Increase for more space; decrease for tighter gaps.<br><br>Default: 1.75 seconds.",
      "",
      min_value=1,
      max_value=3,
      value_labels=follow_time_labels,
      interval=0.01,
      fast_increase=True,
    )

    self._relaxed_jerk_acceleration_control = FrogPilotParamValueControl(
      "RelaxedJerkAcceleration",
      "Acceleration Smoothness",
      "<b>How smoothly openpilot accelerates with the \"Relaxed\" profile.</b> Increase for gentler starts; decrease for faster but more abrupt takeoffs.",
      "",
      min_value=25,
      max_value=200,
      label="%",
    )

    self._relaxed_jerk_deceleration_control = FrogPilotParamValueControl(
      "RelaxedJerkDeceleration",
      "Braking Smoothness",
      "<b>How smoothly openpilot brakes with the \"Relaxed\" profile.</b> Increase for gentler stops; decrease for quicker but sharper braking.",
      "",
      min_value=25,
      max_value=200,
      label="%",
    )

    self._relaxed_jerk_danger_control = FrogPilotParamValueControl(
      "RelaxedJerkDanger",
      "Safety Gap Bias",
      "<b>How much extra space openpilot keeps from the vehicle ahead with the \"Relaxed\" profile.</b> Increase for larger gaps and more cautious following; decrease for tighter gaps and closer following.",
      "",
      min_value=25,
      max_value=200,
      label="%",
    )

    self._relaxed_jerk_speed_decrease_control = FrogPilotParamValueControl(
      "RelaxedJerkSpeedDecrease",
      "Slowdown Response",
      "<b>How smoothly openpilot slows down with the \"Relaxed\" profile.</b> Increase for more gradual deceleration; decrease for faster but sharper slowdowns.",
      "",
      min_value=25,
      max_value=200,
      label="%",
    )

    self._relaxed_jerk_speed_control = FrogPilotParamValueControl(
      "RelaxedJerkSpeed",
      "Speed-Up Response",
      "<b>How smoothly openpilot speeds up with the \"Relaxed\" profile.</b> Increase for more gradual acceleration; decrease for quicker but more jolting acceleration.",
      "",
      min_value=25,
      max_value=200,
      label="%",
    )

    self._reset_relaxed_personality_item = ListItem(
      title="Reset to Defaults",
      description="<b>Reset the \"Relaxed\" profile to defaults.</b>",
      action_item=ButtonAction(
        initial_text="RESET",
        callback=self._on_reset_relaxed_personality,
      ),
    )

    relaxed_items = [
      self._relaxed_follow_control,
      self._relaxed_jerk_acceleration_control,
      self._relaxed_jerk_deceleration_control,
      self._relaxed_jerk_danger_control,
      self._relaxed_jerk_speed_decrease_control,
      self._relaxed_jerk_speed_control,
      self._reset_relaxed_personality_item,
    ]

    self._toggles["RelaxedFollow"] = self._relaxed_follow_control
    self._toggles["RelaxedJerkAcceleration"] = self._relaxed_jerk_acceleration_control
    self._toggles["RelaxedJerkDeceleration"] = self._relaxed_jerk_deceleration_control
    self._toggles["RelaxedJerkDanger"] = self._relaxed_jerk_danger_control
    self._toggles["RelaxedJerkSpeedDecrease"] = self._relaxed_jerk_speed_decrease_control
    self._toggles["RelaxedJerkSpeed"] = self._relaxed_jerk_speed_control
    self._toggles["ResetRelaxedPersonality"] = self._reset_relaxed_personality_item

    self._relaxed_personality_scroller = Scroller(relaxed_items, line_separator=True, spacing=0)

  def _build_longitudinal_tune_panel(self):
    self._acceleration_profile_control = FrogPilotButtonsControl(
      "Acceleration Profile",
      "<b>How quickly openpilot speeds up.</b> \"Eco\" is gentle and efficient, \"Sport\" is firmer and more responsive, and \"Sport+\" accelerates at the maximum rate allowed.",
      "",
      button_texts=["Standard", "Eco", "Sport", "Sport+"],
      checkable=True,
      exclusive=True,
    )
    self._acceleration_profile_control.set_click_callback(self._on_acceleration_profile_click)
    self._acceleration_profile_control.set_checked_button(self._params.get_int("AccelerationProfile"))

    self._deceleration_profile_control = FrogPilotButtonsControl(
      "Deceleration Profile",
      "<b>How firmly openpilot slows down.</b> \"Eco\" favors coasting, \"Sport\" applies stronger braking.",
      "",
      button_texts=["Standard", "Eco", "Sport"],
      checkable=True,
      exclusive=True,
    )
    self._deceleration_profile_control.set_click_callback(self._on_deceleration_profile_click)
    self._deceleration_profile_control.set_checked_button(self._params.get_int("DecelerationProfile"))

    self._human_acceleration_item = ListItem(
      title="Human-Like Acceleration",
      description="<b>Acceleration that mimics human behavior</b> by easing the throttle at low speeds and adding extra power when taking off from a stop.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("HumanAcceleration"),
        callback=lambda state: self._on_toggle("HumanAcceleration", state),
      ),
    )

    self._human_following_item = ListItem(
      title="Human-Like Following",
      description="<b>Following behavior that mimics human drivers</b> by closing gaps behind faster vehicles for quicker takeoffs and dynamically adjusting the desired following distance for gentler, more efficient braking.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("HumanFollowing"),
        callback=lambda state: self._on_toggle("HumanFollowing", state),
      ),
    )

    self._human_lane_changes_item = ListItem(
      title="Human-Like Lane Changes",
      description="<b>Lane-change behavior that mimics human drivers</b> by anticipating and tracking adjacent vehicles during lane changes.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("HumanLaneChanges"),
        callback=lambda state: self._on_toggle("HumanLaneChanges", state),
      ),
    )

    self._lead_detection_threshold_control = FrogPilotParamValueControl(
      "LeadDetectionThreshold",
      "Lead Detection Sensitivity",
      "<b>How sensitive openpilot is to detecting vehicles.</b> Higher sensitivity allows quicker detection at longer distances but may react to non-vehicle objects; lower sensitivity is more conservative and reduces false detections.",
      "",
      min_value=25,
      max_value=50,
      label="%",
    )

    self._taco_tune_item = ListItem(
      title="\"Taco Bell Run\" Turn Speed Hack",
      description="<b>The turn-speed hack from comma's 2022 \"Taco Bell Run\".</b> Designed to slow down for left and right turns.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("TacoTune"),
        callback=lambda state: self._on_toggle("TacoTune", state),
      ),
    )

    longitudinal_tune_items = [
      self._acceleration_profile_control,
      self._deceleration_profile_control,
      self._human_acceleration_item,
      self._human_following_item,
      self._human_lane_changes_item,
      self._lead_detection_threshold_control,
      self._taco_tune_item,
    ]

    self._toggles["AccelerationProfile"] = self._acceleration_profile_control
    self._toggles["DecelerationProfile"] = self._deceleration_profile_control
    self._toggles["HumanAcceleration"] = self._human_acceleration_item
    self._toggles["HumanFollowing"] = self._human_following_item
    self._toggles["HumanLaneChanges"] = self._human_lane_changes_item
    self._toggles["LeadDetectionThreshold"] = self._lead_detection_threshold_control
    self._toggles["TacoTune"] = self._taco_tune_item

    self._longitudinal_tune_scroller = Scroller(longitudinal_tune_items, line_separator=True, spacing=0)

  def _build_qol_panel(self):
    self._custom_cruise_control = FrogPilotParamValueControl(
      "CustomCruise",
      "Cruise Interval",
      "<b>How much the set speed increases or decreases</b> for each + or – cruise control button press.",
      "",
      min_value=1,
      max_value=99,
      label=" mph",
    )

    self._custom_cruise_long_control = FrogPilotParamValueControl(
      "CustomCruiseLong",
      "Cruise Interval (Hold)",
      "<b>How much the set speed increases or decreases while holding the + or – cruise control buttons.</b>",
      "",
      min_value=1,
      max_value=99,
      label=" mph",
    )

    self._force_stops_item = ListItem(
      title="Force Stop at \"Detected\" Stop Lights/Signs",
      description="<b>Force openpilot to stop whenever the driving model \"detects\" a red light or stop sign.</b><br><br><i><b>Disclaimer</b>: openpilot does not explicitly detect traffic lights or stop signs. In \"Experimental Mode\", openpilot makes end-to-end driving decisions from camera input, which means it may stop even when there's no clear reason!</i>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("ForceStops"),
        callback=lambda state: self._on_toggle("ForceStops", state),
      ),
    )

    self._increased_stopped_distance_control = FrogPilotParamValueControl(
      "IncreasedStoppedDistance",
      "Increase Stopped Distance by:",
      "<b>Add extra space when stopped behind vehicles.</b> Increase for more room; decrease for shorter gaps.",
      "",
      min_value=0,
      max_value=10,
      label=" feet",
    )

    self._map_gears_control = FrogPilotButtonToggleControl(
      "MapGears",
      "Map Accel/Decel to Gears",
      "<b>Map the Acceleration or Deceleration profiles to the vehicle's \"Eco\" and \"Sport\" gear modes.</b>",
      "",
      button_params=["MapAcceleration", "MapDeceleration"],
      button_texts=["Acceleration", "Deceleration"],
    )

    self._set_speed_offset_control = FrogPilotParamValueControl(
      "SetSpeedOffset",
      "Offset Set Speed by:",
      "<b>Increase the set speed by the chosen offset.</b> For example, set +5 if you usually drive 5 over the limit.",
      "",
      min_value=0,
      max_value=99,
      label=" mph",
    )

    self._reverse_cruise_item = ListItem(
      title="Reverse Cruise Increase",
      description="<b>Reverse the cruise control button behavior</b> so a short press increases the set speed by 5 instead of 1.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("ReverseCruise"),
        callback=lambda state: self._on_toggle("ReverseCruise", state),
      ),
    )

    self._weather_presets_control = FrogPilotButtonsControl(
      "Weather Condition Offsets",
      "<b>Automatically adjust driving behavior based on real-time weather.</b> Helps maintain comfort and safety in low visibility, rain, or snow.",
      "",
      button_texts=["MANAGE"],
    )
    self._weather_presets_control.set_click_callback(lambda _: self._open_weather())

    qol_items = [
      self._custom_cruise_control,
      self._custom_cruise_long_control,
      self._force_stops_item,
      self._increased_stopped_distance_control,
      self._map_gears_control,
      self._set_speed_offset_control,
      self._reverse_cruise_item,
      self._weather_presets_control,
    ]

    self._toggles["CustomCruise"] = self._custom_cruise_control
    self._toggles["CustomCruiseLong"] = self._custom_cruise_long_control
    self._toggles["ForceStops"] = self._force_stops_item
    self._toggles["IncreasedStoppedDistance"] = self._increased_stopped_distance_control
    self._toggles["MapGears"] = self._map_gears_control
    self._toggles["SetSpeedOffset"] = self._set_speed_offset_control
    self._toggles["ReverseCruise"] = self._reverse_cruise_item
    self._toggles["WeatherPresets"] = self._weather_presets_control

    self._qol_scroller = Scroller(qol_items, line_separator=True, spacing=0)

  def _build_weather_panel(self):
    self._low_visibility_offsets_control = FrogPilotButtonsControl(
      "Low Visibility",
      "<b>Driving adjustments for fog, haze, or other low-visibility conditions.</b>",
      "",
      button_texts=["MANAGE"],
    )
    self._low_visibility_offsets_control.set_click_callback(lambda _: self._open_weather_low_visibility())

    self._rain_offsets_control = FrogPilotButtonsControl(
      "Rain",
      "<b>Driving adjustments for rainy conditions.</b>",
      "",
      button_texts=["MANAGE"],
    )
    self._rain_offsets_control.set_click_callback(lambda _: self._open_weather_rain())

    self._rain_storm_offsets_control = FrogPilotButtonsControl(
      "Rainstorms",
      "<b>Driving adjustments for rainstorms.</b>",
      "",
      button_texts=["MANAGE"],
    )
    self._rain_storm_offsets_control.set_click_callback(lambda _: self._open_weather_rain_storm())

    self._snow_offsets_control = FrogPilotButtonsControl(
      "Snow",
      "<b>Driving adjustments for snowy conditions.</b>",
      "",
      button_texts=["MANAGE"],
    )
    self._snow_offsets_control.set_click_callback(lambda _: self._open_weather_snow())

    self._set_weather_key_control = FrogPilotButtonsControl(
      "Set Your Own Key",
      "<b>Set your own \"OpenWeatherMap\" key to increase the weather update rate.</b><br><br><i>Personal keys grant 1,000 free calls per day, allowing for updates every minute. The default key is shared and only updates every 15 minutes.</i>",
      "",
      button_texts=["ADD", "TEST"],
    )
    self._set_weather_key_control.set_click_callback(self._on_weather_key_click)
    self._update_weather_key_button()

    weather_items = [
      self._low_visibility_offsets_control,
      self._rain_offsets_control,
      self._rain_storm_offsets_control,
      self._snow_offsets_control,
      self._set_weather_key_control,
    ]

    self._toggles["LowVisibilityOffsets"] = self._low_visibility_offsets_control
    self._toggles["RainOffsets"] = self._rain_offsets_control
    self._toggles["RainStormOffsets"] = self._rain_storm_offsets_control
    self._toggles["SnowOffsets"] = self._snow_offsets_control
    self._toggles["SetWeatherKey"] = self._set_weather_key_control

    self._weather_scroller = Scroller(weather_items, line_separator=True, spacing=0)

  def _build_weather_low_visibility_panel(self):
    follow_time_labels = build_follow_time_labels()

    self._increase_following_low_visibility_control = FrogPilotParamValueControl(
      "IncreaseFollowingLowVisibility",
      "Increase Following Distance by:",
      "<b>Add extra space behind lead vehicles in low visibility.</b> Increase for more space; decrease for tighter gaps.",
      "",
      min_value=0,
      max_value=3,
      value_labels=follow_time_labels,
      interval=0.01,
      fast_increase=True,
    )

    self._increased_stopped_distance_low_visibility_control = FrogPilotParamValueControl(
      "IncreasedStoppedDistanceLowVisibility",
      "Increase Stopped Distance by:",
      "<b>Add extra buffer when stopped behind vehicles in low visibility.</b> Increase for more room; decrease for shorter gaps.",
      "",
      min_value=0,
      max_value=10,
      label=" feet",
    )

    self._reduce_acceleration_low_visibility_control = FrogPilotParamValueControl(
      "ReduceAccelerationLowVisibility",
      "Reduce Acceleration by:",
      "<b>Lower the maximum acceleration in low visibility.</b> Increase for softer takeoffs; decrease for quicker but less stable takeoffs.",
      "",
      min_value=0,
      max_value=99,
      label="%",
    )

    self._reduce_lateral_acceleration_low_visibility_control = FrogPilotParamValueControl(
      "ReduceLateralAccelerationLowVisibility",
      "Reduce Speed in Curves by:",
      "<b>Lower the desired speed while driving through curves in low visibility.</b> Increase for safer, gentler turns; decrease for more aggressive driving in curves.",
      "",
      min_value=0,
      max_value=99,
      label="%",
    )

    low_visibility_items = [
      self._increase_following_low_visibility_control,
      self._increased_stopped_distance_low_visibility_control,
      self._reduce_acceleration_low_visibility_control,
      self._reduce_lateral_acceleration_low_visibility_control,
    ]

    self._toggles["IncreaseFollowingLowVisibility"] = self._increase_following_low_visibility_control
    self._toggles["IncreasedStoppedDistanceLowVisibility"] = self._increased_stopped_distance_low_visibility_control
    self._toggles["ReduceAccelerationLowVisibility"] = self._reduce_acceleration_low_visibility_control
    self._toggles["ReduceLateralAccelerationLowVisibility"] = self._reduce_lateral_acceleration_low_visibility_control

    self._weather_low_visibility_scroller = Scroller(low_visibility_items, line_separator=True, spacing=0)

  def _build_weather_rain_panel(self):
    follow_time_labels = build_follow_time_labels()

    self._increase_following_rain_control = FrogPilotParamValueControl(
      "IncreaseFollowingRain",
      "Increase Following Distance by:",
      "<b>Add extra space behind lead vehicles in rain.</b> Increase for more space; decrease for tighter gaps.",
      "",
      min_value=0,
      max_value=3,
      value_labels=follow_time_labels,
      interval=0.01,
      fast_increase=True,
    )

    self._increased_stopped_distance_rain_control = FrogPilotParamValueControl(
      "IncreasedStoppedDistanceRain",
      "Increase Stopped Distance by:",
      "<b>Add extra buffer when stopped behind vehicles in rain.</b> Increase for more room; decrease for shorter gaps.",
      "",
      min_value=0,
      max_value=10,
      label=" feet",
    )

    self._reduce_acceleration_rain_control = FrogPilotParamValueControl(
      "ReduceAccelerationRain",
      "Reduce Acceleration by:",
      "<b>Lower the maximum acceleration in rain.</b> Increase for softer takeoffs; decrease for quicker but less stable takeoffs.",
      "",
      min_value=0,
      max_value=99,
      label="%",
    )

    self._reduce_lateral_acceleration_rain_control = FrogPilotParamValueControl(
      "ReduceLateralAccelerationRain",
      "Reduce Speed in Curves by:",
      "<b>Lower the desired speed while driving through curves in rain.</b> Increase for safer, gentler turns; decrease for more aggressive driving in curves.",
      "",
      min_value=0,
      max_value=99,
      label="%",
    )

    rain_items = [
      self._increase_following_rain_control,
      self._increased_stopped_distance_rain_control,
      self._reduce_acceleration_rain_control,
      self._reduce_lateral_acceleration_rain_control,
    ]

    self._toggles["IncreaseFollowingRain"] = self._increase_following_rain_control
    self._toggles["IncreasedStoppedDistanceRain"] = self._increased_stopped_distance_rain_control
    self._toggles["ReduceAccelerationRain"] = self._reduce_acceleration_rain_control
    self._toggles["ReduceLateralAccelerationRain"] = self._reduce_lateral_acceleration_rain_control

    self._weather_rain_scroller = Scroller(rain_items, line_separator=True, spacing=0)

  def _build_weather_rain_storm_panel(self):
    follow_time_labels = build_follow_time_labels()

    self._increase_following_rain_storm_control = FrogPilotParamValueControl(
      "IncreaseFollowingRainStorm",
      "Increase Following Distance by:",
      "<b>Add extra space behind lead vehicles in a rainstorm.</b> Increase for more space; decrease for tighter gaps.",
      "",
      min_value=0,
      max_value=3,
      value_labels=follow_time_labels,
      interval=0.01,
      fast_increase=True,
    )

    self._increased_stopped_distance_rain_storm_control = FrogPilotParamValueControl(
      "IncreasedStoppedDistanceRainStorm",
      "Increase Stopped Distance by:",
      "<b>Add extra buffer when stopped behind vehicles in a rainstorm.</b> Increase for more room; decrease for shorter gaps.",
      "",
      min_value=0,
      max_value=10,
      label=" feet",
    )

    self._reduce_acceleration_rain_storm_control = FrogPilotParamValueControl(
      "ReduceAccelerationRainStorm",
      "Reduce Acceleration by:",
      "<b>Lower the maximum acceleration in a rainstorm.</b> Increase for softer takeoffs; decrease for quicker but less stable takeoffs.",
      "",
      min_value=0,
      max_value=99,
      label="%",
    )

    self._reduce_lateral_acceleration_rain_storm_control = FrogPilotParamValueControl(
      "ReduceLateralAccelerationRainStorm",
      "Reduce Speed in Curves by:",
      "<b>Lower the desired speed while driving through curves in a rainstorm.</b> Increase for safer, gentler turns; decrease for more aggressive driving in curves.",
      "",
      min_value=0,
      max_value=99,
      label="%",
    )

    rain_storm_items = [
      self._increase_following_rain_storm_control,
      self._increased_stopped_distance_rain_storm_control,
      self._reduce_acceleration_rain_storm_control,
      self._reduce_lateral_acceleration_rain_storm_control,
    ]

    self._toggles["IncreaseFollowingRainStorm"] = self._increase_following_rain_storm_control
    self._toggles["IncreasedStoppedDistanceRainStorm"] = self._increased_stopped_distance_rain_storm_control
    self._toggles["ReduceAccelerationRainStorm"] = self._reduce_acceleration_rain_storm_control
    self._toggles["ReduceLateralAccelerationRainStorm"] = self._reduce_lateral_acceleration_rain_storm_control

    self._weather_rain_storm_scroller = Scroller(rain_storm_items, line_separator=True, spacing=0)

  def _build_weather_snow_panel(self):
    follow_time_labels = build_follow_time_labels()

    self._increase_following_snow_control = FrogPilotParamValueControl(
      "IncreaseFollowingSnow",
      "Increase Following Distance by:",
      "<b>Add extra space behind lead vehicles in snow.</b> Increase for more space; decrease for tighter gaps.",
      "",
      min_value=0,
      max_value=3,
      value_labels=follow_time_labels,
      interval=0.01,
      fast_increase=True,
    )

    self._increased_stopped_distance_snow_control = FrogPilotParamValueControl(
      "IncreasedStoppedDistanceSnow",
      "Increase Stopped Distance by:",
      "<b>Add extra buffer when stopped behind vehicles in snow.</b> Increase for more room; decrease for shorter gaps.",
      "",
      min_value=0,
      max_value=10,
      label=" feet",
    )

    self._reduce_acceleration_snow_control = FrogPilotParamValueControl(
      "ReduceAccelerationSnow",
      "Reduce Acceleration by:",
      "<b>Lower the maximum acceleration in snow.</b> Increase for softer takeoffs; decrease for quicker but less stable takeoffs.",
      "",
      min_value=0,
      max_value=99,
      label="%",
    )

    self._reduce_lateral_acceleration_snow_control = FrogPilotParamValueControl(
      "ReduceLateralAccelerationSnow",
      "Reduce Speed in Curves by:",
      "<b>Lower the desired speed while driving through curves in snow.</b> Increase for safer, gentler turns; decrease for more aggressive driving in curves.",
      "",
      min_value=0,
      max_value=99,
      label="%",
    )

    snow_items = [
      self._increase_following_snow_control,
      self._increased_stopped_distance_snow_control,
      self._reduce_acceleration_snow_control,
      self._reduce_lateral_acceleration_snow_control,
    ]

    self._toggles["IncreaseFollowingSnow"] = self._increase_following_snow_control
    self._toggles["IncreasedStoppedDistanceSnow"] = self._increased_stopped_distance_snow_control
    self._toggles["ReduceAccelerationSnow"] = self._reduce_acceleration_snow_control
    self._toggles["ReduceLateralAccelerationSnow"] = self._reduce_lateral_acceleration_snow_control

    self._weather_snow_scroller = Scroller(snow_items, line_separator=True, spacing=0)

  def _build_speed_limit_controller_panel(self):
    self._slc_fallback_control = FrogPilotButtonsControl(
      "Fallback Speed",
      "<b>The speed used by \"Speed Limit Controller\" when no speed limit is found.</b><br><br>- <b>Set Speed</b>: Use the cruise set speed<br>- <b>Experimental Mode</b>: Estimate the limit using the driving model<br>- <b>Previous Limit</b>: Keep using the last confirmed limit",
      "",
      button_texts=["Set Speed", "Experimental Mode", "Previous Limit"],
      checkable=True,
      exclusive=True,
    )
    self._slc_fallback_control.set_click_callback(self._on_slc_fallback_click)
    self._slc_fallback_control.set_checked_button(self._params.get_int("SLCFallback"))

    self._slc_override_control = FrogPilotButtonsControl(
      "Override Speed",
      "<b>The speed used by \"Speed Limit Controller\" after you manually drive faster than the posted limit.</b><br><br>- <b>Set with Gas Pedal</b>: Use the highest speed reached while pressing the gas<br>- <b>Max Set Speed</b>: Use the cruise set speed<br><br>Overrides clear when openpilot disengages.",
      "",
      button_texts=["None", "Set With Gas Pedal", "Max Set Speed"],
      checkable=True,
      exclusive=True,
    )
    self._slc_override_control.set_click_callback(self._on_slc_override_click)
    self._slc_override_control.set_checked_button(self._params.get_int("SLCOverride"))

    self._slc_priority_item = ListItem(
      title="Speed Limit Source Priority",
      description="<b>The source order for speed limits</b> when more than one is available.",
      action_item=ButtonAction(
        initial_text="SELECT",
        callback=self._on_slc_priority_click,
      ),
    )

    self._slc_offsets_control = FrogPilotButtonsControl(
      "Speed Limit Offsets",
      "<b>Add an offset to the posted speed limit</b> to better match your driving style.",
      "",
      button_texts=["MANAGE"],
    )
    self._slc_offsets_control.set_click_callback(lambda _: self._open_slc_offsets())

    self._slc_qol_control = FrogPilotButtonsControl(
      "Quality of Life",
      "<b>Miscellaneous \"Speed Limit Controller\" changes</b> to fine-tune how openpilot drives.",
      "",
      button_texts=["MANAGE"],
    )
    self._slc_qol_control.set_click_callback(lambda _: self._open_slc_qol())

    self._slc_visuals_control = FrogPilotButtonsControl(
      "Visual Settings",
      "<b>Visual \"Speed Limit Controller\" changes</b> to fine-tune how the driving screen looks.",
      "",
      button_texts=["MANAGE"],
    )
    self._slc_visuals_control.set_click_callback(lambda _: self._open_slc_visuals())

    slc_items = [
      self._slc_fallback_control,
      self._slc_override_control,
      self._slc_priority_item,
      self._slc_offsets_control,
      self._slc_qol_control,
      self._slc_visuals_control,
    ]

    self._toggles["SLCFallback"] = self._slc_fallback_control
    self._toggles["SLCOverride"] = self._slc_override_control
    self._toggles["SLCPriority"] = self._slc_priority_item
    self._toggles["SLCOffsets"] = self._slc_offsets_control
    self._toggles["SLCQOL"] = self._slc_qol_control
    self._toggles["SLCVisuals"] = self._slc_visuals_control

    self._speed_limit_controller_scroller = Scroller(slc_items, line_separator=True, spacing=0)

  def _build_slc_offsets_panel(self):
    self._offset1_control = FrogPilotParamValueControl(
      "Offset1",
      "Speed Offset (0–24 mph)",
      "<b>How much to offset posted speed-limits</b> between 0 and 24 mph.",
      "",
      min_value=-99,
      max_value=99,
      label=" mph",
    )

    self._offset2_control = FrogPilotParamValueControl(
      "Offset2",
      "Speed Offset (25–34 mph)",
      "<b>How much to offset posted speed-limits</b> between 25 and 34 mph.",
      "",
      min_value=-99,
      max_value=99,
      label=" mph",
    )

    self._offset3_control = FrogPilotParamValueControl(
      "Offset3",
      "Speed Offset (35–44 mph)",
      "<b>How much to offset posted speed-limits</b> between 35 and 44 mph.",
      "",
      min_value=-99,
      max_value=99,
      label=" mph",
    )

    self._offset4_control = FrogPilotParamValueControl(
      "Offset4",
      "Speed Offset (45–54 mph)",
      "<b>How much to offset posted speed-limits</b> between 45 and 54 mph.",
      "",
      min_value=-99,
      max_value=99,
      label=" mph",
    )

    self._offset5_control = FrogPilotParamValueControl(
      "Offset5",
      "Speed Offset (55–64 mph)",
      "<b>How much to offset posted speed-limits</b> between 55 and 64 mph.",
      "",
      min_value=-99,
      max_value=99,
      label=" mph",
    )

    self._offset6_control = FrogPilotParamValueControl(
      "Offset6",
      "Speed Offset (65–74 mph)",
      "<b>How much to offset posted speed-limits</b> between 65 and 74 mph.",
      "",
      min_value=-99,
      max_value=99,
      label=" mph",
    )

    self._offset7_control = FrogPilotParamValueControl(
      "Offset7",
      "Speed Offset (75–99 mph)",
      "<b>How much to offset posted speed-limits</b> between 75 and 99 mph.",
      "",
      min_value=-99,
      max_value=99,
      label=" mph",
    )

    offset_items = [
      self._offset1_control,
      self._offset2_control,
      self._offset3_control,
      self._offset4_control,
      self._offset5_control,
      self._offset6_control,
      self._offset7_control,
    ]

    self._toggles["Offset1"] = self._offset1_control
    self._toggles["Offset2"] = self._offset2_control
    self._toggles["Offset3"] = self._offset3_control
    self._toggles["Offset4"] = self._offset4_control
    self._toggles["Offset5"] = self._offset5_control
    self._toggles["Offset6"] = self._offset6_control
    self._toggles["Offset7"] = self._offset7_control

    self._slc_offsets_scroller = Scroller(offset_items, line_separator=True, spacing=0)

  def _build_slc_qol_panel(self):
    self._slc_confirmation_control = FrogPilotButtonToggleControl(
      "SLCConfirmation",
      "Confirm New Speed Limits",
      "<b>Ask before changing to a new speed limit.</b> To accept, tap the flashing on-screen widget or press the Cruise Increase button. To deny, press the Cruise Decrease button or ignore the prompt for 30 seconds.",
      "",
      button_params=["SLCConfirmationLower", "SLCConfirmationHigher"],
      button_texts=["Lower Limits", "Higher Limits"],
    )

    self._slc_lookahead_higher_control = FrogPilotParamValueControl(
      "SLCLookaheadHigher",
      "Higher Limit Lookahead Time",
      "<b>How far ahead openpilot anticipates upcoming higher speed limits</b> from downloaded map data.",
      "",
      min_value=0,
      max_value=30,
      label=" seconds",
    )

    self._slc_lookahead_lower_control = FrogPilotParamValueControl(
      "SLCLookaheadLower",
      "Lower Limit Lookahead Time",
      "<b>How far ahead openpilot anticipates upcoming lower speed limits</b> from downloaded map data.",
      "",
      min_value=0,
      max_value=30,
      label=" seconds",
    )

    self._set_speed_limit_item = ListItem(
      title="Match Speed Limit on Engage",
      description="<b>When openpilot is first enabled, automatically set the max speed to the current posted limit.</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("SetSpeedLimit"),
        callback=lambda state: self._on_toggle("SetSpeedLimit", state),
      ),
    )

    self._slc_mapbox_filler_item = ListItem(
      title="Use Mapbox as Fallback",
      description="<b>Use Mapbox speed-limit data when no other source is available.</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("SLCMapboxFiller"),
        callback=lambda state: self._on_toggle("SLCMapboxFiller", state),
      ),
    )

    slc_qol_items = [
      self._slc_confirmation_control,
      self._slc_lookahead_higher_control,
      self._slc_lookahead_lower_control,
      self._set_speed_limit_item,
      self._slc_mapbox_filler_item,
    ]

    self._toggles["SLCConfirmation"] = self._slc_confirmation_control
    self._toggles["SLCLookaheadHigher"] = self._slc_lookahead_higher_control
    self._toggles["SLCLookaheadLower"] = self._slc_lookahead_lower_control
    self._toggles["SetSpeedLimit"] = self._set_speed_limit_item
    self._toggles["SLCMapboxFiller"] = self._slc_mapbox_filler_item

    self._slc_qol_scroller = Scroller(slc_qol_items, line_separator=True, spacing=0)

  def _build_slc_visuals_panel(self):
    self._show_slc_offset_item = ListItem(
      title="Show Speed Limit Offset",
      description="<b>Show the current offset from the posted limit</b> on the driving screen.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("ShowSLCOffset"),
        callback=lambda state: self._on_toggle("ShowSLCOffset", state),
      ),
    )

    self._speed_limit_sources_item = ListItem(
      title="Show Speed Limit Sources",
      description="<b>Display the speed-limit sources and their current values</b> on the driving screen.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("SpeedLimitSources"),
        callback=lambda state: self._on_toggle("SpeedLimitSources", state),
      ),
    )

    slc_visuals_items = [
      self._show_slc_offset_item,
      self._speed_limit_sources_item,
    ]

    self._toggles["ShowSLCOffset"] = self._show_slc_offset_item
    self._toggles["SpeedLimitSources"] = self._speed_limit_sources_item

    self._slc_visuals_scroller = Scroller(slc_visuals_items, line_separator=True, spacing=0)

  def _on_toggle(self, param: str, state: bool):
    self._params.put_bool(param, state)
    update_frogpilot_toggles()
    self._update_toggles()

  def _on_acceleration_profile_click(self, button_id: int):
    self._params.put_int("AccelerationProfile", button_id)
    update_frogpilot_toggles()

  def _on_deceleration_profile_click(self, button_id: int):
    self._params.put_int("DecelerationProfile", button_id)
    update_frogpilot_toggles()

  def _on_slc_fallback_click(self, button_id: int):
    self._params.put_int("SLCFallback", button_id)
    update_frogpilot_toggles()

  def _on_slc_override_click(self, button_id: int):
    self._params.put_int("SLCOverride", button_id)
    update_frogpilot_toggles()

  def _on_slc_priority_click(self):
    pass

  def _on_reset_curve_data(self):
    gui_app.set_modal_overlay(ConfirmDialog(
      "Are you sure you want to completely reset your curvature data?",
      "Reset",
      "Cancel",
    ))

  def _on_reset_traffic_personality(self):
    gui_app.set_modal_overlay(ConfirmDialog(
      "Are you sure you want to completely reset your settings for Traffic Mode?",
      "Reset",
      "Cancel",
    ))

  def _on_reset_aggressive_personality(self):
    gui_app.set_modal_overlay(ConfirmDialog(
      "Are you sure you want to completely reset your settings for the Aggressive personality?",
      "Reset",
      "Cancel",
    ))

  def _on_reset_standard_personality(self):
    gui_app.set_modal_overlay(ConfirmDialog(
      "Are you sure you want to completely reset your settings for the Standard personality?",
      "Reset",
      "Cancel",
    ))

  def _on_reset_relaxed_personality(self):
    gui_app.set_modal_overlay(ConfirmDialog(
      "Are you sure you want to completely reset your settings for the Relaxed personality?",
      "Reset",
      "Cancel",
    ))

  def _on_weather_key_click(self, button_id: int):
    if button_id == 0:
      key_exists = bool(self._params.get("WeatherToken"))
      if key_exists:
        gui_app.set_modal_overlay(ConfirmDialog(
          "Are you sure you want to remove your key?",
          "Remove",
          "Cancel",
        ))

  def _update_weather_key_button(self):
    key_exists = bool(self._params.get("WeatherToken"))
    self._set_weather_key_control.set_text(0, "REMOVE" if key_exists else "ADD")
    self._set_weather_key_control.set_visible_button(1, key_exists)

  def _update_curve_speed_labels(self):
    cal_lat_accel = self._params.get_float("CalibratedLateralAcceleration")
    cal_progress = self._params.get_float("CalibrationProgress")
    if hasattr(self._calibrated_lateral_acceleration_item, 'action_item'):
      self._calibrated_lateral_acceleration_item.action_item.set_text(f"{cal_lat_accel:.2f} m/s²")
    if hasattr(self._calibration_progress_item, 'action_item'):
      self._calibration_progress_item.action_item.set_text(f"{cal_progress:.2f}%")

  def _open_advanced_longitudinal_tune(self):
    self._current_panel = SubPanel.ADVANCED_LONGITUDINAL_TUNE

  def _open_conditional_experimental(self):
    self._current_panel = SubPanel.CONDITIONAL_EXPERIMENTAL

  def _open_curve_speed(self):
    self._current_panel = SubPanel.CURVE_SPEED

  def _open_custom_driving_personality(self):
    self._current_panel = SubPanel.CUSTOM_DRIVING_PERSONALITY

  def _open_traffic_personality(self):
    self._current_panel = SubPanel.TRAFFIC_PERSONALITY
    self._custom_personality_open = True

  def _open_aggressive_personality(self):
    self._current_panel = SubPanel.AGGRESSIVE_PERSONALITY
    self._custom_personality_open = True

  def _open_standard_personality(self):
    self._current_panel = SubPanel.STANDARD_PERSONALITY
    self._custom_personality_open = True

  def _open_relaxed_personality(self):
    self._current_panel = SubPanel.RELAXED_PERSONALITY
    self._custom_personality_open = True

  def _open_longitudinal_tune(self):
    self._current_panel = SubPanel.LONGITUDINAL_TUNE

  def _open_qol(self):
    self._current_panel = SubPanel.QOL

  def _open_weather(self):
    self._current_panel = SubPanel.WEATHER
    self._qol_open = True

  def _open_weather_low_visibility(self):
    self._current_panel = SubPanel.WEATHER_LOW_VISIBILITY
    self._weather_open = True

  def _open_weather_rain(self):
    self._current_panel = SubPanel.WEATHER_RAIN
    self._weather_open = True

  def _open_weather_rain_storm(self):
    self._current_panel = SubPanel.WEATHER_RAIN_STORM
    self._weather_open = True

  def _open_weather_snow(self):
    self._current_panel = SubPanel.WEATHER_SNOW
    self._weather_open = True

  def _open_speed_limit_controller(self):
    self._current_panel = SubPanel.SPEED_LIMIT_CONTROLLER

  def _open_slc_offsets(self):
    self._current_panel = SubPanel.SPEED_LIMIT_CONTROLLER_OFFSETS
    self._slc_open = True

  def _open_slc_qol(self):
    self._current_panel = SubPanel.SPEED_LIMIT_CONTROLLER_QOL
    self._slc_open = True

  def _open_slc_visuals(self):
    self._current_panel = SubPanel.SPEED_LIMIT_CONTROLLER_VISUALS
    self._slc_open = True

  def _close_sub_panel(self):
    self._current_panel = SubPanel.MAIN
    self._custom_personality_open = False
    self._qol_open = False
    self._slc_open = False
    self._weather_open = False

  def _update_car_params(self):
    try:
      from cereal import car, messaging
      car_params_bytes = self._params.get("CarParamsPersistent")
      if car_params_bytes:
        CP = messaging.log_from_bytes(car_params_bytes, car.CarParams)

        self._has_pcm_cruise = CP.pcmCruise
        self._has_radar = CP.radarUnavailable is False
        self._is_gm = CP.carName == "gm"
        self._is_toyota = CP.carName == "toyota"

        self._longitudinal_actuator_delay = CP.longitudinalActuatorDelay
        self._start_accel = getattr(CP, 'startAccel', 0.0)
        self._stop_accel = getattr(CP, 'stopAccel', 0.0)
        self._stopping_decel_rate = getattr(CP, 'stoppingDecelRate', 0.0)
        self._v_ego_starting = getattr(CP, 'vEgoStarting', 0.0)
        self._v_ego_stopping = getattr(CP, 'vEgoStopping', 0.0)

        self._update_advanced_tune_titles()
    except Exception:
      pass

  def _update_advanced_tune_titles(self):
    if self._longitudinal_actuator_delay != 0:
      self._longitudinal_actuator_delay_control._title_label.set_text(f"Actuator Delay (Default: {self._longitudinal_actuator_delay:.2f})")
    if self._start_accel != 0:
      self._start_accel_control._title_label.set_text(f"Start Acceleration (Default: {self._start_accel:.2f})")
    if self._stop_accel != 0:
      self._stop_accel_control._title_label.set_text(f"Stop Acceleration (Default: {self._stop_accel:.2f})")
    if self._stopping_decel_rate != 0:
      self._stopping_decel_rate_control._title_label.set_text(f"Stopping Rate (Default: {self._stopping_decel_rate:.2f})")
    if self._v_ego_starting != 0:
      self._v_ego_starting_control._title_label.set_text(f"Start Speed (Default: {self._v_ego_starting:.2f})")
    if self._v_ego_stopping != 0:
      self._v_ego_stopping_control._title_label.set_text(f"Stop Speed (Default: {self._v_ego_stopping:.2f})")

  def _update_metric(self):
    if self._is_metric:
      speed_labels = build_metric_speed_labels()
      distance_labels = build_metric_distance_labels()
      max_speed = 150
      max_distance = 3

      self._offset1_control._title_label.set_text("Speed Offset (0–29 km/h)")
      self._offset2_control._title_label.set_text("Speed Offset (30–49 km/h)")
      self._offset3_control._title_label.set_text("Speed Offset (50–59 km/h)")
      self._offset4_control._title_label.set_text("Speed Offset (60–79 km/h)")
      self._offset5_control._title_label.set_text("Speed Offset (80–99 km/h)")
      self._offset6_control._title_label.set_text("Speed Offset (100–119 km/h)")
      self._offset7_control._title_label.set_text("Speed Offset (120–140 km/h)")
    else:
      speed_labels = build_imperial_speed_labels()
      distance_labels = build_imperial_distance_labels()
      max_speed = 99
      max_distance = 10

      self._offset1_control._title_label.set_text("Speed Offset (0–24 mph)")
      self._offset2_control._title_label.set_text("Speed Offset (25–34 mph)")
      self._offset3_control._title_label.set_text("Speed Offset (35–44 mph)")
      self._offset4_control._title_label.set_text("Speed Offset (45–54 mph)")
      self._offset5_control._title_label.set_text("Speed Offset (55–64 mph)")
      self._offset6_control._title_label.set_text("Speed Offset (65–74 mph)")
      self._offset7_control._title_label.set_text("Speed Offset (75–99 mph)")

    self._ce_speed_control.update_control(0, max_speed, speed_labels)
    self._ce_speed_lead_control.update_control(0, max_speed, speed_labels)
    self._ce_signal_speed_control.update_control(0, max_speed, speed_labels)
    self._custom_cruise_control.update_control(1, max_speed, speed_labels)
    self._custom_cruise_long_control.update_control(1, max_speed, speed_labels)
    self._set_speed_offset_control.update_control(0, max_speed, speed_labels)

    self._increased_stopped_distance_control.update_control(0, max_distance, distance_labels)
    self._increased_stopped_distance_low_visibility_control.update_control(0, max_distance, distance_labels)
    self._increased_stopped_distance_rain_control.update_control(0, max_distance, distance_labels)
    self._increased_stopped_distance_rain_storm_control.update_control(0, max_distance, distance_labels)
    self._increased_stopped_distance_snow_control.update_control(0, max_distance, distance_labels)

    offset_max = 150 if self._is_metric else 99
    self._offset1_control.update_control(-offset_max, offset_max)
    self._offset2_control.update_control(-offset_max, offset_max)
    self._offset3_control.update_control(-offset_max, offset_max)
    self._offset4_control.update_control(-offset_max, offset_max)
    self._offset5_control.update_control(-offset_max, offset_max)
    self._offset6_control.update_control(-offset_max, offset_max)
    self._offset7_control.update_control(-offset_max, offset_max)

  def _update_toggles(self):
    self._tuning_level = self._params.get_int("TuningLevel") or 0

    human_accel_enabled = self._params.get_bool("LongitudinalTune") and self._params.get_bool("HumanAcceleration")
    experimental_gm_tune = self._params.get_bool("ExperimentalGMTune")
    frogs_go_moos_tweak = self._params.get_bool("FrogsGoMoosTweak")

    if hasattr(self._custom_cruise_control, 'set_visible'):
      self._custom_cruise_control.set_visible(not self._has_pcm_cruise)
    if hasattr(self._custom_cruise_long_control, 'set_visible'):
      self._custom_cruise_long_control.set_visible(not self._has_pcm_cruise)
    if hasattr(self._set_speed_offset_control, 'set_visible'):
      self._set_speed_offset_control.set_visible(not self._has_pcm_cruise)
    if hasattr(self._set_speed_limit_item, 'set_visible'):
      self._set_speed_limit_item.set_visible(not self._has_pcm_cruise)

    if hasattr(self._human_lane_changes_item, 'set_visible'):
      self._human_lane_changes_item.set_visible(self._has_radar)

    if hasattr(self._map_gears_control, 'set_visible'):
      self._map_gears_control.set_visible(self._is_toyota and not self._is_tsk)

    if hasattr(self._reverse_cruise_item, 'set_visible'):
      self._reverse_cruise_item.set_visible(self._is_toyota)

    if hasattr(self._slc_mapbox_filler_item, 'set_visible'):
      self._slc_mapbox_filler_item.set_visible(bool(self._params.get("MapboxSecretKey")))

    if hasattr(self._start_accel_control, 'set_visible'):
      self._start_accel_control.set_visible(not human_accel_enabled)

    stopping_controls_visible = True
    if self._is_gm and experimental_gm_tune:
      stopping_controls_visible = False
    if self._is_toyota and frogs_go_moos_tweak:
      stopping_controls_visible = False

    if hasattr(self._stopping_decel_rate_control, 'set_visible'):
      self._stopping_decel_rate_control.set_visible(stopping_controls_visible)
    if hasattr(self._v_ego_starting_control, 'set_visible'):
      self._v_ego_starting_control.set_visible(stopping_controls_visible)
    if hasattr(self._v_ego_stopping_control, 'set_visible'):
      self._v_ego_stopping_control.set_visible(stopping_controls_visible)

    ce_model_stop_visible = self._tuning_level >= 2
    if hasattr(self._ce_stop_lights_item, 'set_visible'):
      self._ce_stop_lights_item.set_visible(not ce_model_stop_visible)

  def show_event(self):
    super().show_event()
    self._main_scroller.show_event()
    self._is_metric = self._params.get_bool("IsMetric")
    self._update_car_params()
    self._update_metric()
    self._update_curve_speed_labels()
    self._update_weather_key_button()
    self._update_toggles()

  def hide_event(self):
    super().hide_event()
    self._current_panel = SubPanel.MAIN
    self._custom_personality_open = False
    self._qol_open = False
    self._slc_open = False
    self._weather_open = False

  def _render(self, rect):
    if self._current_panel == SubPanel.ADVANCED_LONGITUDINAL_TUNE:
      self._advanced_longitudinal_tune_scroller.render(rect)
    elif self._current_panel == SubPanel.AGGRESSIVE_PERSONALITY:
      self._aggressive_personality_scroller.render(rect)
    elif self._current_panel == SubPanel.CONDITIONAL_EXPERIMENTAL:
      self._conditional_experimental_scroller.render(rect)
    elif self._current_panel == SubPanel.CURVE_SPEED:
      self._curve_speed_scroller.render(rect)
    elif self._current_panel == SubPanel.CUSTOM_DRIVING_PERSONALITY:
      self._custom_driving_personality_scroller.render(rect)
    elif self._current_panel == SubPanel.LONGITUDINAL_TUNE:
      self._longitudinal_tune_scroller.render(rect)
    elif self._current_panel == SubPanel.QOL:
      self._qol_scroller.render(rect)
    elif self._current_panel == SubPanel.RELAXED_PERSONALITY:
      self._relaxed_personality_scroller.render(rect)
    elif self._current_panel == SubPanel.SPEED_LIMIT_CONTROLLER:
      self._speed_limit_controller_scroller.render(rect)
    elif self._current_panel == SubPanel.SPEED_LIMIT_CONTROLLER_OFFSETS:
      self._slc_offsets_scroller.render(rect)
    elif self._current_panel == SubPanel.SPEED_LIMIT_CONTROLLER_QOL:
      self._slc_qol_scroller.render(rect)
    elif self._current_panel == SubPanel.SPEED_LIMIT_CONTROLLER_VISUALS:
      self._slc_visuals_scroller.render(rect)
    elif self._current_panel == SubPanel.STANDARD_PERSONALITY:
      self._standard_personality_scroller.render(rect)
    elif self._current_panel == SubPanel.TRAFFIC_PERSONALITY:
      self._traffic_personality_scroller.render(rect)
    elif self._current_panel == SubPanel.WEATHER:
      self._weather_scroller.render(rect)
    elif self._current_panel == SubPanel.WEATHER_LOW_VISIBILITY:
      self._weather_low_visibility_scroller.render(rect)
    elif self._current_panel == SubPanel.WEATHER_RAIN:
      self._weather_rain_scroller.render(rect)
    elif self._current_panel == SubPanel.WEATHER_RAIN_STORM:
      self._weather_rain_storm_scroller.render(rect)
    elif self._current_panel == SubPanel.WEATHER_SNOW:
      self._weather_snow_scroller.render(rect)
    else:
      self._main_scroller.render(rect)
