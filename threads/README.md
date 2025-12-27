# POSIX Threads (pthreads) Tutorial

## Overview

POSIX threads (pthreads) provide a standardized API for creating and managing threads within a process. Threads share the same memory space but execute independently.

## Thread Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Process                              │
│                                                         │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Shared Resources                                  │ │
│  │  ┌──────────────────────────────────────────────┐  │ │
│  │  │ Code Segment (Text)                          │  │ │
│  │  │ Data Segment (Global/Static variables)       │  │ │
│  │  │ Heap (malloc allocations)                    │  │ │
│  │  │ File Descriptors                             │  │ │
│  │  │ Signal Handlers                              │  │ │
│  │  └──────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│  Thread 1           Thread 2           Thread 3         │
│  ┌──────────┐       ┌──────────┐      ┌──────────┐      │
│  │ Stack    │       │ Stack    │      │ Stack    │      │
│  │ Registers│       │ Registers│      │ Registers│      │
│  │ PC       │       │ PC       │      │ PC       │      │
│  │ TID      │       │ TID      │      │ TID      │      │
│  └──────────┘       └──────────┘      └──────────┘      │
│      ▼                  ▼                  ▼            │
│  [Running]          [Ready]            [Blocked]        │
└─────────────────────────────────────────────────────────┘

Threads vs Processes:
┌────────────────────┬──────────────────┬──────────────────┐
│ Feature            │ Thread           │ Process          │
├────────────────────┼──────────────────┼──────────────────┤
│ Memory Space       │ Shared           │ Separate         │
│ Creation Overhead  │ Low              │ High             │
│ Context Switch     │ Fast             │ Slow             │
│ Communication      │ Easy (memory)    │ IPC needed       │
│ Isolation          │ None             │ Strong           │
│ Resource Usage     │ Light            │ Heavy            │
└────────────────────┴──────────────────┴──────────────────┘
```

## 1. Thread Creation and Termination

### pthread_create() - Create Thread

```c
#include <pthread.h>

int pthread_create(pthread_t *thread,
                   const pthread_attr_t *attr,
                   void *(*start_routine)(void *),
                   void *arg);
```

**Basic Example**

```c
#include <pthread.h>
#include <stdio.h>
#include <unistd.h>

void *thread_function(void *arg) {
    int id = *(int *)arg;
    printf("Thread %d: Hello from thread!\n", id);
    sleep(1);
    printf("Thread %d: Exiting\n", id);
    return NULL;
}

int main() {
    pthread_t thread;
    int thread_id = 1;
    
    if (pthread_create(&thread, NULL, thread_function, &thread_id) != 0) {
        perror("pthread_create");
        return 1;
    }
    
    printf("Main: Created thread\n");
    
    // Wait for thread to finish
    pthread_join(thread, NULL);
    
    printf("Main: Thread completed\n");
    return 0;
}
```

**Multiple Threads**

```c
#include <pthread.h>
#include <stdio.h>

#define NUM_THREADS 5

void *worker(void *arg) {
    long id = (long)arg;
    printf("Thread %ld starting\n", id);
    sleep(1);
    printf("Thread %ld finishing\n", id);
    return (void *)(id * 2);
}

int main() {
    pthread_t threads[NUM_THREADS];
    
    // Create threads
    for (long i = 0; i < NUM_THREADS; i++) {
        if (pthread_create(&threads[i], NULL, worker, (void *)i) != 0) {
            perror("pthread_create");
            return 1;
        }
    }
    
    // Wait for all threads
    for (int i = 0; i < NUM_THREADS; i++) {
        void *result;
        pthread_join(threads[i], &result);
        printf("Thread %d returned: %ld\n", i, (long)result);
    }
    
    return 0;
}
```

### pthread_exit() - Terminate Thread

```c
#include <pthread.h>

void *thread_function(void *arg) {
    printf("Thread doing work\n");
    
    // Exit thread with return value
    pthread_exit((void *)42);
    
    // This code is never reached
    printf("Never printed\n");
    return NULL;
}
```

### pthread_join() - Wait for Thread

```c
#include <pthread.h>

