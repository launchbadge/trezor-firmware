from trezor.crypto import bip39, slip39
from trezor.errors import MnemonicError

from apps.common import mnemonic, storage

if False:
    from typing import Optional


class RecoveryAborted(Exception):
    pass


_GROUP_STORAGE_OFFSET = 16


def process_share(words: str, mnemonic_type: int) -> Optional[bytes]:
    if mnemonic_type == mnemonic.TYPE_BIP39:
        return _process_bip39(words)
    else:
        return _process_slip39(words)


def _process_bip39(words: str) -> bytes:
    """
    Receives single mnemonic and processes it. Returns what is then stored
    in the storage, which is the mnemonic itself for BIP-39.
    """
    if not bip39.check(words):
        raise MnemonicError()
    return words.encode()


def _process_slip39(words: str) -> Optional[bytes]:
    """
    Receives single mnemonic and processes it. Returns what is then stored in storage or
    None if more shares are needed.
    """
    identifier, iteration_exponent, group_index, group_threshold, group_count, index, threshold, value = slip39.decode_mnemonic(
        words
    )  # TODO: use better data structure for this

    if threshold == 1:
        raise ValueError("Threshold equal to 1 is not allowed.")

    remaining = storage.recovery.get_remaining()
    # TODO: investigate why shares_remianing is bytes instead of bytearray
    shares_remaining = storage.recovery.get_slip39_shares_remaining()

    # if this is the first share, parse and store metadata
    if not remaining:
        storage.recovery.set_slip39_iteration_exponent(iteration_exponent)
        storage.recovery.set_slip39_identifier(identifier)
        storage.recovery.set_slip39_threshold(threshold)
        storage.recovery.set_remaining(threshold - 1)
        storage.recovery_shares.set(index, words)
        if group_count > 1:
            storage.recovery.set_slip39_group_count(group_count)
            storage.recovery.set_slip39_group_threshold(group_threshold)
            shares_remaining = bytearray([0x10] * group_count)
            shares_remaining[group_index] = threshold - 1
            storage.recovery.set_slip39_shares_remaining(shares_remaining)
        return None  # we need more shares

    # These should be checked by UI before so it's a Runtime exception otherwise
    if identifier != storage.recovery.get_slip39_identifier():
        raise RuntimeError("Slip39: Share identifiers do not match")
    if storage.recovery_shares.get(index):
        raise RuntimeError("Slip39: This mnemonic was already entered")

    # add mnemonic to storage
    if group_count > 1:
        # TODO: investigate why shares_remianing is bytes instead of bytearray
        shares_remaining = bytearray(shares_remaining)
        shares_remaining[group_index] = shares_remaining[group_index] - 1
        storage.recovery.set_slip39_shares_remaining(shares_remaining)
    else:
        remaining -= 1
        storage.recovery.set_remaining(remaining)

    storage.recovery_shares.set(index + group_index * _GROUP_STORAGE_OFFSET, words)

    # TODO: investigate why attempting to strip bytearray we get an error
    if remaining != 0 or (
        shares_remaining and len(bytes(shares_remaining).strip(b"\x00")) != 0
    ):
        return None  # we need more shares

    # combine shares and return the master secret
    mnemonics = storage.recovery_shares.fetch()
    identifier, iteration_exponent, secret = slip39.combine_mnemonics(mnemonics)
    return secret
