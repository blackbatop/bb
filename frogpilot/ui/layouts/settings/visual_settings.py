from enum import IntEnum

from openpilot.common.conversions import Conversions as CV
from openpilot.common.params import Params
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.list_view import ListItem, ToggleAction
from openpilot.system.ui.widgets.scroller_tici import Scroller

from openpilot.frogpilot.common.frogpilot_variables import update_frogpilot_toggles
from openpilot.frogpilot.system.ui.widgets.frogpilot_controls import (
  FrogPilotButtonsControl,
  FrogPilotButtonToggleControl,
  FrogPilotManageControl,
  FrogPilotParamValueControl,
)

ADVANCED_CUSTOM_ONROAD_UI_KEYS = {
  "HideAlerts",
  "HideLeadMarker",
  "HideMaxSpeed",
  "HideSpeed",
  "HideSpeedLimit",
  "WheelSpeed",
}

CUSTOM_ONROAD_UI_KEYS = {
  "AccelerationPath",
  "AdjacentPath",
  "BlindSpotPath",
  "Compass",
  "OnroadDistanceButton",
  "PedalsOnUI",
  "RotatingWheel",
}

MODEL_UI_KEYS = {
  "DynamicPathWidth",
  "LaneLinesWidth",
  "PathEdgeWidth",
  "PathWidth",
  "RoadEdgesWidth",
}

NAVIGATION_UI_KEYS = {
  "RoadNameUI",
  "ShowSpeedLimits",
  "SLCMapboxFiller",
  "UseVienna",
}

QUALITY_OF_LIFE_KEYS = {
  "CameraView",
  "DriverCamera",
  "StoppedTimer",
}

INCH_TO_CM = 2.54
CM_TO_INCH = 1.0 / INCH_TO_CM
FOOT_TO_METER = CV.FOOT_TO_METER
METER_TO_FOOT = CV.METER_TO_FOOT


class SubPanel(IntEnum):
  MAIN = 0
  ADVANCED_CUSTOM_UI = 1
  CUSTOM_UI = 2
  MODEL_UI = 3
  NAVIGATION_UI = 4
  QUALITY_OF_LIFE = 5


def build_imperial_small_distance_labels():
  """Build labels for inches (0-24)."""
  labels = {}
  for i in range(25):
    if i == 0:
      labels[i] = "Off"
    elif i == 1:
      labels[i] = "1 inch"
    else:
      labels[i] = f"{i} inches"
  return labels


def build_metric_small_distance_labels():
  """Build labels for centimeters (0-60)."""
  labels = {}
  for i in range(61):
    if i == 0:
      labels[i] = "Off"
    elif i == 1:
      labels[i] = "1 centimeter"
    else:
      labels[i] = f"{i} centimeters"
  return labels


def build_imperial_distance_labels():
  """Build labels for feet (0-10)."""
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
  """Build labels for meters (0.0-3.0 in 0.1 steps)."""
  labels = {}
  for i in range(31):
    val = i / 10.0
    if val == 0.0:
      labels[val] = "Off"
    elif val == 1.0:
      labels[val] = "1 meter"
    else:
      labels[val] = f"{val:.1f} meters"
  return labels


def build_path_edge_labels():
  """Build labels for path edge width (0-100%)."""
  labels = {}
  for i in range(101):
    if i == 0:
      labels[i] = "Off"
    else:
      labels[i] = f"{i}%"
  return labels