int main() {
    pthread_t thread;
    void *result;
    
    pthread_create(&thread, NULL, thread_function, NULL);
    
    // Block until thread terminates
    if (pthread_join(thread, &result) != 0) {
        perror("pthread_join");
        return 1;
    }
    
    printf("Thread returned: %ld\n", (long)result);
    return 0;
}
```

### pthread_detach() - Detached Thread

```c
#include <pthread.h>

void *detached_thread(void *arg) {
    printf("Detached thread running\n");
    sleep(2);
    printf("Detached thread exiting\n");
    return NULL;
}

int main() {
    pthread_t thread;
    
    pthread_create(&thread, NULL, detached_thread, NULL);
    
    // Detach thread - no need to join
    pthread_detach(thread);
    
    printf("Main continuing without waiting\n");
    sleep(3);  // Keep main alive
    
    return 0;
}
```

## 2. Thread Synchronization - Mutexes

### pthread_mutex_t - Mutual Exclusion Lock

```
Without Mutex (Race Condition):
Thread 1                    Thread 2
  read counter (0)            read counter (0)
  increment (1)               increment (1)
  write counter (1)           write counter (1)
Result: counter = 1 (should be 2!)

With Mutex:
Thread 1                    Thread 2
  lock mutex                  [blocked waiting]
  read counter (0)            [waiting...]
  increment (1)               [waiting...]
  write counter (1)           [waiting...]
  unlock mutex                lock mutex
                              read counter (1)
                              increment (2)
                              write counter (2)
                              unlock mutex
Result: counter = 2 (correct!)
```

**Basic Mutex Example**

```c
#include <pthread.h>
#include <stdio.h>

pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
int shared_counter = 0;

void *increment(void *arg) {
    for (int i = 0; i < 100000; i++) {
        pthread_mutex_lock(&mutex);
        shared_counter++;
        pthread_mutex_unlock(&mutex);
    }
    return NULL;
}

int main() {
    pthread_t t1, t2;
    
    pthread_create(&t1, NULL, increment, NULL);
    pthread_create(&t2, NULL, increment, NULL);
    
    pthread_join(t1, NULL);
    pthread_join(t2, NULL);
    
    printf("Counter: %d (expected: 200000)\n", shared_counter);
    
    pthread_mutex_destroy(&mutex);
    return 0;
}
```

**Dynamic Mutex Initialization**

```c
#include <pthread.h>

pthread_mutex_t mutex;

int main() {
    // Initialize mutex
    if (pthread_mutex_init(&mutex, NULL) != 0) {
        perror("pthread_mutex_init");
        return 1;
    }
    
    // Use mutex
    pthread_mutex_lock(&mutex);
    // Critical section
    pthread_mutex_unlock(&mutex);
    
    // Destroy mutex
    pthread_mutex_destroy(&mutex);
    
    return 0;
}
```

**Trylock and Timedlock**

```c
#include <pthread.h>
#include <time.h>
#include <errno.h>

pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;

void *thread_func(void *arg) {
    // Try to lock without blocking
    if (pthread_mutex_trylock(&mutex) == 0) {
        printf("Lock acquired\n");
        // Critical section
        pthread_mutex_unlock(&mutex);
    } else {
        printf("Lock busy, skipping\n");
    }
    
    // Timed lock (5 seconds)
    struct timespec timeout;
    clock_gettime(CLOCK_REALTIME, &timeout);
    timeout.tv_sec += 5;
    
    int ret = pthread_mutex_timedlock(&mutex, &timeout);
    if (ret == 0) {
        printf("Timed lock acquired\n");
        pthread_mutex_unlock(&mutex);
    } else if (ret == ETIMEDOUT) {
        printf("Timed out waiting for lock\n");
    }
    
    return NULL;
}
```

## 3. Condition Variables

### pthread_cond_t - Thread Synchronization

```
Condition Variable Pattern:

Producer Thread:
  lock(mutex)
  add_item_to_buffer()
  signal(cond)     ← Wake up waiting consumer
  unlock(mutex)

Consumer Thread:
  lock(mutex)
  while (buffer_empty())
    wait(cond, mutex)  ← Release mutex and sleep
                       ← When signaled, reacquire mutex
  remove_item_from_buffer()
  unlock(mutex)
