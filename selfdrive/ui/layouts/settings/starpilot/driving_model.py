from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Callable
import json
import shutil
import threading

from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.starpilot.assets.model_manager import ModelManager, TINYGRAD_VERSIONS, canonical_model_key, is_builtin_model_key, model_key_aliases
from openpilot.starpilot.common.starpilot_variables import MODELS_PATH, update_starpilot_toggles
from openpilot.system.hardware import HARDWARE
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.lib.multilang import tr, tr_noop
from openpilot.system.ui.widgets import DialogResult
from openpilot.system.ui.widgets.confirm_dialog import ConfirmDialog, alert_dialog
from openpilot.system.ui.widgets.selection_dialog import SelectionDialog
from openpilot.selfdrive.ui.layouts.settings.starpilot.panel import StarPilotPanel
from openpilot.selfdrive.ui.layouts.settings.starpilot.aethergrid import AetherSliderDialog


@dataclass
class ModelCatalogEntry:
  key: str
  name: str
  series: str
  version: str
  released: str
  builtin: bool
  installed: bool
  partial: bool
  community_favorite: bool
  user_favorite: bool


def _clean_model_name(name: str) -> str:
  return str(name or "").replace("_default", "").replace("(Default)", "").strip()

class StarPilotDrivingModelLayout(StarPilotPanel):
  def __init__(self):
    super().__init__()

    self._model_dir = MODELS_PATH
    self._model_dir.mkdir(parents=True, exist_ok=True)

    self._catalog_entries: dict[str, ModelCatalogEntry] = {}
    self._model_file_to_name: dict[str, str] = {}
    self._model_file_to_name_processed: dict[str, str] = {}
    self._model_series_map: dict[str, str] = {}
    self._model_released_dates: dict[str, str] = {}
    self._model_version_map: dict[str, str] = {}
    self._community_favorites: set[str] = set()
    self._user_favorites: set[str] = set()
    self._current_model_key = self._default_model_key()
    self._current_model_name = self._default_model_name()

    self.SECTIONS = [
      {
        "title": tr_noop("Model Selection"),
        "columns": 1,
        "uniform_width": True,
        "categories": [
          {
            "title": tr_noop("Select Model"),
            "type": "value",
            "icon": "toggle_icons/icon_steering.png",
            "on_click": self._on_select_model_clicked,
            "get_value": lambda: self._current_model_name,
            "visible": lambda: not self._params.get_bool("ModelRandomizer"),
            "color": "#597497"
          },
        ],
      },
      {
        "title": tr_noop("Model Actions"),
        "columns": 2,
        "uniform_width": True,
        "categories": [
          {
            "title": tr_noop("Download Models"),
            "type": "hub",
            "icon": "toggle_icons/icon_system.png",
            "on_click": self._on_download_clicked,
            "color": "#597497",
            "get_status": lambda: self._params_memory.get("ModelDownloadProgress", encoding="utf-8") if self._is_download_active() else ""
          },
          {
            "title": tr_noop("Delete Models"),
            "type": "hub",
            "icon": "toggle_icons/icon_system.png",
            "on_click": self._on_delete_clicked,
            "color": "#597497"
          },
        ],
      },
      {
        "title": tr_noop("Automation"),
        "columns": 2,
        "uniform_width": True,
        "categories": [
          {
            "title": tr_noop("Model Randomizer"),
            "type": "toggle",
            "icon": "toggle_icons/icon_conditional.png",
            "get_state": lambda: self._params.get_bool("ModelRandomizer"),
            "set_state": self._on_model_randomizer_toggled,
            "color": "#597497"
          },
          {
            "title": tr_noop("Auto Download"),
            "type": "toggle",
            "icon": "toggle_icons/icon_system.png",
            "get_state": lambda: self._params.get_bool("AutomaticallyDownloadModels"),
            "set_state": lambda s: self._params.put_bool("AutomaticallyDownloadModels", s),
            "color": "#597497"
          },
        ],
      },
      {
        "title": tr_noop("Randomizer Details"),
        "columns": 2,
        "uniform_width": True,
        "visible": lambda: self._params.get_bool("ModelRandomizer"),
        "categories": [
          {
            "title": tr_noop("Blacklist"),
            "type": "hub",
            "icon": "toggle_icons/icon_system.png",
            "on_click": self._on_blacklist_clicked,
            "color": "#597497"
          },
          {
            "title": tr_noop("Ratings"),
            "type": "hub",
            "icon": "toggle_icons/icon_system.png",
            "on_click": self._on_scores_clicked,
            "color": "#597497"
          },
        ],
      },
      {
        "title": tr_noop("Advanced Tuning"),
        "columns": 2,
        "uniform_width": True,
        "visible": lambda: self._params.get_int("TuningLevel") == 3,
        "categories": [
          {
            "title": tr_noop("Recovery Power"),
            "type": "value",
            "icon": "toggle_icons/icon_road.png",
            "get_value": lambda: f"{self._params.get_float('RecoveryPower'):.1f}",
            "on_click": self._on_recovery_power_clicked,
            "color": "#597497"
          },
          {
            "title": tr_noop("Stop Distance"),
            "type": "value",
            "icon": "toggle_icons/icon_road.png",
            "get_value": lambda: f"{self._params.get_float('StopDistance'):.1f}m",
            "on_click": self._on_stop_distance_clicked,
            "color": "#597497"
          },
        ],
      },
    ]
    
    self._model_manager = ModelManager(self._params, self._params_memory)
    self._download_thread = None
    self._manifest_fetch_thread = None
    self._manifest_fetched = False

    self._fetch_manifest_async()
    self._update_model_metadata()
    self._rebuild_grid()

  def _render(self, rect: rl.Rectangle):
    self._update_state()
    super()._render(rect)

  def show_event(self):
    super().show_event()
    self._fetch_manifest_async()
    self._update_model_metadata()

  def _fetch_manifest_async(self):
    if self._manifest_fetch_thread is not None and self._manifest_fetch_thread.is_alive():
      return
      
    def _task():
      self._model_manager.update_models()
      self._manifest_fetched = True
        
    self._manifest_fetch_thread = threading.Thread(target=_task, daemon=True)
    self._manifest_fetch_thread.start()

  def _default_model_key(self) -> str:
    default_key = self._params.get_default_value("Model") or self._params.get_default_value("DrivingModel")
    if isinstance(default_key, bytes):
      default_key = default_key.decode("utf-8", errors="ignore")
    return canonical_model_key(str(default_key or "").strip()) or "sc2"

  def _default_model_name(self) -> str:
    default_name = self._params.get_default_value("DrivingModelName")
    if isinstance(default_name, bytes):
      default_name = default_name.decode("utf-8", errors="ignore")
    return _clean_model_name(default_name or "") or "South Carolina"

  def _default_model_version(self) -> str:
    default_version = self._params.get_default_value("ModelVersion") or self._params.get_default_value("DrivingModelVersion")
    if isinstance(default_version, bytes):
      default_version = default_version.decode("utf-8", errors="ignore")
    return str(default_version or "").strip() or "v11"

  def _current_selected_key(self) -> str:
    current_key = self._params.get("Model", encoding="utf-8") or self._params.get("DrivingModel", encoding="utf-8") or ""
    return canonical_model_key(str(current_key).strip()) or self._default_model_key()

  def _load_on_disk_files(self) -> set[str]:
    try:
      return {entry.name for entry in self._model_dir.iterdir()}
    except Exception:
      return set()

  def _is_model_installed(self, key: str, version: str = "", on_disk_files: set[str] | None = None) -> bool:
    model_key = canonical_model_key(str(key or "").strip())
    if not model_key:
      return False

    if is_builtin_model_key(model_key):
      return True

    files = on_disk_files if on_disk_files is not None else self._load_on_disk_files()
    if f"{model_key}.thneed" in files:
      return True

    if version in TINYGRAD_VERSIONS:
      required_files = set(self._required_files_for_version(model_key, version))
      return required_files.issubset(files)

    if version == "v7":
      return f"{model_key}.pkl" in files

    return any(file.startswith(f"{model_key}.") or file.startswith(f"{model_key}_") for file in files)

  def _required_files_for_version(self, key: str, version: str) -> list[str]:
    files = [
      f"{key}_driving_policy_tinygrad.pkl",
      f"{key}_driving_vision_tinygrad.pkl",
      f"{key}_driving_policy_metadata.pkl",
      f"{key}_driving_vision_metadata.pkl",
    ]

    if version == "v12":
      files.extend([
        f"{key}_driving_off_policy_tinygrad.pkl",
        f"{key}_driving_off_policy_metadata.pkl",
      ])

    return files

  def _ensure_default_model_visible(self):
    default_key = self._default_model_key()
    default_name = self._default_model_name()
    default_series = tr("Custom Series")
    default_released = ""

    for alias in model_key_aliases(default_key):
      alias = canonical_model_key(alias)
      if alias not in self._model_file_to_name:
        continue

      default_name = self._model_file_to_name.get(alias, default_name)
      default_series = self._model_series_map.get(alias, default_series)
      default_released = self._model_released_dates.get(alias, default_released)

      if alias != default_key:
        self._model_file_to_name.pop(alias, None)
        self._model_file_to_name_processed.pop(alias, None)
        self._model_series_map.pop(alias, None)
        self._model_released_dates.pop(alias, None)
        self._model_version_map.pop(alias, None)
        self._catalog_entries.pop(alias, None)

    version = self._model_version_map.get(default_key, self._default_model_version())
    self._model_file_to_name[default_key] = default_name
    self._model_file_to_name_processed[default_key] = _clean_model_name(default_name)
    self._model_series_map[default_key] = default_series
    if default_released:
      self._model_released_dates[default_key] = default_released
    self._model_version_map.setdefault(default_key, version)

  def _build_catalog_entries(self, on_disk_files: set[str]):
    self._catalog_entries.clear()
    self._model_file_to_name.clear()
    self._model_file_to_name_processed.clear()
    self._model_series_map.clear()
    self._model_released_dates.clear()
    self._model_version_map.clear()

    available_models = [entry.strip() for entry in (self._params.get("AvailableModels", encoding="utf-8") or "").split(",")]
    available_names = [entry.strip() for entry in (self._params.get("AvailableModelNames", encoding="utf-8") or "").split(",")]
    available_series = [entry.strip() for entry in (self._params.get("AvailableModelSeries", encoding="utf-8") or "").split(",")]
    available_versions = [entry.strip() for entry in (self._params.get("ModelVersions", encoding="utf-8") or "").split(",")]
    released_dates = [entry.strip() for entry in (self._params.get("ModelReleasedDates", encoding="utf-8") or "").split(",")]

    self._community_favorites = {canonical_model_key(entry.strip()) for entry in (self._params.get("CommunityFavorites", encoding="utf-8") or "").split(",") if entry.strip()}
    self._user_favorites = {canonical_model_key(entry.strip()) for entry in (self._params.get("UserFavorites", encoding="utf-8") or "").split(",") if entry.strip()}

    size = min(len(available_models), len(available_names))
    for i in range(size):
      canonical_key = canonical_model_key(available_models[i])
      name = available_names[i].strip()
      if not canonical_key or not name:
        continue

      series = available_series[i].strip() if i < len(available_series) and available_series[i].strip() else tr("Custom Series")
      version = available_versions[i].strip() if i < len(available_versions) else ""
      released = released_dates[i].strip() if i < len(released_dates) else ""

      self._model_file_to_name.setdefault(canonical_key, name)
      self._model_file_to_name_processed.setdefault(canonical_key, _clean_model_name(name))
      self._model_series_map.setdefault(canonical_key, series)
      if released:
        self._model_released_dates.setdefault(canonical_key, released)
      if version:
        self._model_version_map.setdefault(canonical_key, version)

    self._ensure_default_model_visible()

    for key, name in self._model_file_to_name.items():
      version = self._model_version_map.get(key, self._default_model_version() if is_builtin_model_key(key) else "")
      installed = self._is_model_installed(key, version, on_disk_files)
      partial = (not is_builtin_model_key(key)) and (not installed) and any(file.startswith(f"{key}.") or file.startswith(f"{key}_") for file in on_disk_files)
      self._catalog_entries[key] = ModelCatalogEntry(
        key=key,
        name=name,
        series=self._model_series_map.get(key, tr("Custom Series")),
        version=version,
        released=self._model_released_dates.get(key, ""),
        builtin=is_builtin_model_key(key),
        installed=installed,
        partial=partial,
        community_favorite=(key in self._community_favorites),
        user_favorite=(key in self._user_favorites),
      )

  def _update_model_metadata(self):
    on_disk_files = self._load_on_disk_files()
    self._build_catalog_entries(on_disk_files)

    self._current_model_key = self._current_selected_key()
    current_entry = self._catalog_entries.get(self._current_model_key)
    if current_entry is None or not current_entry.installed:
      self._current_model_key = self._default_model_key()
      current_entry = self._catalog_entries.get(self._current_model_key)

    if current_entry is not None:
      self._current_model_name = current_entry.name
    else:
      self._current_model_name = self._default_model_name()

  def _show_selection_dialog(self, title: str, options: dict[str, str] | list[str], current_val: str, on_confirm: Callable, current_key: str = ""):
    if not options:
      gui_app.set_modal_overlay(alert_dialog(tr("No options available.")))
      return

    if isinstance(options, list):
      def _on_close_list(res, val):
        if res == DialogResult.CONFIRM: on_confirm(val)
      dialog = SelectionDialog(title, options, current_val, on_close=_on_close_list)
      gui_app.set_modal_overlay(dialog)
      return

    grouped = {}
    name_to_key = {}
    key_to_display = {}
    name_counts = {}
    for key, name in options.items():
      series = self._model_series_map.get(key, tr("Custom Series"))
      if series not in grouped: grouped[series] = []
      name_counts[name] = name_counts.get(name, 0) + 1
      display_name = name if name_counts[name] == 1 else f"{name} [{key}]"
      grouped[series].append(display_name)
      name_to_key[display_name] = key
      key_to_display[key] = display_name
    
    for series in grouped: grouped[series].sort()
    sorted_series = sorted(grouped.keys())
    if "StarPilot" in sorted_series:
      sorted_series.remove("StarPilot")
      sorted_series.insert(0, "StarPilot")
    
    final_grouped = {s: grouped[s] for s in sorted_series}

    def _on_close_grouped(res, val):
      if res == DialogResult.CONFIRM:
        key = name_to_key.get(val, val)
        on_confirm(key)

    def _on_favorite_toggled(key):
      favs = [f.strip() for f in (self._params.get("UserFavorites", encoding='utf-8') or "").split(",") if f.strip()]
      if key in favs: favs.remove(key)
      else: favs.append(key)
      self._params.put("UserFavorites", ",".join(favs))

    user_favs = [f.strip() for f in (self._params.get("UserFavorites", encoding='utf-8') or "").split(",") if f.strip()]
    comm_favs = [f.strip() for f in (self._params.get("CommunityFavorites", encoding='utf-8') or "").split(",") if f.strip()]

    current_display = key_to_display.get(current_key, current_val)

    dialog = SelectionDialog(
        title, final_grouped, current_display, on_close=_on_close_grouped,
        model_released_dates=self._model_released_dates,
        model_file_to_name=self._model_file_to_name,
        user_favorites=user_favs,
        community_favorites=comm_favs,
        on_favorite_toggled=_on_favorite_toggled
    )
    gui_app.set_modal_overlay(dialog)

  def _is_download_active(self) -> bool:
    return bool(self._params_memory.get("ModelToDownload", encoding="utf-8") or self._params_memory.get_bool("DownloadAllModels"))

  def _selected_model_version(self, model_key: str) -> str:
    version = self._model_version_map.get(model_key, "")
    if version:
      return version

    try:
      versions_file = self._model_dir / ".model_versions.json"
      if versions_file.is_file():
        payload = json.loads(versions_file.read_text())
        if isinstance(payload, dict):
          for alias in model_key_aliases(model_key):
            resolved = str(payload.get(alias, "")).strip()
            if resolved:
              return resolved
    except Exception:
      pass

    if is_builtin_model_key(model_key):
      return self._default_model_version()
    return ""

  def _build_selectable_models(self) -> dict[str, str]:
    models: dict[str, str] = {}
    for key, entry in self._catalog_entries.items():
      if entry.installed:
        models[key] = entry.name

    return models

  def _build_deletable_models(self) -> dict[str, str]:
    installed = self._build_selectable_models()
    default_key = self._default_model_key()
    current_name = _clean_model_name(self._current_model_name)
    default_name = _clean_model_name(installed.get(default_key, self._default_model_name()))

    deletable: dict[str, str] = {}
    for key, display_name in installed.items():
      processed_name = _clean_model_name(display_name)
      if processed_name == current_name or processed_name == default_name:
        continue
      deletable[key] = display_name
    return deletable

  def _on_select_model_clicked(self):
    self._update_model_metadata()
    installed_models = self._build_selectable_models()
    if not installed_models:
      gui_app.set_modal_overlay(alert_dialog(tr("No downloaded models found.")))
      return

    def _on_confirm(model_key):
      selected_model = canonical_model_key(model_key)
      self._params.put("Model", selected_model)
      self._params.put("DrivingModel", selected_model)
      self._params.put("DrivingModelName", installed_models[model_key])
      resolved_version = self._selected_model_version(selected_model)
      if resolved_version:
        self._params.put("ModelVersion", resolved_version)
        self._params.put("DrivingModelVersion", resolved_version)
      update_starpilot_toggles()
      self._update_model_metadata()
      if ui_state.started:
        self._params.put_bool("OnroadCycleRequested", True)
        gui_app.set_modal_overlay(alert_dialog(tr("Drive-cycle requested for immediate apply.")))

    self._show_selection_dialog(tr("Select Driving Model"), installed_models, self._current_model_name, _on_confirm, current_key=self._current_model_key)

  def _on_recovery_power_clicked(self):
    def on_close(res, val):
      if res == DialogResult.CONFIRM:
        self._params.put_float("RecoveryPower", float(val))
        self._rebuild_grid()

    gui_app.set_modal_overlay(AetherSliderDialog(tr("Recovery Power"), 0.5, 2.0, 0.1, self._params.get_float("RecoveryPower"), on_close, unit="x", color="#597497"))

  def _on_stop_distance_clicked(self):
    def on_close(res, val):
      if res == DialogResult.CONFIRM:
        self._params.put_float("StopDistance", float(val))
        self._rebuild_grid()

    gui_app.set_modal_overlay(AetherSliderDialog(tr("Stop Distance"), 4.0, 10.0, 0.1, self._params.get_float("StopDistance"), on_close, unit="m", color="#597497"))

  def _on_download_clicked(self):
    self._update_model_metadata()
    if ui_state.started:
      gui_app.set_modal_overlay(alert_dialog(tr("Cannot download models while driving.")))
      return

    is_downloading = self._is_download_active()
    if is_downloading:
      self._params_memory.put_bool("CancelModelDownload", True)
      return

    not_installed = {key: entry.name for key, entry in self._catalog_entries.items() if not entry.installed}
    if not not_installed:
      gui_app.set_modal_overlay(alert_dialog(tr("All models are already installed.")))
      return

    self._show_selection_dialog(tr("Select Model to Download"), not_installed, "", lambda mk: self._params_memory.put("ModelToDownload", mk))

  def _on_delete_clicked(self):
    self._update_model_metadata()
    if ui_state.started:
      gui_app.set_modal_overlay(alert_dialog(tr("Cannot delete model files while driving.")))
      return
    if self._is_download_active():
      gui_app.set_modal_overlay(alert_dialog(tr("Cannot delete model files while a download is in progress.")))
      return

    deletable = self._build_deletable_models()

    if not deletable:
      gui_app.set_modal_overlay(alert_dialog(tr("No deletable models found.")))
      return
    
    def _on_confirm(mk):
      def _execute_delete(res):
        if res == DialogResult.CONFIRM:
          for file in self._model_dir.iterdir():
            if not (file.name == f"{mk}.thneed" or file.name == f"{mk}.pkl" or file.name.startswith(f"{mk}_")):
              continue
            if file.is_file():
              file.unlink(missing_ok=True)
          self._update_model_metadata()
          self._rebuild_grid()
      gui_app.set_modal_overlay(ConfirmDialog(tr(f"Delete '{deletable[mk]}'?"), tr("Delete"), on_close=_execute_delete))

    self._show_selection_dialog(tr("Select Model to Delete"), deletable, "", _on_confirm)

  def _on_blacklist_clicked(self):
    blacklisted = [m.strip() for m in (self._params.get("BlacklistedModels", encoding='utf-8') or "").split(",") if m.strip()]
    def _on_action_selected(res, val):
        if res == DialogResult.CONFIRM:
            if val == tr("ADD"):
                blacklistable = {k: v for k, v in self._model_file_to_name.items() if k not in blacklisted}
                self._show_selection_dialog(tr("Add to Blacklist"), blacklistable, "", lambda k: self._params.put("BlacklistedModels", ",".join(blacklisted + [k])))
            elif val == tr("REMOVE"):
                options = {k: self._model_file_to_name.get(k, k) for k in blacklisted}
                def _remove(k):
                   blacklisted.remove(k)
                   self._params.put("BlacklistedModels", ",".join(blacklisted))
                self._show_selection_dialog(tr("Remove from Blacklist"), options, "", _remove)
            elif val == tr("RESET ALL"): self._params.remove("BlacklistedModels")

    gui_app.set_modal_overlay(SelectionDialog(tr("Manage Blacklist"), [tr("ADD"), tr("REMOVE"), tr("RESET ALL")], on_close=_on_action_selected))

  def _on_scores_clicked(self):
    scores_raw = self._params.get("ModelDrivesAndScores", encoding='utf-8') or ""
    if not scores_raw:
      gui_app.set_modal_overlay(alert_dialog(tr("No model ratings found.")))
      return
    try:
        scores = json.loads(scores_raw)
        lines = [f"{k}: {v.get('Score', 0)}% ({v.get('Drives', 0)} drives)" for k, v in scores.items()]
        gui_app.set_modal_overlay(ConfirmDialog("\n".join(lines), tr("Close"), rich=True))
    except: pass

  def _on_model_randomizer_toggled(self, state: bool):
    self._params.put_bool("ModelRandomizer", state)
    if state:
        not_installed = [key for key, entry in self._catalog_entries.items() if not entry.installed]
        if not_installed:
            def _on_download_confirm(res):
                if res == DialogResult.CONFIRM:
                    self._params_memory.put_bool("DownloadAllModels", True)
                    self._params_memory.put("ModelDownloadProgress", "Downloading...")
            gui_app.set_modal_overlay(ConfirmDialog(tr("Download all models for Randomizer?"), tr("Download All"), on_close=_on_download_confirm))

  def _update_state(self):
    if getattr(self, "_manifest_fetched", False):
      self._manifest_fetched = False
      self._update_model_metadata()
      self._rebuild_grid()

    model_to_download = self._params_memory.get("ModelToDownload", encoding='utf-8') or ""
    download_all = self._params_memory.get_bool("DownloadAllModels")
    is_downloading = bool(model_to_download or download_all)

    if is_downloading and (self._download_thread is None or not self._download_thread.is_alive()):
      def _download_task():
        try:
          if download_all:
            self._model_manager.download_all_models()
          else:
            self._model_manager.download_model(model_to_download)
        except Exception:
          pass
        finally:
          self._params_memory.remove("CancelModelDownload")
          self._params_memory.remove("ModelToDownload")
          self._params_memory.put_bool("DownloadAllModels", False)
          self._params_memory.remove("ModelDownloadProgress")
          self._download_thread = None
          self._update_model_metadata()
          self._rebuild_grid()

      self._download_thread = threading.Thread(target=_download_task, daemon=True)
      self._download_thread.start()
