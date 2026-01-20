import shutil
import threading
import time

from datetime import datetime
from enum import IntEnum
from pathlib import Path

from openpilot.common.params import Params
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.confirm_dialog import ConfirmDialog, alert_dialog, DialogResult
from openpilot.system.ui.widgets.list_view import ListItem, ToggleAction, ButtonAction, TextAction, ITEM_TEXT_VALUE_COLOR
from openpilot.system.ui.widgets.option_dialog import MultiOptionDialog
from openpilot.system.ui.widgets.scroller_tici import Scroller

from openpilot.frogpilot.common.frogpilot_variables import update_frogpilot_toggles
from openpilot.frogpilot.system.ui.widgets.frogpilot_controls import (
  FrogPilotButtonsControl,
)

MAPS_FOLDER_PATH = Path("/data/media/0/osm/offline")

# US State maps by region
MIDWEST_MAP = {
  "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
  "KS": "Kansas", "MI": "Michigan", "MN": "Minnesota",
  "MO": "Missouri", "NE": "Nebraska", "ND": "North Dakota",
  "OH": "Ohio", "SD": "South Dakota", "WI": "Wisconsin"
}

NORTHEAST_MAP = {
  "CT": "Connecticut", "ME": "Maine", "MA": "Massachusetts",
  "NH": "New Hampshire", "NJ": "New Jersey", "NY": "New York",
  "PA": "Pennsylvania", "RI": "Rhode Island", "VT": "Vermont"
}

SOUTH_MAP = {
  "AL": "Alabama", "AR": "Arkansas", "DE": "Delaware",
  "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
  "KY": "Kentucky", "LA": "Louisiana", "MD": "Maryland",
  "MS": "Mississippi", "NC": "North Carolina", "OK": "Oklahoma",
  "SC": "South Carolina", "TN": "Tennessee", "TX": "Texas",
  "VA": "Virginia", "WV": "West Virginia"
}

WEST_MAP = {
  "AK": "Alaska", "AZ": "Arizona", "CA": "California",
  "CO": "Colorado", "HI": "Hawaii", "ID": "Idaho",
  "MT": "Montana", "NV": "Nevada", "NM": "New Mexico",
  "OR": "Oregon", "UT": "Utah", "WA": "Washington",
  "WY": "Wyoming"
}

TERRITORIES_MAP = {
  "AS": "American Samoa", "GU": "Guam", "MP": "Northern Mariana Islands",
  "PR": "Puerto Rico", "VI": "Virgin Islands"
}

# World country maps by continent
AFRICA_MAP = {
  "DZ": "Algeria", "AO": "Angola", "BJ": "Benin",
  "BW": "Botswana", "BF": "Burkina Faso", "BI": "Burundi",
  "CM": "Cameroon", "CF": "Central African Republic", "TD": "Chad",
  "KM": "Comoros", "CG": "Congo (Brazzaville)", "CD": "Congo (Kinshasa)",
  "DJ": "Djibouti", "EG": "Egypt", "GQ": "Equatorial Guinea",
  "ER": "Eritrea", "ET": "Ethiopia", "GA": "Gabon",
  "GM": "Gambia", "GH": "Ghana", "GN": "Guinea",
  "GW": "Guinea-Bissau", "CI": "Ivory Coast", "KE": "Kenya",
  "LS": "Lesotho", "LR": "Liberia", "LY": "Libya",
  "MG": "Madagascar", "MW": "Malawi", "ML": "Mali",
  "MR": "Mauritania", "MA": "Morocco", "MZ": "Mozambique",
  "NA": "Namibia", "NE": "Niger", "NG": "Nigeria",
  "RW": "Rwanda", "SN": "Senegal", "SL": "Sierra Leone",
  "SO": "Somalia", "ZA": "South Africa", "SS": "South Sudan",
  "SD": "Sudan", "SZ": "Swaziland", "TZ": "Tanzania",
  "TG": "Togo", "TN": "Tunisia", "UG": "Uganda",
  "ZM": "Zambia", "ZW": "Zimbabwe"
}

