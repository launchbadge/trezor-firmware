# This file is part of the Trezor project.
#
# Copyright (C) 2012-2019 SatoshiLabs and contributors
#
# This library is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3
# as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the License along with this library.
# If not, see <https://www.gnu.org/licenses/lgpl-3.0.html>.

import filecmp
import itertools
import os
from pathlib import Path

from trezorlib import debuglink, device
from trezorlib.messages.PassphraseSourceType import HOST as PASSPHRASE_ON_HOST

from . import conftest


SAVE_SCREEN = os.environ.get("TREZOR_SAVE_SCREEN")
SAVE_SCREEN_FIXTURES = os.environ.get("TREZOR_SAVE_SCREEN_FIXTURES")


class TrezorTest:
    # fmt: off
    #                1      2     3    4      5      6      7     8      9    10    11    12
    mnemonic12 = "alcohol woman abuse must during monitor noble actual mixed trade anger aisle"
    mnemonic18 = "owner little vague addict embark decide pink prosper true fork panda embody mixture exchange choose canoe electric jewel"
    mnemonic24 = "dignity pass list indicate nasty swamp pool script soccer toe leaf photo multiply desk host tomato cradle drill spread actor shine dismiss champion exotic"
    mnemonic_all = " ".join(["all"] * 12)
    # fmt: on

    pin4 = "1234"
    pin6 = "789456"
    pin8 = "45678978"

    def setup_method(self, method):
        self.client = conftest.get_device()
        # self.client.set_buttonwait(3)

        device.wipe(self.client)
        self.client.open()

        if SAVE_SCREEN:
            remove_files(collect_images())

    def teardown_method(self, method):
        self.client.close()

        if SAVE_SCREEN:
            images = collect_images()
            if SAVE_SCREEN_FIXTURES:
                record_fixtures(images, get_test_id(method))
            else:
                assert_images(images, get_test_id(method))
                remove_files(images)

    def _setup_mnemonic(self, mnemonic=None, pin="", passphrase=False, lock=True):
        if mnemonic is None:
            mnemonic = TrezorTest.mnemonic12
        debuglink.load_device_by_mnemonic(
            self.client,
            mnemonic=mnemonic,
            pin=pin,
            passphrase_protection=passphrase,
            label="test",
            language="english",
        )
        if conftest.TREZOR_VERSION == 1 and lock:
            # remove cached PIN (introduced via load_device)
            self.client.clear_session()
        if conftest.TREZOR_VERSION > 1 and passphrase:
            device.apply_settings(self.client, passphrase_source=PASSPHRASE_ON_HOST)

    def setup_mnemonic_allallall(self, lock=True):
        self._setup_mnemonic(mnemonic=TrezorTest.mnemonic_all, lock=lock)

    def setup_mnemonic_nopin_nopassphrase(self, lock=True):
        self._setup_mnemonic(lock=lock)

    def setup_mnemonic_nopin_passphrase(self, lock=True):
        self._setup_mnemonic(passphrase=True, lock=lock)

    def setup_mnemonic_pin_nopassphrase(self, lock=True):
        self._setup_mnemonic(pin=TrezorTest.pin4, lock=lock)

    def setup_mnemonic_pin_passphrase(self, lock=True):
        self._setup_mnemonic(pin=TrezorTest.pin4, passphrase=True, lock=lock)


SCREENSHOT_PATH = "./core/src"
SCREENSHOT_FIXTURE_PATH = "./tests/ui_tests"


def get_test_id(method):
    return "{}_{}".format(method.__self__.__class__.__name__, method.__name__)


def collect_images():
    return list(Path(SCREENSHOT_PATH).glob("*.png"))


def collect_fixtures(test_id):
    return list(Path(SCREENSHOT_FIXTURE_PATH).glob("{}/*.png".format(test_id)))


def assert_images(images, test_id):
    fixtures = collect_fixtures(test_id)
    if not fixtures:
        return
    images = sorted(images)
    fixtures = sorted(fixtures)

    for fixture, image in itertools.zip_longest(fixtures, images):
        assert fixture is not None, "Missing fixture for image {}".format(image)
        assert image is not None, "Missing image for fixture {}".format(fixture)
        assert filecmp.cmp(fixture, image), "Image {} and fixture {} differ".format(
            image, fixture
        )


def record_fixtures(images, test_id):
    fixture_dir = Path(SCREENSHOT_FIXTURE_PATH) / test_id

    if fixture_dir.is_dir():
        # remove old fixtures
        remove_files(collect_fixtures(test_id))
    else:
        # create the fixture dir, if not present
        print("Creating", fixture_dir)
        fixture_dir.mkdir()

    # move the recorded images into the fixture locations
    for index, image in enumerate(images):
        fixture = fixture_dir / "{}.png".format(index)
        print("Saving", image, "into", fixture)
        image.replace(fixture)


def remove_files(files):
    for f in files:
        print("Removing", f)
        f.unlink()


def generate_entropy(strength, internal_entropy, external_entropy):
    """
    strength - length of produced seed. One of 128, 192, 256
    random - binary stream of random data from external HRNG
    """
    import hashlib

    if strength not in (128, 192, 256):
        raise ValueError("Invalid strength")

    if not internal_entropy:
        raise ValueError("Internal entropy is not provided")

    if len(internal_entropy) < 32:
        raise ValueError("Internal entropy too short")

    if not external_entropy:
        raise ValueError("External entropy is not provided")

    if len(external_entropy) < 32:
        raise ValueError("External entropy too short")

    entropy = hashlib.sha256(internal_entropy + external_entropy).digest()
    entropy_stripped = entropy[: strength // 8]

    if len(entropy_stripped) * 8 != strength:
        raise ValueError("Entropy length mismatch")

    return entropy_stripped
