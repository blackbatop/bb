#!/usr/bin/env python3
import time
import json
import jwt
import random
import string
from pathlib import Path
from typing import cast

from datetime import datetime, timedelta, UTC
from openpilot.common.api import api_get
from openpilot.common.params import Params
from openpilot.common.spinner import Spinner
from openpilot.system.hardware import HARDWARE
from openpilot.system.hardware.hw import Paths
from openpilot.common.swaglog import cloudlog


UNREGISTERED_DONGLE_ID = "UnregisteredDevice"


def is_registered_device() -> bool:
    dongle = Params().get("DongleId", encoding="utf-8")
    return dongle not in (None, UNREGISTERED_DONGLE_ID)


def register(show_spinner=False, register_konik=False) -> str | None:
    params = Params()

    dongle_id: str | None = params.get("DongleId", encoding="utf8")
    if dongle_id is None and Path(Paths.persist_root() + "/comma/dongle_id").is_file():
        with open(Paths.persist_root() + "/comma/dongle_id") as f:
            dongle_id = f.read().strip()

    serial = HARDWARE.get_serial()
    params.put("HardwareSerial", serial)

    needs_registration = dongle_id is None

    if Path("/data/force_registration").is_file():
        needs_registration = True
    if Path("/data/skip_registration").is_file():
        return dongle_id or UNREGISTERED_DONGLE_ID

    pubkey = Path(Paths.persist_root() + "/comma/id_rsa.pub")
    if not pubkey.is_file():
        dongle_id = UNREGISTERED_DONGLE_ID
        cloudlog.warning(f"missing public key: {pubkey}")
    elif needs_registration or register_konik:
        if show_spinner:
            spinner = Spinner()
            spinner.update("registering device")

        with (
            open(Paths.persist_root() + "/comma/id_rsa.pub") as f1,
            open(Paths.persist_root() + "/comma/id_rsa") as f2,
        ):
            public_key = f1.read()
            private_key = f2.read()

        start_time = time.monotonic()
        imei1: str | None = None
        imei2: str | None = None
        while imei1 is None and imei2 is None:
            try:
                imei1, imei2 = HARDWARE.get_imei(0), HARDWARE.get_imei(1)
            except Exception:
                cloudlog.exception("Error getting imei, trying again...")
                time.sleep(1)

            if time.monotonic() - start_time > 60:
                if show_spinner:
                    spinner.update(
                        f"registering device - serial: {serial}, IMEI: ({imei1}, {imei2})"
                    )
                if imei1 is None and imei2 is None:
                    cloudlog.warning(
                        f"Timed out waiting for IMEI, allowing unregistered boot for device {serial}"
                    )
                    dongle_id = UNREGISTERED_DONGLE_ID
                    break

        if imei1 is not None:
            params.put("IMEI", imei1)

        backoff = 0
        start_time = time.monotonic()
        while True:
            try:
                register_token = jwt.encode(
                    {
                        "register": True,
                        "exp": datetime.now(UTC).replace(tzinfo=None)
                        + timedelta(hours=1),
                    },
                    cast(str, private_key),
                    algorithm="RS256",
                )
                cloudlog.info("getting pilotauth")
                resp = api_get(
                    "v2/pilotauth/",
                    method="POST",
                    timeout=15,
                    imei=imei1,
                    imei2=imei2,
                    serial=serial,
                    public_key=public_key,
                    register_token=register_token,
                )

                if resp.status_code in (402, 403):
                    cloudlog.info(f"Unable to register device, got {resp.status_code}")
                    dongle_id = "".join(
                        random.choices(string.ascii_lowercase + string.digits, k=16)
                    )
                else:
                    dongleauth = json.loads(resp.text)
                    dongle_id = dongleauth["dongle_id"]
                break
            except Exception:
                cloudlog.exception("failed to authenticate")
                backoff = min(backoff + 1, 15)
                time.sleep(backoff)

            if time.monotonic() - start_time > 60:
                if show_spinner:
                    spinner.update(
                        f"registering device - serial: {serial}, IMEI: ({imei1}, {imei2})"
                    )
                cloudlog.warning(
                    f"Timed out waiting for API, allowing unregistered boot for device {serial}"
                )
                dongle_id = UNREGISTERED_DONGLE_ID
                break

        if show_spinner:
            spinner.close()

    if not register_konik and dongle_id != params.get("KonikDongleId", encoding="utf8"):
        params.put("DongleId", dongle_id)
        params.put("StockDongleId", dongle_id)

    return dongle_id


if __name__ == "__main__":
    print(register())
