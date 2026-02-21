import secrets
import struct
import base64
from typing import List, Union


class GaloisRingElement:
   
    K = 64
    D = 64
    MOD_MASK = (1 << K) - 1  # 2^64 - 1

    _POLY_REDUCER = [0] * D
    _POLY_REDUCER[0] = MOD_MASK  # -1
    _POLY_REDUCER[1] = MOD_MASK  # -1
    _POLY_REDUCER[3] = MOD_MASK  # -1
    _POLY_REDUCER[4] = MOD_MASK  # -1

    def __init__(self, coeffs: List[int] = None):
        
        if coeffs is None:
            self.coeffs = [0] * self.D
        else:
            if len(coeffs) != self.D:
                raise ValueError(f"Coefficients must be of length {self.D}")
            self.coeffs = [c & self.MOD_MASK for c in coeffs]

    def __repr__(self):
        return f"GRElement(deg={self.D}, [{self.coeffs[0]}, {self.coeffs[1]}, ...])"

    def _add_coeffs(self, c1: List[int], c2: List[int]) -> List[int]:
        return [(a + b) & self.MOD_MASK for a, b in zip(c1, c2)]

    def _sub_coeffs(self, c1: List[int], c2: List[int]) -> List[int]:
        return [(a - b) & self.MOD_MASK for a, b in zip(c1, c2)]

    def __add__(self, other: 'GaloisRingElement') -> 'GaloisRingElement':
        return GaloisRingElement(self._add_coeffs(self.coeffs, other.coeffs))

    def __sub__(self, other: 'GaloisRingElement') -> 'GaloisRingElement':
        return GaloisRingElement(self._sub_coeffs(self.coeffs, other.coeffs))

    def __neg__(self) -> 'GaloisRingElement':
        # -A = 0 - A
        return GaloisRingElement([(-c) & self.MOD_MASK for c in self.coeffs])

    def __mul__(self, other: 'GaloisRingElement') -> 'GaloisRingElement':

        product_len = 2 * self.D - 1
        product = [0] * product_len

        for i in range(self.D):
            if self.coeffs[i] == 0: continue
            for j in range(self.D):
                product[i + j] = (product[i + j] + self.coeffs[i] * other.coeffs[j]) & self.MOD_MASK


        for i in range(product_len - 1, self.D - 1, -1):
            coeff = product[i]
            if coeff == 0: continue

            base_idx = i - self.D
            product[base_idx + 0] = (product[base_idx + 0] + coeff * self._POLY_REDUCER[0]) & self.MOD_MASK
            product[base_idx + 1] = (product[base_idx + 1] + coeff * self._POLY_REDUCER[1]) & self.MOD_MASK
            product[base_idx + 3] = (product[base_idx + 3] + coeff * self._POLY_REDUCER[3]) & self.MOD_MASK
            product[base_idx + 4] = (product[base_idx + 4] + coeff * self._POLY_REDUCER[4]) & self.MOD_MASK



        return GaloisRingElement(product[:self.D])

    @classmethod
    def random(cls) -> 'GaloisRingElement':
        rand_coeffs = [secrets.randbits(cls.K) for _ in range(cls.D)]
        return cls(rand_coeffs)

    def to_string(self) -> str:

        # '<' = little-endian, 'Q' = unsigned long long (8 bytes)
        fmt = f'<{self.D}Q'
        packed_bytes = struct.pack(fmt, *self.coeffs)
        return base64.b64encode(packed_bytes).decode('utf-8')

    @classmethod
    def from_string(cls, s: str) -> 'GaloisRingElement':

        packed_bytes = base64.b64decode(s)
        fmt = f'<{cls.D}Q'
        try:
            coeffs = list(struct.unpack(fmt, packed_bytes))
            return cls(coeffs)
        except struct.error:
            raise ValueError("Invalid string format for GaloisRingElement")




if __name__ == "__main__":
    print("--- Testing Galois Ring (2^64, 64) ---")

    a = GaloisRingElement.random()
    b = GaloisRingElement.random()
    print(f"Element A (preview): {a.coeffs[:5]}...")

    s_a = a.to_string()
    print(f"Serialized A (len={len(s_a)}): {s_a[:20]}...")
    a_recovered = GaloisRingElement.from_string(s_a)
    assert a.coeffs == a_recovered.coeffs
    print("Serialization check: PASS")

    c = a + b
    expected_0 = (a.coeffs[0] + b.coeffs[0]) & ((1 << 64) - 1)
    assert c.coeffs[0] == expected_0
    print("Addition check: PASS")

    d = c - b
    assert d.coeffs == a.coeffs
    print("Subtraction check: PASS")

    coeffs_one = [0] * 64
    coeffs_one[0] = 1
    one = GaloisRingElement(coeffs_one)

    prod = a * one
    assert prod.coeffs == a.coeffs
    print("Multiplication (Identity) check: PASS")

    mul_res = a * b
    print("Multiplication check: Executed (Value verification omitted for random inputs)")

