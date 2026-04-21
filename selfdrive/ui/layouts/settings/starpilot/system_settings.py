from __future__ import annotations
import json
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from dataclasses import replace

import pyray as rl

from openpilot.system.hardware import HARDWARE
from openpilot.system.ui.lib.application import gui_app, FontWeight, MouseEvent, MousePos
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.lib.scroll_panel2 import GuiScrollPanel2
from openpilot.system.ui.widgets import DialogResult, Widget
from openpilot.system.ui.widgets.confirm_dialog import ConfirmDialog, alert_dialog
from openpilot.system.ui.widgets.keyboard import Keyboard
from openpilot.system.ui.widgets.option_dialog import MultiOptionDialog
from openpilot.system.ui.widgets.label import gui_label

from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.selfdrive.ui.layouts.settings.starpilot.panel import StarPilotPanel
from openpilot.selfdrive.ui.layouts.settings.starpilot.aethergrid import (
  AETHER_LIST_METRICS,
  AetherListColors,
  AetherScrollbar,
  AetherContinuousSlider,
  build_list_panel_frame,
  draw_list_panel_shell,
  draw_list_scroll_fades,
  draw_toggle_pill,
)

LEGACY_STARPILOT_PARAM_RENAMES = {
  "FrogPilotApiToken": "StarPilotApiToken",
  "FrogPilotCarParams": "StarPilotCarParams",
  "FrogPilotCarParamsPersistent": "StarPilotCarParamsPersistent",
  "FrogPilotDongleId": "StarPilotDongleId",
  "FrogPilotStats": "StarPilotStats",
}

EXCLUDED_KEYS = {
  "AvailableModels",
  "AvailableModelNames",
  "StarPilotStats",
  "GithubSshKeys",
  "GithubUsername",
  "MapBoxRequests",
  "ModelDrivesAndScores",
  "OverpassRequests",
  "SpeedLimits",
  "SpeedLimitsFiltered",
  "UpdaterAvailableBranches",
}

REPORT_CATEGORIES = [
  "Acceleration feels harsh or jerky",
  "An alert was unclear and I'm not sure what it meant",
  "Braking is too sudden or uncomfortable",
  "I'm not sure if this is normal or a bug:",
  "My steering wheel buttons aren't working",
  "openpilot disengages when I don't expect it",
  "openpilot feels sluggish or slow to respond",
  "Something else (please describe)",
]

