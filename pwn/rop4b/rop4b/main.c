#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>

const char flag_path[] = "/flag.txt";

__attribute__((naked, used))
void pop_rdi_ret(void) {
    __asm__(
        "pop %rdi;"
        "ret;"
    );
}

__attribute__((used))
void read_file(const char *path) {
    char buf[128];
    int fd;

    if (path == NULL) {
        puts("path is NULL");
        exit(1);
    }

    fd = open(path, O_RDONLY);
    if (fd < 0) {
        printf("%s not found\n", path);
        exit(1);
    }

    ssize_t n = read(fd, buf, sizeof(buf) - 1);
    if (n > 0) {
        buf[n] = '\0';
        puts(buf);
    }

    close(fd);
    exit(0);
}

void vuln(void) {
    char buf[64];

    puts("simple ROP challenge");
    puts("Call read_file(\"/flag.txt\") using ROP!");
    printf("> ");

    read(0, buf, 200);
}

int main(void) {
    setbuf(stdin, NULL);
    setbuf(stdout, NULL);
    setbuf(stderr, NULL);

    vuln();

    puts("bye!");
    return 0;
}