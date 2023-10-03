from unittest import mock

import pytest

try:
    # tests with tox
    from tenma_serial import (
        Mode,
        Tenma72Base,
        TenmaError,
        TrackingModeType,
    )
except ModuleNotFoundError:
    from src.tenma_serial import (
        Mode,
        Tenma72Base,
        TenmaError,
        TrackingModeType,
    )


class MockSerial:
    return_read: bytes = 0

    def __init__(self, *args, **kwargs):
        self.wait_cnt = 5

    def read(self, size) -> bytes:
        return self.return_read

    def write(self, cmd):
        pass

    @property
    def in_waiting(self):
        self.wait_cnt -= 1
        if self.wait_cnt == 0:
            self.wait_cnt = 5
            return 0
        return self.wait_cnt


class TestTenma72Base:
    def setup_class(cls) -> None:  # noqa N805
        with mock.patch("serial.Serial", new=MockSerial) as mock_serial:
            cls.tm_base = Tenma72Base("COM3")
            cls.mock_serial_instance = mock_serial

        # cls.tm_base.close
        # cls.tm_base.get_status
        # cls.tm_base.get_version
        # cls.tm_base.off
        # cls.tm_base.on
        # cls.tm_base.read_current
        # cls.tm_base.read_voltage
        # cls.tm_base.recall_conf
        # cls.tm_base.running_current
        # cls.tm_base.running_voltage
        # cls.tm_base.save_conf
        # cls.tm_base.save_conf_flow

    def test_check_channel(self) -> None:
        self.tm_base.check_channel(0)
        self.tm_base.check_channel(1)
        with pytest.raises(
            TenmaError, match=r"Channel CH2 not in range \(1 channels supported\)"
        ):
            self.tm_base.check_channel(self.tm_base.NCHANNELS + 1)

    def test_check_current(self) -> None:
        self.tm_base.check_current(1, 0)
        self.tm_base.check_current(1, 1000)
        with pytest.raises(
            TenmaError,
            match="Trying to set CH1 current to 5001mA, the maximum is 5000mA",
        ):
            self.tm_base.check_current(1, self.tm_base.MAX_MA + 1)

    def test_check_voltage(self) -> None:
        self.tm_base.check_voltage(1, 0)
        self.tm_base.check_voltage(1, 1000)
        with pytest.raises(
            TenmaError,
            match="Trying to set CH1 voltage to 30001mV, the maximum is 30000mV",
        ):
            self.tm_base.check_voltage(1, self.tm_base.MAX_MV + 1)

    def test_get_status(self) -> None:
        self.mock_serial_instance.return_read = b"\x00"
        assert Mode("C.C", "C.C", TrackingModeType(0)) == self.tm_base.get_status()

        self.mock_serial_instance.wait_cnt = 5
        self.mock_serial_instance.return_read = b"\x01"
        assert Mode("C.V", "C.C", TrackingModeType(0)) == self.tm_base.get_status()

        self.mock_serial_instance.wait_cnt = 5
        self.mock_serial_instance.return_read = b"\x02"
        assert Mode("C.C", "C.V", TrackingModeType(0)) == self.tm_base.get_status()

        self.mock_serial_instance.wait_cnt = 5
        self.mock_serial_instance.return_read = b"\xFF"
        assert Mode("C.V", "C.V", TrackingModeType(3), True, True, True, False) == self.tm_base.get_status()
