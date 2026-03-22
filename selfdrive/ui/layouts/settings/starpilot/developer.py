from __future__ import annotations
from openpilot.selfdrive.ui.lib.starpilot_state import starpilot_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.lib.multilang import tr, tr_noop
from openpilot.system.ui.widgets import DialogResult
from openpilot.system.ui.widgets.selection_dialog import SelectionDialog
from openpilot.selfdrive.ui.layouts.settings.starpilot.panel import StarPilotPanel
from openpilot.selfdrive.ui.layouts.settings.starpilot.metro import TileGrid, ToggleTile


SIDEBAR_METRIC_OPTIONS = [
  "None",
  "Acceleration: Current",
  "Acceleration: Max",
  "Auto Tune: Actuator Delay",
  "Auto Tune: Friction",
  "Auto Tune: Lateral Acceleration",
  "Auto Tune: Steer Ratio",
  "Auto Tune: Stiffness Factor",
  "Engagement %: Lateral",
  "Engagement %: Longitudinal",
  "Lateral Control: Steering Angle",
  "Lateral Control: Torque % Used",
  "Longitudinal Control: Actuator Acceleration Output",
  "Longitudinal MPC: Danger Factor",
  "Longitudinal MPC Jerk: Acceleration",
  "Longitudinal MPC Jerk: Danger Zone",
  "Longitudinal MPC Jerk: Speed Control",
]

# Exclusive groups for sidebar metrics (only one in each group can be active)
_SIDEBAR_CPU_GPU = {"ShowCPU", "ShowGPU"}
_SIDEBAR_STORAGE = {"ShowMemoryUsage", "ShowStorageLeft", "ShowStorageUsed"}


class StarPilotDeveloperLayout(StarPilotPanel):
  def __init__(self):
    super().__init__()
    self._sub_panels = {
      "metrics": StarPilotDevMetricsLayout(),
      "sidebar": StarPilotDevSidebarLayout(),
      "widgets": StarPilotDevWidgetsLayout(),
    }
    self.CATEGORIES = [
      {"title": tr_noop("Developer Metrics"), "panel": "metrics", "icon": "toggle_icons/icon_display.png", "color": "#364DEF"},
      {"title": tr_noop("Developer Sidebar"), "panel": "sidebar", "icon": "toggle_icons/icon_device.png", "color": "#364DEF"},
      {"title": tr_noop("Developer Widgets"), "panel": "widgets", "icon": "toggle_icons/icon_road.png", "color": "#364DEF"},
    ]
    for _name, panel in self._sub_panels.items():
      if hasattr(panel, 'set_navigate_callback'):
        panel.set_navigate_callback(self._navigate_to)
      if hasattr(panel, 'set_back_callback'):
        panel.set_back_callback(self._go_back)
    self._rebuild_grid()


