import os

p = 2^56 - 5
K.<i> = GF(p^2, modulus=[1, 0, 1])
d = 9
N = 16

class PRNG:
    def __init__(self):
        self.M = random_matrix(K, d, d)
        self.state = random_vector(K, d)

    def next(self):
        self.state = self.M * self.state
        return self.state[0]

flag = os.environ.get("FLAG", "ctf4b{" + "_" * 89 + "}")
assert len(flag) == 6 * N
prng = PRNG()
print(prng.M.list())
for idx in range(0, len(flag), 6):
    m = K.from_bytes(flag[idx:idx+6].encode())
    print(m + prng.next())
