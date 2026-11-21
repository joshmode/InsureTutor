"""Normalize generated Chinese prose while retaining literal evidence quotes."""

from functools import lru_cache
import re

from opencc import OpenCC


_VERBATIM = re.compile(
    r'("[^"\n]*"|“[^”\n]*”|「[^」\n]*」|『[^』\n]*』|https?://[^\s]+)'
)


@lru_cache(maxsize=2)
def _converter(mode: str) -> OpenCC:
    converter = OpenCC(mode)
    # OpenCC initializes dictionaries lazily. Finish that mutation before
    # publishing the cached converter to concurrent request workers.
    converter.convert("")
    return converter


def normalize_generated_script(text: str, language: str) -> str:
    if language not in {"zh-Hans", "zh-Hant"} or len(text) > 16000:
        # The draft validator rejects oversized output; avoid conversion work
        # ahead of that authoritative check.
        return text
    converter = _converter("t2s" if language == "zh-Hans" else "s2hk")
    return "".join(
        part if index % 2 else converter.convert(part)
        for index, part in enumerate(_VERBATIM.split(text))
    )
