#include <stdint.h>

#include <rtthread.h>
#include <littlevgl2rtt.h>
#include <lvgl.h>
#include <lv_ex_data.h>

#include "ble_service.h"
#include "velapet_ui.h"

int main(void)
{
    rt_err_t result = littlevgl2rtt_init("lcd");

    if (result != RT_EOK)
    {
        rt_kprintf("[ui-test] init=FAIL code=%d\n", result);
        return result;
    }

    lv_ex_data_pool_init();
    velapet_ui_create();
    rt_kprintf("[ui-test] init=PASS resolution=390x450\n");

    result = velapet_ble_init();
    if (result != RT_EOK)
    {
        rt_kprintf("[ble-test] init=FAIL code=%d\n", result);
    }

    while (1)
    {
        uint32_t delay_ms = lv_task_handler();

        if (delay_ms < 1U)
        {
            delay_ms = 1U;
        }
        rt_thread_mdelay(delay_ms);
    }
}
