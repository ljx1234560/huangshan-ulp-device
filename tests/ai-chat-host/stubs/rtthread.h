#ifndef HOST_TEST_RTTHREAD_H
#define HOST_TEST_RTTHREAD_H
#include <stddef.h>
typedef void *rt_thread_t;
#define RT_NULL NULL
#define RT_EOK 0
#define RT_WEAK __attribute__((weak))
void rt_enter_critical(void);
void rt_exit_critical(void);
rt_thread_t rt_thread_create(const char *, void (*)(void *), void *, unsigned, unsigned, unsigned);
int rt_thread_startup(rt_thread_t);
int rt_thread_delete(rt_thread_t);
void rt_thread_mdelay(int);
#endif
