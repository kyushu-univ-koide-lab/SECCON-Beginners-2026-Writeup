#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MAX_MEMOS 4
#define MAX_MEMO_SIZE 0x180
#define MAX_WORKFLOW_STEPS 32
#define POLICY_PUBLIC 1

enum workflow_op {
    OP_BIND_INPUT, OP_ATTACH_OUTPUT, OP_SELECT_POLICY, OP_OPEN_INPUT,
    OP_READ_INPUT, OP_PUBLISH_OUTPUT, OP_FINISH, OP_COUNT,
};

struct memo {
    size_t size;
    size_t write_limit;
    char *text;
};

struct workflow_step {
    unsigned char op;
    unsigned short metrics;
    uintptr_t arg0;
    uintptr_t arg1;
};

struct action_catalog {
    void **table;
    size_t count;
};

struct workflow {
    struct workflow_step *steps;
    struct action_catalog *catalog;
    size_t pc;
    size_t steps_run;

    char *input_path;
    char *output;
    size_t output_limit;
    size_t bytes_read;
    size_t output_size;

    int input_fd;
    unsigned int policy;
    unsigned int metrics;
};

static struct memo memos[MAX_MEMOS];
static struct workflow *workflow;
static void *action_table[OP_COUNT];
static struct action_catalog default_catalog;

static unsigned long read_ulong(void) {
    char buf[0x30];

    if (!fgets(buf, sizeof(buf), stdin)) {
        exit(0);
    }
    return strtoul(buf, NULL, 0);
}

static void *xmalloc(size_t size) {
    void *p = malloc(size);
    if (!p) {
        puts("malloc failed");
        exit(1);
    }
    return p;
}

static void read_data(char *buf, size_t size) {
    ssize_t n;

    n = read(STDIN_FILENO, buf, size);
    if (n < 0) {
        perror("read");
        exit(1);
    }
    if ((size_t)n < size) {
        buf[n] = '\0';
    }
}

static struct memo *select_memo(int used) {
    unsigned long idx;

    printf("idx> ");
    idx = read_ulong();
    if (idx >= MAX_MEMOS) {
        puts("invalid index");
        return NULL;
    }
    if (used && !memos[idx].text) {
        puts("empty");
        return NULL;
    }
    if (!used && memos[idx].text) {
        puts("slot is busy");
        return NULL;
    }
    return &memos[idx];
}

static void add_memo(void) {
    struct memo *m = select_memo(0);
    size_t size;

    if (!m) return;

    printf("size> ");
    size = read_ulong();
    if (size == 0 || size > MAX_MEMO_SIZE) {
        puts("invalid size");
        return;
    }

    m->text = xmalloc(size);
    m->size = size;
    m->write_limit = size;

    printf("memo> ");
    read_data(m->text, size);
    puts("saved");
}

static void rewrite_memo(void) {
    struct memo *m = select_memo(1);

    if (!m) return;

    printf("memo> ");
    read_data(m->text, m->write_limit);
    puts("rewritten");
}

static void shrink_memo(void) {
    struct memo *m = select_memo(1);
    size_t size;
    size_t copy_size;
    char *p;

    if (!m) return;

    printf("size> ");
    size = read_ulong();
    if (size == 0 || size >= m->size) {
        puts("invalid size");
        return;
    }

    p = xmalloc(size);
    copy_size = size < m->size ? size : m->size;
    memcpy(p, m->text, copy_size);
    free(m->text);

    m->text = p;
    m->size = size;
    puts("shrunk");
}

static void inspect_memo(void) {
    struct memo *m = select_memo(1);
    uintptr_t addr;

    if (!m) return;

    addr = (uintptr_t)m->text;
    printf("locator page: 0x%lx\n", addr >> 12);
    printf("locator slot: 0x%03lx\n", addr & 0xfff);
    printf("memo: %.32s\n", m->text);
}

