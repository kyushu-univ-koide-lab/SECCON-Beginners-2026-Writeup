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