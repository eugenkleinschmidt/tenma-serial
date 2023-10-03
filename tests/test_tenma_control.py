try:
    from tenma_serial.tenma_control import main
except ModuleNotFoundError:
    from src.tenma_serial.tenma_control import main  # noqa F401


def test_main() -> None:
    pass  # main()
