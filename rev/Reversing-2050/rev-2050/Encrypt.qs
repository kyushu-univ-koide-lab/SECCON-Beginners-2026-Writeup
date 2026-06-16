namespace QuantumCipher2050 {
    open Microsoft.Quantum.Intrinsic;

    function KeyBytes() : Int[] {
        return [0x51, 0x75, 0x61, 0x6E, 0x74, 0x75, 0x6D];
    }

    function CipherText() : Int[] {
        return [
            0x32, 0x01, 0x07, 0x5A, 0x16, 0x0E, 0x25, 0x34,
            0x19, 0x0D, 0x01, 0x2B, 0x24, 0x18, 0x30, 0x1B,
            0x15, 0x1B, 0x19, 0x2A, 0x3A, 0x3E, 0x07, 0x0D,
            0x0A, 0x55, 0x54, 0x4C, 0x2C
        ];
    }

    operation EncryptQuantum(dataByte : Int, keyByte : Int) : Int {
        use reg = Qubit[8];
        mutable result = 0;
        for i in 0..7 {
            if (dataByte >>> i) &&& 1 == 1 { X(reg[i]); }
            if (keyByte  >>> i) &&& 1 == 1 { X(reg[i]); }
        }
        for i in 0..7 {
            if M(reg[i]) == One { set result |||= (1 <<< i); }
        }
        ResetAll(reg);
        return result;
    }

    operation CheckFlag(input : Int[]) : Bool {
        let ct  = CipherText();
        let key = KeyBytes();
        let klen = Length(key);
        if Length(input) != Length(ct) {
            return false;
        }
        mutable ok = true;
        for i in 0..Length(input) - 1 {
            let kb = key[i % klen];
            let xored = EncryptQuantum(input[i], kb);
            if xored != ct[i] {
                set ok = false;
            }
        }
        return ok;
    }
}