```

**Producer-Consumer with Condition Variables**

```c
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>

#define BUFFER_SIZE 10

int buffer[BUFFER_SIZE];
int count = 0;
int in = 0;
int out = 0;

pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
pthread_cond_t not_empty = PTHREAD_COND_INITIALIZER;
pthread_cond_t not_full = PTHREAD_COND_INITIALIZER;

void *producer(void *arg) {
    for (int i = 0; i < 20; i++) {
        pthread_mutex_lock(&mutex);
        
        // Wait while buffer is full
        while (count == BUFFER_SIZE) {
            pthread_cond_wait(&not_full, &mutex);
        }
        
        // Produce item
        buffer[in] = i;
        in = (in + 1) % BUFFER_SIZE;
        count++;
        printf("Produced: %d (count: %d)\n", i, count);
        
        // Signal consumer
        pthread_cond_signal(&not_empty);
        
        pthread_mutex_unlock(&mutex);
        usleep(100000);
    }
    return NULL;
}

void *consumer(void *arg) {
    for (int i = 0; i < 20; i++) {
        pthread_mutex_lock(&mutex);
        
        // Wait while buffer is empty
        while (count == 0) {
            pthread_cond_wait(&not_empty, &mutex);
        }
        
        // Consume item
        int item = buffer[out];
        out = (out + 1) % BUFFER_SIZE;
        count--;
        printf("Consumed: %d (count: %d)\n", item, count);
        
        // Signal producer
        pthread_cond_signal(&not_full);
        
        pthread_mutex_unlock(&mutex);
        usleep(150000);
    }
    return NULL;
}

int main() {
    pthread_t prod, cons;
    
    pthread_create(&prod, NULL, producer, NULL);
    pthread_create(&cons, NULL, consumer, NULL);
    
    pthread_join(prod, NULL);
    pthread_join(cons, NULL);
    
    pthread_mutex_destroy(&mutex);
    pthread_cond_destroy(&not_empty);
    pthread_cond_destroy(&not_full);
    
    return 0;
}
```

**Broadcast vs Signal**

```c
#include <pthread.h>

pthread_cond_t cond = PTHREAD_COND_INITIALIZER;
pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
int ready = 0;

void *waiter(void *arg) {
    pthread_mutex_lock(&mutex);
    
    while (!ready) {
        pthread_cond_wait(&cond, &mutex);
    }
    
    printf("Thread %ld woke up\n", (long)arg);
    
    pthread_mutex_unlock(&mutex);
    return NULL;
}

int main() {
    pthread_t threads[5];
    
    // Create waiting threads
    for (long i = 0; i < 5; i++) {
        pthread_create(&threads[i], NULL, waiter, (void *)i);
    }
    
    sleep(1);
    
    pthread_mutex_lock(&mutex);
    ready = 1;
    
    // pthread_cond_signal(&cond);    // Wakes ONE thread
    pthread_cond_broadcast(&cond);    // Wakes ALL threads
    
    pthread_mutex_unlock(&mutex);
    
    for (int i = 0; i < 5; i++) {
        pthread_join(threads[i], NULL);
    }
    
    return 0;
}
```

## 4. Read-Write Locks

### pthread_rwlock_t - Multiple Readers, Single Writer

```
Read-Write Lock Behavior:

State: Unlocked
  Reader 1 locks  → State: Read locked (count=1)
  Reader 2 locks  → State: Read locked (count=2)  ✓ Allowed
  Writer waits    → BLOCKED
  Reader 3 locks  → State: Read locked (count=3)  ✓ Allowed
  Reader 1 unlocks → State: Read locked (count=2)
  Reader 2 unlocks → State: Read locked (count=1)
  Reader 3 unlocks → State: Unlocked
  Writer locks    → State: Write locked           ✓ Exclusive

┌────────────────┬──────────────┬──────────────┐
│ Lock State     │ Reader       │ Writer       │
├────────────────┼──────────────┼──────────────┤
│ Unlocked       │ Grant        │ Grant        │
│ Read Locked    │ Grant        │ Block        │
│ Write Locked   │ Block        │ Block        │
└────────────────┴──────────────┴──────────────┘
```

**Example**

```c
#include <pthread.h>
#include <stdio.h>

