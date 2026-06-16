import os
from math import gcd
from Crypto.Util.number import getPrime, bytes_to_long

flag = os.environ.get("FLAG", "ctf4b{dummy}")
e = 65537
while True:
    p = -getPrime(384)
    q = getPrime(384)
    if gcd((p - 1) * (q - 1), e) == 1:
        break
n = p * q
d = pow(e, -1, (p - 1) * (q - 1))

m1 = bytes_to_long(flag.encode())
c = pow(m1, e, n)
m2 = pow(c, d, n)

print(f"{n = }")
print(f"{e = }")
print(f"{c = }")
print(f"{m2 = }")

if m1 != m2:
    print("why!?")
