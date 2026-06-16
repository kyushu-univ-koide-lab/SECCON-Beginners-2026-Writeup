# defeat monster ボスは防御力が高そうですが、攻撃できますか？
配布物：main.c(以下のコード)、chall（ELFバイナリファイル）、Dockerfile、compose.yml
```c
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <string.h>

#define MONSTER_NAME_SIZE 0x20
#define BOSS_NAME_SIZE    0x10

#define MONSTER_POWER 50
#define BOSS_HP       300
#define BOSS_DEFENSE  1000
#define BOSS_BOUNTY   1337

struct monster {
    char name[MONSTER_NAME_SIZE];
    ssize_t power;
};

struct boss {
    char name[BOSS_NAME_SIZE];
    ssize_t hp;
    ssize_t defense;
    ssize_t bounty;
};

struct monster *my_monster;
struct boss *boss;

void setup(void) {
    setvbuf(stdin, NULL, _IONBF, 0);
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);
}

unsigned long read_ulong(void) {
    char buf[0x20];

    if (!fgets(buf, sizeof(buf), stdin)) {
        exit(0);
    }

    return strtoul(buf, NULL, 10);
}

void readn(char *buf, size_t size) {
    ssize_t n = read(STDIN_FILENO, buf, size);

    if (n < 0) {
        perror("read");
        exit(1);
    }
}

void read_cstring(char *buf, size_t size) {
    if (!fgets(buf, size, stdin)) {
        exit(0);
    }

    buf[strcspn(buf, "\n")] = '\0';
}

void win(void) {
    puts("You defeated the boss!");
    system("/bin/sh");
    exit(0);
}

void capture_monster(void) {
    if (my_monster) {
        puts("Your current monster ran away...");
    }

    puts("You captured a monster!");

    my_monster = malloc(sizeof(struct monster));
    if (!my_monster) {
        puts("malloc failed");
        exit(1);
    }

    printf("monster name> ");
    read_cstring(my_monster->name, sizeof(my_monster->name));
    my_monster->power = MONSTER_POWER;

    printf("captured %.*s (@%p) with power %zd\n",
           MONSTER_NAME_SIZE,
           my_monster->name,
           (void *)my_monster,
           my_monster->power);
}

void rename_monster(void) {
    if (!my_monster) {
        puts("You don't have a monster.");
        return;
    }

    puts("Give your monster a new name.");
    printf("new name> ");
    readn(my_monster->name, sizeof(my_monster->name));
}

void release_monster(void) {
    if (!my_monster) {
        puts("You don't have a monster.");
        return;
    }

    printf("released %.*s (@%p)\n",
           MONSTER_NAME_SIZE,
           my_monster->name,
           (void *)my_monster);

    free(my_monster);

    /* my_monster = NULL; */
}

void check_boss(void) {
    if (!boss) {
        puts("A boss appeared!");

        boss = malloc(sizeof(struct boss));
        if (!boss) {
            puts("malloc failed");
            exit(1);
        }

        strcpy(boss->name, "ctf_boss");
        boss->hp = BOSS_HP;
        boss->defense = BOSS_DEFENSE;
        boss->bounty = BOSS_BOUNTY;
    }

    printf("Boss (@%p): %.16s\n", (void *)boss, boss->name);
    printf("  hp      : %zd\n", boss->hp);
    printf("  defense : %zd\n", boss->defense);
}

void battle(void) {
    if (!my_monster) {
        puts("You don't have a monster.");
        return;
    }

    if (!boss) {
        puts("There is no boss.");
        return;
    }

    printf("%.*s attacks the boss!\n",
           MONSTER_NAME_SIZE,
           my_monster->name);

    printf("monster power: %zd, boss defense: %zd\n",
           my_monster->power,
           boss->defense);

    if (my_monster->power > boss->defense) {
        win();
    }

    puts("The attack was not effective...");
}

void menu(void) {
    puts("1. capture monster");
    puts("2. rename monster");
    puts("3. release monster");
    puts("4. check boss");
    puts("5. battle");
    puts("6. quit");
    printf("> ");
}

int main(void) {
    setup();

    while (1) {
        menu();

        switch (read_ulong()) {
            case 1:
                capture_monster();
                break;
            case 2:
                rename_monster();
                break;
            case 3:
                release_monster();
                break;
            case 4:
                check_boss();
                break;
            case 5:
                battle();
                break;
            case 6:
                puts("bye");
                return 0;
            default:
                puts("invalid choice");
                break;
        }
    }
}
```
初見でコード見た時、長すぎて泣きました。今年の出題者の傾向はcase文らしいです。そのため関数が大量にあるせいで長くなってます。（愚痴）
目的はボスを倒し、win関数を呼び出すことです。
そのためにまず、起動時のオプションの概要を軽く紹介しましょう。
1. capture monster モンスターを捕まえられます。名前を0x20の範囲で決められます。このゲームはクソゲーなので、捕まえたモンスターは全部攻撃力が50の雑魚モンスターになってます。
2. rename monster 捕まえたモンスターの名前を変更できます。
3. release monster 捕まえたモンスターを逃がせます。
4. check boss ボスを召喚でき、HPやDEFENSEを参照できます。ちなみに、HP：300、DEFENSE：1000というクソゲーになってます。嬉しいね。
5. battle ボスと戦えます。普通に戦っても負けますが、あることをすればあるいは？
6. quit ゲームから退出

それでは、脆弱性について考察していきましょう。
この問題では、なんか、意図的にコメントアウトされている箇所が存在しますね。release_monster関数の末尾を見て下さい、freeで解放を行ったにも関わらず、my_monsterのポインタをNULL上書きしていません。これはUse-after-freeという脆弱性になります。