pthread_rwlock_t rwlock = PTHREAD_RWLOCK_INITIALIZER;
int shared_data = 0;

void *reader(void *arg) {
    long id = (long)arg;
    
    for (int i = 0; i < 5; i++) {
        pthread_rwlock_rdlock(&rwlock);
        
        printf("Reader %ld: data = %d\n", id, shared_data);
        usleep(100000);
        
        pthread_rwlock_unlock(&rwlock);
        usleep(50000);
    }
    
    return NULL;
}

void *writer(void *arg) {
    long id = (long)arg;
    
    for (int i = 0; i < 3; i++) {
        pthread_rwlock_wrlock(&rwlock);
        
        shared_data++;
        printf("Writer %ld: wrote %d\n", id, shared_data);
        usleep(200000);
        
        pthread_rwlock_unlock(&rwlock);
        usleep(100000);
    }
    
    return NULL;
}

int main() {
    pthread_t readers[3], writers[2];
    
    // Create writers
    for (long i = 0; i < 2; i++) {
        pthread_create(&writers[i], NULL, writer, (void *)i);
    }
    
    // Create readers
    for (long i = 0; i < 3; i++) {
        pthread_create(&readers[i], NULL, reader, (void *)i);
    }
    
    // Wait for all
    for (int i = 0; i < 2; i++) {
        pthread_join(writers[i], NULL);
    }
    for (int i = 0; i < 3; i++) {
        pthread_join(readers[i], NULL);
    }
    
    pthread_rwlock_destroy(&rwlock);
    return 0;
}
```

**Trylock and Timedlock**

```c
#include <pthread.h>
#include <time.h>

pthread_rwlock_t rwlock = PTHREAD_RWLOCK_INITIALIZER;

void *thread_func(void *arg) {
    // Try read lock
    if (pthread_rwlock_tryrdlock(&rwlock) == 0) {
        printf("Read lock acquired\n");
        pthread_rwlock_unlock(&rwlock);
    }
    
    // Try write lock
    if (pthread_rwlock_trywrlock(&rwlock) == 0) {
        printf("Write lock acquired\n");
        pthread_rwlock_unlock(&rwlock);
    }
    
    // Timed read lock
    struct timespec timeout;
    clock_gettime(CLOCK_REALTIME, &timeout);
    timeout.tv_sec += 5;
    
    if (pthread_rwlock_timedrdlock(&rwlock, &timeout) == 0) {
        printf("Timed read lock acquired\n");
        pthread_rwlock_unlock(&rwlock);
    }
    
    return NULL;
}
```

## 5. Barriers

### pthread_barrier_t - Synchronization Point

```
Barrier Synchronization:

Thread 1: ──────────────────────►├─ barrier ─┤► Continue
Thread 2: ──────►├─ barrier ─┤ (wait)       ├► Continue
Thread 3: ────────────►├─ barrier ─┤ (wait)  ├► Continue

All threads must reach barrier before any can continue
```

**Example**

```c
#include <pthread.h>
#include <stdio.h>

#define NUM_THREADS 5

pthread_barrier_t barrier;

void *worker(void *arg) {
    long id = (long)arg;
    
    printf("Thread %ld: Phase 1\n", id);
    sleep(id);  // Different work times
    
    // Wait for all threads to complete phase 1
    printf("Thread %ld: Waiting at barrier\n", id);
    pthread_barrier_wait(&barrier);
    
    printf("Thread %ld: Phase 2 (all synchronized)\n", id);
    
    return NULL;
}

int main() {
    pthread_t threads[NUM_THREADS];
    
    // Initialize barrier for NUM_THREADS threads
    pthread_barrier_init(&barrier, NULL, NUM_THREADS);
    
    for (long i = 0; i < NUM_THREADS; i++) {
        pthread_create(&threads[i], NULL, worker, (void *)i);
    }
    
    for (int i = 0; i < NUM_THREADS; i++) {
        pthread_join(threads[i], NULL);
    }
    
    pthread_barrier_destroy(&barrier);
    return 0;
}
```

## 6. Spin Locks

### pthread_spinlock_t - Busy-Wait Lock

```
Mutex vs Spinlock:

