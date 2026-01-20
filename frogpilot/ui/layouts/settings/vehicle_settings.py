import re

from enum import IntEnum
from pathlib import Path

from openpilot.common.params import Params
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.hardware import HARDWARE
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.confirm_dialog import ConfirmDialog, alert_dialog
from openpilot.system.ui.widgets.list_view import ListItem, ToggleAction, ButtonAction, TextAction, ITEM_TEXT_VALUE_COLOR
from openpilot.system.ui.widgets.option_dialog import MultiOptionDialog
from openpilot.system.ui.widgets.scroller_tici import Scroller

from openpilot.frogpilot.common.frogpilot_variables import update_frogpilot_toggles
from openpilot.frogpilot.system.ui.widgets.frogpilot_controls import (
  FrogPilotButtonsControl,
  FrogPilotButtonToggleControl,
  FrogPilotConfirmationDialog,
  FrogPilotManageControl,
  FrogPilotParamValueControl,
  FrogPilotParamValueButtonControl,
)

OPENDBC_PATH = Path("/data/openpilot/opendbc/car")

# Map car makes to their parent brand folder in opendbc
MAKE_TO_FOLDER = {
  "acura": "honda",
  "audi": "volkswagen",
  "buick": "gm",
  "cadillac": "gm",
  "chevrolet": "gm",
  "chrysler": "chrysler",
  "cupra": "volkswagen",
  "dodge": "chrysler",
  "ford": "ford",
  "genesis": "hyundai",
  "gmc": "gm",
  "holden": "gm",
  "honda": "honda",
  "hyundai": "hyundai",
  "jeep": "chrysler",
  "kia": "hyundai",
  "lexus": "toyota",
  "lincoln": "ford",
  "man": "volkswagen",
  "mazda": "mazda",
  "nissan": "nissan",
  "peugeot": "psa",
  "ram": "chrysler",
  "rivian": "rivian",
  "seat": "volkswagen",
  "škoda": "volkswagen",
  "subaru": "subaru",
  "tesla": "tesla",
  "toyota": "toyota",
  "volkswagen": "volkswagen",
}

CAR_MAKES = [
  "Acura", "Audi", "Buick", "Cadillac", "Chevrolet", "Chrysler", "CUPRA",
  "Dodge", "Ford", "Genesis", "GMC", "Holden", "Honda", "Hyundai", "Jeep",
  "Kia", "Lexus", "Lincoln", "MAN", "Mazda", "Nissan", "Peugeot", "Ram",
  "Rivian", "SEAT", "Škoda", "Subaru", "Tesla", "Toyota", "Volkswagen",
]

GM_KEYS = {"VoltSNG"}
HKG_KEYS = {"TacoTuneHacks"}
SUBARU_KEYS = {"SubaruSNG"}
TOYOTA_KEYS = {"ClusterOffset", "FrogsGoMoosTweak", "LockDoorsTimer", "SNGHack", "ToyotaDoors"}
LONGITUDINAL_KEYS = {"FrogsGoMoosTweak", "SNGHack", "VoltSNG"}
VEHICLE_INFO_KEYS = {"BlindSpotSupport", "HardwareDetected", "OpenpilotLongitudinal", "PedalSupport", "RadarSupport", "SDSUSupport", "SNGSupport"}


class SubPanel(IntEnum):
  MAIN = 0
  GM = 1
  HKG = 2
  SUBARU = 3
  TOYOTA = 4
  VEHICLE_INFO = 5


def get_car_names(car_make: str) -> tuple[list[str], dict[str, str]]:
  """
  Parse opendbc values.py to get car names for a given make.
  Returns (car_names_list, car_name_to_platform_map).
  """
  car_names = []
  car_models = {}

  folder = MAKE_TO_FOLDER.get(car_make.lower(), "")
  if not folder:
    return car_names, car_models

  values_path = OPENDBC_PATH / folder / "values.py"
  if not values_path.exists():
    return car_names, car_models

  try:
    content = values_path.read_text()
  except Exception:
    return car_names, car_models

  # Remove comments and footnotes
  content = re.sub(r'#[^\n]*', '', content)
  content = re.sub(r'footnotes=\[[^\]]*\],\s*', '', content)

  # Find platform definitions: PLATFORM_NAME = SomeClass(
  platform_pattern = re.compile(r'(\w+)\s*=\s*\w+\s*\(')
  platforms = []
  for match in platform_pattern.finditer(content):
    platforms.append((match.start(), match.group(1)))
  platforms.append((len(content), ""))

  # Find car names: CarDocs*("Car Name"
  car_name_pattern = re.compile(r'CarDocs\w*\s*\(\s*"([^"]+)"')
  lower_make = car_make.lower()

  for i in range(len(platforms) - 1):
    start = platforms[i][0]
    end = platforms[i + 1][0]
    platform_name = platforms[i][1]

    section = content[start:end]

    for match in car_name_pattern.finditer(section):
      car_name = match.group(1)
      if car_name.lower().startswith(lower_make):
        car_models[car_name] = platform_name
        car_names.append(car_name)

  car_names.sort(key=str.lower)
  return car_names, car_models


