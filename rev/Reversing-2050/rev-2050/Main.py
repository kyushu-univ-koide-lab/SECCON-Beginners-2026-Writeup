import qsharp

qsharp.eval(open("Encrypt.qs").read())

def main():
    guess = input("Enter the flag: ").strip()
    byte_values = [ord(c) for c in guess]

    ok = qsharp.eval(f"QuantumCipher2050.CheckFlag({byte_values})")

    if ok:
        print("Correct! The quantum vault opens.")
    else:
        print("Wrong. The vault stays sealed.")

if __name__ == "__main__":
    main()