Mutex (blocks thread):
  Thread tries lock
  Lock busy → Thread sleeps (context switch)
  Lock available → Wake up thread (context switch)
  Good for: Long critical sections

Spinlock (busy-wait):
  Thread tries lock
  Lock busy → Thread spins in loop checking lock
  Lock available → Acquire immediately
  Good for: Very short critical sections, real-time systems
```

**Example**

```c
#include <pthread.h>
#include <stdio.h>

pthread_spinlock_t spinlock;
int counter = 0;

void *increment(void *arg) {
    for (int i = 0; i < 100000; i++) {
        pthread_spin_lock(&spinlock);
        counter++;
        pthread_spin_unlock(&spinlock);
    }
    return NULL;
}

int main() {
    pthread_t t1, t2;
    
    // PTHREAD_PROCESS_PRIVATE: only within process
    // PTHREAD_PROCESS_SHARED: shared between processes
    pthread_spin_init(&spinlock, PTHREAD_PROCESS_PRIVATE);
    
    pthread_create(&t1, NULL, increment, NULL);
    pthread_create(&t2, NULL, increment, NULL);
    
    pthread_join(t1, NULL);
    pthread_join(t2, NULL);
    
    printf("Counter: %d\n", counter);
    
    pthread_spin_destroy(&spinlock);
    return 0;
}
```

## 7. Thread-Local Storage

### pthread_key_t - Thread-Specific Data

```c
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>

pthread_key_t key;

void destructor(void *value) {
    printf("Destructor called for value: %ld\n", (long)value);
    // Free allocated memory if needed
}

void *thread_func(void *arg) {
    long id = (long)arg;
    
    // Set thread-specific value
    pthread_setspecific(key, (void *)(id * 100));
    
    // Get thread-specific value
    long value = (long)pthread_getspecific(key);
    printf("Thread %ld: my value is %ld\n", id, value);
    
    return NULL;
}

int main() {
    pthread_t threads[3];
    
    // Create key with destructor
    pthread_key_create(&key, destructor);
    
    for (long i = 0; i < 3; i++) {
        pthread_create(&threads[i], NULL, thread_func, (void *)i);
    }
    
    for (int i = 0; i < 3; i++) {
        pthread_join(threads[i], NULL);
    }
    
    pthread_key_delete(key);
    return 0;
}
```

**Using __thread Keyword (GCC Extension)**

```c
#include <pthread.h>
#include <stdio.h>

__thread int thread_local_var = 0;

void *thread_func(void *arg) {
    long id = (long)arg;
    
    thread_local_var = id * 10;
    printf("Thread %ld: my var = %d\n", id, thread_local_var);
    
    return NULL;
}

int main() {
    pthread_t t1, t2;
    
    pthread_create(&t1, NULL, thread_func, (void *)1);
    pthread_create(&t2, NULL, thread_func, (void *)2);
    
    pthread_join(t1, NULL);
    pthread_join(t2, NULL);
    
    printf("Main: my var = %d\n", thread_local_var);
    
    return 0;
}
```

## 8. Thread Attributes

### pthread_attr_t - Customize Thread Behavior

```c
#include <pthread.h>
#include <stdio.h>

void *thread_func(void *arg) {
    printf("Thread running\n");
    return NULL;
}

int main() {
    pthread_t thread;
    pthread_attr_t attr;
    
    // Initialize attributes
    pthread_attr_init(&attr);
    
    // Set detached state
    pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_DETACHED);
    
    // Set stack size (2MB)
    size_t stacksize = 2 * 1024 * 1024;
    pthread_attr_setstacksize(&attr, stacksize);
    
    // Set scheduling policy
    pthread_attr_setschedpolicy(&attr, SCHED_FIFO);
    
    // Set priority
    struct sched_param param;
    param.sched_priority = 10;
    pthread_attr_setschedparam(&attr, &param);
    
    // Set scope
    pthread_attr_setscope(&attr, PTHREAD_SCOPE_SYSTEM);
    
    // Create thread with attributes
    if (pthread_create(&thread, &attr, thread_func, NULL) != 0) {
        perror("pthread_create");
        return 1;
    }
    
    // Destroy attributes
    pthread_attr_destroy(&attr);
    
    // No need to join (detached)
    sleep(1);
    
    return 0;
}
```

## 9. Thread Cancellation

### pthread_cancel() - Terminate Thread

```c
#include <pthread.h>
#include <stdio.h>

