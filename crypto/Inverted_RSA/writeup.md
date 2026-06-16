## Inverted RSA
RSA暗号において、誤った復号・平文の情報から正しい平文を計算する問題です。
```python=
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
```

output.txtを見ると
```
why!?
```
と出力されている通り、`m2`の復号は間違えています。平文の値が負になることもおかしいですが、それ以外にも処理を間違えている点があります。
`p`が負の値になっているのがこの問題の特徴的な部分です。分かりやすさのため、以降は正の値の素数の組$(P,Q)$であって、$$P = -p,Q = q$$を満たすもので考えます。(符号はそのままにしておきますが、この問題ではこれ以降の値に絶対値をつけて読み替えても問題ありません)
$P,Q$を用いて、
$$N = -PQ$$$$\phi(N)=(-P-1)(Q-1)=-(P+1)(Q-1)$$$$ed\equiv1\pmod{{\phi(N)}}$$
と記述できます。これにより、正しく復号できていない原因は$\phi(N)$の定義が誤っているためであることが分かります。

ここから正しく復号する手順を考えましょう。
適当な整数$\alpha$と$\beta=-\alpha(P+1)$を用いて
$$ed\equiv1\pmod{{\phi(N)}}$$$$ \Leftrightarrow ed = -\alpha(P+1)(Q-1)+1$$$$\Leftrightarrow ed= \beta(Q-1)+1\tag{1}$$と変形できます。
さらに誤った$\phi(N)$により、$m_2$は
$$m_2\equiv c^d  \pmod{N}$$
を満たしています。この式に対し両辺を`e`乗すると、
$$m_2^e\equiv c^{{ed}} \pmod{N}$$
が成り立ちます。$N=-PQ$であることから、この合同式は$\pmod{Q}$においても成り立ち、
$$m_2^e\equiv c^{{ed}} \pmod{Q}\tag{2}$$が成り立ちます。
(1),(2)とフェルマーの小定理を組み合わせることで
$$m_2^e\equiv c \pmod{Q}$$$$\Leftrightarrow Q \mid (m_2^e-c)$$
が言えます。よって$Q$を
$$Q=\gcd(N,m_2^e-c)$$
と求められ、RSA暗号の復号に必要なパラメータを計算することができます。
実装上の注意点として、Pythonは`N<0`の時に`N`で割った余りを求めると結果が負になり、`long_to_bytes()`で復号できません。したがって復号する際に`N=abs(N)`としておくべきです。