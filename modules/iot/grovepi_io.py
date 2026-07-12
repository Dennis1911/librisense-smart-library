"""Minimal, Python-3-safe GrovePi+ I/O layer for LibriSense.

The vendor `grovepi` library (1.0.4, written for Python 2) is broken on
Python 3.13: its analogRead masks the underlying I2C I/O error and then
crashes parsing it ("'int' object is not subscriptable"). The root cause is
the Raspberry Pi BCM2835 I2C clock-stretching bug — SMBus *block* reads
(`read_i2c_block_data`) fail against the GrovePi ATmega with OSError(5).

The fix used here:
  1. Lower the bus speed: dtparam=i2c_arm_baudrate=50000 in config.txt.
  2. Use raw I2C transactions (`i2c_rdwr` + `i2c_msg`) instead of SMBus block
     reads, with a short settle delay between write and read.

This module implements just what LibriSense needs: analog read, digital
read, digital write, and pin mode. It talks the GrovePi firmware protocol
directly. Tested working on a Pi 3 B+ with GrovePi+ on 2026-06-10.
"""
from __future__ import annotations

import time
from smbus2 import SMBus, i2c_msg

GROVEPI_ADDRESS = 0x04

# GrovePi firmware command bytes.
CMD_DIGITAL_READ = 1
CMD_DIGITAL_WRITE = 2
CMD_ANALOG_READ = 3
CMD_ANALOG_WRITE = 4
CMD_PIN_MODE = 5

# Register the GrovePi firmware expects as the first byte of every write.
_REG = 1

# Delay between command write and result read. The ATmega needs time to do
# the ADC conversion + the clock-stretching workaround needs breathing room.
_SETTLE_S = 0.10


class GrovePi:
    """Thin wrapper over the GrovePi+ firmware on I2C bus 1.

    Not thread-safe — wrap calls in a lock if multiple threads read sensors.
    """

    def __init__(self, bus_no: int = 1, address: int = GROVEPI_ADDRESS,
                 settle_s: float = _SETTLE_S) -> None:
        self._bus = SMBus(bus_no)
        self._addr = address
        self._settle = settle_s

    def close(self) -> None:
        self._bus.close()

    def __enter__(self) -> "GrovePi":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- low-level protocol -------------------------------------------------
    def _write_cmd(self, cmd: int, p1: int = 0, p2: int = 0, p3: int = 0) -> None:
        self._bus.i2c_rdwr(i2c_msg.write(self._addr, [_REG, cmd, p1, p2, p3]))

    def _read(self, n: int) -> list[int]:
        msg = i2c_msg.read(self._addr, n)
        self._bus.i2c_rdwr(msg)
        return list(msg)

    # --- public API ---------------------------------------------------------
    def analog_read(self, pin: int) -> int:
        """Read an analog port A0..A2 -> 0..1023 (10-bit ADC)."""
        self._write_cmd(CMD_ANALOG_READ, pin)
        time.sleep(self._settle)
        data = self._read(4)
        return data[1] * 256 + data[2]

    def digital_read(self, pin: int) -> int:
        """Read a digital port -> 0 or 1."""
        self._write_cmd(CMD_DIGITAL_READ, pin)
        time.sleep(self._settle)
        return self._read(1)[0]

    def digital_write(self, pin: int, value: int) -> None:
        """Drive a digital port low (0) or high (1)."""
        self._write_cmd(CMD_DIGITAL_WRITE, pin, 1 if value else 0)
        time.sleep(self._settle)

    def analog_write(self, pin: int, value: int) -> None:
        """PWM-write 0..255 to a PWM-capable port (GrovePi: D3, D5, D6).

        For a piezo buzzer a low duty cycle gives a quieter tone."""
        self._write_cmd(CMD_ANALOG_WRITE, pin, max(0, min(255, value)))
        time.sleep(self._settle)

    def pin_mode(self, pin: int, mode: str) -> None:
        """Set a pin to 'INPUT' or 'OUTPUT'."""
        self._write_cmd(CMD_PIN_MODE, pin, 1 if mode.upper() == "OUTPUT" else 0)
        time.sleep(self._settle)


if __name__ == "__main__":
    # Quick self-test / port scan: prints all analog + digital ports once.
    with GrovePi() as g:
        print("Analog ports:")
        for p in (0, 1, 2):
            try:
                print(f"  A{p}: {g.analog_read(p)}")
            except Exception as e:  # noqa: BLE001 - diagnostic tool
                print(f"  A{p}: ERROR {e!r}")
        print("Digital ports:")
        for p in (2, 3, 4, 5, 6, 7, 8):
            try:
                print(f"  D{p}: {g.digital_read(p)}")
            except Exception as e:  # noqa: BLE001
                print(f"  D{p}: ERROR {e!r}")
