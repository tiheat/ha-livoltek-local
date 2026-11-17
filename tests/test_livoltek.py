"""Tests for the Modbus client and register decoding."""

import asyncio
import struct

import pytest
from livoltek import (
    BLOCK_COUNT,
    BLOCK_START,
    LivoltekConnectionError,
    LivoltekError,
    LivoltekModbusError,
    async_read,
    build_request,
    decode,
    parse_response,
)

# Live sample captured on 2026-11-13 around 09:53 (4.2 kW of AC output).
SAMPLE = {
    4100: 41750,
    4101: 5999,
    4112: 2948,
    4113: 1331,
    4115: 39237,
    4116: 890,
    4117: 437,
    4119: 3889,
    4124: 51,
    4125: 3,
    4136: 6659,
    4157: 995,
}


def sample_registers() -> list[int]:
    registers = [0] * BLOCK_COUNT
    for address, value in SAMPLE.items():
        registers[address - BLOCK_START] = value
    return registers


def test_decode_scales_live_sample():
    data = decode(sample_registers())
    assert data.ac_power == 4175.0
    assert data.frequency == 59.99
    assert (data.pv1_voltage, data.pv1_current, data.pv1_power) == (294.8, 13.31, 3923.7)
    assert (data.pv2_voltage, data.pv2_current, data.pv2_power) == (89.0, 4.37, 388.9)
    assert data.temperature == 51
    assert data.status == 3
    assert data.energy_today == 6.659
    assert data.power_factor == 0.995


def test_decode_string_power_matches_voltage_times_current():
    data = decode(sample_registers())
    assert data.pv1_power == pytest.approx(data.pv1_voltage * data.pv1_current, rel=0.01)
    assert data.pv2_power == pytest.approx(data.pv2_voltage * data.pv2_current, rel=0.01)


def test_decode_rejects_wrong_size():
    with pytest.raises(LivoltekError):
        decode([0] * 10)


def test_build_request():
    assert build_request(1, 1, 4100, 58) == bytes.fromhex("00010000000601031004003a")


def test_parse_response_ok():
    pdu = bytes([0x03, 4]) + struct.pack(">2H", 10, 20)
    assert parse_response(pdu, 2) == [10, 20]


def test_parse_response_exception():
    with pytest.raises(LivoltekModbusError) as err:
        parse_response(bytes([0x83, 0x02]), 2)
    assert err.value.code == 0x02


def test_parse_response_wrong_size():
    with pytest.raises(LivoltekError):
        parse_response(bytes([0x03, 2, 0, 1]), 2)


async def _serve(handler):
    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1]


def _respond_with(pdu_builder):
    async def handler(reader, writer):
        request = await reader.readexactly(12)
        tid, _proto, _length, unit, _fc, _address, count = struct.unpack(">HHHBBHH", request)
        pdu = pdu_builder(count)
        writer.write(struct.pack(">HHHB", tid, 0, len(pdu) + 1, unit) + pdu)
        await writer.drain()
        writer.close()

    return handler


def test_async_read_end_to_end():
    async def run():
        registers = sample_registers()
        server, port = await _serve(
            _respond_with(lambda count: bytes([0x03, count * 2]) + struct.pack(f">{count}H", *registers))
        )
        async with server:
            return await async_read("127.0.0.1", port, 1, timeout=2)

    assert asyncio.run(run()).ac_power == 4175.0


def _ok_pdu(count):
    return bytes([0x03, count * 2]) + struct.pack(f">{count}H", *sample_registers())


def test_async_read_inverter_off_raises_modbus_error_without_retry():
    connections = []

    async def handler(reader, writer):
        connections.append(1)
        await _respond_with(lambda count: bytes([0x83, 0x0B]))(reader, writer)

    async def run():
        server, port = await _serve(handler)
        async with server:
            await async_read("127.0.0.1", port, 1, timeout=2, retry_delay=0)

    with pytest.raises(LivoltekModbusError):
        asyncio.run(run())
    assert len(connections) == 1


def test_async_read_skips_reply_to_another_request():
    """The Wi-Fi module sometimes hands us the answer to its own cloud polling first."""

    async def handler(reader, writer):
        request = await reader.readexactly(12)
        tid, _proto, _length, unit, _fc, _address, count = struct.unpack(">HHHBBHH", request)
        other = bytes([0x03, 4]) + struct.pack(">2H", 1, 2)
        writer.write(struct.pack(">HHHB", (tid + 1) & 0xFFFF, 0, len(other) + 1, unit) + other)
        pdu = _ok_pdu(count)
        writer.write(struct.pack(">HHHB", tid, 0, len(pdu) + 1, unit) + pdu)
        await writer.drain()
        writer.close()

    async def run():
        server, port = await _serve(handler)
        async with server:
            return await async_read("127.0.0.1", port, 1, timeout=2, retries=0)

    assert asyncio.run(run()).ac_power == 4175.0


def test_async_read_retries_after_invalid_reply():
    connections = []

    async def handler(reader, writer):
        connections.append(1)
        if len(connections) == 1:
            await reader.readexactly(12)
            writer.write(b"\x00\x01\x12\x34\x00\x00\x01")  # garbage header: protocol != 0
            await writer.drain()
            writer.close()
            return
        await _respond_with(_ok_pdu)(reader, writer)

    async def run():
        server, port = await _serve(handler)
        async with server:
            return await async_read("127.0.0.1", port, 1, timeout=2, retry_delay=0)

    assert asyncio.run(run()).ac_power == 4175.0
    assert len(connections) == 2


def test_async_read_gives_up_after_retries():
    connections = []

    async def handler(reader, writer):
        connections.append(1)
        await reader.readexactly(12)
        writer.close()  # closes without answering

    async def run():
        server, port = await _serve(handler)
        async with server:
            await async_read("127.0.0.1", port, 1, timeout=1, retries=2, retry_delay=0)

    with pytest.raises(LivoltekConnectionError):
        asyncio.run(run())
    assert len(connections) == 3


def test_async_read_unreachable_raises_connection_error():
    with pytest.raises(LivoltekConnectionError):
        asyncio.run(async_read("127.0.0.1", 1, 1, timeout=1, retry_delay=0))
