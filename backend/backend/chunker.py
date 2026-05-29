import re
from dataclasses import dataclass

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_SECTION_NUM = re.compile(r"^([0-9]+(?:\.[0-9]+)*)[.\s]\s*(.*)$")


@dataclass
class StructureChunk:
    section: str
    heading: str
    text: str


def chunk_by_structure(markdown: str) -> list[StructureChunk]:
    chunks: list[StructureChunk] = []
    heading: str | None = None
    section = ""
    body: list[str] = []
    order = 0

    def flush() -> None:
        if heading is None:
            return
        content = "\n".join(body).strip()
        text = heading if not content else f"{heading}\n{content}"
        chunks.append(StructureChunk(section=section, heading=heading, text=text))

    for line in markdown.splitlines():
        match = _HEADING.match(line)
        if match:
            flush()
            order += 1
            raw = match.group(2).strip()
            numbered = _SECTION_NUM.match(raw)
            if numbered:
                section = numbered.group(1)
                heading = numbered.group(2).strip() or raw
            else:
                section = str(order)
                heading = raw
            body = []
        else:
            body.append(line)
    flush()
    return chunks
