from tenma.tenmaDcLib import Tenma72Base


class TestTenma72Base:
    def setup_cls(cls) -> None:
        cls.tm_base = Tenma72Base("COM3")

    def test_check_voltage(self) -> None:
        self.tm_base.checkVoltage()
