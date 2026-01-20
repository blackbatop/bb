import json

from cereal import car, custom, log, messaging
from enum import IntEnum

from openpilot.common.params import Params
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.confirm_dialog import alert_dialog
from openpilot.system.ui.widgets.list_view import button_item, multiple_button_item
from openpilot.system.ui.widgets.scroller_tici import Scroller

from openpilot.frogpilot.common.frogpilot_variables import (
  TUNING_LEVELS,
  nnff_supported,
  update_frogpilot_toggles,
)
from openpilot.frogpilot.ui.layouts.settings.data_settings import FrogPilotDataPanel
from openpilot.frogpilot.ui.layouts.settings.device_settings import FrogPilotDevicePanel
from openpilot.frogpilot.ui.layouts.settings.lateral_settings import FrogPilotLateralPanel
from openpilot.frogpilot.ui.layouts.settings.longitudinal_settings import FrogPilotLongitudinalPanel
from openpilot.frogpilot.ui.layouts.settings.model_settings import FrogPilotModelPanel
from openpilot.frogpilot.ui.layouts.settings.sounds_settings import FrogPilotSoundsPanel
from openpilot.frogpilot.ui.layouts.settings.theme_settings import FrogPilotThemePanel
from openpilot.frogpilot.ui.layouts.settings.utilities import FrogPilotUtilitiesPanel
from openpilot.frogpilot.ui.layouts.settings.vehicle_settings import FrogPilotVehiclesPanel
from openpilot.frogpilot.ui.layouts.settings.visual_settings import FrogPilotVisualsPanel

TUNING_BUTTON_WIDTH = 180


class SubPanel(IntEnum):
  NONE = 0
  DATA = 1
  DEVICE = 2
  LATERAL = 3
  LONGITUDINAL = 4
  MODEL = 5
  SOUNDS = 6
  THEME = 7
  UTILITIES = 8
  VEHICLES = 9
  VISUALS = 10