ANTARCTICA_MAP = {"AQ": "Antarctica"}

ASIA_MAP = {
  "AF": "Afghanistan", "AM": "Armenia", "AZ": "Azerbaijan",
  "BH": "Bahrain", "BD": "Bangladesh", "BT": "Bhutan",
  "BN": "Brunei", "KH": "Cambodia", "CN": "China",
  "CY": "Cyprus", "TL": "East Timor", "HK": "Hong Kong",
  "IN": "India", "ID": "Indonesia", "IR": "Iran",
  "IQ": "Iraq", "IL": "Israel", "JP": "Japan",
  "JO": "Jordan", "KZ": "Kazakhstan", "KW": "Kuwait",
  "KG": "Kyrgyzstan", "LA": "Laos", "LB": "Lebanon",
  "MY": "Malaysia", "MV": "Maldives", "MO": "Macao",
  "MN": "Mongolia", "MM": "Myanmar", "NP": "Nepal",
  "KP": "North Korea", "OM": "Oman", "PK": "Pakistan",
  "PS": "Palestine", "PH": "Philippines", "QA": "Qatar",
  "RU": "Russia", "SA": "Saudi Arabia", "SG": "Singapore",
  "KR": "South Korea", "LK": "Sri Lanka", "SY": "Syria",
  "TW": "Taiwan", "TJ": "Tajikistan", "TH": "Thailand",
  "TR": "Turkey", "TM": "Turkmenistan", "AE": "United Arab Emirates",
  "UZ": "Uzbekistan", "VN": "Vietnam", "YE": "Yemen"
}

EUROPE_MAP = {
  "AL": "Albania", "AT": "Austria", "BY": "Belarus",
  "BE": "Belgium", "BA": "Bosnia and Herzegovina", "BG": "Bulgaria",
  "HR": "Croatia", "CZ": "Czech Republic", "DK": "Denmark",
  "EE": "Estonia", "FI": "Finland", "FR": "France",
  "GE": "Georgia", "DE": "Germany", "GR": "Greece",
  "HU": "Hungary", "IS": "Iceland", "IE": "Ireland",
  "IT": "Italy", "KZ": "Kazakhstan", "LV": "Latvia",
  "LT": "Lithuania", "LU": "Luxembourg", "MK": "Macedonia",
  "MD": "Moldova", "ME": "Montenegro", "NL": "Netherlands",
  "NO": "Norway", "PL": "Poland", "PT": "Portugal",
  "RO": "Romania", "RS": "Serbia", "SK": "Slovakia",
  "SI": "Slovenia", "ES": "Spain", "SE": "Sweden",
  "CH": "Switzerland", "TR": "Turkey", "UA": "Ukraine",
  "GB": "United Kingdom"
}

NORTH_AMERICA_MAP = {
  "BS": "Bahamas", "BZ": "Belize", "CA": "Canada",
  "CR": "Costa Rica", "CU": "Cuba", "DO": "Dominican Republic",
  "SV": "El Salvador", "GL": "Greenland", "GD": "Grenada",
  "GT": "Guatemala", "HT": "Haiti", "HN": "Honduras",
  "JM": "Jamaica", "MX": "Mexico", "NI": "Nicaragua",
  "PA": "Panama", "TT": "Trinidad and Tobago", "US": "United States"
}

OCEANIA_MAP = {
  "AU": "Australia", "FJ": "Fiji", "TF": "French Southern Territories",
  "NC": "New Caledonia", "NZ": "New Zealand", "PG": "Papua New Guinea",
  "SB": "Solomon Islands", "VU": "Vanuatu"
}

SOUTH_AMERICA_MAP = {
  "AR": "Argentina", "BO": "Bolivia", "BR": "Brazil",
  "CL": "Chile", "CO": "Colombia", "EC": "Ecuador",
  "FK": "Falkland Islands", "GY": "Guyana", "PY": "Paraguay",
  "PE": "Peru", "SR": "Suriname", "UY": "Uruguay",
  "VE": "Venezuela"
}

