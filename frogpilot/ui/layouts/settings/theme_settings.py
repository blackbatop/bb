import re
import shutil
import threading

from enum import IntEnum
from pathlib import Path

from openpilot.common.params import Params
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.confirm_dialog import ConfirmDialog, alert_dialog, DialogResult
from openpilot.system.ui.widgets.keyboard import Keyboard
from openpilot.system.ui.widgets.list_view import ListItem, ToggleAction, TextAction, ITEM_TEXT_VALUE_COLOR
from openpilot.system.ui.widgets.option_dialog import MultiOptionDialog
from openpilot.system.ui.widgets.scroller_tici import Scroller

from openpilot.frogpilot.common.frogpilot_variables import update_frogpilot_toggles
from openpilot.frogpilot.system.ui.widgets.frogpilot_controls import (
  FrogPilotButtonsControl,
  FrogPilotButtonToggleControl,
  FrogPilotConfirmationDialog,
  FrogPilotManageControl,
)

THEME_PACKS_DIR = Path("/data/themes/theme_packs/")
WHEELS_DIR = Path("/data/themes/steering_wheels/")

CUSTOM_THEME_KEYS = {
  "ColorScheme",
  "DistanceIconPack",
  "DownloadStatusLabel",
  "IconPack",
  "SignalAnimation",
  "SoundPack",
  "WheelIcon",
}

HOLIDAY_THEMES = [
  "New Year's",
  "Valentine's Day",
  "St. Patrick's Day",
  "World Frog Day",
  "April Fools",
  "Easter",
  "May the Fourth",
  "Cinco de Mayo",
  "Stitch Day",
  "Fourth of July",
  "Halloween",
  "Thanksgiving",
  "Christmas",
]

# Asset type configurations: (sub_folder, param_key, downloadable_param, download_key)
ASSET_CONFIGS = {
  "ColorScheme": ("colors", "ColorScheme", "DownloadableColors", "ColorToDownload"),
  "DistanceIconPack": ("distance_icons", "DistanceIconPack", "DownloadableDistanceIcons", "DistanceIconToDownload"),
  "IconPack": ("icons", "IconPack", "DownloadableIcons", "IconToDownload"),
  "SignalAnimation": ("signals", "SignalAnimation", "DownloadableSignals", "SignalToDownload"),
  "SoundPack": ("sounds", "SoundPack", "DownloadableSounds", "SoundToDownload"),
  "WheelIcon": ("", "WheelIcon", "DownloadableWheels", "WheelToDownload"),
}


class SubPanel(IntEnum):
  MAIN = 0
  CUSTOM_THEMES = 1


def is_user_created_theme(theme_name: str) -> bool:
  """Check if a theme is user-created."""
  return theme_name.endswith("-user_created")


def normalize_theme_name(name: str) -> str:
  """Normalize a theme name for file matching."""
  normalized = name.lower()
  normalized = re.sub(r'[()]', '-', normalized)
  normalized = re.sub(r'\s+', '-', normalized)
  normalized = re.sub(r'[^a-z0-9\-]', '', normalized)
  normalized = normalized.rstrip('-')
  return normalized


def get_theme_display_name(param_key: str, params: Params) -> str:
  """Get the display name for a theme from its stored param value."""
  value = params.get(param_key, encoding="utf-8") or ""
  if not value:
    return "Stock"

  base_name = value

  # Extract creator if present (after ~)
  creator = ""
  tilde_idx = base_name.find("~")
  if tilde_idx >= 0:
    creator = base_name[tilde_idx + 1:]
    base_name = base_name[:tilde_idx]

  # Split on - or _ and capitalize each part
  separator = "-" if "-" in base_name else "_"
  parts = [p for p in base_name.split(separator) if p]
  parts = [p.capitalize() for p in parts]

  # Format display name
  if "-" in base_name and len(parts) > 1:
    display_name = f"{parts[0]} ({' '.join(parts[1:])})"
  else:
    display_name = " ".join(parts)

  # Add user created indicator
  if is_user_created_theme(value):
    display_name = display_name.split(" (")[0] + " 🌟"

  # Add creator
  if creator:
    display_name += f" - by: {creator}"

  return display_name


def store_theme_name(input_name: str, param_key: str, params: Params) -> str:
  """Store a theme name and return its display name."""
  output = input_name.lower()
  output = output.replace("(", "").replace(")", "").replace("'", "").replace(".", "")

  # Use - for names with parentheses, _ otherwise
  if "(" in input_name:
    output = output.replace(" ", "-")
  else:
    output = output.replace(" ", "_")

  # Handle user created marker
  output = output.replace("_🌟", "-user_created").replace(" 🌟", "-user_created")
  output = output.strip()

  params.put(param_key, output)
  return get_theme_display_name(param_key, params)