class SystemSettingsManagerView(Widget):
  def __init__(self, controller: "StarPilotSystemLayout"):
    super().__init__()
    self._controller = controller
    self._scroll_panel = GuiScrollPanel2(horizontal=False)
    self._scrollbar = AetherScrollbar()
    self._content_height = 0.0
    self._scroll_offset = 0.0
    self._pressed_target: str | None = None
    self._can_click = True
    
    self._action_rects: dict[str, rl.Rectangle] = {}
    self._toggle_rects: dict[str, rl.Rectangle] = {}
    self._shell_rect = rl.Rectangle(0, 0, 0, 0)
    self._scroll_rect = rl.Rectangle(0, 0, 0, 0)

    shutdown_labels = {0: tr("5 mins")}
    for i in range(1, 4): shutdown_labels[i] = f"{i * 15} mins"
    for i in range(4, 34): shutdown_labels[i] = f"{i - 3} " + (tr("hour") if i == 4 else tr("hours"))

    brightness_labels = {101: tr("Auto"), 0: tr("Off")}

    self._sliders = {
      "ScreenBrightness": AetherContinuousSlider(0, 101, 1, self._controller._params.get_int("ScreenBrightness"), lambda v: self._controller._set_brightness("ScreenBrightness", v), title=tr("Brightness (Offroad)"), unit="%", labels=brightness_labels, color=AetherListColors.PRIMARY),
      "ScreenBrightnessOnroad": AetherContinuousSlider(1, 101, 1, max(1, self._controller._params.get_int("ScreenBrightnessOnroad")), lambda v: self._controller._set_brightness("ScreenBrightnessOnroad", max(1, int(v))), title=tr("Brightness (Onroad)"), unit="%", labels=brightness_labels, color=AetherListColors.PRIMARY),
      "ScreenTimeout": AetherContinuousSlider(5, 60, 5, self._controller._params.get_int("ScreenTimeout"), lambda v: self._controller._params.put_int("ScreenTimeout", int(v)), title=tr("Timeout (Offroad)"), unit="s", color=AetherListColors.PRIMARY),
      "ScreenTimeoutOnroad": AetherContinuousSlider(5, 60, 5, self._controller._params.get_int("ScreenTimeoutOnroad"), lambda v: self._controller._params.put_int("ScreenTimeoutOnroad", int(v)), title=tr("Timeout (Onroad)"), unit="s", color=AetherListColors.PRIMARY),
      "DeviceShutdown": AetherContinuousSlider(0, 33, 1, self._controller._params.get_int("DeviceShutdown"), lambda v: self._controller._params.put_int("DeviceShutdown", int(v)), title=tr("Device Shutdown"), labels=shutdown_labels, color=AetherListColors.PRIMARY),
      "LowVoltageShutdown": AetherContinuousSlider(11.8, 12.5, 0.1, self._controller._params.get_float("LowVoltageShutdown"), lambda v: self._controller._params.put_float("LowVoltageShutdown", float(v)), title=tr("Low-Voltage Cutoff"), unit="V", color=AetherListColors.PRIMARY),
    }

  def _clear_ephemeral_state(self):
    self._pressed_target = None
    self._can_click = True

  def show_event(self):
    super().show_event()
    self._clear_ephemeral_state()

  def hide_event(self):
    super().hide_event()
    self._clear_ephemeral_state()

  def _handle_mouse_press(self, mouse_pos: MousePos):
    self._pressed_target = None
    self._can_click = True
    
    for action_id, rect in self._action_rects.items():
      visible_rect = rl.get_collision_rec(rect, self._scroll_rect)
      if visible_rect.width > 0 and visible_rect.height > 0 and rl.check_collision_point_rec(mouse_pos, visible_rect):
        self._pressed_target = f"action:{action_id}"
        return
        
    for toggle_id, rect in self._toggle_rects.items():
      visible_rect = rl.get_collision_rec(rect, self._scroll_rect)
      if visible_rect.width > 0 and visible_rect.height > 0 and rl.check_collision_point_rec(mouse_pos, visible_rect):
        self._pressed_target = f"toggle:{toggle_id}"
        return

    for slider in self._sliders.values():
      slider._handle_mouse_press(mouse_pos)

  def _handle_mouse_event(self, mouse_event: MouseEvent):
    if not self._scroll_panel.is_touch_valid():
      self._can_click = False
    for slider in self._sliders.values():
      slider._handle_mouse_event(mouse_event)

  def _handle_mouse_release(self, mouse_pos: MousePos):
    target = self._pressed_target
    self._pressed_target = None
    
    if target and self._can_click:
      if target.startswith("action:"):
        action_id = target.split(":", 1)[1]
        rect = self._action_rects.get(action_id)
      elif target.startswith("toggle:"):
        toggle_id = target.split(":", 1)[1]
        rect = self._toggle_rects.get(toggle_id)
        
      if rect:
        visible_rect = rl.get_collision_rec(rect, self._scroll_rect)
        if visible_rect.width > 0 and visible_rect.height > 0 and rl.check_collision_point_rec(mouse_pos, visible_rect):
          self._activate_target(target)
          
    for slider in self._sliders.values():
      slider._handle_mouse_release(mouse_pos)

  def _activate_target(self, target: str):
    action_id = target.split(":", 1)[1]
    self._controller.handle_action(action_id)

  def _render(self, rect: rl.Rectangle):
    self.set_rect(rect)
    self._action_rects.clear()
    self._toggle_rects.clear()

    metrics = replace(AETHER_LIST_METRICS, header_height=110)
    frame = build_list_panel_frame(rect, metrics)
    self._shell_rect = frame.shell
    draw_list_panel_shell(frame)

    header_rect = frame.header
    self._draw_header(header_rect)

    scroll_rect = frame.scroll
    self._scroll_rect = scroll_rect

    content_width = scroll_rect.width - AETHER_LIST_METRICS.content_right_gutter
    self._content_height = self._measure_content_height()
    self._scroll_offset = self._scroll_panel.update(scroll_rect, max(self._content_height, scroll_rect.height))

    rl.begin_scissor_mode(int(scroll_rect.x), int(scroll_rect.y), int(scroll_rect.width), int(scroll_rect.height))
    self._draw_scroll_content(scroll_rect, content_width)
    rl.end_scissor_mode()

    if self._content_height > scroll_rect.height:
      self._draw_scrollbar(scroll_rect)

    draw_list_scroll_fades(scroll_rect, self._content_height, self._scroll_offset, AetherListColors.PANEL_BG, fade_height=AETHER_LIST_METRICS.fade_height)

  def _draw_header(self, rect: rl.Rectangle):
    title_rect = rl.Rectangle(rect.x, rect.y + 4, rect.width * 0.55, 40)
    gui_label(title_rect, tr("System Settings"), 40, AetherListColors.HEADER, FontWeight.SEMI_BOLD)
    subtitle_rect = rl.Rectangle(rect.x, rect.y + 48, rect.width * 0.58, 36)
    gui_label(subtitle_rect, tr("Manage device behavior, power, and storage seamlessly."), 24, AetherListColors.SUBTEXT, FontWeight.NORMAL)

  def _measure_column_height(self, sections: list[dict]) -> float:
    total_height = 0
    for section in sections:
      total_height += AETHER_LIST_METRICS.section_header_height + AETHER_LIST_METRICS.section_header_gap
      for row in section["rows"]:
        if row["type"] == "slider":
          total_height += 100 + 16
        elif row["type"] in ["toggle", "toggle_row"]:
          total_height += 90 + 16
        elif row["type"] == "action_group":
          total_height += 110 + 16
      total_height += AETHER_LIST_METRICS.section_gap
    return max(total_height - AETHER_LIST_METRICS.section_gap, 0.0)

  def _measure_content_height(self) -> float:
    cols = self._controller.utility_columns()
    return max(self._measure_column_height(cols["left"]), self._measure_column_height(cols["right"]), 0.0)

  def _draw_scroll_content(self, rect: rl.Rectangle, width: float):
    cols = self._controller.utility_columns()
    col_w = (width - AETHER_LIST_METRICS.section_gap) / 2
    left_x = rect.x
    right_x = rect.x + col_w + AETHER_LIST_METRICS.section_gap
    
    self._draw_column(rl.Rectangle(left_x, rect.y + self._scroll_offset, col_w, rect.height), cols["left"])
    self._draw_column(rl.Rectangle(right_x, rect.y + self._scroll_offset, col_w, rect.height), cols["right"])

  def _draw_column(self, rect: rl.Rectangle, sections: list[dict]):
    y = rect.y
    mouse_pos = gui_app.last_mouse_event.pos
    
    for section in sections:
      title_rect = rl.Rectangle(rect.x, y, rect.width, AETHER_LIST_METRICS.section_header_height)
      gui_label(title_rect, section["title"], 26, AetherListColors.SUBTEXT, FontWeight.MEDIUM)
      y += AETHER_LIST_METRICS.section_header_height + AETHER_LIST_METRICS.section_header_gap
      
      for row in section["rows"]:
        if row["type"] == "slider":
          slider = self._sliders[row["id"]]
          slider.render(rl.Rectangle(rect.x, y, rect.width, 100))
          y += 100 + 16
        elif row["type"] == "toggle_row":
          items = row["items"]
          item_w = (rect.width - 16 * (len(items) - 1)) / len(items)
          for i, item in enumerate(items):
            enabled = item.get("enabled", True)
            toggle_rect = rl.Rectangle(rect.x + i * (item_w + 16), y, item_w, 90)
            if enabled:
                self._toggle_rects[item["id"]] = toggle_rect
            hovered = rl.check_collision_point_rec(mouse_pos, toggle_rect)
            pressed = self._pressed_target == f"toggle:{item['id']}"
            draw_toggle_pill(toggle_rect, item["value"], enabled, item["title"], tr("ON") if item["value"] else tr("OFF"), hovered, pressed)
          y += 90 + 16
        elif row["type"] == "toggle":
          enabled = row.get("enabled", True)
          toggle_rect = rl.Rectangle(rect.x, y, rect.width, 90)
          if enabled:
              self._toggle_rects[row["id"]] = toggle_rect
          hovered = rl.check_collision_point_rec(mouse_pos, toggle_rect)
          pressed = self._pressed_target == f"toggle:{row['id']}"
          draw_toggle_pill(toggle_rect, row["value"], enabled, row["title"], tr("ON") if row["value"] else tr("OFF"), hovered, pressed)
          y += 90 + 16
        elif row["type"] == "action_group":
          group_rect = rl.Rectangle(rect.x, y, rect.width, 110)
          self._draw_action_group(group_rect, row, mouse_pos)
          y += 110 + 16
          
      y += AETHER_LIST_METRICS.section_gap

  def _draw_action_group(self, rect: rl.Rectangle, row: dict, mouse_pos: MousePos):
    rl.draw_rectangle_rounded(rect, 0.3, 16, rl.Color(35, 35, 40, 255))
    
    title_y = rect.y + (rect.height - 24) / 2
    gui_label(rl.Rectangle(rect.x + 24, title_y, rect.width * 0.4, 24), row["title"], 24, rl.WHITE, FontWeight.BOLD)
    
    actions = row["actions"]
    btn_gap = 12
    available_w = rect.width * 0.6 - 40
    btn_w = (available_w - (len(actions) - 1) * btn_gap) / len(actions)
    start_x = rect.x + rect.width - available_w - 16
    
    for i, action in enumerate(actions):
      btn_rect = rl.Rectangle(start_x + i * (btn_w + btn_gap), rect.y + 12, btn_w, rect.height - 24)
      self._action_rects[action["id"]] = btn_rect
      
      hovered = rl.check_collision_point_rec(mouse_pos, btn_rect)
      pressed = self._pressed_target == f"action:{action['id']}"
      
      active = action.get("active", False)
      color = AetherListColors.PRIMARY if active else rl.Color(60, 60, 65, 255)
      if action.get("danger"):
        color = AetherListColors.DANGER
        
      if hovered: color = rl.Color(min(color.r + 20, 255), min(color.g + 20, 255), min(color.b + 20, 255), 255)
      if pressed: color = rl.Color(max(color.r - 20, 0), max(color.g - 20, 0), max(color.b - 20, 0), 255)
      
      rl.draw_rectangle_rounded(btn_rect, 0.4, 16, color)
      gui_label(btn_rect, action["label"], 24, rl.WHITE, FontWeight.BOLD, alignment=rl.GuiTextAlignment.TEXT_ALIGN_CENTER)

  def _draw_scrollbar(self, rect: rl.Rectangle):
    self._scrollbar.render(rect, self._content_height, self._scroll_offset)


