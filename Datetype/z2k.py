import secrets
import struct
import base64
from typing import Union, Type
from Datetype.GR import *

class Z2kElement:

    K = 64
    MOD_MASK = (1 << K) - 1

    def __init__(self, value: int):
     
        self.value = value & self.MOD_MASK

    def __repr__(self):
        return f"Z2k({self.value})"

    def __add__(self, other: 'Z2kElement') -> 'Z2kElement':
        if isinstance(other, int): 
            return Z2kElement(self.value + other)
        return Z2kElement(self.value + other.value)

    def __sub__(self, other: 'Z2kElement') -> 'Z2kElement':
        if isinstance(other, int):
            return Z2kElement(self.value - other)
        return Z2kElement(self.value - other.value)

    def __neg__(self) -> 'Z2kElement':
        # -A = 0 - A
        return Z2kElement(-self.value)

    def __mul__(self, other: 'Z2kElement') -> 'Z2kElement':
        if isinstance(other, int):
            return Z2kElement(self.value * other)
        return Z2kElement(self.value * other.value)

    def __eq__(self, other):
        if isinstance(other, int):
            return self.value == (other & self.MOD_MASK)
        return self.value == other.value

    @classmethod
    def random(cls) -> 'Z2kElement':
        return cls(secrets.randbits(cls.K))

    def to_string(self) -> str:
        # <Q : Little-endian unsigned long long (8 bytes)
        packed_bytes = struct.pack('<Q', self.value)
        return base64.b64encode(packed_bytes).decode('utf-8')

    @classmethod
    def from_string(cls, s: str) -> 'Z2kElement':
        try:
            packed_bytes = base64.b64decode(s)
            val = struct.unpack('<Q', packed_bytes)[0]
            return cls(val)
        except struct.error:
            raise ValueError("Invalid string format for Z2kElement")

    def to_galois_ring(self, gr_class) -> 'GaloisRingElement':
        coeffs = [0] * gr_class.D
        # 将常数项设为当前值
        coeffs[0] = self.value
        return gr_class(coeffs)



if __name__ == "__main__":
   
    print("--- Testing Z2k Element (2^64) ---")

    z1 = Z2kElement(10)
    z2 = Z2kElement(20)
    z3 = Z2kElement.random()

    assert (z1 + z2).value == 30
    assert (z1 - z2).value == (10 - 20) & ((1 << 64) - 1)  
    print("Arithmetic check: PASS")

    
    s_z3 = z3.to_string()
    z3_rec = Z2kElement.from_string(s_z3)
    assert z3 == z3_rec
    print(f"Serialization check: PASS ({s_z3})")
    
    scalar = Z2kElement(12345)
    gr_elem = scalar.to_galois_ring(GaloisRingElement)

    print(f"Converted GR Element: {gr_elem}")

    assert gr_elem.coeffs[0] == 12345
    assert gr_elem.coeffs[1] == 0
    assert len(gr_elem.coeffs) == 64

    print("Conversion to GR check: PASS")