SCHEDULE_OPTIONS = ["Manually", "Weekly", "Monthly"]


class SubPanel(IntEnum):
  MAIN = 0
  COUNTRIES = 1
  STATES = 2


def calculate_directory_size(directory: Path) -> str:
  """Calculate directory size and return formatted string."""
  MB = 1024.0 * 1024.0
  GB = 1024.0 * MB

  if not directory.exists():
    return "0 MB"

  total_size = 0
  for file in directory.rglob("*"):
    if file.is_file():
      total_size += file.stat().st_size

  if total_size >= GB:
    return f"{total_size / GB:.2f} GB"
  return f"{total_size / MB:.2f} MB"


def day_suffix(day: int) -> str:
  """Get ordinal suffix for day."""
  if day % 10 == 1 and day != 11:
    return "st"
  if day % 10 == 2 and day != 12:
    return "nd"
  if day % 10 == 3 and day != 13:
    return "rd"
  return "th"


def format_current_date() -> str:
  """Format current date as 'Month Day(suffix), Year'."""
  now = datetime.now()
  return now.strftime(f"%B {now.day}{day_suffix(now.day)}, %Y")


def format_elapsed_time(elapsed_ms: float) -> str:
  """Format elapsed time in milliseconds to readable string."""
  total_seconds = int(elapsed_ms / 1000)
  hours = total_seconds // 3600
  minutes = (total_seconds % 3600) // 60
  seconds = total_seconds % 60

  parts = []
  if hours > 0:
    parts.append(f"{hours} {'hour' if hours == 1 else 'hours'}")
  if minutes > 0:
    parts.append(f"{minutes} {'minute' if minutes == 1 else 'minutes'}")
  parts.append(f"{seconds} {'second' if seconds == 1 else 'seconds'}")

  return " ".join(parts)