class FrogPilotLayout(Widget):
  def __init__(self):
    super().__init__()

    self._params = Params()

    self._can_use_pedal = False
    self._can_use_sdsu = False
    self._car_make = ""
    self._car_model = ""
    self._current_subpanel = SubPanel.NONE
    self._force_open_descriptions = False
    self._friction = 0.0
    self._frogpilot_toggle_levels = {}
    self._has_alpha_longitudinal = False
    self._has_auto_tune = True
    self._has_bsm = True
    self._has_dash_speed_limits = True
    self._has_nnff_log = True
    self._has_openpilot_longitudinal = True
    self._has_pcm_cruise = False
    self._has_pedal = False
    self._has_radar = True
    self._has_sdsu = False
    self._has_sng = False
    self._has_zss = False
    self._is_angle_car = False
    self._is_bolt = False
    self._is_frogs_go_moo = False
    self._is_gm = True
    self._is_hkg = True
    self._is_hkg_canfd = True
    self._is_subaru = False
    self._is_torque_car = False
    self._is_toyota = True
    self._is_tsk = False
    self._is_volt = True
    self._lat_accel_factor = 0.0
    self._lkas_allowed_for_aol = False
    self._longitudinal_actuator_delay = 0.0
    self._openpilot_longitudinal_control_disabled = False
    self._shown_descriptions = {}
    self._start_accel = 0.0
    self._steer_actuator_delay = 0.0
    self._steer_kp = 1.0
    self._steer_ratio = 0.0
    self._stop_accel = 0.0
    self._stopping_decel_rate = 0.0
    self._tuning_level = self._params.get_int("TuningLevel") or 0
    self._v_ego_starting = 0.0
    self._v_ego_stopping = 0.0

    self._subpanels = {
      SubPanel.DATA: FrogPilotDataPanel(),
      SubPanel.DEVICE: FrogPilotDevicePanel(),
      SubPanel.LATERAL: FrogPilotLateralPanel(),
      SubPanel.LONGITUDINAL: FrogPilotLongitudinalPanel(),
      SubPanel.MODEL: FrogPilotModelPanel(),
      SubPanel.SOUNDS: FrogPilotSoundsPanel(),
      SubPanel.THEME: FrogPilotThemePanel(),
      SubPanel.UTILITIES: FrogPilotUtilitiesPanel(),
      SubPanel.VEHICLES: FrogPilotVehiclesPanel(),
      SubPanel.VISUALS: FrogPilotVisualsPanel(),
    }

    self._load_shown_descriptions()
    self._load_toggle_levels()
    self._check_force_open_descriptions()

    self._tuning_level_item = multiple_button_item(
      lambda: "Tuning Level",
      lambda: (
        "Choose your tuning level. Lower levels keep it simple; higher levels unlock more toggles for finer control.\n\n"
        "Minimal - Ideal for those who prefer simplicity or ease of use\n"
        "Standard - Recommended for most users for a balanced experience\n"
        "Advanced - Fine-tuning for experienced users\n"
        "Developer - Highly customizable settings for seasoned enthusiasts"
      ),
      buttons=[lambda: "Minimal", lambda: "Standard", lambda: "Advanced", lambda: "Developer"],
      button_width=TUNING_BUTTON_WIDTH,
      selected_index=self._tuning_level,
      callback=self._on_tuning_level_changed,
      icon="../../frogpilot/assets/toggle_icons/icon_tuning.png",
    )

    self._sound_panel_item = button_item(
      lambda: "Alerts and Sounds",
      lambda: "MANAGE",
      lambda: "<b>Adjust alert volumes and enable custom notifications.</b>",
      callback=lambda: self._open_subpanel(SubPanel.SOUNDS),
    )

    self._model_panel_item = button_item(
      lambda: "Driving Model",
      lambda: "MANAGE",
      lambda: "<b>Select and configure driving models.</b>",
      callback=lambda: self._open_subpanel(SubPanel.MODEL),
    )

    self._longitudinal_panel_item = button_item(
      lambda: "Gas / Brake",
      lambda: "MANAGE",
      lambda: "<b>Fine-tune acceleration and braking controls.</b>",
      callback=lambda: self._open_subpanel(SubPanel.LONGITUDINAL),
    )

    self._lateral_panel_item = button_item(
      lambda: "Steering",
      lambda: "MANAGE",
      lambda: "<b>Fine-tune steering controls.</b>",
      callback=lambda: self._open_subpanel(SubPanel.LATERAL),
    )

    self._data_panel_item = button_item(
      lambda: "Data",
      lambda: "MANAGE",
      lambda: "<b>Manage data and backups.</b>",
      callback=lambda: self._open_subpanel(SubPanel.DATA),
    )

    self._device_panel_item = button_item(
      lambda: "Device Controls",
      lambda: "MANAGE",
      lambda: "<b>Configure device settings and screen options.</b>",
      callback=lambda: self._open_subpanel(SubPanel.DEVICE),
    )

    self._utilities_panel_item = button_item(
      lambda: "Utilities",
      lambda: "MANAGE",
      lambda: "<b>Tools to keep FrogPilot running smoothly.</b>",
      callback=lambda: self._open_subpanel(SubPanel.UTILITIES),
    )

    self._visuals_panel_item = button_item(
      lambda: "Appearance",
      lambda: "MANAGE",
      lambda: "<b>Customize the look of the driving screen.</b>",
      callback=lambda: self._open_subpanel(SubPanel.VISUALS),
    )

    self._theme_panel_item = button_item(
      lambda: "Theme",
      lambda: "MANAGE",
      lambda: "<b>Customize themes and colors.</b>",
      callback=lambda: self._open_subpanel(SubPanel.THEME),
    )

    self._vehicles_panel_item = button_item(
      lambda: "Vehicle Settings",
      lambda: "MANAGE",
      lambda: "<b>Configure car-specific options.</b>",
      callback=lambda: self._open_subpanel(SubPanel.VEHICLES),
    )

    items = [
      self._tuning_level_item,
      self._sound_panel_item,
      self._model_panel_item,
      self._longitudinal_panel_item,
      self._lateral_panel_item,
      self._data_panel_item,
      self._device_panel_item,
      self._utilities_panel_item,
      self._visuals_panel_item,
      self._theme_panel_item,
      self._vehicles_panel_item,
    ]

    self._main_scroller = Scroller(items, line_separator=True, spacing=0)

    ui_state.add_offroad_transition_callback(self._update_variables)

  def _load_shown_descriptions(self):
    try:
      data = self._params.get("ShownToggleDescriptions")
      if data:
        self._shown_descriptions = json.loads(data)
    except (json.JSONDecodeError, TypeError):
      self._shown_descriptions = {}

  def _save_shown_descriptions(self):
    self._params.put_nonblocking("ShownToggleDescriptions", json.dumps(self._shown_descriptions))

  def _load_toggle_levels(self):
    keys = self._params.all_keys()
    for key in keys:
      key_str = key.decode() if isinstance(key, bytes) else key
      self._frogpilot_toggle_levels[key_str] = self._params.get_tuning_level(key)

  def _check_force_open_descriptions(self):
    class_name = "FrogPilotLayout"
    if not self._shown_descriptions.get(class_name, False):
      self._force_open_descriptions = True

  def _on_tuning_level_changed(self, level: int):
    self._tuning_level = level
    self._params.put_int("TuningLevel", level)
    update_frogpilot_toggles()
    self._update_panel_visibility()

    if level == TUNING_LEVELS["DEVELOPER"]:
      gui_app.set_modal_overlay(alert_dialog(
        "WARNING: These settings are risky and can drastically change how openpilot drives. "
        "Only change if you fully understand what they do!"
      ))

  def _open_subpanel(self, subpanel: SubPanel):
    if self._current_subpanel != SubPanel.NONE:
      self._subpanels[self._current_subpanel].hide_event()
    self._current_subpanel = subpanel
    if subpanel != SubPanel.NONE:
      self._subpanels[subpanel].show_event()

  def _close_subpanel(self):
    if self._current_subpanel != SubPanel.NONE:
      self._subpanels[self._current_subpanel].hide_event()
    self._current_subpanel = SubPanel.NONE

  def _render(self, rect):
    if self._current_subpanel != SubPanel.NONE:
      self._subpanels[self._current_subpanel].render(rect)
    else:
      self._main_scroller.render(rect)

  def show_event(self):
    super().show_event()
    self._main_scroller.show_event()

    class_name = "FrogPilotLayout"
    if not self._shown_descriptions.get(class_name, False):
      self._shown_descriptions[class_name] = True
      self._save_shown_descriptions()

    if self._force_open_descriptions:
      self._force_open_descriptions = False
      gui_app.set_modal_overlay(alert_dialog(
        "All toggle descriptions are currently expanded. You can tap a toggle's name to open or close its description at any time!"
      ))

    if self._current_subpanel != SubPanel.NONE:
      self._subpanels[self._current_subpanel].show_event()

    self._update_variables()

  def hide_event(self):
    super().hide_event()
    if self._current_subpanel != SubPanel.NONE:
      self._subpanels[self._current_subpanel].hide_event()
    update_frogpilot_toggles()

  def _update_variables(self):
    try:
      car_params_bytes = self._params.get("CarParamsPersistent")
      if car_params_bytes:
        CP = messaging.log_from_bytes(car_params_bytes, car.CarParams)

        self._car_make = CP.brand
        self._car_model = CP.carFingerprint

        self._friction = CP.lateralTuning.torque.friction
        self._has_alpha_longitudinal = CP.alphaLongitudinalAvailable
        self._has_bsm = CP.enableBsm
        self._has_dash_speed_limits = self._car_make in ("ford", "hyundai", "toyota")
        self._has_nnff_log = nnff_supported(self._car_model)
        self._has_openpilot_longitudinal = CP.openpilotLongitudinalControl
        self._has_pcm_cruise = CP.pcmCruise
        self._has_pedal = CP.enableGasInterceptorDEPRECATED
        self._has_radar = not CP.radarUnavailable
        self._has_sng = CP.autoResumeSng
        self._is_angle_car = CP.steerControlType == car.CarParams.SteerControlType.angle
        self._is_bolt = self._car_model in ("CHEVROLET_BOLT_CC", "CHEVROLET_BOLT_EUV")
        self._is_gm = self._car_make == "gm"
        self._is_hkg = self._car_make == "hyundai"
        self._is_subaru = self._car_make == "subaru"
        self._is_torque_car = CP.lateralTuning.which() == "torque"
        self._is_toyota = self._car_make == "toyota"
        self._is_tsk = CP.secOcRequired
        self._is_volt = self._car_model == "CHEVROLET_VOLT"
        self._lat_accel_factor = CP.lateralTuning.torque.latAccelFactor
        self._longitudinal_actuator_delay = CP.longitudinalActuatorDelay
        self._start_accel = CP.startAccel
        self._steer_actuator_delay = CP.steerActuatorDelay
        self._steer_ratio = CP.steerRatio
        self._stop_accel = CP.stopAccel
        self._stopping_decel_rate = CP.stoppingDecelRate
        self._v_ego_starting = CP.vEgoStarting
        self._v_ego_stopping = CP.vEgoStopping

        self._update_stock_values(CP)
    except Exception:
      pass

    try:
      fp_car_params_bytes = self._params.get("FrogPilotCarParamsPersistent")
      if fp_car_params_bytes:
        FPCP = messaging.log_from_bytes(fp_car_params_bytes, custom.FrogPilotCarParams)
        self._can_use_pedal = FPCP.canUsePedal
        self._can_use_sdsu = FPCP.canUseSDSU
        self._openpilot_longitudinal_control_disabled = FPCP.openpilotLongitudinalControlDisabled
    except Exception:
      pass

    try:
      ltp_bytes = self._params.get("LiveTorqueParameters")
      if ltp_bytes:
        LTP = messaging.log_from_bytes(ltp_bytes, log.LiveTorqueParametersData)
        self._has_auto_tune = LTP.useParams
    except Exception:
      pass

    self._update_panel_visibility()

  def _update_stock_values(self, CP):
    stock_params = [
      ("SteerDelayStock", "SteerDelay", self._steer_actuator_delay),
      ("SteerFrictionStock", "SteerFriction", self._friction),
      ("SteerKPStock", "SteerKP", self._steer_kp),
      ("SteerLatAccelStock", "SteerLatAccel", self._lat_accel_factor),
      ("LongitudinalActuatorDelayStock", "LongitudinalActuatorDelay", self._longitudinal_actuator_delay),
      ("StartAccelStock", "StartAccel", self._start_accel),
      ("SteerRatioStock", "SteerRatio", self._steer_ratio),
      ("StopAccelStock", "StopAccel", self._stop_accel),
      ("StoppingDecelRateStock", "StoppingDecelRate", self._stopping_decel_rate),
      ("VEgoStartingStock", "VEgoStarting", self._v_ego_starting),
      ("VEgoStoppingStock", "VEgoStopping", self._v_ego_stopping),
    ]

    for stock_key, user_key, new_value in stock_params:
      if new_value == 0:
        continue

      current_stock = self._params.get_float(stock_key)
      if current_stock != new_value:
        current_user = self._params.get_float(user_key)
        if current_user == current_stock or current_stock == 0:
          self._params.put_float_nonblocking(user_key, new_value)
        self._params.put_float_nonblocking(stock_key, new_value)

  def _update_panel_visibility(self):
    self._longitudinal_panel_item.set_visible(self._has_openpilot_longitudinal)

    device_mgmt_level = self._frogpilot_toggle_levels.get("DeviceManagement", 0)
    screen_mgmt_level = self._frogpilot_toggle_levels.get("ScreenManagement", 0)
    self._device_panel_item.set_visible(self._tuning_level >= device_mgmt_level or self._tuning_level >= screen_mgmt_level)

  @property
  def tuning_level(self) -> int:
    return self._tuning_level

  @property
  def has_openpilot_longitudinal(self) -> bool:
    return self._has_openpilot_longitudinal

  @property
  def car_make(self) -> str:
    return self._car_make

  @property
  def car_model(self) -> str:
    return self._car_model