def get_theme_list(directory: Path, sub_folder: str, asset_param: str, params: Params, exclude_current: bool = True) -> list[str]:
  """Get list of available themes from a directory."""
  use_files = not sub_folder
  current_asset = params.get(asset_param, encoding="utf-8") or "" if exclude_current else ""

  theme_list = []

  if not directory.exists():
    return theme_list

  for entry in directory.iterdir():
    # Skip current asset
    if entry.stem == current_asset:
      continue

    # For files mode, skip directories
    if use_files and entry.is_dir():
      continue

    # For sub-folder mode, check if sub-folder exists
    if not use_files:
      target_path = entry / sub_folder
      if not target_path.exists():
        continue

    base_name = entry.stem
    user_created = is_user_created_theme(base_name)
    if user_created:
      base_name = base_name.replace("-user_created", "")

    # Extract creator
    creator = ""
    tilde_idx = base_name.find("~")
    if tilde_idx >= 0:
      creator = base_name[tilde_idx + 1:]
      base_name = base_name[:tilde_idx]

    # Split and capitalize
    separator = "-" if "-" in base_name else "_"
    parts = [p for p in base_name.split(separator) if p]
    parts = [p.capitalize() for p in parts]

    # Format display name
    if user_created:
      display_name = " ".join(parts)
    else:
      if len(parts) <= 1 or use_files:
        display_name = " ".join(parts)
      else:
        display_name = f"{parts[0]} ({' '.join(parts[1:])})"

    if user_created:
      display_name += " 🌟"
    if creator:
      display_name += f" - by: {creator}"

    theme_list.append(display_name)

  return sorted(theme_list)


def update_asset_param(asset_param: str, params: Params, value: str, add: bool):
  """Update the downloadable asset list."""
  assets_str = params.get(asset_param, encoding="utf-8") or ""
  assets = [a for a in assets_str.split(",") if a]

  if add:
    if value not in assets:
      assets.append(value)
  else:
    if value in assets:
      assets.remove(value)

  assets.sort()
  params.put(asset_param, ",".join(assets))


def download_theme_asset(input_name: str, download_key: str, downloadable_param: str, params: Params, params_memory: Params):
  """Initiate a theme asset download."""
  output = input_name

  # Handle creator suffix
  tilde_idx = output.find("~")
  if tilde_idx >= 0:
    output = output[:tilde_idx].lower() + "~" + output[tilde_idx + 1:]
  else:
    output = output.lower()

  output = output.replace("(", "").replace(")", "")
  output = output.replace(" ", "-" if "(" in input_name else "_")

  params_memory.put(download_key, output)


def delete_theme_asset(directory: Path, sub_folder: str, downloadable_param: str, theme_to_delete: str, params: Params):
  """Delete a theme asset."""
  use_files = not sub_folder

  # Normalize the name for matching
  base_name = theme_to_delete.lower()
  base_name = re.sub(r'[()]', '-', base_name)
  base_name = base_name.replace(" ", "-")
  base_name = re.sub(r'[^a-z0-9\-]', '', base_name)
  base_name = base_name.rstrip('-')

  base_underscore = base_name.replace("-", "_")

  candidate_names = [
    base_name,
    base_name + "-user-created",
    base_underscore,
    base_underscore + "-user_created",
  ]

  if use_files:
    # Delete file
    for file in directory.iterdir():
      if not file.is_file():
        continue
      normalized_file = file.stem.lower().replace("_", "-")
      normalized_file = re.sub(r'[^a-z0-9\-~]', '', normalized_file)

      if normalized_file in candidate_names:
        file.unlink()
        break
  else:
    # Delete directory
    for candidate in candidate_names:
      target_dir = directory / candidate / sub_folder
      if target_dir.exists():
        shutil.rmtree(target_dir.parent, ignore_errors=True)
        break

  # Update downloadable list - add back to available downloads
  update_asset_param(downloadable_param, params, theme_to_delete, True)


