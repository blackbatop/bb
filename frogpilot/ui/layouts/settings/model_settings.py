import json
import threading

from enum import IntEnum
from pathlib import Path

from openpilot.common.params import Params
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.hardware import HARDWARE
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets import Widget, DialogResult
from openpilot.system.ui.widgets.confirm_dialog import ConfirmDialog, alert_dialog
from openpilot.system.ui.widgets.list_view import ListItem, ToggleAction, TextAction, ITEM_TEXT_VALUE_COLOR
from openpilot.system.ui.widgets.option_dialog import MultiOptionDialog
from openpilot.system.ui.widgets.scroller_tici import Scroller

from openpilot.frogpilot.common.frogpilot_utilities import clean_model_name
from openpilot.frogpilot.common.frogpilot_variables import update_frogpilot_toggles
from openpilot.frogpilot.system.ui.widgets.frogpilot_controls import (
  FrogPilotButtonsControl,
  FrogPilotConfirmationDialog,
)

MODEL_DIR = Path("/data/models/")

TINYGRAD_SUFFIXES = [
  "_driving_policy_metadata.pkl",
  "_driving_policy_tinygrad.pkl",
  "_driving_vision_metadata.pkl",
  "_driving_vision_tinygrad.pkl",
]


class SubPanel(IntEnum):
  MAIN = 0
  MODEL_LABELS = 1


def has_all_tinygrad_files(model_key: str) -> bool:
  """Check if a model has all required tinygrad files."""
  for suffix in TINYGRAD_SUFFIXES:
    if not (MODEL_DIR / f"{model_key}{suffix}").exists():
      return False
  return True


