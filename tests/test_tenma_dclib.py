import pytest

from tenma.tenma_dc_lib import Tenma72Base, TenmaError


class TestTenma72Base:
    def setup_class(cls) -> None:  # noqa N805
        cls.tm_base = Tenma72Base("COM3")
        # cls.tm_base.check_channel
        # cls.tm_base.check_current
        # cls.tm_base.check_voltage
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

    def test_check_voltage(self) -> None:
        self.tm_base.check_voltage(1, 0)
        self.tm_base.check_voltage(1, 1000)
        with pytest.raises(TenmaError, match=""):
            self.tm_base.check_voltage(1, self.tm_base.MAX_MV + 1)
