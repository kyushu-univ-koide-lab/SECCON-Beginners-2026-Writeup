## old_virus
`hard`  
ur flag g0t pwned by s0me 2000s-era h4x0r. BRB st34l1ng ur d4t4 lol. …s3r10usly tho, g3t 1t b4ck.

[NOTE]: This is not real malware,so you don't have to worry about it doing anything bad to your computer :)

### 配布ファイル
- flag.txt.hacked
- old-virus

### 解法
とりあえず、old-virusがバイナリファイルなので、ghidraにかけてみる。
```clike=
undefined8 main(void)

{
  int iVar1;
  undefined8 uVar2;
  FILE *pFVar3;
  size_t sVar4;
  long in_FS_OFFSET;
  undefined1 local_518 [256];
  undefined1 local_418 [512];
  undefined1 local_218 [520];
  long local_10;
  
  local_10 = *(long *)(in_FS_OFFSET + 0x28);
  iVar1 = access("flag.txt.hacked",0);
  if (iVar1 == 0) {
    art_already();
    uVar2 = 0;
  }
  else {
    pFVar3 = fopen("flag.txt","rb");
    if (pFVar3 == (FILE *)0x0) {
      fprintf(stderr,"no %s here\n","flag.txt");
      uVar2 = 1;
    }
    else {
      sVar4 = fread(local_518,1,0x100,pFVar3);
      fclose(pFVar3);
      iVar1 = aes_ecb_encrypt(local_518,sVar4 & 0xffffffff,local_418);
      if (iVar1 < 0) {
        fwrite("aes failed\n",1,0xb,stderr);
        uVar2 = 1;
      }
      else {
        rc4("ImashyKey!Dontlookme!!!",0x17,local_418,local_218,iVar1);
        pFVar3 = fopen("flag.txt.hacked","wb");
        if (pFVar3 == (FILE *)0x0) {
          fprintf(stderr,"cannot write %s\n","flag.txt.hacked");
          uVar2 = 1;
        }
        else {
          fwrite(local_218,1,(long)iVar1,pFVar3);
          fclose(pFVar3);
          unlink("flag.txt");
          art_done();
          uVar2 = 0;
        }
      }
    }
  }
  if (local_10 != *(long *)(in_FS_OFFSET + 0x28)) {
                    /* WARNING: Subroutine does not return */
    __stack_chk_fail();
  }
  return uVar2;
}
```
flag.txtやflag.txt.hackedという文字列が出てきているので、これが暗号化のメイン関数と見て良さそう。分岐の条件や関数を軽く見てみる。エラー文や関数名を見ると、aes_ecb_encrypt()とrc4()という関数が暗号化の具体的な処理をしていることがわかる。先に、rc4()のほうを見てみる。
```clike=
void rc4(long param_1,int param_2,long param_3,long param_4,int param_5)

{
  byte bVar1;
  long in_FS_OFFSET;
  uint local_124;
  uint local_120;
  int local_11c;
  byte abStack_118 [264];
  long local_10;
  
  local_10 = *(long *)(in_FS_OFFSET + 0x28);
  for (local_124 = 0; (int)local_124 < 0x100; local_124 = local_124 + 1) {
    abStack_118[(int)local_124] = (byte)local_124;
  }
  local_120 = 0;
  for (local_124 = 0; (int)local_124 < 0x100; local_124 = local_124 + 1) {
    local_120 = (uint)*(byte *)(param_1 + (int)local_124 % param_2) +
                abStack_118[(int)local_124] + local_120 & 0xff;
    bVar1 = abStack_118[(int)local_124];
    abStack_118[(int)local_124] = abStack_118[(int)local_120];
    abStack_118[(int)local_120] = bVar1;
  }
  local_120 = 0;
  local_124 = 0;
  for (local_11c = 0; local_11c < param_5; local_11c = local_11c + 1) {
    local_124 = local_124 + 1 & 0xff;
    local_120 = local_120 + abStack_118[(int)local_124] & 0xff;
    bVar1 = abStack_118[(int)local_124];
    abStack_118[(int)local_124] = abStack_118[(int)local_120];
    abStack_118[(int)local_120] = bVar1;
    *(byte *)(param_4 + local_11c) =
         *(byte *)(param_3 + local_11c) ^
         abStack_118[(int)(uint)(byte)(abStack_118[(int)local_120] + abStack_118[(int)local_124])];
  }
  if (local_10 != *(long *)(in_FS_OFFSET + 0x28)) {
                    /* WARNING: Subroutine does not return */
    __stack_chk_fail();
  }
  return;
}
```
ただ、見づらいので、変数名や配列名をわかりやすいものにしたものがこれ。
```clike=
void rc4(long key, int key_len, long input, long output, int data_len)
{
    byte tmp;
    long stack_canary_storage;
    uint i;
    uint j;
    int n;
    byte S[264];  // 実際に使うのは先頭256バイト(S[0]~S[255])
    long stack_canary;

    stack_canary = *(long *)(stack_canary_storage + 0x28);

    /* KSA前半: Sボックスを0~255で初期化 */
    for (i = 0; (int)i < 0x100; i = i + 1) {
        S[(int)i] = (byte)i;
    }

    /* KSA後半: 鍵を使ってSボックスをシャッフル */
    j = 0;
    for (i = 0; (int)i < 0x100; i = i + 1) {
        j = (uint)*(byte *)(key + (int)i % key_len) +
            S[(int)i] + j & 0xff;
        tmp = S[(int)i];
        S[(int)i] = S[(int)j];
        S[(int)j] = tmp;
    }

    /* PRGA: キーストリーム生成とXORによる暗号化/復号 */
    j = 0;
    i = 0;
    for (n = 0; n < data_len; n = n + 1) {
        i = i + 1 & 0xff;
        j = j + S[(int)i] & 0xff;
        tmp = S[(int)i];
        S[(int)i] = S[(int)j];
        S[(int)j] = tmp;
        *(byte *)(output + n) =
            *(byte *)(input + n) ^
            S[(int)(uint)(byte)(S[(int)j] + S[(int)i])];
    }

    if (stack_canary != *(long *)(stack_canary_storage + 0x28)) {
        __stack_chk_fail();
    }
    return;
}
```
cryptoではないので、暗号化の内容の説明は省略するが、一般的なrc4暗号に見える。また、第一引数がkeyになっていることがわかる。main関数内の呼び出しを振り返ると、
```c
rc4("ImashyKey!Dontlookme!!!",0x17,local_418,local_218,iVar1);
```
のように鍵が書いてあるので、第一の鍵はgetできた。次は、aes_ecb_encyrpt()である。これもわかりやすくしたものを貼る。
```clike
int aes_ecb_encrypt(uchar *plaintext, int plaintext_len, uchar *ciphertext_out)
{
    int ret;
    EVP_CIPHER *cipher;
    long stack_canary_storage;
    int update_len;
    int total_len;
    EVP_CIPHER_CTX *ctx;
    long stack_canary;

    stack_canary = *(long *)(stack_canary_storage + 0x28);

    ctx = EVP_CIPHER_CTX_new();
    if (ctx == (EVP_CIPHER_CTX *)0x0) {
        ret = -1;
    }
    else {
        update_len = 0;
        total_len = 0;

        cipher = EVP_aes_128_ecb();

        /* AES-128-ECB の初期化
         * 鍵: "THISISNOTAESKEY!ImashyKey!Dontlookme!!!" の先頭16バイト
         *      = "THISISNOTAESKEY!" が実際のAES鍵として使われる
         * IV : NULL (ECBモードはIVを使わない) */
        EVP_EncryptInit_ex(ctx, cipher, (ENGINE *)0x0,
                           (uchar *)"THISISNOTAESKEY!ImashyKey!Dontlookme!!!",
                           (uchar *)0x0);

        /* 本体の暗号化(パディング前のブロック分) */
        EVP_EncryptUpdate(ctx, ciphertext_out, &update_len, plaintext, plaintext_len);
        total_len = update_len;

        /* 最終ブロック(PKCSパディング)の暗号化 */
        EVP_EncryptFinal_ex(ctx, ciphertext_out + update_len, &update_len);
        total_len = total_len + update_len;

        EVP_CIPHER_CTX_free(ctx);
        ret = total_len;
    }

    if (stack_canary != *(long *)(stack_canary_storage + 0x28)) {
        __stack_chk_fail();
    }
    return ret;
}
```
これも暗号の内容の説明は省略するが、EVPから始まる関数は、OpenSSLが提供する高レベル暗号化API(EVP:Envelope)であり、自作関数ではないので、調べれば仕様がわかる。既存の暗号を自作で少し変えているというトラップが仕掛けられていない。AES暗号で、ECBモードが用いられていて、鍵の情報`THISISNOTAESKEY!ImashyKey!Dontlookme!!!`も引数からわかるので、これで、復号の準備は整った。
### solver.py
```python!
#!/usr/bin/env python3
from Crypto.Cipher import AES

def rc4(key: bytes, data: bytes) -> bytes:
    """先ほどのGhidraの逆コンパイル結果をそのままPythonに書き直したもの"""
    S = list(range(256))
    j = 0
    key_len = len(key)
    for i in range(256):
        j = (key[i % key_len] + S[i] + j) & 0xff
        S[i], S[j] = S[j], S[i]

    out = bytearray(len(data))
    i = j = 0
    for n in range(len(data)):
        i = (i + 1) & 0xff
        j = (j + S[i]) & 0xff
        S[i], S[j] = S[j], S[i]
        k = S[(S[j] + S[i]) & 0xff]
        out[n] = data[n] ^ k
    return bytes(out)


def main():
    with open("flag.txt.hacked", "rb") as f:
        enc = f.read()

    # ① RC4を解除(暗号化と同じ処理を再度かければ元に戻る)
    rc4_key = b"ImashyKey!Dontlookme!!!"
    aes_ct = rc4(rc4_key, enc)

    # ② AES-128-ECBを復号
    aes_key = b"THISISNOTAESKEY!"  # 先頭16バイト
    cipher = AES.new(aes_key, AES.MODE_ECB)
    plain = cipher.decrypt(aes_ct)

    print("RC4後(AES暗号文)のhex:", aes_ct.hex())
    print("復号結果:")
    print(plain)


if __name__ == "__main__":
    main()
```
```bash!
# python solver.py
RC4後(AES暗号文)のhex: f52b4e3960ce9325d94df0055c515bd3b30aab441175843bfba24da0acaf85d3757f1e36c24752b9c4ee78af8f64e7c0
復号結果:
b'ctf4b{Y2K_n05t419ic_viru5_6ut_G2G}\n\r\r\r\r\r\r\r\r\r\r\r\r\r'
```
