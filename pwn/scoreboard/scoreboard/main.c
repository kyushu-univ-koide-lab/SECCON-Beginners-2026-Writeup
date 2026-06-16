// chall.c
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>

#define SCORE_COUNT 32
#define NAME_SIZE 0x80

static uint64_t scores[SCORE_COUNT];

static void setup(void) {
    setvbuf(stdin, NULL, _IONBF, 0);
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);
}

static void read_line(char *buf, size_t size) {
    if (size == 0) {
        return;
    }

    size_t i = 0;
    char c = 0;

    while (i + 1 < size) {
        ssize_t n = read(STDIN_FILENO, &c, 1);
        if (n <= 0) {
            exit(0);
        }

        if (c == '\n') {
            break;
        }

        buf[i++] = c;
    }

    buf[i] = '\0';

    if (c != '\n') {
        while (read(STDIN_FILENO, &c, 1) == 1 && c != '\n') {
        }
    }
}

static long read_long(void) {
    char buf[0x40];

    read_line(buf, sizeof(buf));
    return strtol(buf, NULL, 0);
}

static uint64_t read_u64(void) {
    char buf[0x40];

    read_line(buf, sizeof(buf));
    return strtoull(buf, NULL, 0);
}

static void health_check(void) {
    puts("[*] running health check");
    system("/bin/true");
    puts("[*] service is ready");
}

static void submit_score(void) {
    long rank;
    uint64_t score;

    printf("rank:");
    rank = read_long();
    if (rank >= SCORE_COUNT) {
        puts("invalid rank");
        exit(1);
    }

    printf("score:");
    score = read_u64();

    scores[rank] = score;
}

static void submit_feedback(void) {
    char feedback[0x60];
    printf("feedback:");
    read(STDIN_FILENO, feedback, 0x200);
}

int main(void) {
    setup();

    for (int i = 0; i < SCORE_COUNT; i++) {
        scores[i] = 1000 + i;
    }

    puts("=== Score Submitter ===");

    health_check();
    submit_score();
    submit_feedback();

    return 0;
}