## greenroom
```
        "PATH": "/app/bin",
```
で限定されたbinしか使えないなど制限が多かったので、`/proc/self/environ`を直接みにいくという方針です。`cat`は使えないので、printfを使いました。
```sh
mapfile -d '' arr < /proc/self/environ; printf "%s\n" "${arr[@]}"
```