class StarPilotSystemLayout(StarPilotPanel):
  def __init__(self):
    super().__init__()
    self._keyboard = Keyboard(min_text_size=0)
    self._manager_view = SystemSettingsManagerView(self)

  def show_event(self):
    super().show_event()
    self._manager_view.show_event()

  def hide_event(self):
    super().hide_event()
    self._manager_view.hide_event()

  def _render(self, rect: rl.Rectangle):
    self._manager_view.render(rect)

  def utility_columns(self) -> dict[str, list[dict]]:
    state = self._get_force_drive_state()
    no_uploads = self._params.get_bool("NoUploads")
    disable_onroad = self._params.get_bool("DisableOnroadUploads")
    
    screen_management = self._params.get_bool("ScreenManagement")
    screen_rows = [
        {"id": "ScreenManagement", "type": "toggle", "title": tr("Screen Management"), "value": screen_management},
        {"id": "StandbyMode", "type": "toggle", "title": tr("Standby Mode"), "value": self._params.get_bool("StandbyMode"), "enabled": screen_management},
    ]
    if screen_management:
        screen_rows.extend([
            {"id": "ScreenBrightness", "type": "slider"},
            {"id": "ScreenBrightnessOnroad", "type": "slider"},
            {"id": "ScreenTimeout", "type": "slider"},
            {"id": "ScreenTimeoutOnroad", "type": "slider"},
        ])

    device_management = self._params.get_bool("DeviceManagement")
    device_rows = [
        {"id": "DeviceManagement", "type": "toggle", "title": tr("Device Management"), "value": device_management},
        {"id": "IncreaseThermalLimits", "type": "toggle", "title": tr("Raise Thermal Limits"), "value": self._params.get_bool("IncreaseThermalLimits"), "enabled": device_management},
    ]
    if device_management:
        device_rows.extend([
            {"id": "DeviceShutdown", "type": "slider"},
            {"id": "LowVoltageShutdown", "type": "slider"},
        ])

    network_rows = [
        {"type": "toggle_row", "items": [
            {"id": "NoUploads", "title": tr("Disable Uploads"), "value": no_uploads},
            {"id": "UseKonikServer", "title": tr("Use Konik Server"), "value": self._get_konik_state()}
        ]},
        {"type": "toggle_row", "items": [
            {"id": "DisableOnroadUploads", "title": tr("Disable Onroad Uploads"), "value": disable_onroad, "enabled": not no_uploads},
            {"id": "NoLogging", "title": tr("Disable Logging"), "value": self._params.get_bool("NoLogging")}
        ]},
        {"id": "HigherBitrate", "type": "toggle", "title": tr("High-Quality Recording"), "value": self._params.get_bool("HigherBitrate"), "enabled": not disable_onroad and not no_uploads}
    ]

    data_rows = [
        {"id": "Storage", "type": "action_group", "title": tr("Storage & Logs"), "actions": [
            {"id": "Storage", "label": f"{tr('Clear Data')} ({self._get_storage()})", "danger": True},
            {"id": "ErrorLogs", "label": tr("Clear Logs"), "danger": True}
        ]},
        {"id": "SystemBackups", "type": "action_group", "title": tr("System Backups"), "actions": [
            {"id": "CreateBackup", "label": tr("Create")},
            {"id": "RestoreBackup", "label": tr("Restore")},
            {"id": "DeleteBackup", "label": tr("Delete"), "danger": True}
        ]},
        {"id": "ToggleBackups", "type": "action_group", "title": tr("Toggle Backups"), "actions": [
            {"id": "CreateToggleBackup", "label": tr("Create")},
            {"id": "RestoreToggleBackup", "label": tr("Restore")},
            {"id": "DeleteToggleBackup", "label": tr("Delete"), "danger": True}
        ]},
    ]

    util_rows = [
        {"type": "toggle_row", "items": [{"id": "DebugMode", "type": "toggle", "title": tr("Debug Mode"), "value": self._params.get_bool("DebugMode")}]},
        {"id": "ForceDriveState", "type": "action_group", "title": tr("Force Drive State"), "actions": [
            {"id": "DriveDefault", "label": tr("Auto"), "active": state == tr("Default")},
            {"id": "DriveOnroad", "label": tr("Onroad"), "active": state == tr("Onroad")},
            {"id": "DriveOffroad", "label": tr("Offroad"), "active": state == tr("Offroad")}
        ]},
        {"id": "QuickActions", "type": "action_group", "title": tr("Quick Actions"), "actions": [
            {"id": "FlashPanda", "label": tr("Flash Panda")},
            {"id": "ReportIssue", "label": tr("Report Issue")}
        ]},
        {"id": "FactoryReset", "type": "action_group", "title": tr("Factory Reset"), "actions": [
            {"id": "ResetDefaults", "label": tr("Toggles"), "danger": True},
            {"id": "ResetStock", "label": tr("Stock OP"), "danger": True}
        ]},
    ]

    return {
      "left": [
        {"title": tr("Display Configuration"), "rows": screen_rows},
        {"title": tr("Developer & Maintenance"), "rows": util_rows},
      ],
      "right": [
        {"title": tr("Power & Thermals"), "rows": device_rows},
        {"title": tr("Networking & Data"), "rows": network_rows},
        {"title": tr("Data & Backups"), "rows": data_rows},
      ]
    }

  def handle_action(self, action_id: str):
    if action_id == "ScreenManagement":
      self._params.put_bool("ScreenManagement", not self._params.get_bool("ScreenManagement"))
    elif action_id == "StandbyMode":
      self._params.put_bool("StandbyMode", not self._params.get_bool("StandbyMode"))
    elif action_id == "DeviceManagement":
      self._params.put_bool("DeviceManagement", not self._params.get_bool("DeviceManagement"))
    elif action_id == "IncreaseThermalLimits":
      self._params.put_bool("IncreaseThermalLimits", not self._params.get_bool("IncreaseThermalLimits"))
    elif action_id == "UseKonikServer":
      self._on_konik_toggle(not self._get_konik_state())
    elif action_id == "NoLogging":
      self._params.put_bool("NoLogging", not self._params.get_bool("NoLogging"))
    elif action_id == "NoUploads":
      self._params.put_bool("NoUploads", not self._params.get_bool("NoUploads"))
    elif action_id == "DisableOnroadUploads":
      self._params.put_bool("DisableOnroadUploads", not self._params.get_bool("DisableOnroadUploads"))
    elif action_id == "HigherBitrate":
      self._on_higher_bitrate_toggle(not self._params.get_bool("HigherBitrate"))
    elif action_id == "Storage":
      self._on_delete_driving_data()
    elif action_id == "ErrorLogs":
      self._on_delete_error_logs()
    elif action_id == "CreateBackup":
      self._on_create_backup()
    elif action_id == "RestoreBackup":
      self._on_restore_backup()
    elif action_id == "DeleteBackup":
      self._on_delete_backup()
    elif action_id == "CreateToggleBackup":
      self._on_create_toggle_backup()
    elif action_id == "RestoreToggleBackup":
      self._on_restore_toggle_backup()
    elif action_id == "DeleteToggleBackup":
      self._on_delete_toggle_backup()
    elif action_id == "DebugMode":
      self._params.put_bool("DebugMode", not self._params.get_bool("DebugMode"))
    elif action_id == "DriveDefault":
      self._params.put_bool("ForceOffroad", False)
      self._params.put_bool("ForceOnroad", False)
    elif action_id == "DriveOnroad":
      self._params.put_bool("ForceOnroad", True)
      self._params.put_bool("ForceOffroad", False)
    elif action_id == "DriveOffroad":
      self._params.put_bool("ForceOffroad", True)
      self._params.put_bool("ForceOnroad", False)
    elif action_id == "FlashPanda":
      self._on_flash_panda()
    elif action_id == "ReportIssue":
      self._on_report_issue()
    elif action_id == "ResetDefaults":
      self._on_reset_defaults()
    elif action_id == "ResetStock":
      self._on_reset_stock()

  def _set_brightness(self, key, val):
    self._params.put_int(key, int(val))
    if key == "ScreenBrightnessOnroad" or key == "ScreenBrightness":
        HARDWARE.set_brightness(int(val))

  def _get_konik_state(self):
    if Path("/data/not_vetted").exists():
      return True
    return self._params.get_bool("UseKonikServer")

  def _on_konik_toggle(self, state):
    self._params.put_bool("UseKonikServer", state)
    cache_path = Path("/cache/use_konik")
    if state:
      cache_path.parent.mkdir(parents=True, exist_ok=True)
      cache_path.touch()
    else:
      if cache_path.exists():
        cache_path.unlink()
    if ui_state.started:
      gui_app.push_widget(
        ConfirmDialog(
          tr("Reboot required. Reboot now?"), tr("Reboot"), tr("Cancel"), on_close=lambda res: HARDWARE.reboot() if res == DialogResult.CONFIRM else None
        )
      )

  def _on_higher_bitrate_toggle(self, state):
    self._params.put_bool("HigherBitrate", state)
    cache_path = Path("/cache/use_HD")
    if state:
      cache_path.parent.mkdir(parents=True, exist_ok=True)
      cache_path.touch()
    else:
      if cache_path.exists():
        cache_path.unlink()
    if ui_state.started:
      gui_app.push_widget(
        ConfirmDialog(
          tr("Reboot required. Reboot now?"), tr("Reboot"), tr("Cancel"), on_close=lambda res: HARDWARE.reboot() if res == DialogResult.CONFIRM else None
        )
      )

  def _get_storage(self):
    paths = ["/data/media/0/osm/offline", "/data/media/0/realdata", "/data/backups"]
    total = 0
    for p in paths:
      pp = Path(p)
      if pp.exists():
        total += sum(f.stat().st_size for f in pp.rglob('*') if f.is_file())
    mb = total / (1024 * 1024)
    if mb > 1024:
      return f"{(mb / 1024):.2f} GB"
    return f"{mb:.2f} MB"

  def _on_delete_driving_data(self):
    def _do_delete(res):
      if res == DialogResult.CONFIRM:
        def _task():
          drive_paths = ["/data/media/0/realdata/", "/data/media/0/realdata_HD/", "/data/media/0/realdata_konik/"]
          for path in drive_paths:
            p = Path(path)
            if p.exists():
              for entry in p.iterdir():
                if entry.is_dir():
                  shutil.rmtree(entry, ignore_errors=True)
        threading.Thread(target=_task, daemon=True).start()
        gui_app.push_widget(alert_dialog(tr("Driving data deletion started.")))
    gui_app.push_widget(ConfirmDialog(tr("Delete all driving data and footage?"), tr("Delete"), on_close=_do_delete))

  def _on_delete_error_logs(self):
    def _do_delete(res):
      if res == DialogResult.CONFIRM:
        shutil.rmtree("/data/error_logs", ignore_errors=True)
        os.makedirs("/data/error_logs", exist_ok=True)
        gui_app.push_widget(alert_dialog(tr("Error logs deleted.")))
    gui_app.push_widget(ConfirmDialog(tr("Delete all error logs?"), tr("Delete"), on_close=_do_delete))

  def _get_backups(self, folder="backups"):
    b_dir = Path(f"/data/{folder}")
    if not b_dir.exists():
      return []
    if folder == "backups":
      return [f.name for f in b_dir.glob("*.tar.zst") if "in_progress" not in f.name]
    return [d.name for d in b_dir.iterdir() if d.is_dir() and "in_progress" not in d.name]

  def _on_create_backup(self):
    def on_name(res, name):
      if res == DialogResult.CONFIRM:
        safe_name = name.replace(" ", "_") if name else f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = f"/data/backups/{safe_name}.tar.zst"
        if Path(backup_path).exists():
          gui_app.push_widget(alert_dialog(tr("A backup with this name already exists.")))
          return
        gui_app.push_widget(alert_dialog(tr("Backup creation started.")))
        def _task():
          os.makedirs("/data/backups", exist_ok=True)
          subprocess.run(["tar", "--use-compress-program=zstd", "-cf", backup_path, "/data/openpilot"])
        threading.Thread(target=_task, daemon=True).start()
    self._keyboard.reset(min_text_size=0)
    self._keyboard.set_title(tr("Name your backup"), "")
    self._keyboard.set_text("")
    self._keyboard.set_callback(lambda result: on_name(result, self._keyboard.text))
    gui_app.push_widget(self._keyboard)

  def _on_restore_backup(self):
    backups = self._get_backups("backups")
    if not backups:
      gui_app.push_widget(alert_dialog(tr("No backups found.")))
      return
    dialog = MultiOptionDialog(tr("Select Backup"), backups)
    def _on_select(res):
      if res == DialogResult.CONFIRM and dialog.selection:
        gui_app.push_widget(alert_dialog(tr("Restoring... device will reboot.")))
        def _task():
          subprocess.run(["rm", "-rf", "/data/openpilot/*"])
          subprocess.run(["tar", "--use-compress-program=zstd", "-xf", f"/data/backups/{dialog.selection}", "-C", "/"])
          os.system("reboot")
        threading.Thread(target=_task, daemon=True).start()
    gui_app.push_widget(dialog, callback=_on_select)

  def _on_delete_backup(self):
    backups = self._get_backups("backups")
    if not backups:
      gui_app.push_widget(alert_dialog(tr("No backups found.")))
      return
    dialog = MultiOptionDialog(tr("Delete Backup"), backups)
    def _on_select(res):
      if res == DialogResult.CONFIRM and dialog.selection:
        os.remove(f"/data/backups/{dialog.selection}")
    gui_app.push_widget(dialog, callback=_on_select)

  def _on_create_toggle_backup(self):
    def on_name(res, name):
      if res == DialogResult.CONFIRM:
        safe_name = name.replace(" ", "_") if name else f"toggle_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = Path(f"/data/toggle_backups/{safe_name}")
        if backup_path.exists():
          gui_app.push_widget(alert_dialog(tr("A toggle backup with this name already exists.")))
          return
        os.makedirs(backup_path, exist_ok=True)
        shutil.copytree("/data/params/d", str(backup_path), dirs_exist_ok=True)
        gui_app.push_widget(alert_dialog(tr("Toggle backup created.")))
    self._keyboard.reset(min_text_size=0)
    self._keyboard.set_title(tr("Name your toggle backup"), "")
    self._keyboard.set_text("")
    self._keyboard.set_callback(lambda result: on_name(result, self._keyboard.text))
    gui_app.push_widget(self._keyboard)

  def _on_restore_toggle_backup(self):
    backups = self._get_backups("toggle_backups")
    if not backups:
      gui_app.push_widget(alert_dialog(tr("No toggle backups found.")))
      return
    dialog = MultiOptionDialog(tr("Select Toggle Backup"), backups)
    def _on_select(res):
      if res == DialogResult.CONFIRM and dialog.selection:
        def on_confirm(r2):
          if r2 == DialogResult.CONFIRM:
            src = Path(f"/data/toggle_backups/{dialog.selection}")
            params_dir = Path("/data/params/d")
            for old_key, new_key in LEGACY_STARPILOT_PARAM_RENAMES.items():
              if (src / old_key).exists():
                (params_dir / new_key).unlink(missing_ok=True)
            shutil.copytree(str(src), "/data/params/d", dirs_exist_ok=True)
            for old_key, new_key in LEGACY_STARPILOT_PARAM_RENAMES.items():
              old_path = params_dir / old_key
              new_path = params_dir / new_key
              if old_path.exists():
                old_path.replace(new_path)
            gui_app.push_widget(alert_dialog(tr("Toggles restored.")))
        gui_app.push_widget(ConfirmDialog(tr("This will overwrite your current toggles."), tr("Restore"), on_close=on_confirm))
    gui_app.push_widget(dialog, callback=_on_select)

  def _on_delete_toggle_backup(self):
    backups = self._get_backups("toggle_backups")
    if not backups:
      gui_app.push_widget(alert_dialog(tr("No toggle backups found.")))
      return
    dialog = MultiOptionDialog(tr("Delete Toggle Backup"), backups)
    def _on_select(res):
      if res == DialogResult.CONFIRM and dialog.selection:
        shutil.rmtree(f"/data/toggle_backups/{dialog.selection}", ignore_errors=True)
    gui_app.push_widget(dialog, callback=_on_select)

  def _get_force_drive_state(self):
    if self._params.get_bool("ForceOnroad"):
      return tr("Onroad")
    if self._params.get_bool("ForceOffroad"):
      return tr("Offroad")
    return tr("Default")

  def _on_flash_panda(self):
    def _do_flash(res):
      if res == DialogResult.CONFIRM:
        self._params_memory.put_bool("FlashPanda", True)
        gui_app.push_widget(alert_dialog(tr("Panda flashing started. Device will reboot when finished.")))
    gui_app.push_widget(ConfirmDialog(tr("Flash Panda firmware?"), tr("Flash"), callback=_do_flash))

  def _on_report_issue(self):
    def on_category(res):
      if res != DialogResult.CONFIRM or not dialog.selection:
        return
      discord_user = self._params.get("DiscordUsername", encoding='utf-8') or ""
      def on_discord(res2, username):
        if res2 == DialogResult.CONFIRM and username:
          self._params.put("DiscordUsername", username)
          report = json.dumps({"DiscordUser": username, "Issue": dialog.selection})
          self._params_memory.put("IssueReported", report)
          gui_app.push_widget(alert_dialog(tr("Issue reported. Thank you!")))
      self._keyboard.reset(min_text_size=1)
      self._keyboard.set_title(tr("Discord Username"), "")
      self._keyboard.set_text(discord_user or "")
      self._keyboard.set_callback(lambda result: on_discord(result, self._keyboard.text))
      gui_app.push_widget(self._keyboard)
    dialog = MultiOptionDialog(tr("Select Issue"), REPORT_CATEGORIES, callback=on_category)
    gui_app.push_widget(dialog)

  def _on_reset_defaults(self):
    def _do_reset(res):
      if res == DialogResult.CONFIRM:
        all_keys = self._params.all_keys()
        for k in all_keys:
          if k in EXCLUDED_KEYS:
            continue
          default = self._params.get_default_value(k)
          if default is not None:
            self._params.put(k, default)
        gui_app.push_widget(alert_dialog(tr("Toggles reset to defaults.")))
    gui_app.push_widget(ConfirmDialog(tr("Reset all toggles to defaults?"), tr("Reset"), callback=_do_reset))

  def _on_reset_stock(self):
    def _do_reset(res):
      if res == DialogResult.CONFIRM:
        all_keys = self._params.all_keys()
        for k in all_keys:
          if k in EXCLUDED_KEYS:
            continue
          stock = self._params.get_stock_value(k)
          if stock is not None:
            self._params.put(k, stock)
        gui_app.push_widget(alert_dialog(tr("Toggles reset to stock openpilot.")))
    gui_app.push_widget(ConfirmDialog(tr("Reset all toggles to stock openpilot?"), tr("Reset"), callback=_do_reset))