class FrogPilotMapsPanel(Widget):
  def __init__(self):
    super().__init__()

    self._current_panel = SubPanel.MAIN
    self._params = Params()
    self._params_memory = Params("", True)
    self._toggles = {}

    # State tracking
    self._cancelling_download = False
    self._has_maps_selected = False
    self._online = False
    self._parked = True
    self._started = False

    # Download tracking
    self._download_start_time = None
    self._elapsed_time_ms = 0

    # Pending dialog action tracking
    self._pending_action = None
    self._pending_data = {}

    self._build_panel()

    ui_state.add_offroad_transition_callback(self._update_toggles)

  def _build_panel(self):
    # Preferred Schedule - ButtonControl for schedule options
    self._preferred_schedule_control = FrogPilotButtonsControl(
      "Automatically Update Maps",
      "<b>How often maps update</b> from \"OpenStreetMap (OSM)\" with the latest speed limit information. Weekly updates run every Sunday; monthly updates run on the 1st.",
      "",
      button_texts=SCHEDULE_OPTIONS,
    )
    self._preferred_schedule_control.set_click_callback(self._on_preferred_schedule_click)
    self._update_schedule_button()

    # Download Maps Button
    self._download_maps_control = FrogPilotButtonsControl(
      "Download Maps",
      "<b>Manually update your selected map sources</b> so \"Speed Limit Controller\" has the latest speed limit information.",
      "",
      button_texts=["DOWNLOAD"],
    )
    self._download_maps_control.set_click_callback(self._on_download_maps_click)

    # Last Updated Label
    last_update = self._params.get("LastMapsUpdate", encoding="utf-8") or "Never"
    self._last_updated_item = ListItem(
      title="Last Updated",
      action_item=TextAction(lambda: self._params.get("LastMapsUpdate", encoding="utf-8") or "Never", color=ITEM_TEXT_VALUE_COLOR),
    )

    # Select Maps - Countries/States
    self._select_maps_control = FrogPilotButtonsControl(
      "Map Sources",
      "<b>Select the countries or U.S. states to use with \"Speed Limit Controller\".</b>",
      "",
      button_texts=["COUNTRIES", "STATES"],
    )
    self._select_maps_control.set_click_callback(self._on_select_maps_click)

    # Progress labels
    self._download_status_item = ListItem(
      title="Progress",
      action_item=TextAction(lambda: self._get_download_status(), color=ITEM_TEXT_VALUE_COLOR),
    )
    self._download_time_elapsed_item = ListItem(
      title="Time Elapsed",
      action_item=TextAction(lambda: self._get_time_elapsed(), color=ITEM_TEXT_VALUE_COLOR),
    )
    self._download_eta_item = ListItem(
      title="Time Remaining",
      action_item=TextAction(lambda: self._get_download_eta(), color=ITEM_TEXT_VALUE_COLOR),
    )

    # Remove Maps Button
    self._remove_maps_control = FrogPilotButtonsControl(
      "Remove Maps",
      "<b>Delete downloaded map data</b> to free up storage space.",
      "",
      button_texts=["REMOVE"],
    )
    self._remove_maps_control.set_click_callback(self._on_remove_maps_click)

    # Storage Used Label
    self._maps_size_item = ListItem(
      title="Storage Used",
      action_item=TextAction(lambda: calculate_directory_size(MAPS_FOLDER_PATH), color=ITEM_TEXT_VALUE_COLOR),
    )

    main_items = [
      self._preferred_schedule_control,
      self._download_maps_control,
      self._last_updated_item,
      self._select_maps_control,
      self._download_status_item,
      self._download_time_elapsed_item,
      self._download_eta_item,
      self._remove_maps_control,
      self._maps_size_item,
    ]

    # Initially hide download progress items
    if hasattr(self._download_status_item, "set_visible"):
      self._download_status_item.set_visible(False)
      self._download_time_elapsed_item.set_visible(False)
      self._download_eta_item.set_visible(False)

    self._toggles["PreferredSchedule"] = self._preferred_schedule_control
    self._toggles["DownloadMaps"] = self._download_maps_control
    self._toggles["LastUpdated"] = self._last_updated_item
    self._toggles["SelectMaps"] = self._select_maps_control
    self._toggles["DownloadStatus"] = self._download_status_item
    self._toggles["DownloadTimeElapsed"] = self._download_time_elapsed_item
    self._toggles["DownloadETA"] = self._download_eta_item
    self._toggles["RemoveMaps"] = self._remove_maps_control
    self._toggles["MapsSize"] = self._maps_size_item

    self._main_scroller = Scroller(main_items, line_separator=True, spacing=0)

  def _get_download_status(self) -> str:
    """Get current download status."""
    return "Calculating..."

  def _get_time_elapsed(self) -> str:
    """Get formatted elapsed time."""
    if self._elapsed_time_ms > 0:
      return format_elapsed_time(self._elapsed_time_ms)
    return "Calculating..."

  def _get_download_eta(self) -> str:
    """Get estimated time remaining."""
    return "Calculating..."

  def _update_schedule_button(self):
    """Update schedule button to show current selection."""
    schedule_index = self._params.get_int("PreferredSchedule") or 0
    self._preferred_schedule_control.set_checked_button(schedule_index)

  def _on_preferred_schedule_click(self, button_id: int):
    self._params.put_int("PreferredSchedule", button_id)
    update_frogpilot_toggles()

  def _on_download_maps_click(self, button_id: int):
    # Check if we're cancelling
    if self._params_memory.get_bool("DownloadMaps"):
      self._pending_action = "cancel_download"
      gui_app.set_modal_overlay(ConfirmDialog(
        "Cancel the download?",
        "Yes",
        "No",
      ))
    else:
      self._start_download()

  def _start_download(self):
    """Start the map download."""
    self._download_start_time = datetime.now()
    self._elapsed_time_ms = 0

    # Show progress items
    if hasattr(self._download_status_item, "set_visible"):
      self._download_status_item.set_visible(True)
      self._download_time_elapsed_item.set_visible(True)
      self._download_eta_item.set_visible(True)

    # Hide last updated and remove button
    if hasattr(self._last_updated_item, "set_visible"):
      self._last_updated_item.set_visible(False)
    if hasattr(self._remove_maps_control, "set_visible"):
      self._remove_maps_control.set_visible(False)

    # Change button text to CANCEL
    self._download_maps_control.set_text(0, "CANCEL")

    # Trigger download
    self._params_memory.put_bool("DownloadMaps", True)

  def _cancel_download(self):
    """Cancel the current download."""
    self._cancelling_download = True
    self._download_maps_control.set_enabled(False)

    self._params_memory.put_bool("CancelDownloadMaps", True)
    self._params_memory.remove("DownloadMaps")

    def reset():
      self._cancelling_download = False
      self._download_maps_control.set_enabled(True)
      self._download_maps_control.set_text(0, "DOWNLOAD")

      if hasattr(self._download_status_item, "set_visible"):
        self._download_status_item.set_visible(False)
        self._download_time_elapsed_item.set_visible(False)
        self._download_eta_item.set_visible(False)

      if hasattr(self._last_updated_item, "set_visible"):
        self._last_updated_item.set_visible(True)
      if hasattr(self._remove_maps_control, "set_visible"):
        self._remove_maps_control.set_visible(MAPS_FOLDER_PATH.exists())

    threading.Timer(2.5, reset).start()

  def _on_select_maps_click(self, button_id: int):
    if button_id == 0:
      self._current_panel = SubPanel.COUNTRIES
    else:
      self._current_panel = SubPanel.STATES

  def _on_remove_maps_click(self, button_id: int):
    self._pending_action = "remove_maps"
    gui_app.set_modal_overlay(ConfirmDialog(
      "Delete all downloaded maps?",
      "Delete",
      "Cancel",
    ))

  def handle_dialog_result(self, result: DialogResult, selection: str = ""):
    """Handle dialog results for pending actions."""
    action = self._pending_action
    self._pending_action = None

    if action == "cancel_download":
      if result == DialogResult.CONFIRM:
        self._cancel_download()

    elif action == "remove_maps":
      if result == DialogResult.CONFIRM:
        def remove_thread():
          if MAPS_FOLDER_PATH.exists():
            shutil.rmtree(MAPS_FOLDER_PATH, ignore_errors=True)
        threading.Thread(target=remove_thread, daemon=True).start()

  def _update_toggles(self):
    self._has_maps_selected = bool(self._params.get("MapsSelected", encoding="utf-8"))

    # Remove maps button only visible if maps folder exists
    if hasattr(self._remove_maps_control, "set_visible"):
      self._remove_maps_control.set_visible(MAPS_FOLDER_PATH.exists())

  def _close_sub_panel(self):
    self._current_panel = SubPanel.MAIN
    self._has_maps_selected = bool(self._params.get("MapsSelected", encoding="utf-8"))

  def show_event(self):
    super().show_event()
    self._main_scroller.show_event()
    self._update_toggles()
    self._update_schedule_button()
    self._started = ui_state.started

  def hide_event(self):
    super().hide_event()
    self._current_panel = SubPanel.MAIN

  def _render(self, rect):
    self._started = ui_state.started
    self._parked = not self._started

    # Update download button enabled state
    download_active = self._params_memory.get_bool("DownloadMaps")
    self._download_maps_control.set_enabled(
      not self._cancelling_download and self._has_maps_selected and self._online and self._parked
    )

    if self._current_panel == SubPanel.COUNTRIES:
      # Would render countries selection panel
      self._main_scroller.render(rect)
    elif self._current_panel == SubPanel.STATES:
      # Would render states selection panel
      self._main_scroller.render(rect)
    else:
      self._main_scroller.render(rect)
