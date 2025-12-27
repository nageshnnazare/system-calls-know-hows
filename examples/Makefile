# Makefile for system call examples
# Usage: make all

CC = gcc
CFLAGS = -Wall -Wextra -g
PTHREAD_FLAGS = -pthread
TARGETS = process_manager file_operations memory_demo pipe_demo signal_demo resource_limits shm_demo threads_demo tcp_server tcp_client

.PHONY: all clean

all: $(TARGETS)

process_manager: process_manager.c
	$(CC) $(CFLAGS) -o $@ $<

file_operations: file_operations.c
	$(CC) $(CFLAGS) -o $@ $<

memory_demo: memory_demo.c
	$(CC) $(CFLAGS) -o $@ $<

pipe_demo: pipe_demo.c
	$(CC) $(CFLAGS) -o $@ $<

signal_demo: signal_demo.c
	$(CC) $(CFLAGS) -o $@ $<

resource_limits: resource_limits.c
	$(CC) $(CFLAGS) -o $@ $<

shm_demo: shm_demo.c
	$(CC) $(CFLAGS) -o $@ $<

threads_demo: threads_demo.c
	$(CC) $(CFLAGS) $(PTHREAD_FLAGS) -o $@ $<

tcp_server: tcp_server.c
	$(CC) $(CFLAGS) -o $@ $<

tcp_client: tcp_client.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f $(TARGETS)
	rm -f test_syscall.txt redirect_output.txt mmap_test.txt
	rm -f *.o

help:
	@echo "Available targets:"
	@echo "  all             - Build all examples"
	@echo "  clean           - Remove built files"
	@echo "  process_manager - Build process management demo"
	@echo "  file_operations - Build file operations demo"
	@echo "  memory_demo     - Build memory management demo"
	@echo "  pipe_demo       - Build pipe demo"
	@echo "  signal_demo     - Build signal demo"
	@echo "  resource_limits - Build resource limits demo"
	@echo "  shm_demo        - Build shared memory demo"
	@echo "  threads_demo    - Build POSIX threads demo"
	@echo "  tcp_server      - Build TCP server example"
	@echo "  tcp_client      - Build TCP client example"