class FrogPilotModelPanel(Widget):
  def __init__(self):
    super().__init__()

    self._current_panel = SubPanel.MAIN
    self._params = Params()
    self._params_memory = Params("", True)
    self._toggles = {}
    self._tuning_level = 0

    # State tracking
    self._all_models_downloaded = False
    self._all_models_downloading = False
    self._cancelling_download = False
    self._current_model = ""
    self._default_model = ""
    self._finalizing_download = False
    self._model_downloading = False
    self._no_models_downloaded = False
    self._online = False
    self._parked = True
    self._started = False
    self._tinygrad_update = False
    self._updating_tinygrad = False

    # Model mappings
    self._available_model_names: list[str] = []
    self._model_file_to_name: dict[str, str] = {}
    self._model_file_to_name_processed: dict[str, str] = {}

    # Get default model
    default_model_bytes = self._params.get_key_default_value("DrivingModel")
    self._default_model = default_model_bytes.decode() if default_model_bytes else ""

    self._build_main_panel()
    self._build_model_labels_panel()

    ui_state.add_offroad_transition_callback(self._update_toggles)

  def _build_main_panel(self):
    self._auto_download_item = ListItem(
      title="Automatically Download New Models",
      description="<b>Automatically download new driving models</b> as they become available.",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("AutomaticallyDownloadModels"),
        callback=lambda state: self._simple_toggle("AutomaticallyDownloadModels", state),
      ),
    )

    self._delete_model_control = FrogPilotButtonsControl(
      "Delete Driving Models",
      "<b>Delete downloaded driving models</b> to free up storage space.",
      "",
      button_texts=["DELETE", "DELETE ALL"],
    )
    self._delete_model_control.set_click_callback(self._on_delete_model_click)

    self._download_model_control = FrogPilotButtonsControl(
      "Download Driving Models",
      "<b>Manually download driving models</b> to the device.",
      "",
      button_texts=["DOWNLOAD", "DOWNLOAD ALL"],
    )
    self._download_model_control.set_click_callback(self._on_download_model_click)

    self._model_randomizer_item = ListItem(
      title="Model Randomizer",
      description="<b>Select a random driving model each drive</b> and use feedback prompts at the end of the drive to help find the model that best suits you!",
      action_item=ToggleAction(
        initial_state=self._params.get_bool("ModelRandomizer"),
        callback=self._on_model_randomizer_toggle,
      ),
    )

    self._manage_blacklist_control = FrogPilotButtonsControl(
      "Manage Model Blacklist",
      "<b>Add or remove driving models from the \"Model Randomizer\" blacklist.</b>",
      "",
      button_texts=["ADD", "REMOVE", "REMOVE ALL"],
    )
    self._manage_blacklist_control.set_click_callback(self._on_manage_blacklist_click)

    self._manage_scores_control = FrogPilotButtonsControl(
      "Manage Model Ratings",
      "<b>View or reset saved model ratings</b> used by the \"Model Randomizer\".",
      "",
      button_texts=["RESET", "VIEW"],
    )
    self._manage_scores_control.set_click_callback(self._on_manage_scores_click)

    self._select_model_item = ListItem(
      title="Select Driving Model",
      description="<b>Choose which driving model openpilot uses.</b>",
      action_item=TextAction(lambda: self._get_current_model_display(), color=ITEM_TEXT_VALUE_COLOR),
      callback=self._on_select_model_click,
    )

    self._update_tinygrad_control = FrogPilotButtonsControl(
      "Update Model Manager",
      "<b>Update the \"Model Manager\"</b> to support the latest models.",
      "",
      button_texts=["UPDATE"],
    )
    self._update_tinygrad_control.set_click_callback(self._on_update_tinygrad_click)

    main_items = [
      self._auto_download_item,
      self._delete_model_control,
      self._download_model_control,
      self._model_randomizer_item,
      self._manage_blacklist_control,
      self._manage_scores_control,
      self._select_model_item,
      self._update_tinygrad_control,
    ]

    self._toggles["AutomaticallyDownloadModels"] = self._auto_download_item
    self._toggles["DeleteModel"] = self._delete_model_control
    self._toggles["DownloadModel"] = self._download_model_control
    self._toggles["ModelRandomizer"] = self._model_randomizer_item
    self._toggles["ManageBlacklistedModels"] = self._manage_blacklist_control
    self._toggles["ManageScores"] = self._manage_scores_control
    self._toggles["SelectModel"] = self._select_model_item
    self._toggles["UpdateTinygrad"] = self._update_tinygrad_control

    self._main_scroller = Scroller(main_items, line_separator=True, spacing=0)

  def _build_model_labels_panel(self):
    self._model_labels_items: list[ListItem] = []
    self._model_labels_scroller = Scroller(self._model_labels_items, line_separator=True, spacing=0)

  def _get_current_model_display(self) -> str:
    """Get the display string for the current model."""
    display = self._current_model
    model_key = clean_model_name(self._params.get("DrivingModel", encoding="utf-8") or "")
    if model_key == self._default_model:
      display += " (Default)"
    return display

  def _simple_toggle(self, param: str, state: bool):
    self._params.put_bool(param, state)
    update_frogpilot_toggles()

  def _on_model_randomizer_toggle(self, state: bool):
    self._params.put_bool("ModelRandomizer", state)
    update_frogpilot_toggles()
    self._update_toggles()

    if state and not self._all_models_downloaded:
      gui_app.set_modal_overlay(ConfirmDialog(
        "The \"Model Randomizer\" works only with downloaded models. Download all models now?",
        "Yes",
        "No",
      ))

  def _on_delete_model_click(self, button_id: int):
    deletable_models = self._get_deletable_models()

    if not deletable_models:
      gui_app.set_modal_overlay(alert_dialog("No models available to delete."))
      return

    if button_id == 0:
      # Delete single model
      gui_app.set_modal_overlay(MultiOptionDialog(
        "Select a driving model to delete",
        deletable_models,
      ))
    elif button_id == 1:
      # Delete all models
      gui_app.set_modal_overlay(ConfirmDialog(
        "Are you sure you want to delete all of your downloaded driving models?",
        "Delete",
        "Cancel",
      ))

  def _get_deletable_models(self) -> list[str]:
    """Get list of models that can be deleted (excludes current and default)."""
    deletable = []

    if not MODEL_DIR.exists():
      return deletable

    for file in MODEL_DIR.iterdir():
      if not file.is_file():
        continue

      base = file.stem
      for model_key in self._model_file_to_name_processed:
        if base.startswith(model_key):
          model_name = self._model_file_to_name_processed[model_key]
          if model_name not in deletable:
            deletable.append(model_name)
          break

    # Remove current model and default model from deletable list
    current_clean = clean_model_name(self._current_model)
    if current_clean in deletable:
      deletable.remove(current_clean)

    default_name = self._model_file_to_name_processed.get(clean_model_name(self._default_model), "")
    if default_name in deletable:
      deletable.remove(default_name)

    deletable.sort()
    return deletable

  def _delete_model(self, model_name: str):
    """Delete a specific model's files."""
    model_file = None
    for key, name in self._model_file_to_name_processed.items():
      if name == model_name:
        model_file = key
        break

    if not model_file or not MODEL_DIR.exists():
      return

    for file in MODEL_DIR.iterdir():
      if file.is_file() and file.stem.startswith(model_file):
        file.unlink()

    self._all_models_downloaded = False
    self._update_deletable_state()

  def _delete_all_models(self):
    """Delete all deletable models."""
    deletable = self._get_deletable_models()

    if not MODEL_DIR.exists():
      return

    for file in MODEL_DIR.iterdir():
      if not file.is_file():
        continue

      base = file.stem
      for model_key in self._model_file_to_name_processed:
        model_name = self._model_file_to_name_processed[model_key]
        if model_name in deletable and base.startswith(model_key):
          file.unlink()
          break

    self._all_models_downloaded = False
    self._no_models_downloaded = True
    self._update_deletable_state()

  def _update_deletable_state(self):
    """Update the enabled state of delete buttons."""
    deletable = self._get_deletable_models()
    self._no_models_downloaded = len(deletable) == 0
    can_delete = not (self._all_models_downloading or self._model_downloading or self._no_models_downloaded)
    self._delete_model_control.set_enabled(can_delete)

  def _on_download_model_click(self, button_id: int):
    if self._tinygrad_update:
      gui_app.set_modal_overlay(ConfirmDialog(
        "Tinygrad is out of date and must be updated before you can download new models. Update now?",
        "Yes",
        "No",
      ))
      return

    if button_id == 0:
      # Download single model or cancel
      if self._model_downloading:
        self._params_memory.put_bool("CancelModelDownload", True)
        self._cancelling_download = True
      else:
        downloadable = self._get_downloadable_models()
        if not downloadable:
          gui_app.set_modal_overlay(alert_dialog("All models are already downloaded."))
          return

        gui_app.set_modal_overlay(MultiOptionDialog(
          "Select a driving model to download",
          downloadable,
        ))
    elif button_id == 1:
      # Download all or cancel
      if self._all_models_downloading:
        self._params_memory.put_bool("CancelModelDownload", True)
        self._cancelling_download = True
      else:
        self._params_memory.put_bool("DownloadAllModels", True)
        self._params_memory.put("ModelDownloadProgress", "Downloading...")
        self._download_model_control.set_text(1, "CANCEL")
        self._download_model_control.set_visible_button(0, False)
        self._all_models_downloading = True

  def _get_downloadable_models(self) -> list[str]:
    """Get list of models that can be downloaded."""
    downloadable = list(self._available_model_names)

    for model_key in self._model_file_to_name:
      model_name = self._model_file_to_name[model_key]
      if has_all_tinygrad_files(model_key):
        if model_name in downloadable:
          downloadable.remove(model_name)

    downloadable.sort()
    return downloadable

  def _start_model_download(self, model_name: str):
    """Start downloading a specific model."""
    model_key = None
    for key, name in self._model_file_to_name.items():
      if name == model_name:
        model_key = key
        break

    if model_key:
      self._params_memory.put("ModelToDownload", model_key)
      self._params_memory.put("ModelDownloadProgress", "Downloading...")
      self._download_model_control.set_text(0, "CANCEL")
      self._download_model_control.set_visible_button(1, False)
      self._model_downloading = True

  def _on_manage_blacklist_click(self, button_id: int):
    blacklisted_str = self._params.get("BlacklistedModels", encoding="utf-8") or ""
    blacklisted = [m for m in blacklisted_str.split(",") if m]

    if button_id == 0:
      # Add to blacklist
      blacklistable = []
      for model_key in self._model_file_to_name_processed:
        if model_key not in blacklisted:
          blacklistable.append(self._model_file_to_name_processed[model_key])

      if len(blacklistable) <= 1:
        remaining = blacklistable[0] if blacklistable else "None"
        gui_app.set_modal_overlay(alert_dialog(
          f"There are no more driving models to blacklist. The only available model is \"{remaining}\"!"
        ))
        return

      blacklistable.sort()
      gui_app.set_modal_overlay(MultiOptionDialog(
        "Select a driving model to add to the blacklist",
        blacklistable,
      ))

    elif button_id == 1:
      # Remove from blacklist
      whitelistable = []
      for model_key in blacklisted:
        model_name = self._model_file_to_name_processed.get(model_key, "")
        if model_name:
          whitelistable.append(model_name)

      if not whitelistable:
        gui_app.set_modal_overlay(alert_dialog("No models are currently blacklisted."))
        return

      whitelistable.sort()
      gui_app.set_modal_overlay(MultiOptionDialog(
        "Select a driving model to remove from the blacklist",
        whitelistable,
      ))

    elif button_id == 2:
      # Remove all from blacklist
      if not blacklisted:
        gui_app.set_modal_overlay(alert_dialog("No models are currently blacklisted."))
        return

      gui_app.set_modal_overlay(ConfirmDialog(
        "Are you sure you want to remove all of your blacklisted driving models?",
        "Yes",
        "No",
      ))

  def _add_to_blacklist(self, model_name: str):
    """Add a model to the blacklist."""
    model_key = None
    for key, name in self._model_file_to_name_processed.items():
      if name == model_name:
        model_key = key
        break

    if model_key:
      blacklisted_str = self._params.get("BlacklistedModels", encoding="utf-8") or ""
      blacklisted = [m for m in blacklisted_str.split(",") if m]
      if model_key not in blacklisted:
        blacklisted.append(model_key)
        self._params.put("BlacklistedModels", ",".join(blacklisted))

  def _remove_from_blacklist(self, model_name: str):
    """Remove a model from the blacklist."""
    model_key = None
    for key, name in self._model_file_to_name_processed.items():
      if name == model_name:
        model_key = key
        break

    if model_key:
      blacklisted_str = self._params.get("BlacklistedModels", encoding="utf-8") or ""
      blacklisted = [m for m in blacklisted_str.split(",") if m]
      if model_key in blacklisted:
        blacklisted.remove(model_key)
        self._params.put("BlacklistedModels", ",".join(blacklisted))

  def _clear_blacklist(self):
    """Clear all models from blacklist."""
    self._params.remove("BlacklistedModels")

  def _on_manage_scores_click(self, button_id: int):
    if button_id == 0:
      # Reset scores
      gui_app.set_modal_overlay(ConfirmDialog(
        "Reset all model drives and ratings? This clears your drive history and collected feedback!",
        "Yes",
        "No",
      ))
    elif button_id == 1:
      # View scores
      self._update_model_labels()
      self._current_panel = SubPanel.MODEL_LABELS

  def _reset_model_scores(self):
    """Reset all model drives and scores."""
    self._params.remove("ModelDrivesAndScores")

  def _update_model_labels(self):
    """Update the model labels panel with current ratings."""
    self._model_labels_items.clear()

    scores_str = self._params.get("ModelDrivesAndScores", encoding="utf-8") or "{}"
    try:
      model_drives_and_scores = json.loads(scores_str)
    except json.JSONDecodeError:
      model_drives_and_scores = {}

    for model_name in sorted(self._available_model_names):
      clean_name = clean_model_name(model_name)
      model_data = model_drives_and_scores.get(clean_name, {})

      drives = model_data.get("Drives", 0)
      score = model_data.get("Score", 0)

      if drives == 1:
        drives_display = f"{drives} Drive"
      elif drives > 0:
        drives_display = f"{drives} Drives"
      else:
        drives_display = "N/A"

      if drives > 0:
        score_display = f"Score: {score}%"
      else:
        score_display = "N/A"

      label_text = f"{score_display} ({drives_display})"

      item = ListItem(
        title=clean_name,
        action_item=TextAction(label_text, color=ITEM_TEXT_VALUE_COLOR),
      )
      self._model_labels_items.append(item)

    self._model_labels_scroller = Scroller(self._model_labels_items, line_separator=True, spacing=0)

  def _on_select_model_click(self):
    selectable = []

    for model_key in self._model_file_to_name:
      if model_key != clean_model_name(self._default_model) and has_all_tinygrad_files(model_key):
        selectable.append(self._model_file_to_name[model_key])

    selectable.sort()

    # Add default model at the beginning
    default_name = self._model_file_to_name.get(clean_model_name(self._default_model), "")
    if default_name:
      selectable.insert(0, f"{default_name} (Default)")

    current_display = self._current_model
    model_key = clean_model_name(self._params.get("DrivingModel", encoding="utf-8") or "")
    if model_key == self._default_model:
      current_display += " (Default)"

    gui_app.set_modal_overlay(MultiOptionDialog(
      "Select a Model",
      selectable,
      current_display,
    ))

  def _select_model(self, model_name: str):
    """Select a driving model."""
    model_name = model_name.replace(" (Default)", "")
    self._current_model = model_name

    model_key = None
    for key, name in self._model_file_to_name.items():
      if name == model_name:
        model_key = key
        break

    if model_key:
      self._params.put("DrivingModel", model_key)
      update_frogpilot_toggles()

      if self._started:
        gui_app.set_modal_overlay(ConfirmDialog(
          "Reboot required to take effect.",
          "Reboot Now",
          "Reboot Later",
        ))

    self._update_deletable_state()

  def _on_update_tinygrad_click(self, button_id: int):
    if self._updating_tinygrad:
      self._params_memory.put_bool("CancelModelDownload", True)
      self._update_tinygrad_control.set_enabled(False)
      self._cancelling_download = True
    else:
      gui_app.set_modal_overlay(ConfirmDialog(
        "Updating Tinygrad will delete existing Tinygrad-based driving models and need to be re-downloaded. Proceed?",
        "Yes",
        "No",
      ))

  def _start_tinygrad_update(self):
    """Start the tinygrad update process."""
    self._params_memory.put_bool("UpdateTinygrad", True)
    self._params_memory.put("ModelDownloadProgress", "Downloading...")
    self._update_tinygrad_control.set_text(0, "CANCEL")
    self._updating_tinygrad = True

  def _translate_progress(self, progress: str) -> str:
    """Translate download progress messages."""
    translations = {
      "Downloading...": "Downloading...",
      "Downloaded!": "Downloaded!",
      "All models downloaded!": "All models downloaded!",
      "Repository unavailable": "Repository unavailable",
    }

    if progress in translations:
      return translations[progress]

    progress_lower = progress.lower()
    if "cancelled" in progress_lower:
      return "Download cancelled..."
    if "failed" in progress_lower:
      return "Download failed..."
    if "offline" in progress_lower:
      return "GitHub and GitLab are offline..."

    return progress

  def _update_download_state(self):
    """Update UI based on download progress."""
    if self._finalizing_download:
      return

    progress = self._params_memory.get("ModelDownloadProgress", encoding="utf-8") or ""

    if self._all_models_downloading or self._model_downloading:
      import re
      download_failed = bool(re.search(r"cancelled|exists|failed|missing|offline", progress, re.IGNORECASE))

      translated = self._translate_progress(progress)

      if progress in ("All models downloaded!", "Downloaded!") or download_failed:
        self._finalizing_download = True

        def finalize():
          self._all_models_downloading = False
          self._cancelling_download = False
          self._finalizing_download = False
          self._model_downloading = False
          self._no_models_downloaded = False

          # Update all models downloaded state
          downloadable = self._get_downloadable_models()
          self._all_models_downloaded = len(downloadable) == 0

          self._params_memory.remove("ModelDownloadProgress")

          self._download_model_control.set_enabled(True)
          self._download_model_control.set_text(0, "DOWNLOAD")
          self._download_model_control.set_text(1, "DOWNLOAD ALL")
          self._download_model_control.set_visible_button(0, True)
          self._download_model_control.set_visible_button(1, True)

        threading.Timer(2.5, finalize).start()

    if self._updating_tinygrad:
      import re
      download_failed = bool(re.search(r"cancelled|exists|failed|missing|offline", progress, re.IGNORECASE))

      translated = self._translate_progress(progress)

      if progress == "Updated!" or download_failed:
        self._finalizing_download = True

        def finalize_tinygrad():
          check_progress = self._params_memory.get("ModelDownloadProgress", encoding="utf-8") or ""
          self._model_downloading = bool(check_progress)

          if self._model_downloading:
            self._download_model_control.set_text(1, "CANCEL")
            self._download_model_control.set_visible_button(0, False)
          else:
            self._cancelling_download = False

          self._tinygrad_update = self._params.get_bool("TinygradUpdateAvailable")
          self._finalizing_download = False
          self._updating_tinygrad = False

          self._update_tinygrad_control.set_enabled(self._tinygrad_update)
          self._update_tinygrad_control.set_text(0, "UPDATE")

        threading.Timer(2.5, finalize_tinygrad).start()

  def _update_button_states(self):
    """Update button enabled/visible states."""
    can_delete = not (self._all_models_downloading or self._model_downloading or self._no_models_downloaded)
    self._delete_model_control.set_enabled(can_delete)

    # Download buttons
    self._download_model_control.set_text(0, "CANCEL" if self._model_downloading else "DOWNLOAD")
    self._download_model_control.set_text(1, "CANCEL" if self._all_models_downloading else "DOWNLOAD ALL")

    can_download_single = (not self._all_models_downloaded and not self._all_models_downloading and
                           not self._cancelling_download and not self._finalizing_download and
                           not self._updating_tinygrad and self._online and self._parked)
    can_download_all = (not self._all_models_downloaded and not self._model_downloading and
                        not self._cancelling_download and not self._finalizing_download and
                        not self._updating_tinygrad and self._online and self._parked)

    self._download_model_control.set_enabled_buttons(0, can_download_single)
    self._download_model_control.set_enabled_buttons(1, can_download_all)

    self._download_model_control.set_visible_button(0, not self._all_models_downloading)
    self._download_model_control.set_visible_button(1, not self._model_downloading)

    # Tinygrad update button
    can_update = (not self._model_downloading and not self._cancelling_download and
                  not self._finalizing_download and self._online and self._parked and self._tinygrad_update)
    self._update_tinygrad_control.set_enabled(can_update)

  def _update_toggles(self):
    self._tuning_level = self._params.get_int("TuningLevel") or 0
    model_randomizer = self._params.get_bool("ModelRandomizer")

    # ManageBlacklistedModels and ManageScores only visible when ModelRandomizer enabled
    if hasattr(self._manage_blacklist_control, "set_visible"):
      self._manage_blacklist_control.set_visible(model_randomizer)
    if hasattr(self._manage_scores_control, "set_visible"):
      self._manage_scores_control.set_visible(model_randomizer)

    # SelectModel only visible when ModelRandomizer disabled
    if hasattr(self._select_model_item, "set_visible"):
      self._select_model_item.set_visible(not model_randomizer)

  def _load_model_data(self):
    """Load available models and current state."""
    self._all_models_downloading = self._params_memory.get_bool("DownloadAllModels")
    progress = self._params_memory.get("ModelDownloadProgress", encoding="utf-8") or ""
    self._model_downloading = bool(progress)
    self._tinygrad_update = self._params.get_bool("TinygradUpdateAvailable")
    self._updating_tinygrad = self._params_memory.get_bool("UpdateTinygrad")

    self._model_downloading = self._model_downloading and not self._updating_tinygrad

    # Load available models
    available_models_str = self._params.get("AvailableModels", encoding="utf-8") or ""
    available_models = sorted([m for m in available_models_str.split(",") if m])

    available_names_str = self._params.get("AvailableModelNames", encoding="utf-8") or ""
    self._available_model_names = sorted([m for m in available_names_str.split(",") if m])

    # Build mappings
    self._model_file_to_name.clear()
    self._model_file_to_name_processed.clear()
    for i in range(min(len(available_models), len(self._available_model_names))):
      model_key = available_models[i]
      model_name = self._available_model_names[i]
      self._model_file_to_name[model_key] = model_name
      self._model_file_to_name_processed[model_key] = clean_model_name(model_name)

    # Check downloadable models
    downloadable = self._get_downloadable_models()
    self._all_models_downloaded = len(downloadable) == 0

    # Check deletable models
    self._update_deletable_state()

    # Get current model
    model_key = clean_model_name(self._params.get("DrivingModel", encoding="utf-8") or "")
    if not has_all_tinygrad_files(model_key):
      model_key = self._default_model
    self._current_model = self._model_file_to_name.get(model_key, "")

  def _close_sub_panel(self):
    self._current_panel = SubPanel.MAIN

  def show_event(self):
    super().show_event()
    self._main_scroller.show_event()
    self._load_model_data()
    self._update_toggles()
    self._started = ui_state.started

  def hide_event(self):
    super().hide_event()
    self._current_panel = SubPanel.MAIN

  def _render(self, rect):
    # Update online/parked state
    self._started = ui_state.started
    self._parked = not self._started  # Simplified - in real impl check frogpilot_scene.parked

    # Update download state
    self._update_download_state()
    self._update_button_states()

    if self._current_panel == SubPanel.MODEL_LABELS:
      self._model_labels_scroller.render(rect)
    else:
      self._main_scroller.render(rect)
