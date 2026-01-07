class PrinterDriver:
    def print_text(self, text: str) -> bool:
        raise NotImplementedError


class DummyPrinterDriver(PrinterDriver):
    def print_text(self, text: str) -> bool:
        print("[DummyPrinter] printing...\n")
        print(text)
        return True
