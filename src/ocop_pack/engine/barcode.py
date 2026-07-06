from __future__ import annotations

from hashlib import sha256

LEFT_ODD = {
    "0": "0001101",
    "1": "0011001",
    "2": "0010011",
    "3": "0111101",
    "4": "0100011",
    "5": "0110001",
    "6": "0101111",
    "7": "0111011",
    "8": "0110111",
    "9": "0001011",
}
LEFT_EVEN = {
    "0": "0100111",
    "1": "0110011",
    "2": "0011011",
    "3": "0100001",
    "4": "0011101",
    "5": "0111001",
    "6": "0000101",
    "7": "0010001",
    "8": "0001001",
    "9": "0010111",
}
RIGHT = {
    "0": "1110010",
    "1": "1100110",
    "2": "1101100",
    "3": "1000010",
    "4": "1011100",
    "5": "1001110",
    "6": "1010000",
    "7": "1000100",
    "8": "1001000",
    "9": "1110100",
}
PARITY = {
    "0": "LLLLLL",
    "1": "LLGLGG",
    "2": "LLGGLG",
    "3": "LLGGGL",
    "4": "LGLLGG",
    "5": "LGGLLG",
    "6": "LGGGLL",
    "7": "LGLGLG",
    "8": "LGLGGL",
    "9": "LGGLGL",
}


def ean13_value(seed: str) -> str:
    base = "".join(str(byte % 10) for byte in sha256(seed.encode("utf-8")).digest())[:12]
    return f"{base}{_checksum(base)}"


def ean13_modules(seed: str) -> str:
    value = ean13_value(seed)
    modules = ["101"]
    parity = PARITY[value[0]]
    for digit, mode in zip(value[1:7], parity, strict=True):
        modules.append(LEFT_ODD[digit] if mode == "L" else LEFT_EVEN[digit])
    modules.append("01010")
    modules.extend(RIGHT[digit] for digit in value[7:])
    modules.append("101")
    return "".join(modules)


def _checksum(value: str) -> int:
    total = sum((3 if idx % 2 else 1) * int(digit) for idx, digit in enumerate(value))
    return (10 - total % 10) % 10
