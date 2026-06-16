import os
import random
import sys

FLAG = os.getenv("FLAG", "ctf4b{dummy_flag}")
ROUNDS = 5
MAX_NAME_LENGTH = 64
MAX_GUESS_LENGTH = 16


def read_limited(prompt, max_length):
    sys.stdout.write(prompt)
    sys.stdout.flush()

    line = sys.stdin.readline(max_length + 2)
    if not line:
        sys.exit()

    value = line.rstrip("\r\n")
    if len(value) > max_length or (not line.endswith("\n") and len(line) > max_length):
        print("wrong")
        sys.exit()

    return value.strip()


print("=== Omikuji ===")
print("Tell me your name, and I will draw your fortune.")
name = read_limited("name > ", MAX_NAME_LENGTH)
random.seed(name)

print(f"Welcome, {name}!")
print(f"Guess the next {ROUNDS} omikuji numbers to get the flag.")

for i in range(ROUNDS):
    x = random.randint(1, 1000000)
    try:
        guess = int(read_limited(f"guess {i + 1} > ", MAX_GUESS_LENGTH))
    except ValueError:
        print("wrong")
        exit()

    if guess != x:
        print("wrong")
        exit()

print(f"Congratulations! Here is your flag: {FLAG}")
