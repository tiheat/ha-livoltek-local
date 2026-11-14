"""Minimal Modbus TCP client and register decoding for Livoltek grid-tie inverters.

Kept free of Home Assistant imports so it can be unit tested on its own.

Each read opens a TCP connection, sends one "read holding registers" request and closes
the connection. The Hi-Flying Wi-Fi module (HF-LPB130) that bridges the inverter also
uploads data to the Livoltek cloud, and keeping a connection open permanently, or polling
register by register, interferes with that upload.
"""

from __future__ import annotations

import asyncio
import contextlib
import random
import struct
from dataclasses import dataclass

FUNCTION_READ_HOLDING = 0x03

# One request covers every register we use (4100..4157).
BLOCK_START = 4100
BLOCK_COUNT = 58

MODBUS_EXCEPTIONS = {
    0x01: "illegal function",
    0x02: "illegal data address",
    0x03: "illegal data value",
    0x04: "server device failure",
    0x0A: "gateway path unavailable",
    0x0B: "gateway target device failed to respond",
}


class LivoltekError(Exception):
    """Base error."""


class LivoltekConnectionError(LivoltekError):
    """The Wi-Fi module could not be reached or did not answer in time."""


class LivoltekModbusError(LivoltekError):
    """The inverter answered with a Modbus exception (for example, it is off at night)."""

    def __init__(self, code: int) -> None:
        self.code = code
        super().__init__(f"Modbus exception {code:#04x}: {MODBUS_EXCEPTIONS.get(code, 'unknown')}")


def build_request(transaction_id: int, unit_id: int, address: int, count: int) -> bytes:
    """Build a Modbus TCP 'read holding registers' request."""
    return struct.pack(">HHHBBHH", transaction_id, 0, 6, unit_id, FUNCTION_READ_HOLDING, address, count)


def parse_response(pdu: bytes, count: int) -> list[int]:
    """Parse the PDU (function code onwards) of a 'read holding registers' response."""
    if not pdu:
        raise LivoltekError("Empty Modbus response")
    function = pdu[0]
    if function & 0x80:
        raise LivoltekModbusError(pdu[1] if len(pdu) > 1 else 0)
    if function != FUNCTION_READ_HOLDING:
        raise LivoltekError(f"Unexpected function code {function:#04x}")
    byte_count = pdu[1]
    if byte_count != count * 2 or len(pdu) < 2 + byte_count:
        raise LivoltekError(f"Unexpected payload size {byte_count} for {count} registers")
    return list(struct.unpack(f">{count}H", pdu[2 : 2 + byte_count]))


async def read_holding_registers(
    host: str,
    port: int,
    unit_id: int,
    address: int,
    count: int,
    timeout: float = 5.0,
) -> list[int]:
    """Open a connection, read `count` holding registers starting at `address`, then close it."""
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
    except (TimeoutError, OSError) as err:
        raise LivoltekConnectionError(f"Cannot connect to {host}:{port}: {err}") from err

    transaction_id = random.randint(1, 0xFFFF)
    try:
        writer.write(build_request(transaction_id, unit_id, address, count))
        await writer.drain()
        header = await asyncio.wait_for(reader.readexactly(7), timeout)
        rx_id, protocol, length, _unit = struct.unpack(">HHHB", header)
        if rx_id != transaction_id or protocol != 0 or length < 2:
            raise LivoltekError("Malformed Modbus TCP header")
        pdu = await asyncio.wait_for(reader.readexactly(length - 1), timeout)
    except (TimeoutError, OSError, asyncio.IncompleteReadError) as err:
        raise LivoltekConnectionError(f"No answer from {host}:{port}: {err}") from err
    finally:
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()

    return parse_response(pdu, count)


@dataclass(frozen=True)
class LivoltekData:
    """Decoded inverter readings."""

    ac_power: float  # W
    frequency: float  # Hz
    pv1_voltage: float  # V
    pv1_current: float  # A
    pv1_power: float  # W
    pv2_voltage: float  # V
    pv2_current: float  # A
    pv2_power: float  # W
    temperature: int  # °C
    status: int
    energy_today: float  # kWh
    power_factor: float


def decode(registers: list[int]) -> LivoltekData:
    """Decode the 4100..4157 block.

    Register map identified against live data (Livoltek grid-tie inverter, Nov 2026):
    4100 AC power x0.1 W, 4101 grid frequency x0.01 Hz, 4112/4113/4115 PV1 voltage x0.1 V /
    current x0.01 A / power x0.1 W, 4116/4117/4119 PV2 (same scales), 4124 temperature °C,
    4125 status code, 4136 energy today x0.001 kWh, 4157 power factor x0.001.
    """
    if len(registers) != BLOCK_COUNT:
        raise LivoltekError(f"Expected {BLOCK_COUNT} registers, got {len(registers)}")

    def reg(address: int) -> int:
        return registers[address - BLOCK_START]

    return LivoltekData(
        ac_power=round(reg(4100) * 0.1, 1),
        frequency=round(reg(4101) * 0.01, 2),
        pv1_voltage=round(reg(4112) * 0.1, 1),
        pv1_current=round(reg(4113) * 0.01, 2),
        pv1_power=round(reg(4115) * 0.1, 1),
        pv2_voltage=round(reg(4116) * 0.1, 1),
        pv2_current=round(reg(4117) * 0.01, 2),
        pv2_power=round(reg(4119) * 0.1, 1),
        temperature=reg(4124),
        status=reg(4125),
        energy_today=round(reg(4136) * 0.001, 3),
        power_factor=round(reg(4157) * 0.001, 3),
    )


async def async_read(host: str, port: int, unit_id: int, timeout: float = 5.0) -> LivoltekData:
    """Read and decode the inverter block in a single request."""
    return decode(await read_holding_registers(host, port, unit_id, BLOCK_START, BLOCK_COUNT, timeout))
