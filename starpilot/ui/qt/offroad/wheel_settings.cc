#include "starpilot/ui/qt/offroad/wheel_settings.h"

namespace {

QMap<int, QString> getWheelFunctionsMap() {
  return {
    {0, QObject::tr("No Action")},
    {3, QObject::tr("Pause Steering")},
    {7, QObject::tr("Toggle \"Switchback Mode\" On/Off")},
  };
}

QMap<int, QString> getLongitudinalWheelFunctionsMap() {
  return {
    {1, QObject::tr("Change \"Personality Profile\"")},
    {2, QObject::tr("Force openpilot to Coast")},
    {4, QObject::tr("Pause Acceleration/Braking")},
    {5, QObject::tr("Toggle \"Experimental Mode\" On/Off")},
    {6, QObject::tr("Toggle \"Traffic Mode\" On/Off")},
  };
}

QMap<int, QString> getMergedWheelFunctionsMap() {
  QMap<int, QString> functionsMap = getWheelFunctionsMap();
  const QMap<int, QString> longitudinalFunctionsMap = getLongitudinalWheelFunctionsMap();
  for (auto it = longitudinalFunctionsMap.constBegin(); it != longitudinalFunctionsMap.constEnd(); ++it) {
    functionsMap[it.key()] = it.value();
  }
  return functionsMap;
}

QString getWheelFunctionLabel(Params &params, const QString &key) {
  const QMap<int, QString> functionsMap = getMergedWheelFunctionsMap();
  return functionsMap.value(params.getInt(key.toStdString()), QObject::tr("No Action"));
}

bool lockLkasButtonIfNeeded(Params &params) {
  if (!params.getBool("RemapCancelToDistance")) {
    return false;
  }

  if (params.getInt("LKASButtonControl") != 0) {
    params.putInt("LKASButtonControl", 0);
    updateStarPilotToggles();
  }

  return true;
}

}  // namespace

StarPilotWheelPanel::StarPilotWheelPanel(StarPilotSettingsWindow *parent, bool forceOpen) : StarPilotListWidget(parent), parent(parent) {
  forceOpenDescriptions = forceOpen;

  const std::vector<std::tuple<QString, QString, QString, QString>> wheelToggles {
    {"DistanceButtonControl", tr("Distance Button"), tr("<b>Action performed when the \"Distance\" button is pressed.</b>"), "../../starpilot/assets/toggle_icons/icon_mute.png"},
    {"LongDistanceButtonControl", tr("Distance Button (Long Press)"), tr("<b>Action performed when the \"Distance\" button is pressed for more than 0.5 seconds.</b>"), "../../starpilot/assets/toggle_icons/icon_mute.png"},
    {"VeryLongDistanceButtonControl", tr("Distance Button (Very Long Press)"), tr("<b>Action performed when the \"Distance\" button is pressed for more than 2.5 seconds.</b>"), "../../starpilot/assets/toggle_icons/icon_mute.png"},
    {"LKASButtonControl", tr("LKAS Button"), tr("<b>Action performed when the \"LKAS\" button is pressed.</b>"), "../../starpilot/assets/toggle_icons/icon_mute.png"}
  };

  for (const auto &[param, title, desc, icon] : wheelToggles) {
    ButtonControl *wheelToggle = new ButtonControl(title, tr("SELECT"), desc);
    QObject::connect(wheelToggle, &ButtonControl::clicked, [key = param, parent, wheelToggle, this]() {
      if (key == "LKASButtonControl" && lockLkasButtonIfNeeded(params)) {
        wheelToggle->setValue(tr("No Action"));
        wheelToggle->setEnabled(false);
        return;
      }

      QMap<int, QString> functionsMap = getWheelFunctionsMap();
      if (parent->hasOpenpilotLongitudinal) {
        const QMap<int, QString> longitudinalFunctionsMap = getLongitudinalWheelFunctionsMap();
        for (auto it = longitudinalFunctionsMap.constBegin(); it != longitudinalFunctionsMap.constEnd(); ++it) {
          functionsMap[it.key()] = it.value();
        }
      }

      QString selection = MultiOptionDialog::getSelection(tr("Select a function to assign to this button"), functionsMap.values(), functionsMap[params.getInt(key.toStdString())], this);
      if (!selection.isEmpty()) {
        params.putInt(key.toStdString(), functionsMap.key(selection));
        wheelToggle->setValue(selection);
        updateStarPilotToggles();
      }
    });

    if (param == "LKASButtonControl" && lockLkasButtonIfNeeded(params)) {
      wheelToggle->setValue(tr("No Action"));
      wheelToggle->setEnabled(false);
    } else {
      wheelToggle->setValue(getWheelFunctionLabel(params, param));
    }

    toggles[param] = wheelToggle;

    addItem(wheelToggle);

    QObject::connect(wheelToggle, &AbstractControl::hideDescriptionEvent, [this]() {
      update();
    });
    QObject::connect(wheelToggle, &AbstractControl::showDescriptionEvent, [this]() {
      update();
    });
  }

  openDescriptions(forceOpenDescriptions, toggles);
}

void StarPilotWheelPanel::showEvent(QShowEvent *event) {
  updateToggles();
}

void StarPilotWheelPanel::updateToggles() {
  const bool showAllToggles = parent->showAllTogglesEnabled();

  for (auto &[key, toggle] : toggles) {
    bool setVisible = showAllToggles || parent->tuningLevel >= parent->starpilotToggleLevels[key].toDouble();

    if (!showAllToggles && key == "LKASButtonControl") {
      setVisible &= !parent->isSubaru;
      setVisible &= !parent->lkasAllowedForAOL || !(params.getBool("AlwaysOnLateral") && params.getBool("AlwaysOnLateralLKAS"));
    }

    if (ButtonControl *wheelToggle = qobject_cast<ButtonControl*>(toggle)) {
      if (key == "LKASButtonControl") {
        const bool lkasLocked = lockLkasButtonIfNeeded(params);
        wheelToggle->setEnabled(!lkasLocked);
        wheelToggle->setValue(lkasLocked ? tr("No Action") : getWheelFunctionLabel(params, key));
      } else {
        wheelToggle->setValue(getWheelFunctionLabel(params, key));
      }
    }

    toggle->setVisible(setVisible);
  }

  openDescriptions(forceOpenDescriptions, toggles);

  update();
}
