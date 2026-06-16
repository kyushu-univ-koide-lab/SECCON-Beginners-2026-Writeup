#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MAX_NOTES 16
#define MAX_SIZE 0x100
#define APPROVAL_TOKEN 0x4a4f425f41505052ULL

struct note {
    size_t size;
    char *data;
};

struct job {
    char command[0x30];
    unsigned long token;
    unsigned long runs;
};

static struct note notes[MAX_NOTES];
static struct job *job;

static unsigned long read_ulong(void) {
    char buf[0x30];

    if (!fgets(buf, sizeof(buf), stdin)) {
        exit(0);
    }
    return strtoul(buf, NULL, 0);
}

static void read_note_data(char *buf, size_t size) {
    ssize_t n;

    n = read(STDIN_FILENO, buf, size);
    if (n < 0) {
        perror("read");
        exit(1);
    }
    buf[n] = '\0';
}

static size_t read_index(void) {
    unsigned long idx;

    printf("idx> ");
    idx = read_ulong();
    if (idx >= MAX_NOTES) {
        puts("invalid index");
        return MAX_NOTES;
    }
    return idx;
}

static void add_note(void) {
    size_t idx;
    size_t size;

    idx = read_index();
    if (idx >= MAX_NOTES) {
        return;
    }
    if (notes[idx].data) {
        puts("slot is busy");
        return;
    }

    printf("size> ");
    size = read_ulong();
    if (size == 0 || size > MAX_SIZE) {
        puts("invalid size");
        return;
    }

    notes[idx].data = malloc(size);
    if (!notes[idx].data) {
        puts("malloc failed");
        exit(1);
    }
    notes[idx].size = size;

    printf("body> ");
    read_note_data(notes[idx].data, size);
    puts("stored");
}

static void edit_note(void) {
    size_t idx;

    idx = read_index();
    if (idx >= MAX_NOTES) {
        return;
    }
    if (!notes[idx].data) {
        puts("empty");
        return;
    }

    printf("body> ");
    read_note_data(notes[idx].data, notes[idx].size);
    puts("updated");
}

static void show_note(void) {
    uintptr_t addr;
    size_t idx;

    idx = read_index();
    if (idx >= MAX_NOTES) {
        return;
    }
    if (!notes[idx].data) {
        puts("empty");
        return;
    }

    addr = (uintptr_t)notes[idx].data;
    printf("locator page: 0x%lx\n", addr >> 12);
    printf("locator slot: 0x%03lx\n", addr & 0xfff);
    printf("body: %s\n", notes[idx].data);
}

static void delete_note(void) {
    size_t idx;

    idx = read_index();
    if (idx >= MAX_NOTES) {
        return;
    }
    if (!notes[idx].data) {
        puts("empty");
        return;
    }

    free(notes[idx].data);
    notes[idx].data = NULL;
    notes[idx].size = 0;
    puts("deleted");
}

static void create_job(void) {
    if (job) {
        puts("job already exists");
        return;
    }

    job = malloc(sizeof(*job));
    if (!job) {
        puts("malloc failed");
        exit(1);
    }

    memset(job, 0, sizeof(*job));
    strcpy(job->command, "echo maintenance queued");
    puts("maintenance job queued");
}

static void run_job(void) {
    if (!job) {
        puts("no queued job");
        return;
    }

    job->runs++;
    if (job->token != APPROVAL_TOKEN) {
        printf("approval missing (%lu)\n", job->runs);
        return;
    }

    puts("dispatching approved job");
    system(job->command);
}

static void menu(void) {
    puts("1. add note");
    puts("2. edit note");
    puts("3. show note");
    puts("4. delete note");
    puts("5. queue maintenance job");
    puts("6. dispatch maintenance job");
    puts("7. quit");
    printf("> ");
}

static void setup(void) {
    setvbuf(stdin, NULL, _IONBF, 0);
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);
}

int main(void) {
    setup();

    for (;;) {
        menu();
        switch (read_ulong()) {
        case 1:
            add_note();
            break;
        case 2:
            edit_note();
            break;
        case 3:
            show_note();
            break;
        case 4:
            delete_note();
            break;
        case 5:
            create_job();
            break;
        case 6:
            run_job();
            break;
        case 7:
            puts("bye");
            return 0;
        default:
            puts("invalid choice");
            return 0;
        }
    }
}
