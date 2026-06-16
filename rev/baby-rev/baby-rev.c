#include <stdio.h>

int main()
{
    const unsigned char xorFlag[] = {0xeb,0xfc,0xee,0xbc,0xea,0xf3,0xe4,0xb8,0xb8,0xe3,0xd7,0xe5,0xb8,0xe5,0xd7,0xe6,0xb8,0xd7,0xe0,0xbc,0xe6,0xec,0xfb,0xd7,0xe2,0xfd,0xfb,0xfc,0xd7,0xf0,0xb8,0xfa,0xa9,0xf5};
    const int xorKey = 0x88;
    const int len = 34;

    unsigned char inp[64] = {0};
    printf("INPUT > ");


    if (scanf("%63s", inp) != 1) {
        printf("Wrong:(\n");
        return -1;
    }

    int inputLen = 0;
    while (inp[inputLen] != '\0') inputLen++;
    if (inputLen != len) {
        printf("Wrong:(\n");
        return -1;
    }

    for (int i = 0; i < len; i++) {
        if ((inp[i] ^ xorKey) != xorFlag[i]) {
            printf("Wrong:(\n");
            return -1;
        }
    }

    printf("Correct:)\n");
    return 0;
}