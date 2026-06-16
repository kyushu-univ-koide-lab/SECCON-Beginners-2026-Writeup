import os
from math import gcd
from pathlib import Path

from Crypto.Util.number import bytes_to_long, getPrime, long_to_bytes

FLAG = os.getenv("FLAG", "ctf4b{dummy_flag}").encode()
m = bytes_to_long(FLAG)

p = getPrime(512)
q1 = getPrime(512)
q2 = getPrime(512)
n1 = p * q1
n2 = p * q2
e = 65537
c = pow(m, e, n1)

assert m < n1
assert gcd(n1, n2) == p
assert gcd(n1, n2) != 1

phi = (p - 1) * (q1 - 1)
d = pow(e, -1, phi)
assert long_to_bytes(pow(c, d, n1)) == FLAG

output = "\n".join([
    f"n1 = {n1}",
    f"n2 = {n2}",
    f"e = {e}",
    f"c = {c}",
])

Path(__file__).with_name("output.txt").write_text(output + "\n")
print(output)