class StarPilotDevMetricsLayout(StarPilotPanel):
  def __init__(self):
    super().__init__()
    self.CATEGORIES = [
      {
        "title": tr_noop("Adjacent Lane Metrics"),
        "type": "toggle",
        "key": "AdjacentPathMetrics",
        "get_state": lambda: self._params.get_bool("AdjacentPathMetrics"),
        "set_state": lambda s: self._params.put_bool("AdjacentPathMetrics", s),
        "icon": "toggle_icons/icon_road.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("Border Metrics"),
        "type": "toggle",
        "key": "BorderMetrics",
        "get_state": lambda: self._params.get_bool("BorderMetrics"),
        "set_state": lambda s: self._params.put_bool("BorderMetrics", s),
        "icon": "toggle_icons/icon_display.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("Blind Spot"),
        "type": "toggle",
        "key": "BlindSpotMetrics",
        "parent": "BorderMetrics",
        "get_state": lambda: self._params.get_bool("BlindSpotMetrics"),
        "set_state": lambda s: self._params.put_bool("BlindSpotMetrics", s),
        "icon": "toggle_icons/icon_display.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("Steering Torque"),
        "type": "toggle",
        "key": "ShowSteering",
        "parent": "BorderMetrics",
        "get_state": lambda: self._params.get_bool("ShowSteering"),
        "set_state": lambda s: self._params.put_bool("ShowSteering", s),
        "icon": "toggle_icons/icon_display.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("Turn Signal"),
        "type": "toggle",
        "key": "SignalMetrics",
        "parent": "BorderMetrics",
        "get_state": lambda: self._params.get_bool("SignalMetrics"),
        "set_state": lambda s: self._params.put_bool("SignalMetrics", s),
        "icon": "toggle_icons/icon_display.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("FPS Display"),
        "type": "toggle",
        "key": "FPSCounter",
        "get_state": lambda: self._params.get_bool("FPSCounter"),
        "set_state": lambda s: self._params.put_bool("FPSCounter", s),
        "icon": "toggle_icons/icon_display.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("Lead Info"),
        "type": "toggle",
        "key": "LeadInfo",
        "get_state": lambda: self._params.get_bool("LeadInfo"),
        "set_state": lambda s: self._params.put_bool("LeadInfo", s),
        "icon": "toggle_icons/icon_display.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("Numerical Temp"),
        "type": "toggle",
        "key": "NumericalTemp",
        "get_state": lambda: self._params.get_bool("NumericalTemp"),
        "set_state": lambda s: self._params.put_bool("NumericalTemp", s),
        "icon": "toggle_icons/icon_display.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("Fahrenheit"),
        "type": "toggle",
        "key": "Fahrenheit",
        "parent": "NumericalTemp",
        "get_state": lambda: self._params.get_bool("Fahrenheit"),
        "set_state": lambda s: self._params.put_bool("Fahrenheit", s),
        "icon": "toggle_icons/icon_display.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("Sidebar Metrics"),
        "type": "toggle",
        "key": "SidebarMetrics",
        "get_state": lambda: self._params.get_bool("SidebarMetrics"),
        "set_state": lambda s: self._params.put_bool("SidebarMetrics", s),
        "icon": "toggle_icons/icon_display.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("CPU"),
        "type": "toggle",
        "key": "ShowCPU",
        "parent": "SidebarMetrics",
        "get_state": lambda: self._params.get_bool("ShowCPU"),
        "set_state": lambda s: self._set_sidebar_exclusive("ShowCPU", s),
        "icon": "toggle_icons/icon_display.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("GPU"),
        "type": "toggle",
        "key": "ShowGPU",
        "parent": "SidebarMetrics",
        "get_state": lambda: self._params.get_bool("ShowGPU"),
        "set_state": lambda s: self._set_sidebar_exclusive("ShowGPU", s),
        "icon": "toggle_icons/icon_display.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("IP Address"),
        "type": "toggle",
        "key": "ShowIP",
        "parent": "SidebarMetrics",
        "get_state": lambda: self._params.get_bool("ShowIP"),
        "set_state": lambda s: self._params.put_bool("ShowIP", s),
        "icon": "toggle_icons/icon_display.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("RAM Usage"),
        "type": "toggle",
        "key": "ShowMemoryUsage",
        "parent": "SidebarMetrics",
        "get_state": lambda: self._params.get_bool("ShowMemoryUsage"),
        "set_state": lambda s: self._set_sidebar_exclusive("ShowMemoryUsage", s),
        "icon": "toggle_icons/icon_display.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("SSD Left"),
        "type": "toggle",
        "key": "ShowStorageLeft",
        "parent": "SidebarMetrics",
        "get_state": lambda: self._params.get_bool("ShowStorageLeft"),
        "set_state": lambda s: self._set_sidebar_exclusive("ShowStorageLeft", s),
        "icon": "toggle_icons/icon_display.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("SSD Used"),
        "type": "toggle",
        "key": "ShowStorageUsed",
        "parent": "SidebarMetrics",
        "get_state": lambda: self._params.get_bool("ShowStorageUsed"),
        "set_state": lambda s: self._set_sidebar_exclusive("ShowStorageUsed", s),
        "icon": "toggle_icons/icon_display.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("Use SI Units"),
        "type": "toggle",
        "key": "UseSI",
        "get_state": lambda: self._params.get_bool("UseSI"),
        "set_state": lambda s: self._params.put_bool("UseSI", s),
        "icon": "toggle_icons/icon_display.png",
        "color": "#364DEF",
      },
    ]
    self._rebuild_grid()

  def _set_sidebar_exclusive(self, key: str, state: bool):
    self._params.put_bool(key, state)
    if state:
      if key in _SIDEBAR_CPU_GPU:
        for k in _SIDEBAR_CPU_GPU:
          if k != key:
            self._params.put_bool(k, False)
      elif key in _SIDEBAR_STORAGE:
        for k in _SIDEBAR_STORAGE:
          if k != key:
            self._params.put_bool(k, False)
    self._rebuild_grid()

  def _rebuild_grid(self):
    if not self.CATEGORIES:
      return
    if self._tile_grid is None:
      self._tile_grid = TileGrid(columns=None, padding=20)
    self._tile_grid.clear()

    border_on = self._params.get_bool("BorderMetrics")
    temp_on = self._params.get_bool("NumericalTemp")
    sidebar_on = self._params.get_bool("SidebarMetrics")

    for cat in self.CATEGORIES:
      key = cat.get("key")
      parent = cat.get("parent")

      # Conditional visibility
      if parent == "BorderMetrics" and not border_on:
        if key == "BlindSpotMetrics" and not starpilot_state.car_state.hasBSM:
          continue
        if not border_on:
          continue
      elif parent == "NumericalTemp" and not temp_on:
        continue
      elif parent == "SidebarMetrics" and not sidebar_on:
        continue

      # BlindSpotMetrics extra gate
      if key == "BlindSpotMetrics" and not starpilot_state.car_state.hasBSM:
        continue

      tile = ToggleTile(
        title=tr(cat["title"]),
        get_state=cat["get_state"],
        set_state=cat["set_state"],
        icon_path=cat.get("icon"),
        bg_color=cat.get("color"),
      )
      self._tile_grid.add_tile(tile)


