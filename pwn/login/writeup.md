# login まずは手始めにadminを目指しましょう
配布物：main.c(以下のコード)、chall（ELFバイナリファイル）
```c
#include <stdio.h>

struct user {
    char username[0x10];
    int is_admin;
};

void win() {
    system("/bin/sh");
}

static void setup(void) {
    setvbuf(stdin, NULL, _IONBF, 0);
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);
}

int main() {
    setup();

    struct user normal_user = {0};
    printf("Input username: ");
    fgets(normal_user.username, sizeof(struct user), stdin);
    normal_user.username[strcspn(normal_user.username, "\n")] = '\0';
    if (normal_user.is_admin) {
        printf("Welcome, admin %s!\n", normal_user.username);
        win();
    } else {
        printf("Welcome, %s!\n", normal_user.username);
    }
    return 0;
}
```
コードを見てみるとwin関数をよびだせば、終わりそうです。そのためにはnormal_user.is_adminがTrueになる必要があります。初期値は当然「0」なので（struct user normal_user = {0}）書き換えなければ、Falseになってelseになってしまいます。しかし、fgetsが読み込むバイト数を見てみると、user構造体は16byte＋4byteで構成されており、fgetsはsizeof(struct user)となっているので、20byte読みます。本当は、設計者の想定としては、16byte（username）だけのはずです。このBOFを利用すれば、入力に「1」を17文字送り込めば、is_adminが0x0000000１となり、非ゼロなので、win関数に飛べます。後は、ls -> cat flag.txt -> ctf4b{l0g1n_r00t_us4r!} の流れでflagゲットです！