static void execute_workflow(struct workflow *wf) {
    struct action_catalog *catalog;
    struct workflow_step *step;
    void *action;

    action_table[OP_BIND_INPUT] = &&bind_input;
    action_table[OP_ATTACH_OUTPUT] = &&attach_output;
    action_table[OP_SELECT_POLICY] = &&select_policy;
    action_table[OP_OPEN_INPUT] = &&open_input;
    action_table[OP_READ_INPUT] = &&read_input;
    action_table[OP_PUBLISH_OUTPUT] = &&publish_output;
    action_table[OP_FINISH] = &&finish;

    if (!wf) return;

next_step:
    catalog = wf->catalog;
    if (!wf->steps || !catalog || !catalog->table) {
        puts("no workflow");
        return;
    }
    if (++wf->steps_run > MAX_WORKFLOW_STEPS) {
        puts("workflow budget exceeded");
        return;
    }

    step = &wf->steps[wf->pc++];
    if (step->op >= catalog->count) {
        puts("unknown workflow step");
        return;
    }
    if (step->metrics) {
        goto collect_metrics;
    }

    action = catalog->table[step->op];
    goto *action;

bind_input:
    wf->input_path = (char *)step->arg0;
    goto next_step;

attach_output:
    wf->output = (char *)step->arg0;
    wf->output_limit = (size_t)step->arg1;
    goto next_step;

select_policy:
    wf->policy = (unsigned int)step->arg0;
    goto next_step;

open_input:
    if (wf->policy != POLICY_PUBLIC || !wf->input_path ||
        strncmp(wf->input_path, "docs/", 5) != 0) {
        puts("workflow policy rejected");
        wf->input_fd = -1;
        goto next_step;
    }
    wf->input_fd = open(wf->input_path, O_RDONLY);
    goto next_step;

read_input:
    if (wf->input_fd < 0 || !wf->output || wf->output_limit == 0 ||
        wf->output_limit > 0x200) {
        puts("workflow input rejected");
        wf->bytes_read = 0;
        wf->output_size = 0;
        goto next_step;
    }
    wf->bytes_read = (size_t)read(wf->input_fd, wf->output, wf->output_limit);
    wf->output_size = 0;
    goto next_step;

publish_output:
    if (wf->policy != POLICY_PUBLIC || wf->output_size == 0 ||
        wf->output_size > wf->output_limit) {
        puts("workflow not ready");
        goto next_step;
    }
    write(STDOUT_FILENO, wf->output, wf->output_size);
    write(STDOUT_FILENO, "\n", 1);
    goto next_step;

collect_metrics:
    wf->output_size = 0;
    wf->metrics++;
    wf->bytes_read = 0;
    wf->output_size = wf->bytes_read;
    goto next_step;

finish:
    return;
}

static void open_workflow(void) {
    static struct workflow_step empty_steps[1];

    if (workflow) {
        puts("workflow already open");
        return;
    }

    if (!action_table[OP_FINISH]) {
        execute_workflow(NULL);
        default_catalog.table = action_table;
        default_catalog.count = OP_COUNT;
    }
    memset(empty_steps, 0, sizeof(empty_steps));
    empty_steps[0].op = OP_FINISH;

    workflow = xmalloc(sizeof(*workflow));
    memset(workflow, 0, sizeof(*workflow));
    workflow->steps = empty_steps;
    workflow->catalog = &default_catalog;
    workflow->input_fd = -1;
    puts("workflow opened");
}

static void run_workflow(void) {
    if (!workflow) {
        puts("no workflow");
        return;
    }

    workflow->steps_run = 0;
    puts("running workflow");
    execute_workflow(workflow);
    exit(0);
}

static void menu(void) {
    puts("1. add memo\n2. rewrite memo\n3. shrink memo\n4. inspect memo");
    puts("5. open workflow\n6. run workflow\n7. quit");
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
        case 1: add_memo(); break;
        case 2: rewrite_memo(); break;
        case 3: shrink_memo(); break;
        case 4: inspect_memo(); break;
        case 5: open_workflow(); break;
        case 6: run_workflow(); break;
        case 7: puts("bye"); return 0;
        default:
            puts("invalid choice");
            return 0;
        }
    }
}
