#include <stdio.h>

int main() {
    printf("Hello from ARM64!\\n");
    
    unsigned long x0 = 0x1111111111111111UL;
    unsigned long x1 = 0x2222222222222222UL;
    unsigned long x2 = 0x3333333333333333UL;
    
    printf("X0: 0x%016lx\\n", x0);
    printf("X1: 0x%016lx\\n", x1);
    printf("X2: 0x%016lx\\n", x2);
    
    printf("HASH: %016lx%016lx%016lx\\n", x0, x1, x2);
    
    return 0;
}
