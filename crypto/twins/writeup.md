## twins
RSA暗号の問題です。
```python=
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

```
一般的なRSA暗号と異なる部分として、平文`m`の暗号化に用いる公開鍵`n1`とは別に`n2`が定義され、出力されています。
$n_1 = p q_1$、$n_2 = p q_2$ であるため、$$ p = \gcd(n_1, n_2) $$が成り立ちます。
$p$が分かるなら、$$q_1=n_1/p$$ $$d \equiv e^{-1} \pmod{(p-1)(q_1-1)}$$と復号に必要なパラメータが求められます。
