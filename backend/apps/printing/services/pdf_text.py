from __future__ import annotations

from dataclasses import dataclass, field


def _escape_pdf_text(value: str) -> str:
    return (value or "").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


@dataclass
class SimpleTextPdfWriter:
    page_width: int = 612
    page_height: int = 792
    font_name: str = "Courier"
    font_size: int = 10
    line_height: int = 14
    left_margin: int = 40
    top_margin: int = 36
    bottom_margin: int = 36
    right_margin: int = 40
    pages: list[list[str]] = field(default_factory=lambda: [[]])

    def _available_lines_per_page(self) -> int:
        usable_height = self.page_height - self.top_margin - self.bottom_margin
        return max(1, usable_height // self.line_height)

    def _max_chars_per_line(self) -> int:
        usable_width = self.page_width - self.left_margin - self.right_margin
        approx_char_width = max(1.0, self.font_size * 0.6)
        return max(8, int(usable_width // approx_char_width))

    def _active_page(self) -> list[str]:
        if not self.pages:
            self.pages.append([])
        return self.pages[-1]

    def newPageIfNeeded(self, required_lines: int = 1) -> None:
        available = self._available_lines_per_page()
        if len(self._active_page()) + max(1, required_lines) > available:
            self.pages.append([])

    def _wrap_text(self, text: str) -> list[str]:
        max_chars = self._max_chars_per_line()
        words = (text or "").split()
        if not words:
            return [""]
        wrapped: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if len(candidate) <= max_chars:
                current = candidate
                continue
            wrapped.append(current)
            current = word
        wrapped.append(current)
        return wrapped

    def writeLine(self, text: str = "") -> None:
        for wrapped in self._wrap_text(text):
            self.newPageIfNeeded(1)
            self._active_page().append(wrapped)

    def writeTitle(self, text: str) -> None:
        self.writeLine((text or "").strip().upper())
        self.writeLine("")

    def writeKeyValue(self, label: str, value: str) -> None:
        self.writeLine(f"{(label or '').strip()}: {(value or '').strip()}")

    def _page_stream(self, lines: list[str]) -> str:
        start_y = self.page_height - self.top_margin
        content_lines = [
            "BT",
            f"/F1 {self.font_size} Tf",
            f"{self.line_height} TL",
            f"{self.left_margin} {start_y} Td",
        ]
        for index, line in enumerate(lines or [""]):
            content_lines.append(f"({_escape_pdf_text(line)}) Tj")
            if index < len(lines) - 1:
                content_lines.append("T*")
        content_lines.append("ET")
        return "\n".join(content_lines)

    def build(self) -> bytes:
        page_lines = [page if page else [""] for page in self.pages]
        objects = [
            "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
            f"2 0 obj << /Type /Pages /Kids [{' '.join(f'{3 + idx * 2} 0 R' for idx in range(len(page_lines)))}] /Count {len(page_lines)} >> endobj",
        ]
        next_obj = 3
        for lines in page_lines:
            stream = self._page_stream(lines)
            stream_bytes_len = len(stream.encode("latin-1", errors="ignore"))
            content_obj = next_obj + 1
            objects.append(
                f"{next_obj} 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.page_width} {self.page_height}] "
                f"/Contents {content_obj} 0 R /Resources << /Font << /F1 {3 + len(page_lines) * 2} 0 R >> >> >> endobj"
            )
            objects.append(f"{content_obj} 0 obj << /Length {stream_bytes_len} >> stream\n{stream}\nendstream endobj")
            next_obj += 2
        objects.append(f"{next_obj} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /{self.font_name} >> endobj")

        pdf = "%PDF-1.4\n"
        offsets: list[int] = []
        for obj in objects:
            offsets.append(len(pdf.encode("latin-1")))
            pdf += obj + "\n"
        xref_offset = len(pdf.encode("latin-1"))
        pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
        for offset in offsets:
            pdf += f"{offset:010d} 00000 n \n"
        pdf += f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF"
        return pdf.encode("latin-1", errors="ignore")
