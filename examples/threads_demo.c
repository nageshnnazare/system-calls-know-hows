/*
 * threads_demo.c - Demonstrates POSIX threads (pthreads)
 * 
 * Compile: gcc -pthread -o threads_demo threads_demo.c
 * Usage: ./threads_demo
 */

#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>

// Shared data
pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
pthread_cond_t cond = PTHREAD_COND_INITIALIZER;
int counter = 0;
int ready = 0;

// Simple thread function
void *simple_thread(void *arg) {
    long id = (long)arg;
    printf("[Thread %ld] Started\n", id);
    sleep(1);
    printf("[Thread %ld] Finished\n", id);
    return (void *)(id * 2);
}

// Thread with mutex
void *mutex_thread(void *arg) {
    for (int i = 0; i < 10000; i++) {
        pthread_mutex_lock(&mutex);
        counter++;
        pthread_mutex_unlock(&mutex);
    }
    return NULL;
}

// Producer thread
void *producer(void *arg) {
    for (int i = 0; i < 5; i++) {
        pthread_mutex_lock(&mutex);
        
        printf("[Producer] Producing item %d\n", i);
        counter = i;
        ready = 1;
        
        pthread_cond_signal(&cond);
        pthread_mutex_unlock(&mutex);
        
        sleep(1);
    }
    return NULL;
}

// Consumer thread
void *consumer(void *arg) {
    for (int i = 0; i < 5; i++) {
        pthread_mutex_lock(&mutex);
        
        while (!ready) {
            pthread_cond_wait(&cond, &mutex);
        }
        
        printf("[Consumer] Consuming item %d\n", counter);
        ready = 0;
        
        pthread_mutex_unlock(&mutex);
    }
    return NULL;
}

void demo_simple_threads() {
    printf("\n=== Simple Threads Demo ===\n");
    
    pthread_t threads[3];
    
    // Create threads
    for (long i = 0; i < 3; i++) {
        if (pthread_create(&threads[i], NULL, simple_thread, (void *)i) != 0) {
            perror("pthread_create");
            return;
        }
    }
    
    // Wait for threads and get return values
    for (int i = 0; i < 3; i++) {
        void *result;
        pthread_join(threads[i], &result);
        printf("[Main] Thread %d returned: %ld\n", i, (long)result);
    }
}

void demo_mutex() {
    printf("\n=== Mutex Demo ===\n");
    
    pthread_t t1, t2;
    counter = 0;
    
    printf("[Main] Initial counter: %d\n", counter);
    
    pthread_create(&t1, NULL, mutex_thread, NULL);
    pthread_create(&t2, NULL, mutex_thread, NULL);
    
    pthread_join(t1, NULL);
    pthread_join(t2, NULL);
    
    printf("[Main] Final counter: %d (expected: 20000)\n", counter);
}

void demo_condition_variable() {
    printf("\n=== Condition Variable Demo ===\n");
    
    pthread_t prod, cons;
    counter = 0;
    ready = 0;
    
    pthread_create(&cons, NULL, consumer, NULL);
    pthread_create(&prod, NULL, producer, NULL);
    
    pthread_join(prod, NULL);
    pthread_join(cons, NULL);
}

// Thread attributes demo
void demo_thread_attributes() {
    printf("\n=== Thread Attributes Demo ===\n");
    
    pthread_t thread;
    pthread_attr_t attr;
    
    // Initialize attributes
    pthread_attr_init(&attr);
    
    // Set detached state
    pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_DETACHED);
    
    // Set stack size
    size_t stacksize = 2 * 1024 * 1024;  // 2MB
    pthread_attr_setstacksize(&attr, stacksize);
    
    printf("[Main] Creating detached thread with 2MB stack\n");
    
    if (pthread_create(&thread, &attr, simple_thread, (void *)99L) != 0) {
        perror("pthread_create");
        pthread_attr_destroy(&attr);
        return;
    }
    
    pthread_attr_destroy(&attr);
    
    // No need to join (detached)
    sleep(2);
    printf("[Main] Detached thread completed\n");
}

// Thread-local storage demo
pthread_key_t tls_key;

void tls_destructor(void *value) {
    printf("[Destructor] Freeing TLS value: %ld\n", (long)value);
}

void *tls_thread(void *arg) {
    long id = (long)arg;
    
    // Set thread-specific data
    pthread_setspecific(tls_key, (void *)(id * 100));
    
    // Get thread-specific data
    long value = (long)pthread_getspecific(tls_key);
    printf("[Thread %ld] My TLS value: %ld\n", id, value);
    
    return NULL;
}

void demo_thread_local_storage() {
    printf("\n=== Thread-Local Storage Demo ===\n");
    
    pthread_t threads[3];
    
    // Create key
    pthread_key_create(&tls_key, tls_destructor);
    
    for (long i = 0; i < 3; i++) {
        pthread_create(&threads[i], NULL, tls_thread, (void *)i);
    }
    
    for (int i = 0; i < 3; i++) {
        pthread_join(threads[i], NULL);
    }
    
    pthread_key_delete(tls_key);
}

int main() {
    printf("=== POSIX Threads Demo ===\n");
    printf("This program demonstrates various pthread features\n");
    
    demo_simple_threads();
    demo_mutex();
    demo_condition_variable();
    demo_thread_attributes();
    demo_thread_local_storage();
    
    printf("\n=== All Demos Complete ===\n");
    
    return 0;
}