class FrogPilotThemePanel(Widget):
  def __init__(self):
    super().__init__()

    self._current_panel = SubPanel.MAIN
    self._params = Params()
    self._params_memory = Params("", True)
    self._toggles = {}
    self._tuning_level = 0

    # State tracking
    self._cancelling_download = False
    self._finalizing_download = False
    self._online = False
    self._parked = True
    self._random_themes = False
    self._started = False
    self._theme_downloading = False

    # Pending dialog action tracking
    self._pending_action = None  # "delete", "download", "select", "delete_confirm", "custom_top", "custom_bottom", "clear_startup"
    self._pending_asset_type = None  # "ColorScheme", "DistanceIconPack", etc.
    self._pending_selection = None  # Selected item from first dialog

    # Download state per asset type
    self._color_downloading = False
    self._distance_icon_downloading = False
    self._icon_downloading = False
    self._signal_downloading = False
    self._sound_downloading = False
    self._wheel_downloading = False

    # Downloaded state (no more available to download)
    self._colors_downloaded = False
    self._distance_icons_downloaded = False
    self._icons_downloaded = False
    self._signals_downloaded = False
    self._sounds_downloaded = False
    self._wheels_downloaded = False

    # Download status
    self._download_status = "Idle"

    # Keyboard for text input
    self._keyboard = Keyboard()

    self._build_main_panel()
    self._build_custom_themes_panel()

    ui_state.add_offroad_transition_callback(self._update_toggles)

  def _build_main_panel(self):
    self._custom_themes_control = FrogPilotManageControl(
      "CustomThemes",
      "Custom Themes",
      "<b>The overall look and feel of openpilot.</b> Use the \"Theme Maker\" in \"The Pond\" to create and share your own themes!",
      "../../frogpilot/assets/toggle_icons/icon_frog.png",
    )
    self._custom_themes_control.set_manage_callback(self._open_custom_themes_panel)

    self._holiday_themes_item = ListItem(
      title="Holiday Themes",
      description="<b>Themes based on U.S. holidays.</b> Minor holidays last one day; major holidays (Christmas, Easter, Halloween) run for a full week.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("HolidayThemes"),
        callback=lambda state: self._simple_toggle("HolidayThemes", state),
      ),
    )

    self._rainbow_path_item = ListItem(
      title="Rainbow Path",
      description="<b>Color the driving path like a Mario Kart-style \"Rainbow Road\".</b>",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("RainbowPath"),
        callback=lambda state: self._simple_toggle("RainbowPath", state),
      ),
    )

    self._random_events_item = ListItem(
      title="Random Events",
      description="<b>Occasional on-screen effects triggered by driving conditions.</b> These are purely visual and don't impact how openpilot drives!",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("RandomEvents"),
        callback=lambda state: self._simple_toggle("RandomEvents", state),
      ),
    )

    self._random_themes_control = FrogPilotButtonToggleControl(
      "RandomThemes",
      "Random Themes",
      "<b>Pick a random theme between each drive</b> from the themes you have downloaded. Great for variety without changing settings while driving.",
      "../../frogpilot/assets/toggle_icons/icon_random_themes.png",
      button_params=["RandomThemesHolidays"],
      button_texts=["Include Holiday Themes"],
    )
    self._random_themes_control.set_toggle_callback(self._on_random_themes_toggle)

    self._startup_alert_control = FrogPilotButtonsControl(
      "Startup Alert",
      "<b>Customize the \"Startup Alert\" message</b> shown at the start of each drive.",
      "../../frogpilot/assets/toggle_icons/icon_message.png",
      button_texts=["STOCK", "FROGPILOT", "CUSTOM", "CLEAR"],
    )
    self._startup_alert_control.set_click_callback(self._on_startup_alert_click)
    self._update_startup_alert_buttons()

    main_items = [
      self._custom_themes_control,
      self._holiday_themes_item,
      self._rainbow_path_item,
      self._random_events_item,
      self._random_themes_control,
      self._startup_alert_control,
    ]

    self._toggles["CustomThemes"] = self._custom_themes_control
    self._toggles["HolidayThemes"] = self._holiday_themes_item
    self._toggles["RainbowPath"] = self._rainbow_path_item
    self._toggles["RandomEvents"] = self._random_events_item
    self._toggles["RandomThemes"] = self._random_themes_control
    self._toggles["StartupAlert"] = self._startup_alert_control

    self._main_scroller = Scroller(main_items, line_separator=True, spacing=0)

  def _build_custom_themes_panel(self):
    # Color Scheme
    self._color_scheme_control = FrogPilotButtonsControl(
      "Color Scheme",
      "<b>The color scheme used throughout openpilot.</b> Use the \"Theme Maker\" in \"The Pond\" to create and share your own themes!",
      "",
      button_texts=["DELETE", "DOWNLOAD", "SELECT"],
    )
    self._color_scheme_control.set_click_callback(self._on_color_scheme_click)
    self._color_scheme_control.set_value(get_theme_display_name("ColorScheme", self._params))

    # Distance Icon Pack
    self._distance_icon_control = FrogPilotButtonsControl(
      "Distance Button",
      "<b>The distance button icons shown on the driving screen.</b> Use the \"Theme Maker\" in \"The Pond\" to create and share your own themes!",
      "",
      button_texts=["DELETE", "DOWNLOAD", "SELECT"],
    )
    self._distance_icon_control.set_click_callback(self._on_distance_icon_click)
    self._distance_icon_control.set_value(get_theme_display_name("DistanceIconPack", self._params))

    # Icon Pack
    self._icon_pack_control = FrogPilotButtonsControl(
      "Icon Pack",
      "<b>The icon style used across openpilot.</b> Use the \"Theme Maker\" in \"The Pond\" to create and share your own themes!",
      "",
      button_texts=["DELETE", "DOWNLOAD", "SELECT"],
    )
    self._icon_pack_control.set_click_callback(self._on_icon_pack_click)
    self._icon_pack_control.set_value(get_theme_display_name("IconPack", self._params))

    # Signal Animation
    self._signal_animation_control = FrogPilotButtonsControl(
      "Turn Signal",
      "<b>Themed turn-signal animations.</b> Use the \"Theme Maker\" in \"The Pond\" to create and share your own themes!",
      "",
      button_texts=["DELETE", "DOWNLOAD", "SELECT"],
    )
    self._signal_animation_control.set_click_callback(self._on_signal_animation_click)
    self._signal_animation_control.set_value(get_theme_display_name("SignalAnimation", self._params))

    # Sound Pack
    self._sound_pack_control = FrogPilotButtonsControl(
      "Sound Pack",
      "<b>The sound pack used by openpilot.</b> Use the \"Theme Maker\" in \"The Pond\" to create and share your own themes!",
      "",
      button_texts=["DELETE", "DOWNLOAD", "SELECT"],
    )
    self._sound_pack_control.set_click_callback(self._on_sound_pack_click)
    self._sound_pack_control.set_value(get_theme_display_name("SoundPack", self._params))

    # Wheel Icon
    self._wheel_icon_control = FrogPilotButtonsControl(
      "Steering Wheel",
      "<b>The steering-wheel icon</b> shown at the top-right of the driving screen. Use the \"Theme Maker\" in \"The Pond\" to create and share your own themes!",
      "",
      button_texts=["DELETE", "DOWNLOAD", "SELECT"],
    )
    self._wheel_icon_control.set_click_callback(self._on_wheel_icon_click)
    self._wheel_icon_control.set_value(get_theme_display_name("WheelIcon", self._params))

    # Download Status Label
    self._download_status_item = ListItem(
      title="Download Status",
      action_item=TextAction(lambda: self._download_status, color=ITEM_TEXT_VALUE_COLOR),
    )

    custom_theme_items = [
      self._color_scheme_control,
      self._distance_icon_control,
      self._icon_pack_control,
      self._signal_animation_control,
      self._sound_pack_control,
      self._wheel_icon_control,
      self._download_status_item,
    ]

    self._toggles["ColorScheme"] = self._color_scheme_control
    self._toggles["DistanceIconPack"] = self._distance_icon_control
    self._toggles["IconPack"] = self._icon_pack_control
    self._toggles["SignalAnimation"] = self._signal_animation_control
    self._toggles["SoundPack"] = self._sound_pack_control
    self._toggles["WheelIcon"] = self._wheel_icon_control
    self._toggles["DownloadStatusLabel"] = self._download_status_item

    self._custom_themes_scroller = Scroller(custom_theme_items, line_separator=True, spacing=0)

  def _simple_toggle(self, param: str, state: bool):
    self._params.put_bool(param, state)
    update_frogpilot_toggles()

  def _on_random_themes_toggle(self, state: bool):
    self._params.put_bool("RandomThemes", state)
    update_frogpilot_toggles()
    self._random_themes = state

    if state:
      gui_app.set_modal_overlay(alert_dialog(
        "\"Random Themes\" only works with downloaded themes, so make sure you download the themes you want it to use!"
      ))

      # Hide SELECT buttons and clear values
      self._color_scheme_control.set_value("")
      self._color_scheme_control.set_visible_button(2, False)
      self._distance_icon_control.set_value("")
      self._distance_icon_control.set_visible_button(2, False)
      self._icon_pack_control.set_value("")
      self._icon_pack_control.set_visible_button(2, False)
      self._signal_animation_control.set_value("")
      self._signal_animation_control.set_visible_button(2, False)
      self._sound_pack_control.set_value("")
      self._sound_pack_control.set_visible_button(2, False)
      self._wheel_icon_control.set_value("")
      self._wheel_icon_control.set_visible_button(2, False)
    else:
      # Show SELECT buttons and restore values
      self._color_scheme_control.set_value(get_theme_display_name("ColorScheme", self._params))
      self._color_scheme_control.set_visible_button(2, True)
      self._distance_icon_control.set_value(get_theme_display_name("DistanceIconPack", self._params))
      self._distance_icon_control.set_visible_button(2, True)
      self._icon_pack_control.set_value(get_theme_display_name("IconPack", self._params))
      self._icon_pack_control.set_visible_button(2, True)
      self._signal_animation_control.set_value(get_theme_display_name("SignalAnimation", self._params))
      self._signal_animation_control.set_visible_button(2, True)
      self._sound_pack_control.set_value(get_theme_display_name("SoundPack", self._params))
      self._sound_pack_control.set_visible_button(2, True)
      self._wheel_icon_control.set_value(get_theme_display_name("WheelIcon", self._params))
      self._wheel_icon_control.set_visible_button(2, True)

  def _update_startup_alert_buttons(self):
    """Update startup alert button states based on current values."""
    current_top = self._params.get("StartupMessageTop", encoding="utf-8") or ""
    current_bottom = self._params.get("StartupMessageBottom", encoding="utf-8") or ""

    stock_top = "Be ready to take over at any time"
    stock_bottom = "Always keep hands on wheel and eyes on road"
    frogpilot_top = "Hop in and buckle up!"
    frogpilot_bottom = "Human-tested, frog-approved 🐸"

    if current_top == stock_top and current_bottom == stock_bottom:
      self._startup_alert_control.set_checked_button(0)
    elif current_top == frogpilot_top and current_bottom == frogpilot_bottom:
      self._startup_alert_control.set_checked_button(1)
    elif current_top or current_bottom:
      self._startup_alert_control.set_checked_button(2)

  def _on_startup_alert_click(self, button_id: int):
    stock_top = "Be ready to take over at any time"
    stock_bottom = "Always keep hands on wheel and eyes on road"
    frogpilot_top = "Hop in and buckle up!"
    frogpilot_bottom = "Human-tested, frog-approved 🐸"

    if button_id == 0:
      # Stock
      self._params.put("StartupMessageTop", stock_top)
      self._params.put("StartupMessageBottom", stock_bottom)
    elif button_id == 1:
      # FrogPilot
      self._params.put("StartupMessageTop", frogpilot_top)
      self._params.put("StartupMessageBottom", frogpilot_bottom)
    elif button_id == 2:
      # Custom - show input dialog for top message
      self._pending_action = "custom_top"
      current_top = self._params.get("StartupMessageTop", encoding="utf-8") or ""
      self._keyboard.reset()
      self._keyboard.set_title("Enter the text for the top half")
      self._keyboard.set_text(current_top)
      gui_app.set_modal_overlay(self._keyboard, callback=self._on_keyboard_result)
    elif button_id == 3:
      # Clear - show confirmation
      self._pending_action = "clear_startup"
      gui_app.set_modal_overlay(ConfirmDialog(
        "Are you sure you want to completely reset your startup message?",
        "Yes",
        "No",
      ))

  def _get_control_for_asset(self, asset_type: str) -> FrogPilotButtonsControl:
    """Get the control widget for an asset type."""
    controls = {
      "ColorScheme": self._color_scheme_control,
      "DistanceIconPack": self._distance_icon_control,
      "IconPack": self._icon_pack_control,
      "SignalAnimation": self._signal_animation_control,
      "SoundPack": self._sound_pack_control,
      "WheelIcon": self._wheel_icon_control,
    }
    return controls.get(asset_type)

  def _get_downloading_attr(self, asset_type: str) -> str:
    """Get the downloading attribute name for an asset type."""
    attrs = {
      "ColorScheme": "_color_downloading",
      "DistanceIconPack": "_distance_icon_downloading",
      "IconPack": "_icon_downloading",
      "SignalAnimation": "_signal_downloading",
      "SoundPack": "_sound_downloading",
      "WheelIcon": "_wheel_downloading",
    }
    return attrs.get(asset_type)

  def _get_downloaded_attr(self, asset_type: str) -> str:
    """Get the downloaded attribute name for an asset type."""
    attrs = {
      "ColorScheme": "_colors_downloaded",
      "DistanceIconPack": "_distance_icons_downloaded",
      "IconPack": "_icons_downloaded",
      "SignalAnimation": "_signals_downloaded",
      "SoundPack": "_sounds_downloaded",
      "WheelIcon": "_wheels_downloaded",
    }
    return attrs.get(asset_type)

  def _handle_asset_click(self, button_id: int, asset_type: str):
    """Generic handler for asset button clicks (DELETE, DOWNLOAD, SELECT)."""
    config = ASSET_CONFIGS[asset_type]
    sub_folder, param_key, downloadable_param, download_key = config

    directory = WHEELS_DIR if asset_type == "WheelIcon" else THEME_PACKS_DIR
    downloading_attr = self._get_downloading_attr(asset_type)

    if button_id == 0:
      # DELETE - show selection dialog
      theme_list = get_theme_list(directory, sub_folder, param_key, self._params)
      if not theme_list:
        gui_app.set_modal_overlay(alert_dialog(f"No {asset_type.lower()} available to delete."))
        return

      self._pending_action = "delete"
      self._pending_asset_type = asset_type
      gui_app.set_modal_overlay(MultiOptionDialog(
        f"Select a {asset_type.lower()} to delete",
        theme_list,
      ))

    elif button_id == 1:
      # DOWNLOAD or CANCEL
      if getattr(self, downloading_attr):
        # Cancel download
        self._cancelling_download = True
        self._params_memory.put_bool("CancelThemeDownload", True)

        def reset_cancel():
          self._cancelling_download = False
          setattr(self, downloading_attr, False)
          self._theme_downloading = False
          self._params_memory.put_bool("CancelThemeDownload", False)

        threading.Timer(2.5, reset_cancel).start()
      else:
        # Start download - show selection dialog
        downloadable_str = self._params.get(downloadable_param, encoding="utf-8") or ""
        downloadable = [d for d in downloadable_str.split(",") if d]

        if not downloadable:
          gui_app.set_modal_overlay(alert_dialog(f"All {asset_type.lower()}s are already downloaded."))
          return

        self._pending_action = "download"
        self._pending_asset_type = asset_type
        gui_app.set_modal_overlay(MultiOptionDialog(
          f"Select a {asset_type.lower()} to download",
          downloadable,
        ))

    elif button_id == 2:
      # SELECT - show selection dialog
      theme_list = get_theme_list(directory, sub_folder, param_key, self._params, exclude_current=False)

      # Add default options
      if asset_type == "SignalAnimation":
        theme_list.append("None")
      elif asset_type == "WheelIcon":
        theme_list.append("None")
        theme_list.append("Stock")
      else:
        theme_list.append("Stock")

      theme_list.extend(HOLIDAY_THEMES)
      theme_list.sort()

      current = get_theme_display_name(param_key, self._params)

      self._pending_action = "select"
      self._pending_asset_type = asset_type
      gui_app.set_modal_overlay(MultiOptionDialog(
        f"Select a {asset_type.lower()}",
        theme_list,
        current,
      ))

  def _on_color_scheme_click(self, button_id: int):
    self._handle_asset_click(button_id, "ColorScheme")

  def _on_distance_icon_click(self, button_id: int):
    self._handle_asset_click(button_id, "DistanceIconPack")

  def _on_icon_pack_click(self, button_id: int):
    self._handle_asset_click(button_id, "IconPack")

  def _on_signal_animation_click(self, button_id: int):
    self._handle_asset_click(button_id, "SignalAnimation")

  def _on_sound_pack_click(self, button_id: int):
    self._handle_asset_click(button_id, "SoundPack")

  def _on_wheel_icon_click(self, button_id: int):
    self._handle_asset_click(button_id, "WheelIcon")

  def _on_keyboard_result(self, result: DialogResult):
    """Callback for keyboard modal overlay."""
    self.handle_dialog_result(result, self._keyboard.text)

  def handle_dialog_result(self, result: DialogResult, selection: str = ""):
    """Handle dialog results for all pending actions."""
    action = self._pending_action
    asset_type = self._pending_asset_type
    self._pending_action = None

    if action == "delete":
      # First dialog - theme selection for delete
      if result != DialogResult.CONFIRM or not selection:
        self._pending_asset_type = None
        return

      # Show confirmation dialog
      self._pending_action = "delete_confirm"
      self._pending_selection = selection
      gui_app.set_modal_overlay(ConfirmDialog(
        f'Delete the "{selection}" {asset_type.lower()}?',
        "Delete",
        "Cancel",
      ))

    elif action == "delete_confirm":
      # Confirmation for delete
      if result != DialogResult.CONFIRM:
        self._pending_asset_type = None
        self._pending_selection = None
        return

      selection = self._pending_selection
      self._pending_selection = None

      config = ASSET_CONFIGS[asset_type]
      sub_folder, param_key, downloadable_param, download_key = config
      directory = WHEELS_DIR if asset_type == "WheelIcon" else THEME_PACKS_DIR

      # Mark as not all downloaded anymore
      downloaded_attr = self._get_downloaded_attr(asset_type)
      setattr(self, downloaded_attr, False)

      # Delete the asset
      delete_theme_asset(directory, sub_folder, downloadable_param, selection, self._params)
      self._pending_asset_type = None

    elif action == "download":
      # Theme selection for download
      if result != DialogResult.CONFIRM or not selection:
        self._pending_asset_type = None
        return

      config = ASSET_CONFIGS[asset_type]
      sub_folder, param_key, downloadable_param, download_key = config

      # Set downloading flags
      downloading_attr = self._get_downloading_attr(asset_type)
      setattr(self, downloading_attr, True)
      self._theme_downloading = True

      self._params_memory.put("ThemeDownloadProgress", "Downloading...")
      self._download_status = "Downloading..."

      # Initiate download
      download_theme_asset(selection, download_key, downloadable_param, self._params, self._params_memory)
      self._pending_asset_type = None

    elif action == "select":
      # Theme selection
      if result != DialogResult.CONFIRM or not selection:
        self._pending_asset_type = None
        return

      config = ASSET_CONFIGS[asset_type]
      sub_folder, param_key, downloadable_param, download_key = config

      # Store the theme and update display
      control = self._get_control_for_asset(asset_type)
      display_name = store_theme_name(selection, param_key, self._params)
      control.set_value(display_name)
      self._pending_asset_type = None

    elif action == "custom_top":
      # Custom startup message - top line
      if result != DialogResult.CONFIRM or not selection:
        return

      self._params.put("StartupMessageTop", selection.strip())

      # Now show dialog for bottom line
      self._pending_action = "custom_bottom"
      current_bottom = self._params.get("StartupMessageBottom", encoding="utf-8") or ""
      self._keyboard.reset()
      self._keyboard.set_title("Enter the text for the bottom half")
      self._keyboard.set_text(current_bottom)
      gui_app.set_modal_overlay(self._keyboard, callback=self._on_keyboard_result)

    elif action == "custom_bottom":
      # Custom startup message - bottom line
      if result == DialogResult.CONFIRM and selection:
        self._params.put("StartupMessageBottom", selection.strip())
      self._update_startup_alert_buttons()

    elif action == "clear_startup":
      # Clear startup message confirmation
      if result == DialogResult.CONFIRM:
        self._params.remove("StartupMessageTop")
        self._params.remove("StartupMessageBottom")
        self._startup_alert_control.clear_checked_buttons()

  def _translate_progress(self, progress: str) -> str:
    """Translate download progress messages."""
    translations = {
      "Download cancelled...": "Download cancelled...",
      "Download failed...": "Download failed...",
      "Downloaded!": "Downloaded!",
      "Downloading...": "Downloading...",
      "GitHub and GitLab are offline...": "GitHub and GitLab are offline...",
      "Repository unavailable": "Repository unavailable",
      "Unpacking theme...": "Unpacking theme...",
      "Verifying authenticity...": "Verifying authenticity...",
    }

    if progress in translations:
      return translations[progress]
    if progress.endswith("%"):
      return progress

    return "Idle"

  def _update_download_state(self):
    """Update UI based on download progress."""
    if self._finalizing_download:
      return

    if not self._theme_downloading:
      return

    progress = self._params_memory.get("ThemeDownloadProgress", encoding="utf-8") or ""
    download_failed = bool(re.search(r"cancelled|exists|failed|offline", progress, re.IGNORECASE))

    if progress and progress != "Downloading...":
      self._download_status = self._translate_progress(progress)

    if progress == "Downloaded!" or download_failed:
      self._finalizing_download = True

      def finalize():
        self._color_downloading = False
        self._distance_icon_downloading = False
        self._finalizing_download = False
        self._icon_downloading = False
        self._signal_downloading = False
        self._sound_downloading = False
        self._theme_downloading = False
        self._wheel_downloading = False

        # Update downloaded states
        self._colors_downloaded = not self._params.get("DownloadableColors", encoding="utf-8")
        self._distance_icons_downloaded = not self._params.get("DownloadableDistanceIcons", encoding="utf-8")
        self._icons_downloaded = not self._params.get("DownloadableIcons", encoding="utf-8")
        self._signals_downloaded = not self._params.get("DownloadableSignals", encoding="utf-8")
        self._sounds_downloaded = not self._params.get("DownloadableSounds", encoding="utf-8")
        self._wheels_downloaded = not self._params.get("DownloadableWheels", encoding="utf-8")

        self._params_memory.remove("CancelThemeDownload")
        self._params_memory.remove("ThemeDownloadProgress")

        self._download_status = "Idle"

      threading.Timer(2.5, finalize).start()

  def _update_button_states(self):
    """Update button enabled/visible states."""
    # Helper for updating each asset control
    def update_asset_buttons(control, downloading, downloaded):
      control.set_text(1, "CANCEL" if downloading else "DOWNLOAD")
      control.set_enabled_buttons(0, not self._theme_downloading)
      can_download = (self._online and
                      (not self._theme_downloading or downloading) and
                      not self._cancelling_download and
                      not self._finalizing_download and
                      not downloaded and
                      self._parked)
      control.set_enabled_buttons(1, can_download)
      control.set_enabled_buttons(2, not self._theme_downloading)

    update_asset_buttons(self._color_scheme_control, self._color_downloading, self._colors_downloaded)
    update_asset_buttons(self._distance_icon_control, self._distance_icon_downloading, self._distance_icons_downloaded)
    update_asset_buttons(self._icon_pack_control, self._icon_downloading, self._icons_downloaded)
    update_asset_buttons(self._signal_animation_control, self._signal_downloading, self._signals_downloaded)
    update_asset_buttons(self._sound_pack_control, self._sound_downloading, self._sounds_downloaded)
    update_asset_buttons(self._wheel_icon_control, self._wheel_downloading, self._wheels_downloaded)

  def _open_custom_themes_panel(self):
    self._current_panel = SubPanel.CUSTOM_THEMES

  def _close_sub_panel(self):
    self._current_panel = SubPanel.MAIN

  def _update_toggles(self):
    self._tuning_level = self._params.get_int("TuningLevel") or 0

    # DistanceIconPack only visible if QOLVisuals AND OnroadDistanceButton
    qol_visuals = self._params.get_bool("QOLVisuals")
    onroad_distance_button = self._params.get_bool("OnroadDistanceButton")
    if hasattr(self._distance_icon_control, "set_visible"):
      self._distance_icon_control.set_visible(qol_visuals and onroad_distance_button)

    # RandomThemes only visible if CustomThemes enabled
    custom_themes = self._params.get_bool("CustomThemes")
    if hasattr(self._random_themes_control, "set_visible"):
      self._random_themes_control.set_visible(custom_themes)

  def _load_downloaded_states(self):
    """Load initial downloaded states."""
    self._colors_downloaded = not self._params.get("DownloadableColors", encoding="utf-8")
    self._distance_icons_downloaded = not self._params.get("DownloadableDistanceIcons", encoding="utf-8")
    self._icons_downloaded = not self._params.get("DownloadableIcons", encoding="utf-8")
    self._signals_downloaded = not self._params.get("DownloadableSignals", encoding="utf-8")
    self._sounds_downloaded = not self._params.get("DownloadableSounds", encoding="utf-8")
    self._wheels_downloaded = not self._params.get("DownloadableWheels", encoding="utf-8")

    self._random_themes = self._params.get_bool("RandomThemes")

    if self._random_themes:
      # Hide SELECT buttons and clear values
      self._color_scheme_control.set_value("")
      self._color_scheme_control.set_visible_button(2, False)
      self._distance_icon_control.set_value("")
      self._distance_icon_control.set_visible_button(2, False)
      self._icon_pack_control.set_value("")
      self._icon_pack_control.set_visible_button(2, False)
      self._signal_animation_control.set_value("")
      self._signal_animation_control.set_visible_button(2, False)
      self._sound_pack_control.set_value("")
      self._sound_pack_control.set_visible_button(2, False)
      self._wheel_icon_control.set_value("")
      self._wheel_icon_control.set_visible_button(2, False)

  def show_event(self):
    super().show_event()
    self._main_scroller.show_event()
    self._load_downloaded_states()
    self._update_toggles()
    self._update_startup_alert_buttons()
    self._started = ui_state.started

  def hide_event(self):
    super().hide_event()
    self._current_panel = SubPanel.MAIN

  def _render(self, rect):
    self._started = ui_state.started
    self._parked = not self._started

    # Update download state
    self._update_download_state()
    self._update_button_states()

    if self._current_panel == SubPanel.CUSTOM_THEMES:
      self._custom_themes_scroller.render(rect)
    else:
      self._main_scroller.render(rect)