class StarPilotDevSidebarLayout(StarPilotPanel):
  def __init__(self):
    super().__init__()
    self.CATEGORIES = [
      {
        "title": tr_noop("Metric #1"),
        "type": "value",
        "key": "DeveloperSidebarMetric1",
        "get_value": lambda: tr(self._get_metric_name("DeveloperSidebarMetric1")),
        "on_click": lambda: self._show_metric_selector("DeveloperSidebarMetric1"),
        "icon": "toggle_icons/icon_device.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("Metric #2"),
        "type": "value",
        "key": "DeveloperSidebarMetric2",
        "get_value": lambda: tr(self._get_metric_name("DeveloperSidebarMetric2")),
        "on_click": lambda: self._show_metric_selector("DeveloperSidebarMetric2"),
        "icon": "toggle_icons/icon_device.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("Metric #3"),
        "type": "value",
        "key": "DeveloperSidebarMetric3",
        "get_value": lambda: tr(self._get_metric_name("DeveloperSidebarMetric3")),
        "on_click": lambda: self._show_metric_selector("DeveloperSidebarMetric3"),
        "icon": "toggle_icons/icon_device.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("Metric #4"),
        "type": "value",
        "key": "DeveloperSidebarMetric4",
        "get_value": lambda: tr(self._get_metric_name("DeveloperSidebarMetric4")),
        "on_click": lambda: self._show_metric_selector("DeveloperSidebarMetric4"),
        "icon": "toggle_icons/icon_device.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("Metric #5"),
        "type": "value",
        "key": "DeveloperSidebarMetric5",
        "get_value": lambda: tr(self._get_metric_name("DeveloperSidebarMetric5")),
        "on_click": lambda: self._show_metric_selector("DeveloperSidebarMetric5"),
        "icon": "toggle_icons/icon_device.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("Metric #6"),
        "type": "value",
        "key": "DeveloperSidebarMetric6",
        "get_value": lambda: tr(self._get_metric_name("DeveloperSidebarMetric6")),
        "on_click": lambda: self._show_metric_selector("DeveloperSidebarMetric6"),
        "icon": "toggle_icons/icon_device.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("Metric #7"),
        "type": "value",
        "key": "DeveloperSidebarMetric7",
        "get_value": lambda: tr(self._get_metric_name("DeveloperSidebarMetric7")),
        "on_click": lambda: self._show_metric_selector("DeveloperSidebarMetric7"),
        "icon": "toggle_icons/icon_device.png",
        "color": "#364DEF",
      },
    ]
    self._rebuild_grid()

  def _get_metric_name(self, key: str) -> str:
    idx = self._params.get_int(key)
    if 0 <= idx < len(SIDEBAR_METRIC_OPTIONS):
      return SIDEBAR_METRIC_OPTIONS[idx]
    return "None"

  def _show_metric_selector(self, key: str):
    current_idx = self._params.get_int(key)
    current = SIDEBAR_METRIC_OPTIONS[current_idx] if 0 <= current_idx < len(SIDEBAR_METRIC_OPTIONS) else "None"

    def on_close(res, val):
      if res == DialogResult.CONFIRM:
        try:
          selected_idx = SIDEBAR_METRIC_OPTIONS.index(val)
          self._params.put_int(key, selected_idx)
          self._rebuild_grid()
        except ValueError:
          pass

    gui_app.set_modal_overlay(SelectionDialog(tr("Select a Metric"), SIDEBAR_METRIC_OPTIONS, current, on_close=on_close))