void cleanup_handler(void *arg) {
    printf("Cleanup: %s\n", (char *)arg);
}

void *thread_func(void *arg) {
    // Push cleanup handler
    pthread_cleanup_push(cleanup_handler, "Resource freed");
    
    // Set cancellation type
    pthread_setcanceltype(PTHREAD_CANCEL_ASYNCHRONOUS, NULL);
    
    for (int i = 0; i < 10; i++) {
        printf("Thread: iteration %d\n", i);
        sleep(1);
        
        // Cancellation point
        pthread_testcancel();
    }
    
    // Pop cleanup handler (execute=0: don't execute now)
    pthread_cleanup_pop(0);
    
    return NULL;
}

int main() {
    pthread_t thread;
    
    pthread_create(&thread, NULL, thread_func, NULL);
    
    sleep(3);
    
    // Cancel thread
    printf("Main: Canceling thread\n");
    pthread_cancel(thread);
    
    pthread_join(thread, NULL);
    
    printf("Main: Thread canceled\n");
    
    return 0;
}
```

## 10. Thread Safety and Synchronization Patterns

### Once Initialization

```c
#include <pthread.h>
#include <stdio.h>

pthread_once_t once_control = PTHREAD_ONCE_INIT;

void init_routine(void) {
    printf("Initialization executed once\n");
    // Initialize shared resources
}

void *thread_func(void *arg) {
    // This ensures init_routine is called exactly once
    pthread_once(&once_control, init_routine);
    
    printf("Thread %ld running\n", (long)arg);
    
    return NULL;
}

int main() {
    pthread_t threads[5];
    
    for (long i = 0; i < 5; i++) {
        pthread_create(&threads[i], NULL, thread_func, (void *)i);
    }
    
    for (int i = 0; i < 5; i++) {
        pthread_join(threads[i], NULL);
    }
    
    return 0;
}
```

### Thread-Safe Singleton Pattern

```c
#include <pthread.h>

static pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
static int *singleton = NULL;

int *get_singleton() {
    if (singleton == NULL) {
        pthread_mutex_lock(&mutex);
        if (singleton == NULL) {  // Double-checked locking
            singleton = malloc(sizeof(int));
            *singleton = 42;
        }
        pthread_mutex_unlock(&mutex);
    }
    return singleton;
}
```

## Compilation

```bash
# Compile with pthread library
gcc -pthread -o program program.c

# Or explicitly link
gcc -o program program.c -lpthread

# With debugging and warnings
gcc -pthread -Wall -Wextra -g -o program program.c
```

## Common Pitfalls

1. **Race Conditions** - Always protect shared data with mutexes
2. **Deadlocks** - Acquire locks in consistent order
3. **Forgetting to Join** - Causes resource leaks
4. **Not Using Condition Variables** - Busy-waiting wastes CPU
5. **Mixing Processes and Threads** - fork() with threads is dangerous
6. **Signal Handling** - Signals in multithreaded programs are complex

## Best Practices

```c
1. ✓ Initialize mutexes before use
2. ✓ Always unlock what you lock
3. ✓ Use condition variables for waiting
4. ✓ Join or detach all threads
5. ✓ Minimize critical section size
6. ✓ Use thread-safe functions (e.g., strtok_r vs strtok)
7. ✓ Handle pthread function return values
8. ✓ Use barriers for phase synchronization
9. ✓ Consider read-write locks for reader-heavy workloads
10. ✓ Test thoroughly for race conditions
```

## See Also

- `man pthreads` - Overview
- `man pthread_create`
- `man pthread_mutex_lock`
- `man pthread_cond_wait`
- [Complete examples](../examples/)