class FrogPilotVisualsPanel(Widget):
  def __init__(self):
    super().__init__()

    self._current_panel = SubPanel.MAIN
    self._is_metric = False
    self._params = Params()
    self._toggles = {}
    self._tuning_level = 0

    # Car capabilities
    self._has_bsm = False
    self._has_openpilot_longitudinal = False

    # Build all panels
    self._build_main_panel()
    self._build_advanced_custom_ui_panel()
    self._build_custom_ui_panel()
    self._build_model_ui_panel()
    self._build_navigation_ui_panel()
    self._build_quality_of_life_panel()

    ui_state.add_offroad_transition_callback(self._on_offroad_transition)

  def _on_offroad_transition(self):
    previous_metric = self._is_metric
    self._is_metric = self._params.get_bool("IsMetric")
    if self._is_metric != previous_metric:
      self._convert_metric_values(previous_metric)
    self._update_metric()
    self._load_car_capabilities()
    self._update_toggles()

  def _simple_toggle(self, param: str, state: bool):
    self._params.put_bool(param, state)
    update_frogpilot_toggles()

  # ==================== MAIN PANEL ====================
  def _build_main_panel(self):
    self._advanced_custom_ui_control = FrogPilotManageControl(
      "AdvancedCustomUI",
      "Advanced UI Controls",
      "<b>Advanced visual changes</b> to fine-tune how the driving screen looks.",
      "../../frogpilot/assets/toggle_icons/icon_advanced_device.png",
    )
    self._advanced_custom_ui_control.set_manage_callback(self._open_advanced_custom_ui)

    self._custom_ui_control = FrogPilotManageControl(
      "CustomUI",
      "Driving Screen Widgets",
      "<b>Custom FrogPilot widgets</b> for the driving screen.",
      "../assets/icons/calibration.png",
    )
    self._custom_ui_control.set_manage_callback(self._open_custom_ui)

    self._model_ui_control = FrogPilotManageControl(
      "ModelUI",
      "Model UI",
      "<b>Model visualizations</b> for the driving path, lane lines, path edges, and road edges.",
      "../../frogpilot/assets/toggle_icons/icon_road.png",
    )
    self._model_ui_control.set_manage_callback(self._open_model_ui)

    self._navigation_ui_control = FrogPilotManageControl(
      "NavigationUI",
      "Navigation Widgets",
      "<b>Speed limits, and other navigation widgets.</b>",
      "../../frogpilot/assets/toggle_icons/icon_map.png",
    )
    self._navigation_ui_control.set_manage_callback(self._open_navigation_ui)

    self._qol_visuals_control = FrogPilotManageControl(
      "QOLVisuals",
      "Quality of Life",
      "<b>Miscellaneous visual changes</b> to fine-tune how the driving screen looks.",
      "../../frogpilot/assets/toggle_icons/icon_quality_of_life.png",
    )
    self._qol_visuals_control.set_manage_callback(self._open_quality_of_life)

    main_items = [
      self._advanced_custom_ui_control,
      self._custom_ui_control,
      self._model_ui_control,
      self._navigation_ui_control,
      self._qol_visuals_control,
    ]

    self._toggles["AdvancedCustomUI"] = self._advanced_custom_ui_control
    self._toggles["CustomUI"] = self._custom_ui_control
    self._toggles["ModelUI"] = self._model_ui_control
    self._toggles["NavigationUI"] = self._navigation_ui_control
    self._toggles["QOLVisuals"] = self._qol_visuals_control

    self._main_scroller = Scroller(main_items, line_separator=True, spacing=0)

  # ==================== ADVANCED CUSTOM UI PANEL ====================
  def _build_advanced_custom_ui_panel(self):
    self._hide_speed_item = ListItem(
      title="Hide Current Speed",
      description="<b>Hide the current speed</b> from the driving screen.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("HideSpeed"),
        callback=lambda state: self._simple_toggle("HideSpeed", state),
      ),
    )

    self._hide_lead_marker_item = ListItem(
      title="Hide Lead Marker",
      description="<b>Hide the lead-vehicle marker</b> from the driving screen.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("HideLeadMarker"),
        callback=lambda state: self._simple_toggle("HideLeadMarker", state),
      ),
    )

    self._hide_max_speed_item = ListItem(
      title="Hide Max Speed",
      description="<b>Hide the max speed</b> from the driving screen.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("HideMaxSpeed"),
        callback=lambda state: self._simple_toggle("HideMaxSpeed", state),
      ),
    )

    self._hide_alerts_item = ListItem(
      title="Hide Non-Critical Alerts",
      description="<b>Hide non-critical alerts</b> from the driving screen.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("HideAlerts"),
        callback=lambda state: self._simple_toggle("HideAlerts", state),
      ),
    )

    self._hide_speed_limit_item = ListItem(
      title="Hide Speed Limits",
      description="<b>Hide posted speed limits</b> from the driving screen.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("HideSpeedLimit"),
        callback=lambda state: self._simple_toggle("HideSpeedLimit", state),
      ),
    )

    self._wheel_speed_item = ListItem(
      title="Use Wheel Speed",
      description="<b>Use the vehicle's wheel speed</b> instead of the cluster speed. This is purely a visual change and doesn't impact how openpilot drives!",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("WheelSpeed"),
        callback=lambda state: self._simple_toggle("WheelSpeed", state),
      ),
    )

    advanced_items = [
      self._hide_speed_item,
      self._hide_lead_marker_item,
      self._hide_max_speed_item,
      self._hide_alerts_item,
      self._hide_speed_limit_item,
      self._wheel_speed_item,
    ]

    self._toggles["HideSpeed"] = self._hide_speed_item
    self._toggles["HideLeadMarker"] = self._hide_lead_marker_item
    self._toggles["HideMaxSpeed"] = self._hide_max_speed_item
    self._toggles["HideAlerts"] = self._hide_alerts_item
    self._toggles["HideSpeedLimit"] = self._hide_speed_limit_item
    self._toggles["WheelSpeed"] = self._wheel_speed_item

    self._advanced_custom_ui_scroller = Scroller(advanced_items, line_separator=True, spacing=0)

  # ==================== CUSTOM UI PANEL ====================
  def _build_custom_ui_panel(self):
    self._acceleration_path_item = ListItem(
      title="Acceleration Path",
      description="<b>Color the driving path by planned acceleration and braking.</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("AccelerationPath"),
        callback=lambda state: self._simple_toggle("AccelerationPath", state),
      ),
    )

    self._adjacent_path_item = ListItem(
      title="Adjacent Lanes",
      description="<b>Show the driving paths for the left and right lanes.</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("AdjacentPath"),
        callback=lambda state: self._simple_toggle("AdjacentPath", state),
      ),
    )

    self._blind_spot_path_item = ListItem(
      title="Blind Spot Path",
      description="<b>Show a red path when a vehicle is in that lane's blind spot.</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("BlindSpotPath"),
        callback=lambda state: self._simple_toggle("BlindSpotPath", state),
      ),
    )

    self._compass_item = ListItem(
      title="Compass",
      description="<b>Show the current driving direction</b> with a simple on-screen compass.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("Compass"),
        callback=lambda state: self._simple_toggle("Compass", state),
      ),
    )

    self._onroad_distance_button_item = ListItem(
      title="Driving Personality Button",
      description="<b>Control and view the current driving personality</b> via a driving screen widget.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("OnroadDistanceButton"),
        callback=lambda state: self._simple_toggle("OnroadDistanceButton", state),
      ),
    )

    # PedalsOnUI with Dynamic/Static mutually exclusive options
    self._pedals_on_ui_control = FrogPilotButtonToggleControl(
      "PedalsOnUI",
      "Gas / Brake Pedal Indicators",
      "<b>On-screen gas and brake indicators.</b><br><br><b>Dynamic</b>: Opacity changes according to how much openpilot is accelerating or braking<br><b>Static</b>: Full when active, dim when not",
      "",
      button_params=["DynamicPedalsOnUI", "StaticPedalsOnUI"],
      button_texts=["Dynamic", "Static"],
    )
    self._pedals_on_ui_control.set_button_callback(self._on_pedals_button_click)

    self._rotating_wheel_item = ListItem(
      title="Rotating Steering Wheel",
      description="<b>Rotate the driving screen wheel</b> with the physical steering wheel.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("RotatingWheel"),
        callback=lambda state: self._simple_toggle("RotatingWheel", state),
      ),
    )

    custom_items = [
      self._acceleration_path_item,
      self._adjacent_path_item,
      self._blind_spot_path_item,
      self._compass_item,
      self._onroad_distance_button_item,
      self._pedals_on_ui_control,
      self._rotating_wheel_item,
    ]

    self._toggles["AccelerationPath"] = self._acceleration_path_item
    self._toggles["AdjacentPath"] = self._adjacent_path_item
    self._toggles["BlindSpotPath"] = self._blind_spot_path_item
    self._toggles["Compass"] = self._compass_item
    self._toggles["OnroadDistanceButton"] = self._onroad_distance_button_item
    self._toggles["PedalsOnUI"] = self._pedals_on_ui_control
    self._toggles["RotatingWheel"] = self._rotating_wheel_item

    self._custom_ui_scroller = Scroller(custom_items, line_separator=True, spacing=0)

  def _on_pedals_button_click(self, button_id: int):
    """Handle mutually exclusive Dynamic/Static pedals options."""
    if button_id == 0:
      # Dynamic clicked - disable Static
      self._params.put_bool("StaticPedalsOnUI", False)
    elif button_id == 1:
      # Static clicked - disable Dynamic
      self._params.put_bool("DynamicPedalsOnUI", False)
    update_frogpilot_toggles()

  # ==================== MODEL UI PANEL ====================
  def _build_model_ui_panel(self):
    self._dynamic_path_width_item = ListItem(
      title="Dynamic Path Width",
      description="<b>Change the path width based on engagement.</b><br><br><b>Fully Engaged</b>: 100%<br><b>Always On Lateral</b>: 75%<br><b>Disengaged</b>: 50%",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("DynamicPathWidth"),
        callback=lambda state: self._simple_toggle("DynamicPathWidth", state),
      ),
    )

    # Lane Lines Width - 0-24 inches or 0-60 cm
    self._lane_lines_width_control = FrogPilotParamValueControl(
      "LaneLinesWidth",
      "Lane Lines Width",
      "<b>Set the lane-line thickness.</b><br><br>Default matches the MUTCD lane-line width standard of 4 inches.",
      "",
      min_value=0,
      max_value=24,
      unit=" inches",
      labels=build_imperial_small_distance_labels(),
    )

    # Path Edge Width - 0-100%
    self._path_edge_width_control = FrogPilotParamValueControl(
      "PathEdgeWidth",
      "Path Edges Width",
      "<b>Set the driving-path edge width</b> that represents different driving modes and statuses.<br><br>Default is 20% of the total path width.<br><br>Color Guide:<br><br>- <b>Light Blue</b>: Always On Lateral<br>- <b>Green</b>: Default<br>- <b>Orange</b>: Experimental Mode<br>- <b>Red</b>: Traffic Mode<br>- <b>Yellow</b>: Conditional Experimental Mode overridden",
      "",
      min_value=0,
      max_value=100,
      unit="",
      labels=build_path_edge_labels(),
    )

    # Path Width - 0-10 feet or 0-3 meters (0.1 step)
    self._path_width_control = FrogPilotParamValueControl(
      "PathWidth",
      "Path Width",
      "<b>Set the driving-path width.</b><br><br>Default (6.1 feet) matches the width of a 2019 Lexus ES 350.",
      "",
      min_value=0,
      max_value=10,
      unit=" feet",
      labels=build_imperial_distance_labels(),
      step=0.1,
    )

    # Road Edges Width - 0-24 inches or 0-60 cm
    self._road_edges_width_control = FrogPilotParamValueControl(
      "RoadEdgesWidth",
      "Road Edges Width",
      "<b>Set the road-edge thickness.</b><br><br>Default matches half of the MUTCD lane-line width standard of 4 inches.",
      "",
      min_value=0,
      max_value=24,
      unit=" inches",
      labels=build_imperial_small_distance_labels(),
    )

    model_items = [
      self._dynamic_path_width_item,
      self._lane_lines_width_control,
      self._path_edge_width_control,
      self._path_width_control,
      self._road_edges_width_control,
    ]

    self._toggles["DynamicPathWidth"] = self._dynamic_path_width_item
    self._toggles["LaneLinesWidth"] = self._lane_lines_width_control
    self._toggles["PathEdgeWidth"] = self._path_edge_width_control
    self._toggles["PathWidth"] = self._path_width_control
    self._toggles["RoadEdgesWidth"] = self._road_edges_width_control

    self._model_ui_scroller = Scroller(model_items, line_separator=True, spacing=0)

  # ==================== NAVIGATION UI PANEL ====================
  def _build_navigation_ui_panel(self):
    self._road_name_ui_item = ListItem(
      title="Road Name",
      description="<b>Display the road name at the bottom of the driving screen</b> using data from \"OpenStreetMap (OSM)\".",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("RoadNameUI"),
        callback=lambda state: self._simple_toggle("RoadNameUI", state),
      ),
    )

    self._show_speed_limits_item = ListItem(
      title="Show Speed Limits",
      description="<b>Show speed limits</b> in the top-left corner of the driving screen. Uses data from the car's dashboard (if supported) and \"OpenStreetMap (OSM)\".",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("ShowSpeedLimits"),
        callback=lambda state: self._on_show_speed_limits_toggle(state),
      ),
    )

    self._slc_mapbox_filler_item = ListItem(
      title="Show Speed Limits from Mapbox",
      description="<b>Use Mapbox speed-limit data when no other source is available.</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("SLCMapboxFiller"),
        callback=lambda state: self._simple_toggle("SLCMapboxFiller", state),
      ),
    )

    self._use_vienna_item = ListItem(
      title="Use Vienna-Style Speed Signs",
      description="<b>Show Vienna-style (EU) speed-limit signs</b> instead of MUTCD (US).",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("UseVienna"),
        callback=lambda state: self._simple_toggle("UseVienna", state),
      ),
    )

    navigation_items = [
      self._road_name_ui_item,
      self._show_speed_limits_item,
      self._slc_mapbox_filler_item,
      self._use_vienna_item,
    ]

    self._toggles["RoadNameUI"] = self._road_name_ui_item
    self._toggles["ShowSpeedLimits"] = self._show_speed_limits_item
    self._toggles["SLCMapboxFiller"] = self._slc_mapbox_filler_item
    self._toggles["UseVienna"] = self._use_vienna_item

    self._navigation_ui_scroller = Scroller(navigation_items, line_separator=True, spacing=0)

  def _on_show_speed_limits_toggle(self, state: bool):
    """Handle ShowSpeedLimits toggle and update dependent visibility."""
    self._params.put_bool("ShowSpeedLimits", state)
    update_frogpilot_toggles()
    self._update_toggles()

  # ==================== QUALITY OF LIFE PANEL ====================
  def _build_quality_of_life_panel(self):
    # Camera View - 4 options: Auto, Driver, Standard, Wide
    self._camera_view_control = FrogPilotButtonsControl(
      "CameraView",
      "Camera View",
      "<b>Select the active camera view.</b> This is purely a visual change and doesn't impact how openpilot drives!",
      "",
      button_texts=["AUTO", "DRIVER", "STANDARD", "WIDE"],
      checkable=True,
      exclusive=True,
    )
    self._camera_view_control.set_click_callback(self._on_camera_view_click)
    self._update_camera_view_selection()

    self._driver_camera_item = ListItem(
      title="Show Driver Camera When In Reverse",
      description="<b>Show the driver camera feed</b> when the vehicle is in reverse.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("DriverCamera"),
        callback=lambda state: self._simple_toggle("DriverCamera", state),
      ),
    )

    self._stopped_timer_item = ListItem(
      title="Stopped Timer",
      description="<b>Show a timer when stopped</b> in place of the current speed to indicate how long the vehicle has been stopped.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("StoppedTimer"),
        callback=lambda state: self._simple_toggle("StoppedTimer", state),
      ),
    )

    qol_items = [
      self._camera_view_control,
      self._driver_camera_item,
      self._stopped_timer_item,
    ]

    self._toggles["CameraView"] = self._camera_view_control
    self._toggles["DriverCamera"] = self._driver_camera_item
    self._toggles["StoppedTimer"] = self._stopped_timer_item

    self._qol_scroller = Scroller(qol_items, line_separator=True, spacing=0)

  def _on_camera_view_click(self, button_id: int):
    """Handle camera view selection (0=Auto, 1=Driver, 2=Standard, 3=Wide)."""
    self._params.put_int("CameraView", button_id)
    self._update_camera_view_selection()
    update_frogpilot_toggles()

  def _update_camera_view_selection(self):
    """Update the camera view button selection state."""
    current = self._params.get_int("CameraView") or 0
    if hasattr(self._camera_view_control, "set_checked_button"):
      self._camera_view_control.set_checked_button(current)

  # ==================== PANEL NAVIGATION ====================
  def _open_advanced_custom_ui(self):
    self._current_panel = SubPanel.ADVANCED_CUSTOM_UI

  def _open_custom_ui(self):
    self._current_panel = SubPanel.CUSTOM_UI

  def _open_model_ui(self):
    self._current_panel = SubPanel.MODEL_UI

  def _open_navigation_ui(self):
    self._current_panel = SubPanel.NAVIGATION_UI

  def _open_quality_of_life(self):
    self._current_panel = SubPanel.QUALITY_OF_LIFE

  def _close_sub_panel(self):
    self._current_panel = SubPanel.MAIN

  # ==================== METRIC CONVERSION ====================
  def _convert_metric_values(self, was_metric: bool):
    """Convert stored values when metric setting changes."""
    if was_metric:
      # Converting from metric to imperial
      small_conversion = CM_TO_INCH
      distance_conversion = METER_TO_FOOT
    else:
      # Converting from imperial to metric
      small_conversion = INCH_TO_CM
      distance_conversion = FOOT_TO_METER

    # Convert lane lines width (inches <-> cm)
    lane_lines_width = self._params.get_int("LaneLinesWidth") or 0
    self._params.put_int("LaneLinesWidth", int(lane_lines_width * small_conversion))

    # Convert road edges width (inches <-> cm)
    road_edges_width = self._params.get_int("RoadEdgesWidth") or 0
    self._params.put_int("RoadEdgesWidth", int(road_edges_width * small_conversion))

    # Convert path width (feet <-> meters)
    path_width = self._params.get_float("PathWidth") or 0.0
    self._params.put_float("PathWidth", path_width * distance_conversion)

  def _update_metric(self):
    """Update control labels and ranges based on metric setting."""
    if self._is_metric:
      # Metric: cm for small distances, meters for path width
      self._lane_lines_width_control.set_description(
        "<b>Set the lane-line thickness.</b><br><br>Default matches the MUTCD lane-line width standard of 10 centimeters."
      )
      self._path_width_control.set_description(
        "<b>Set the driving-path width.</b><br><br>Default (1.9 meters) matches the width of a 2019 Lexus ES 350."
      )
      self._road_edges_width_control.set_description(
        "<b>Set the road-edge thickness.</b><br><br>Default matches half of the MUTCD lane-line width standard of 10 centimeters."
      )

      if hasattr(self._lane_lines_width_control, "update_control"):
        self._lane_lines_width_control.update_control(0, 60, build_metric_small_distance_labels())
      if hasattr(self._road_edges_width_control, "update_control"):
        self._road_edges_width_control.update_control(0, 60, build_metric_small_distance_labels())
      if hasattr(self._path_width_control, "update_control"):
        self._path_width_control.update_control(0, 3, build_metric_distance_labels())
    else:
      # Imperial: inches for small distances, feet for path width
      self._lane_lines_width_control.set_description(
        "<b>Set the lane-line thickness.</b><br><br>Default matches the MUTCD lane-line width standard of 4 inches."
      )
      self._path_width_control.set_description(
        "<b>Set the driving-path width.</b><br><br>Default (6.1 feet) matches the width of a 2019 Lexus ES 350."
      )
      self._road_edges_width_control.set_description(
        "<b>Set the road-edge thickness.</b><br><br>Default matches half of the MUTCD lane-line width standard of 4 inches."
      )

      if hasattr(self._lane_lines_width_control, "update_control"):
        self._lane_lines_width_control.update_control(0, 24, build_imperial_small_distance_labels())
      if hasattr(self._road_edges_width_control, "update_control"):
        self._road_edges_width_control.update_control(0, 24, build_imperial_small_distance_labels())
      if hasattr(self._path_width_control, "update_control"):
        self._path_width_control.update_control(0, 10, build_imperial_distance_labels())

  # ==================== VISIBILITY UPDATES ====================
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

  def _update_toggles(self):
    """Update toggle visibility based on tuning level and car capabilities."""
    self._tuning_level = self._params.get_int("TuningLevel") or 0

    # Load toggle levels
    try:
      import json
      toggle_levels_str = self._params.get("FrogPilotTogglesLevels", encoding="utf-8") or "{}"
      toggle_levels = json.loads(toggle_levels_str)
    except Exception:
      toggle_levels = {}

    # First, hide all parent toggles
    for key in ["AdvancedCustomUI", "CustomUI", "ModelUI", "NavigationUI", "QOLVisuals"]:
      if key in self._toggles and hasattr(self._toggles[key], "set_visible"):
        self._toggles[key].set_visible(False)

    # Check which child toggles are visible and show their parents accordingly
    slc_enabled = self._params.get_bool("SpeedLimitController")
    show_speed_limits = self._params.get_bool("ShowSpeedLimits")
    mapbox_key = self._params.get("MapboxSecretKey", encoding="utf-8") or ""

    # Advanced Custom UI children
    advanced_visible = False
    for key in ADVANCED_CUSTOM_ONROAD_UI_KEYS:
      if key not in self._toggles:
        continue

      toggle_level = toggle_levels.get(key, 0)
      visible = self._tuning_level >= toggle_level

      # Special visibility conditions
      if key == "HideLeadMarker":
        visible = visible and self._has_openpilot_longitudinal
      elif key == "HideSpeedLimit":
        visible = visible and self._has_openpilot_longitudinal and slc_enabled

      if hasattr(self._toggles[key], "set_visible"):
        self._toggles[key].set_visible(visible)

      if visible:
        advanced_visible = True

    if advanced_visible and hasattr(self._toggles["AdvancedCustomUI"], "set_visible"):
      self._toggles["AdvancedCustomUI"].set_visible(True)

    # Custom UI children
    custom_visible = False
    for key in CUSTOM_ONROAD_UI_KEYS:
      if key not in self._toggles:
        continue

      toggle_level = toggle_levels.get(key, 0)
      visible = self._tuning_level >= toggle_level

      # Special visibility conditions
      if key == "AccelerationPath":
        visible = visible and self._has_openpilot_longitudinal
      elif key == "BlindSpotPath":
        visible = visible and self._has_bsm
      elif key == "OnroadDistanceButton":
        visible = visible and self._has_openpilot_longitudinal
      elif key == "PedalsOnUI":
        visible = visible and self._has_openpilot_longitudinal

      if hasattr(self._toggles[key], "set_visible"):
        self._toggles[key].set_visible(visible)

      if visible:
        custom_visible = True

    if custom_visible and hasattr(self._toggles["CustomUI"], "set_visible"):
      self._toggles["CustomUI"].set_visible(True)

    # Model UI children
    model_visible = False
    for key in MODEL_UI_KEYS:
      if key not in self._toggles:
        continue

      toggle_level = toggle_levels.get(key, 0)
      visible = self._tuning_level >= toggle_level

      if hasattr(self._toggles[key], "set_visible"):
        self._toggles[key].set_visible(visible)

      if visible:
        model_visible = True

    if model_visible and hasattr(self._toggles["ModelUI"], "set_visible"):
      self._toggles["ModelUI"].set_visible(True)

    # Navigation UI children
    nav_visible = False
    for key in NAVIGATION_UI_KEYS:
      if key not in self._toggles:
        continue

      toggle_level = toggle_levels.get(key, 0)
      visible = self._tuning_level >= toggle_level

      # Special visibility conditions
      if key == "ShowSpeedLimits":
        # ShowSpeedLimits visible when SpeedLimitController is OFF or no longitudinal
        visible = visible and (not slc_enabled or not self._has_openpilot_longitudinal)
      elif key == "SLCMapboxFiller":
        # Visible if ShowSpeedLimits enabled, SLC off (or no longitudinal), and Mapbox key present
        visible = visible and show_speed_limits
        visible = visible and (not slc_enabled or not self._has_openpilot_longitudinal)
        visible = visible and bool(mapbox_key)
      elif key == "UseVienna":
        # Visible if either ShowSpeedLimits or SpeedLimitController is enabled
        visible = visible and (show_speed_limits or slc_enabled)

      if hasattr(self._toggles[key], "set_visible"):
        self._toggles[key].set_visible(visible)

      if visible:
        nav_visible = True

    if nav_visible and hasattr(self._toggles["NavigationUI"], "set_visible"):
      self._toggles["NavigationUI"].set_visible(True)

    # Quality of Life children
    qol_visible = False
    for key in QUALITY_OF_LIFE_KEYS:
      if key not in self._toggles:
        continue

      toggle_level = toggle_levels.get(key, 0)
      visible = self._tuning_level >= toggle_level

      if hasattr(self._toggles[key], "set_visible"):
        self._toggles[key].set_visible(visible)

      if visible:
        qol_visible = True

    if qol_visible and hasattr(self._toggles["QOLVisuals"], "set_visible"):
      self._toggles["QOLVisuals"].set_visible(True)

  # ==================== LIFECYCLE ====================
  def show_event(self):
    super().show_event()
    self._main_scroller.show_event()
    self._is_metric = self._params.get_bool("IsMetric")
    self._update_metric()
    self._load_car_capabilities()
    self._update_toggles()
    self._update_camera_view_selection()

  def hide_event(self):
    super().hide_event()
    self._current_panel = SubPanel.MAIN

  def _render(self, rect):
    if self._current_panel == SubPanel.ADVANCED_CUSTOM_UI:
      self._advanced_custom_ui_scroller.render(rect)
    elif self._current_panel == SubPanel.CUSTOM_UI:
      self._custom_ui_scroller.render(rect)
    elif self._current_panel == SubPanel.MODEL_UI:
      self._model_ui_scroller.render(rect)
    elif self._current_panel == SubPanel.NAVIGATION_UI:
      self._navigation_ui_scroller.render(rect)
    elif self._current_panel == SubPanel.QUALITY_OF_LIFE:
      self._qol_scroller.render(rect)
    else:
      self._main_scroller.render(rect)