def build_lock_timer_labels() -> dict[int, str]:
  """Build labels for lock doors timer (0-300 seconds)."""
  labels = {}
  for i in range(0, 301):
    if i == 0:
      labels[i] = "Never"
    elif i == 1:
      labels[i] = "1 second"
    else:
      labels[i] = f"{i} seconds"
  return labels


class FrogPilotVehiclesPanel(Widget):
  def __init__(self):
    super().__init__()

    self._current_panel = SubPanel.MAIN
    self._params = Params()
    self._toggles = {}
    self._tuning_level = 0

    # Car model mapping (car_name -> platform)
    self._car_models: dict[str, str] = {}

    # State tracking
    self._started = False

    # Car capabilities (loaded from frogpilot_variables)
    self._has_bsm = False
    self._has_openpilot_longitudinal = False
    self._has_pedal = False
    self._has_radar = False
    self._has_sdsu = False
    self._has_sng = False
    self._has_zss = False
    self._can_use_pedal = False
    self._can_use_sdsu = False
    self._has_alpha_longitudinal = False
    self._openpilot_longitudinal_disabled = False

    # Car brand flags
    self._is_gm = False
    self._is_hkg = False
    self._is_hkg_canfd = False
    self._is_subaru = False
    self._is_toyota = False
    self._is_volt = False

    self._build_main_panel()
    self._build_gm_panel()
    self._build_hkg_panel()
    self._build_subaru_panel()
    self._build_toyota_panel()
    self._build_vehicle_info_panel()

    ui_state.add_offroad_transition_callback(self._update_toggles)

  def _build_main_panel(self):
    # Car Make Selection
    self._car_make_item = ListItem(
      title="Car Make",
      action_item=ButtonAction(
        text="SELECT",
        callback=self._on_car_make_click,
      ),
    )

    # Car Model Selection
    self._car_model_item = ListItem(
      title="Car Model",
      action_item=ButtonAction(
        text="SELECT",
        callback=self._on_car_model_click,
      ),
    )

    # Force Fingerprint Toggle
    self._force_fingerprint_item = ListItem(
      title="Disable Automatic Fingerprint Detection",
      description="<b>Force the selected fingerprint</b> and prevent it from ever changing.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("ForceFingerprint"),
        callback=lambda state: self._simple_toggle("ForceFingerprint", state),
      ),
    )

    # Disable openpilot Longitudinal Toggle
    self._disable_op_long_item = ListItem(
      title="Disable openpilot Longitudinal Control",
      description="<b>Disable openpilot longitudinal</b> and use the car's stock ACC instead.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("DisableOpenpilotLongitudinal"),
        callback=self._on_disable_op_long_toggle,
      ),
    )

    # GM Settings
    self._gm_control = FrogPilotManageControl(
      "GMToggles",
      "General Motors Settings",
      "<b>FrogPilot features for General Motors vehicles.</b>",
      "",
    )
    self._gm_control.set_manage_callback(self._open_gm_panel)

    # HKG Settings
    self._hkg_control = FrogPilotManageControl(
      "HKGToggles",
      "Hyundai/Kia/Genesis Settings",
      "<b>FrogPilot features for Genesis, Hyundai, and Kia vehicles.</b>",
      "",
    )
    self._hkg_control.set_manage_callback(self._open_hkg_panel)

    # Subaru Settings
    self._subaru_control = FrogPilotManageControl(
      "SubaruToggles",
      "Subaru Settings",
      "<b>FrogPilot features for Subaru vehicles.</b>",
      "",
    )
    self._subaru_control.set_manage_callback(self._open_subaru_panel)

    # Toyota Settings
    self._toyota_control = FrogPilotManageControl(
      "ToyotaToggles",
      "Toyota/Lexus Settings",
      "<b>FrogPilot features for Lexus and Toyota vehicles.</b>",
      "",
    )
    self._toyota_control.set_manage_callback(self._open_toyota_panel)

    # Vehicle Info
    self._vehicle_info_control = FrogPilotManageControl(
      "VehicleInfo",
      "Vehicle Info",
      "<b>Information about your vehicle in regards to openpilot support and functionality.</b>",
      "",
    )
    self._vehicle_info_control.set_manage_callback(self._open_vehicle_info_panel)

    main_items = [
      self._car_make_item,
      self._car_model_item,
      self._force_fingerprint_item,
      self._disable_op_long_item,
      self._gm_control,
      self._hkg_control,
      self._subaru_control,
      self._toyota_control,
      self._vehicle_info_control,
    ]

    self._toggles["CarMake"] = self._car_make_item
    self._toggles["CarModel"] = self._car_model_item
    self._toggles["ForceFingerprint"] = self._force_fingerprint_item
    self._toggles["DisableOpenpilotLongitudinal"] = self._disable_op_long_item
    self._toggles["GMToggles"] = self._gm_control
    self._toggles["HKGToggles"] = self._hkg_control
    self._toggles["SubaruToggles"] = self._subaru_control
    self._toggles["ToyotaToggles"] = self._toyota_control
    self._toggles["VehicleInfo"] = self._vehicle_info_control

    self._main_scroller = Scroller(main_items, line_separator=True, spacing=0)

  def _build_gm_panel(self):
    self._volt_sng_item = ListItem(
      title="Stop-and-Go Hack",
      description="<b>Force stop-and-go</b> on the 2017 Chevy Volt.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("VoltSNG"),
        callback=lambda state: self._simple_toggle("VoltSNG", state),
      ),
    )

    gm_items = [
      self._volt_sng_item,
    ]

    self._toggles["VoltSNG"] = self._volt_sng_item

    self._gm_scroller = Scroller(gm_items, line_separator=True, spacing=0)

  def _build_hkg_panel(self):
    self._taco_tune_item = ListItem(
      title="\"Taco Bell Run\" Torque Hack",
      description="<b>The steering torque hack from comma's 2022 \"Taco Bell Run\".</b> Designed to increase steering torque at low speeds for left and right turns.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("TacoTuneHacks"),
        callback=self._on_taco_tune_toggle,
      ),
    )

    hkg_items = [
      self._taco_tune_item,
    ]

    self._toggles["TacoTuneHacks"] = self._taco_tune_item

    self._hkg_scroller = Scroller(hkg_items, line_separator=True, spacing=0)

  def _build_subaru_panel(self):
    self._subaru_sng_item = ListItem(
      title="Stop and Go",
      description="<b>Stop and go for supported Subaru vehicles.</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("SubaruSNG"),
        callback=lambda state: self._simple_toggle("SubaruSNG", state),
      ),
    )

    subaru_items = [
      self._subaru_sng_item,
    ]

    self._toggles["SubaruSNG"] = self._subaru_sng_item

    self._subaru_scroller = Scroller(subaru_items, line_separator=True, spacing=0)

  def _build_toyota_panel(self):
    # Toyota Doors with Lock/Unlock buttons
    self._toyota_doors_control = FrogPilotButtonToggleControl(
      "ToyotaDoors",
      "Automatically Lock/Unlock Doors",
      "<b>Automatically lock/unlock doors</b> when shifting in and out of drive.",
      "",
      button_params=["LockDoors", "UnlockDoors"],
      button_texts=["Lock", "Unlock"],
    )

    # Cluster Offset with Reset button
    self._cluster_offset_control = FrogPilotParamValueButtonControl(
      "ClusterOffset",
      "Dashboard Speed Offset",
      "<b>The speed offset openpilot uses to match the speed on the dashboard display.</b>",
      "",
      min_value=1.000,
      max_value=1.050,
      label="x",
      interval=0.001,
      button_texts=["Reset"],
    )
    self._cluster_offset_control.set_button_click_callback(self._on_cluster_offset_reset)

    # FrogsGoMoo's Tweaks
    self._frogs_go_moos_item = ListItem(
      title="FrogsGoMoo's Personal Tweaks",
      description="<b>Personal tweaks by FrogsGoMoo for quicker acceleration and smoother braking.</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("FrogsGoMoosTweak"),
        callback=lambda state: self._simple_toggle("FrogsGoMoosTweak", state),
      ),
    )

    # Lock Doors Timer
    lock_timer_labels = build_lock_timer_labels()
    self._lock_doors_timer_control = FrogPilotParamValueControl(
      "LockDoorsTimer",
      "Lock Doors On Ignition Off After",
      "<b>Automatically lock the doors on ignition off</b> when no one is detected in the front seats.<br><br><b>Warning:</b> openpilot can't detect if keys are still inside the car, so ensure you have a spare key to prevent accidental lockouts!",
      "",
      min_value=0,
      max_value=300,
      value_labels=lock_timer_labels,
      interval=1,
    )

    # SNG Hack
    self._sng_hack_item = ListItem(
      title="Stop-and-Go Hack",
      description="<b>Force stop-and-go</b> on Lexus/Toyota vehicles without stock stop-and-go functionality.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("SNGHack"),
        callback=lambda state: self._simple_toggle("SNGHack", state),
      ),
    )

    toyota_items = [
      self._toyota_doors_control,
      self._cluster_offset_control,
      self._frogs_go_moos_item,
      self._lock_doors_timer_control,
      self._sng_hack_item,
    ]

    self._toggles["ToyotaDoors"] = self._toyota_doors_control
    self._toggles["ClusterOffset"] = self._cluster_offset_control
    self._toggles["FrogsGoMoosTweak"] = self._frogs_go_moos_item
    self._toggles["LockDoorsTimer"] = self._lock_doors_timer_control
    self._toggles["SNGHack"] = self._sng_hack_item

    self._toyota_scroller = Scroller(toyota_items, line_separator=True, spacing=0)

  def _build_vehicle_info_panel(self):
    # All are read-only labels
    self._hardware_detected_item = ListItem(
      title="3rd Party Hardware Detected",
      description="<b>Detected 3rd party hardware.</b>",
      action_item=TextAction(lambda: self._get_hardware_detected(), color=ITEM_TEXT_VALUE_COLOR),
    )

    self._bsm_support_item = ListItem(
      title="Blind Spot Support",
      description="<b>Does openpilot use the vehicle's blind spot data?</b>",
      action_item=TextAction(lambda: "Yes" if self._has_bsm else "No", color=ITEM_TEXT_VALUE_COLOR),
    )

    self._pedal_support_item = ListItem(
      title="comma Pedal Support",
      description="<b>Does your vehicle support the \"comma pedal\"?</b>",
      action_item=TextAction(lambda: "Yes" if self._can_use_pedal else "No", color=ITEM_TEXT_VALUE_COLOR),
    )

    self._op_long_support_item = ListItem(
      title="openpilot Longitudinal Support",
      description="<b>Can openpilot control the vehicle's acceleration and braking?</b>",
      action_item=TextAction(lambda: "Yes" if self._has_openpilot_longitudinal else "No", color=ITEM_TEXT_VALUE_COLOR),
    )

    self._radar_support_item = ListItem(
      title="Radar Support",
      description="<b>Does openpilot use the vehicle's radar data</b> alongside the device's camera for tracking lead vehicles?",
      action_item=TextAction(lambda: "Yes" if self._has_radar else "No", color=ITEM_TEXT_VALUE_COLOR),
    )

    self._sdsu_support_item = ListItem(
      title="SDSU Support",
      description="<b>Does your vehicle support \"SDSUs\"?</b>",
      action_item=TextAction(lambda: "Yes" if self._can_use_sdsu else "No", color=ITEM_TEXT_VALUE_COLOR),
    )

    self._sng_support_item = ListItem(
      title="Stop-and-Go Support",
      description="<b>Does your vehicle support stop-and-go driving?</b>",
      action_item=TextAction(lambda: "Yes" if self._has_sng else "No", color=ITEM_TEXT_VALUE_COLOR),
    )

    vehicle_info_items = [
      self._hardware_detected_item,
      self._bsm_support_item,
      self._pedal_support_item,
      self._op_long_support_item,
      self._radar_support_item,
      self._sdsu_support_item,
      self._sng_support_item,
    ]

    self._toggles["HardwareDetected"] = self._hardware_detected_item
    self._toggles["BlindSpotSupport"] = self._bsm_support_item
    self._toggles["PedalSupport"] = self._pedal_support_item
    self._toggles["OpenpilotLongitudinal"] = self._op_long_support_item
    self._toggles["RadarSupport"] = self._radar_support_item
    self._toggles["SDSUSupport"] = self._sdsu_support_item
    self._toggles["SNGSupport"] = self._sng_support_item

    self._vehicle_info_scroller = Scroller(vehicle_info_items, line_separator=True, spacing=0)

  def _get_hardware_detected(self) -> str:
    """Get comma-separated list of detected hardware."""
    detected = []
    if self._has_pedal:
      detected.append("comma Pedal")
    if self._has_sdsu:
      detected.append("SDSU")
    if self._has_zss:
      detected.append("ZSS")
    return ", ".join(detected) if detected else "None"

  def _simple_toggle(self, param: str, state: bool):
    self._params.put_bool(param, state)
    update_frogpilot_toggles()

  def _on_car_make_click(self):
    gui_app.set_modal_overlay(MultiOptionDialog(
      "Choose your car make",
      CAR_MAKES,
    ))
    # Note: Dialog result handling would set CarMake param

  def _on_car_model_click(self):
    car_make = self._params.get("CarMake", encoding="utf-8") or ""
    if not car_make:
      gui_app.set_modal_overlay(alert_dialog("Please select a car make first."))
      return

    car_names, self._car_models = get_car_names(car_make)

    if not car_names:
      gui_app.set_modal_overlay(alert_dialog(f"No models found for {car_make}."))
      return

    gui_app.set_modal_overlay(MultiOptionDialog(
      "Choose your car model",
      car_names,
    ))
    # Note: Dialog result handling would set CarModel and CarModelName params

  def _on_disable_op_long_toggle(self, state: bool):
    if state:
      def on_confirm():
        self._params.put_bool("DisableOpenpilotLongitudinal", True)
        update_frogpilot_toggles()

        if self._started:
          gui_app.set_modal_overlay(ConfirmDialog(
            "Reboot required to take effect.",
            "Reboot Now",
            "Reboot Later",
          ))

      gui_app.set_modal_overlay(ConfirmDialog(
        "Are you sure you want to completely disable openpilot longitudinal control?",
        "Yes",
        "No",
      ))
    else:
      self._params.put_bool("DisableOpenpilotLongitudinal", False)
      update_frogpilot_toggles()

    self._update_toggles()

  def _on_taco_tune_toggle(self, state: bool):
    self._params.put_bool("TacoTuneHacks", state)
    update_frogpilot_toggles()

    if state and self._started:
      gui_app.set_modal_overlay(ConfirmDialog(
        "Reboot required to take effect.",
        "Reboot Now",
        "Reboot Later",
      ))

  def _on_cluster_offset_reset(self, button_id: int):
    default_value = self._params.get_key_default_value("ClusterOffset")
    if default_value:
      try:
        self._params.put_float("ClusterOffset", float(default_value))
      except (ValueError, TypeError):
        self._params.put_float("ClusterOffset", 1.015)

  def _open_gm_panel(self):
    self._current_panel = SubPanel.GM

  def _open_hkg_panel(self):
    self._current_panel = SubPanel.HKG

  def _open_subaru_panel(self):
    self._current_panel = SubPanel.SUBARU

  def _open_toyota_panel(self):
    self._current_panel = SubPanel.TOYOTA

  def _open_vehicle_info_panel(self):
    self._current_panel = SubPanel.VEHICLE_INFO

  def _close_sub_panel(self):
    self._current_panel = SubPanel.MAIN

  def _load_car_capabilities(self):
    """Load car capabilities from frogpilot variables."""
    try:
      from openpilot.frogpilot.common.frogpilot_variables import get_frogpilot_toggles
      toggles = get_frogpilot_toggles()

      self._has_bsm = getattr(toggles, "has_bsm", False)
      self._has_openpilot_longitudinal = getattr(toggles, "has_openpilot_longitudinal", False)
      self._has_pedal = getattr(toggles, "has_pedal", False)
      self._has_radar = getattr(toggles, "has_radar", False)
      self._has_sdsu = getattr(toggles, "has_sdsu", False)
      self._has_sng = getattr(toggles, "has_sng", False)
      self._has_zss = getattr(toggles, "has_zss", False)
      self._can_use_pedal = getattr(toggles, "can_use_pedal", False)
      self._can_use_sdsu = getattr(toggles, "can_use_sdsu", False)
      self._has_alpha_longitudinal = getattr(toggles, "has_alpha_longitudinal", False)
      self._openpilot_longitudinal_disabled = getattr(toggles, "openpilot_longitudinal_disabled", False)

      self._is_gm = getattr(toggles, "is_gm", False)
      self._is_hkg = getattr(toggles, "is_hkg", False)
      self._is_hkg_canfd = getattr(toggles, "is_hkg_canfd", False)
      self._is_subaru = getattr(toggles, "is_subaru", False)
      self._is_toyota = getattr(toggles, "is_toyota", False)
      self._is_volt = getattr(toggles, "is_volt", False)
    except Exception:
      pass

  def _update_toggles(self):
    self._tuning_level = self._params.get_int("TuningLevel") or 0

    # GM panel visibility
    volt_sng_visible = self._is_gm and self._has_openpilot_longitudinal and self._is_volt and not self._has_sng
    if hasattr(self._volt_sng_item, "set_visible"):
      self._volt_sng_item.set_visible(volt_sng_visible)

    # GM parent visible if any child is visible
    gm_visible = volt_sng_visible
    if hasattr(self._gm_control, "set_visible"):
      self._gm_control.set_visible(gm_visible)

    # HKG panel visibility
    taco_tune_visible = self._is_hkg and self._is_hkg_canfd
    if hasattr(self._taco_tune_item, "set_visible"):
      self._taco_tune_item.set_visible(taco_tune_visible)

    # HKG parent visible if any child is visible
    hkg_visible = taco_tune_visible
    if hasattr(self._hkg_control, "set_visible"):
      self._hkg_control.set_visible(hkg_visible)

    # Subaru panel visibility
    subaru_sng_visible = self._is_subaru and self._has_sng
    if hasattr(self._subaru_sng_item, "set_visible"):
      self._subaru_sng_item.set_visible(subaru_sng_visible)

    # Subaru parent visible if any child is visible
    subaru_visible = subaru_sng_visible
    if hasattr(self._subaru_control, "set_visible"):
      self._subaru_control.set_visible(subaru_visible)

    # Toyota panel visibility
    toyota_doors_visible = self._is_toyota
    cluster_offset_visible = self._is_toyota
    frogs_go_moos_visible = self._is_toyota and self._has_openpilot_longitudinal
    lock_doors_timer_visible = self._is_toyota
    sng_hack_visible = self._is_toyota and self._has_openpilot_longitudinal and not self._has_sng

    if hasattr(self._toyota_doors_control, "set_visible"):
      self._toyota_doors_control.set_visible(toyota_doors_visible)
    if hasattr(self._cluster_offset_control, "set_visible"):
      self._cluster_offset_control.set_visible(cluster_offset_visible)
    if hasattr(self._frogs_go_moos_item, "set_visible"):
      self._frogs_go_moos_item.set_visible(frogs_go_moos_visible)
    if hasattr(self._lock_doors_timer_control, "set_visible"):
      self._lock_doors_timer_control.set_visible(lock_doors_timer_visible)
    if hasattr(self._sng_hack_item, "set_visible"):
      self._sng_hack_item.set_visible(sng_hack_visible)

    # Toyota parent visible if any child is visible
    toyota_visible = toyota_doors_visible or cluster_offset_visible or frogs_go_moos_visible or lock_doors_timer_visible or sng_hack_visible
    if hasattr(self._toyota_control, "set_visible"):
      self._toyota_control.set_visible(toyota_visible)

    # Disable openpilot longitudinal visibility
    disable_op_long_visible = ((self._has_openpilot_longitudinal or self._openpilot_longitudinal_disabled) and
                                not self._has_alpha_longitudinal)
    if hasattr(self._disable_op_long_item, "set_visible"):
      self._disable_op_long_item.set_visible(disable_op_long_visible)

  def _update_car_display(self):
    """Update car make/model display values."""
    car_make = self._params.get("CarMake", encoding="utf-8") or ""
    car_model_name = self._params.get("CarModelName", encoding="utf-8") or ""
    if not car_model_name:
      car_model_name = self._params.get("CarModel", encoding="utf-8") or ""

    # Update display values if controls support it
    # Note: This would need the ListItem to support set_value

  def show_event(self):
    super().show_event()
    self._main_scroller.show_event()
    self._load_car_capabilities()
    self._update_toggles()
    self._update_car_display()
    self._started = ui_state.started

  def hide_event(self):
    super().hide_event()
    self._current_panel = SubPanel.MAIN

  def _render(self, rect):
    self._started = ui_state.started

    if self._current_panel == SubPanel.GM:
      self._gm_scroller.render(rect)
    elif self._current_panel == SubPanel.HKG:
      self._hkg_scroller.render(rect)
    elif self._current_panel == SubPanel.SUBARU:
      self._subaru_scroller.render(rect)
    elif self._current_panel == SubPanel.TOYOTA:
      self._toyota_scroller.render(rect)
    elif self._current_panel == SubPanel.VEHICLE_INFO:
      self._vehicle_info_scroller.render(rect)
    else:
      self._main_scroller.render(rect)
