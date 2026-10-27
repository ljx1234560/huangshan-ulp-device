#ifndef VELAPET_BLE_SERVICE_H
#define VELAPET_BLE_SERVICE_H

#include <rtthread.h>

#define VELAPET_BLE_DEVICE_NAME "VelaPet-BLE"
#define VELAPET_BLE_ADV_DURATION_SECONDS 300U

rt_err_t velapet_ble_init(void);

#endif