class StarPilotDevWidgetsLayout(StarPilotPanel):
  def __init__(self):
    super().__init__()
    self.CATEGORIES = [
      {
        "title": tr_noop("Adjacent Leads Tracking"),
        "type": "toggle",
        "key": "AdjacentLeadsUI",
        "get_state": lambda: self._params.get_bool("AdjacentLeadsUI"),
        "set_state": lambda s: self._params.put_bool("AdjacentLeadsUI", s),
        "icon": "toggle_icons/icon_display.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("Model Stopping Point"),
        "type": "toggle",
        "key": "ShowStoppingPoint",
        "get_state": lambda: self._params.get_bool("ShowStoppingPoint"),
        "set_state": lambda s: self._params.put_bool("ShowStoppingPoint", s),
        "icon": "toggle_icons/icon_road.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("Show Distance"),
        "type": "toggle",
        "key": "ShowStoppingPointMetrics",
        "parent": "ShowStoppingPoint",
        "get_state": lambda: self._params.get_bool("ShowStoppingPointMetrics"),
        "set_state": lambda s: self._params.put_bool("ShowStoppingPointMetrics", s),
        "icon": "toggle_icons/icon_road.png",
        "color": "#364DEF",
      },
      {
        "title": tr_noop("Radar Tracks"),
        "type": "toggle",
        "key": "RadarTracksUI",
        "get_state": lambda: self._params.get_bool("RadarTracksUI"),
        "set_state": lambda s: self._params.put_bool("RadarTracksUI", s),
        "icon": "toggle_icons/icon_display.png",
        "color": "#364DEF",
      },
    ]
    self._rebuild_grid()

  def _rebuild_grid(self):
    if not self.CATEGORIES:
      return
    if self._tile_grid is None:
      self._tile_grid = TileGrid(columns=None, padding=20)
    self._tile_grid.clear()

    stopping_on = self._params.get_bool("ShowStoppingPoint")

    for cat in self.CATEGORIES:
      key = cat.get("key")
      parent = cat.get("parent")

      # Conditional visibility
      if key == "AdjacentLeadsUI" and not starpilot_state.car_state.hasRadar:
        continue
      elif key == "RadarTracksUI" and not starpilot_state.car_state.hasRadar:
        continue
      elif key == "ShowStoppingPoint" and not starpilot_state.car_state.hasOpenpilotLongitudinal:
        continue
      elif parent == "ShowStoppingPoint" and not stopping_on:
        continue

      tile = ToggleTile(
        title=tr(cat["title"]),
        get_state=cat["get_state"],
        set_state=cat["set_state"],
        icon_path=cat.get("icon"),
        bg_color=cat.get("color"),
      )
      self._tile_grid.add_tile(tile)
