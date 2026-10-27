#include "ble_service.h"

#include <stdint.h>
#include <string.h>

#include <finsh.h>

#include "bf0_ble_gap.h"
#include "bf0_sibles.h"
#include "bf0_sibles_advertising.h"
#include "bf0_sibles_internal.h"

enum velapet_ble_attribute
{
    VELAPET_BLE_SERVICE,
    VELAPET_BLE_CHARACTERISTIC,
    VELAPET_BLE_CHARACTERISTIC_VALUE,
    VELAPET_BLE_ATTRIBUTE_COUNT
};

#define VELAPET_BLE_SERVICE_UUID                                                  \
    {                                                                            \
        0x56, 0x65, 0x6c, 0x61, 0x50, 0x65, 0x74, 0x00,                         \
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01                          \
    }

#define VELAPET_BLE_CHARACTERISTIC_UUID                                           \
    {                                                                            \
        0x56, 0x65, 0x6c, 0x61, 0x50, 0x65, 0x74, 0x00,                         \
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02                          \
    }

#define SERIAL_UUID_16(value)                                                     \
    {                                                                            \
        (uint8_t)((value) & 0xffU), (uint8_t)((value) >> 8U)                      \
    }

static uint8_t g_velapet_service_uuid[ATT_UUID_128_LEN] =
    VELAPET_BLE_SERVICE_UUID;

BLE_GATT_SERVICE_DEFINE_128(g_velapet_attribute_database)
{
    BLE_GATT_SERVICE_DECLARE(VELAPET_BLE_SERVICE,
                             SERIAL_UUID_16_PRI_SERVICE,
                             BLE_GATT_PERM_READ_ENABLE),
    BLE_GATT_CHAR_DECLARE(VELAPET_BLE_CHARACTERISTIC,
                          SERIAL_UUID_16_CHARACTERISTIC,
                          BLE_GATT_PERM_READ_ENABLE),
    BLE_GATT_CHAR_VALUE_DECLARE(VELAPET_BLE_CHARACTERISTIC_VALUE,
                                VELAPET_BLE_CHARACTERISTIC_UUID,
                                BLE_GATT_PERM_READ_ENABLE |
                                    BLE_GATT_PERM_WRITE_REQ_ENABLE |
                                    BLE_GATT_PERM_WRITE_COMMAND_ENABLE,
                                BLE_GATT_VALUE_PERM_UUID_128 |
                                    BLE_GATT_VALUE_PERM_RI_ENABLE,
                                sizeof(uint32_t)),
};

typedef struct
{
    rt_mailbox_t mailbox;
    rt_thread_t worker;
    rt_timer_t advertising_timer;
    uint8_t initialized;
    uint8_t powered;
    uint8_t advertising_initialized;
    uint8_t advertising;
    uint8_t connected;
    uint8_t address_valid;
    uint8_t last_adv_status;
    uint8_t peer_address[6];
    bd_addr_t local_address;
    sibles_hdl service_handle;
    uint32_t value;
} velapet_ble_state_t;

static velapet_ble_state_t g_ble_state;

SIBLES_ADVERTISING_CONTEXT_DECLAR(g_velapet_advertising_context);

static void velapet_ble_advertising_timeout(void *parameter)
{
    uint8_t result;

    (void)parameter;
    if (!g_ble_state.advertising)
    {
        return;
    }

    result = sibles_advertising_stop(g_velapet_advertising_context);
    rt_kprintf("[ble-test] timeout_stop=%s status=%u\n",
               (result == SIBLES_ADV_NO_ERR) ? "PASS" : "FAIL",
               result);
}

static uint8_t *velapet_ble_get_value(uint8_t connection,
                                      uint8_t index,
                                      uint16_t *length)
{
    (void)connection;
    *length = 0U;
    if (index == VELAPET_BLE_CHARACTERISTIC_VALUE)
    {
        *length = sizeof(g_ble_state.value);
        return (uint8_t *)&g_ble_state.value;
    }
    return RT_NULL;
}

static uint8_t velapet_ble_set_value(uint8_t connection, sibles_set_cbk_t *value)
{
    (void)connection;
    if (value->idx == VELAPET_BLE_CHARACTERISTIC_VALUE &&
            value->len <= sizeof(g_ble_state.value))
    {
        g_ble_state.value = 0U;
        rt_memcpy(&g_ble_state.value, value->value, value->len);
        rt_kprintf("[ble-test] write=PASS length=%u value=%u\n",
                   value->len,
                   g_ble_state.value);
    }
    return 0U;
}

static rt_err_t velapet_ble_register_service(void)
{
    BLE_GATT_SERVICE_INIT_128(service,
                              g_velapet_attribute_database,
                              VELAPET_BLE_ATTRIBUTE_COUNT,
                              BLE_GATT_SERVICE_PERM_NOAUTH |
                                  BLE_GATT_SERVICE_PERM_UUID_128,
                              g_velapet_service_uuid);

    g_ble_state.service_handle = sibles_register_svc_128(&service);
    if (g_ble_state.service_handle == RT_NULL)
    {
        rt_kprintf("[ble-test] service=FAIL\n");
        return -RT_ERROR;
    }

    sibles_register_cbk(g_ble_state.service_handle,
                        velapet_ble_get_value,
                        velapet_ble_set_value);
    rt_kprintf("[ble-test] service=PASS handle=%p\n",
               g_ble_state.service_handle);
    return RT_EOK;
}

static const char *velapet_ble_result(void)
{
    if (!g_ble_state.initialized)
    {
        return "FAIL";
    }
    if (g_ble_state.connected || g_ble_state.advertising)
    {
        return "PASS";
    }
    if (g_ble_state.powered)
    {
        return "IDLE";
    }
    return "WAITING";
}

static uint8_t velapet_ble_advertising_event(uint8_t event, void *context, void *data)
{
    (void)context;

    if (event == SIBLES_ADV_EVT_ADV_STARTED)
    {
        const sibles_adv_evt_startted_t *started = (const sibles_adv_evt_startted_t *)data;
        g_ble_state.last_adv_status = started->status;
        g_ble_state.advertising = (started->status == 0U);
        if (g_ble_state.advertising && g_ble_state.advertising_timer != RT_NULL)
        {
            rt_timer_start(g_ble_state.advertising_timer);
        }
        rt_kprintf("[ble-test] advertising=%s name=%s duration_s=%u status=%u\n",
                   g_ble_state.advertising ? "PASS" : "FAIL",
                   VELAPET_BLE_DEVICE_NAME,
                   VELAPET_BLE_ADV_DURATION_SECONDS,
                   started->status);
    }
    else if (event == SIBLES_ADV_EVT_ADV_STOPPED)
    {
        const sibles_adv_evt_stopped_t *stopped = (const sibles_adv_evt_stopped_t *)data;
        g_ble_state.advertising = 0U;
        if (g_ble_state.advertising_timer != RT_NULL)
        {
            rt_timer_stop(g_ble_state.advertising_timer);
        }
        rt_kprintf("[ble-test] advertising=STOP reason=%u\n", stopped->reason);
    }

    return 0U;
}

static uint8_t velapet_ble_start_advertising(void)
{
    sibles_advertising_para_t parameters = {0};
    const size_t name_length = strlen(VELAPET_BLE_DEVICE_NAME);
    static const uint8_t manufacturer_payload[] = {'V', 'P', 0x01U};
    ble_gap_dev_name_t *device_name;
    uint8_t result;

    if (g_ble_state.advertising)
    {
        if (g_ble_state.advertising_timer != RT_NULL)
        {
            rt_timer_stop(g_ble_state.advertising_timer);
            rt_timer_start(g_ble_state.advertising_timer);
        }
        g_ble_state.last_adv_status = SIBLES_ADV_NO_ERR;
        rt_kprintf("[ble-test] advertising=PASS name=%s duration_s=%u status=0 renewed=1\n",
                   VELAPET_BLE_DEVICE_NAME,
                   VELAPET_BLE_ADV_DURATION_SECONDS);
        return SIBLES_ADV_NO_ERR;
    }

    if (!g_ble_state.advertising_initialized)
    {
        device_name = rt_malloc(sizeof(ble_gap_dev_name_t) + name_length);
        if (device_name == RT_NULL)
        {
            rt_kprintf("[ble-test] advertising=FAIL reason=NO_MEMORY\n");
            return 1U;
        }
        device_name->len = (uint8_t)name_length;
        rt_memcpy(device_name->name, VELAPET_BLE_DEVICE_NAME, name_length);
        ble_gap_set_dev_name(device_name);
        rt_free(device_name);

        parameters.own_addr_type = GAPM_STATIC_ADDR;
        parameters.config.adv_mode = SIBLES_ADV_CONNECT_MODE;
        /* Match the vendor examples with an unlimited controller duration, then
           enforce the test bound with an RT-Thread one-shot software timer. */
        parameters.config.mode_config.conn_config.duration = 0U;
        parameters.config.mode_config.conn_config.interval = 0x30U;
        parameters.config.mode_config.conn_config.is_repeated = 0U;
        parameters.config.max_tx_pwr = 0x7FU;
        /* The SDK restarts the connectable activity after a disconnect.
           Its STARTED callback renews our bounded 300-second timer. */
        parameters.config.is_auto_restart = 1U;
        parameters.evt_handler = velapet_ble_advertising_event;

        /* Follow the SDK peripheral example exactly: keep real advertising data
           in the primary packet and return the complete name in the response. */
        parameters.rsp_data.completed_name =
            rt_malloc(sizeof(sibles_adv_type_name_t) + name_length);
        parameters.adv_data.manufacturer_data =
            rt_malloc(sizeof(sibles_adv_type_manufacturer_data_t) +
                      sizeof(manufacturer_payload));
        if (parameters.rsp_data.completed_name == RT_NULL ||
                parameters.adv_data.manufacturer_data == RT_NULL)
        {
            if (parameters.rsp_data.completed_name != RT_NULL)
            {
                rt_free(parameters.rsp_data.completed_name);
            }
            if (parameters.adv_data.manufacturer_data != RT_NULL)
            {
                rt_free(parameters.adv_data.manufacturer_data);
            }
            rt_kprintf("[ble-test] advertising=FAIL reason=NO_MEMORY\n");
            return 1U;
        }

        parameters.rsp_data.completed_name->name_len = (uint8_t)name_length;
        rt_memcpy(parameters.rsp_data.completed_name->name,
                  VELAPET_BLE_DEVICE_NAME,
                  name_length);
        parameters.adv_data.manufacturer_data->company_id = SIG_SIFLI_COMPANY_ID;
        parameters.adv_data.manufacturer_data->data_len =
            (uint8_t)sizeof(manufacturer_payload);
        rt_memcpy(parameters.adv_data.manufacturer_data->additional_data,
                  manufacturer_payload,
                  sizeof(manufacturer_payload));

        result = sibles_advertising_init(g_velapet_advertising_context, &parameters);
        rt_free(parameters.rsp_data.completed_name);
        rt_free(parameters.adv_data.manufacturer_data);
        if (result != SIBLES_ADV_NO_ERR)
        {
            g_ble_state.last_adv_status = result;
            rt_kprintf("[ble-test] advertising=FAIL stage=init status=%u\n", result);
            return result;
        }
        g_ble_state.advertising_initialized = 1U;
    }

    result = sibles_advertising_start(g_velapet_advertising_context);
    if (result != SIBLES_ADV_NO_ERR)
    {
        g_ble_state.last_adv_status = result;
        rt_kprintf("[ble-test] advertising=FAIL stage=start status=%u\n", result);
    }
    return result;
}

static void velapet_ble_worker(void *parameter)
{
    rt_uint32_t event;

    (void)parameter;
    while (rt_mb_recv(g_ble_state.mailbox, &event, RT_WAITING_FOREVER) == RT_EOK)
    {
        if (event == BLE_POWER_ON_IND)
        {
            g_ble_state.powered = 1U;
            if (ble_get_public_address(&g_ble_state.local_address) == HL_ERR_NO_ERROR)
            {
                g_ble_state.address_valid = 1U;
            }
            rt_kprintf("[ble-test] stack=PASS\n");
            if (velapet_ble_register_service() == RT_EOK)
            {
                velapet_ble_start_advertising();
            }
        }
    }
}

int velapet_ble_event_handler(uint16_t event_id, uint8_t *data, uint16_t len, uint32_t context)
{
    (void)len;
    (void)context;

    switch (event_id)
    {
    case BLE_POWER_ON_IND:
        if (g_ble_state.mailbox != RT_NULL)
        {
            rt_mb_send(g_ble_state.mailbox, BLE_POWER_ON_IND);
        }
        break;

    case BLE_GAP_CONNECTED_IND:
    {
        const ble_gap_connect_ind_t *connected = (const ble_gap_connect_ind_t *)data;
        g_ble_state.connected = 1U;
        g_ble_state.advertising = 0U;
        rt_memcpy(g_ble_state.peer_address, connected->peer_addr.addr,
                  sizeof(g_ble_state.peer_address));
        rt_kprintf("[ble-test] connection=PASS peer=%02x:%02x:%02x:%02x:%02x:%02x\n",
                   g_ble_state.peer_address[5], g_ble_state.peer_address[4],
                   g_ble_state.peer_address[3], g_ble_state.peer_address[2],
                   g_ble_state.peer_address[1], g_ble_state.peer_address[0]);
        break;
    }

    case BLE_GAP_DISCONNECTED_IND:
    {
        const ble_gap_disconnected_ind_t *disconnected =
            (const ble_gap_disconnected_ind_t *)data;
        g_ble_state.connected = 0U;
        rt_kprintf("[ble-test] connection=DISCONNECTED reason=%u\n",
                   disconnected->reason);
        break;
    }

    default:
        break;
    }

    return 0;
}
BLE_EVENT_REGISTER(velapet_ble_event_handler, RT_NULL);

rt_err_t velapet_ble_init(void)
{
    if (g_ble_state.initialized)
    {
        return RT_EOK;
    }

    g_ble_state.mailbox = rt_mb_create("vp_ble", 4U, RT_IPC_FLAG_FIFO);
    if (g_ble_state.mailbox == RT_NULL)
    {
        return -RT_ENOMEM;
    }

    g_ble_state.worker = rt_thread_create("vp_ble",
                                           velapet_ble_worker,
                                           RT_NULL,
                                           2048U,
                                           20U,
                                           10U);
    if (g_ble_state.worker == RT_NULL)
    {
        rt_mb_delete(g_ble_state.mailbox);
        g_ble_state.mailbox = RT_NULL;
        return -RT_ENOMEM;
    }

    g_ble_state.advertising_timer =
        rt_timer_create("vp_ble_to",
                        velapet_ble_advertising_timeout,
                        RT_NULL,
                        rt_tick_from_millisecond(
                            VELAPET_BLE_ADV_DURATION_SECONDS * 1000U),
                        RT_TIMER_FLAG_ONE_SHOT | RT_TIMER_FLAG_SOFT_TIMER);
    if (g_ble_state.advertising_timer == RT_NULL)
    {
        rt_thread_delete(g_ble_state.worker);
        g_ble_state.worker = RT_NULL;
        rt_mb_delete(g_ble_state.mailbox);
        g_ble_state.mailbox = RT_NULL;
        return -RT_ENOMEM;
    }

    g_ble_state.initialized = 1U;
    rt_thread_startup(g_ble_state.worker);
    rt_kprintf("[ble-test] init=PASS name=%s\n", VELAPET_BLE_DEVICE_NAME);
    sifli_ble_enable();
    return RT_EOK;
}

static int ble_test(int argc, char **argv)
{
    if (argc == 2 && strcmp(argv[1], "start") == 0)
    {
        if (!g_ble_state.powered)
        {
            rt_kprintf("[ble-test] start=FAIL reason=STACK_NOT_READY\n");
            return -RT_ERROR;
        }
        if (g_ble_state.connected)
        {
            rt_kprintf("[ble-test] start=FAIL reason=CONNECTED\n");
            return -RT_EBUSY;
        }
        return (velapet_ble_start_advertising() == SIBLES_ADV_NO_ERR) ? RT_EOK : -RT_ERROR;
    }

    if (argc == 2 && strcmp(argv[1], "stop") == 0)
    {
        uint8_t result = sibles_advertising_stop(g_velapet_advertising_context);
        rt_kprintf("[ble-test] stop=%s status=%u\n",
                   (result == SIBLES_ADV_NO_ERR) ? "PASS" : "FAIL",
                   result);
        return (result == SIBLES_ADV_NO_ERR) ? RT_EOK : -RT_ERROR;
    }

    rt_kprintf("[ble-test] status=%s powered=%u advertising=%u connected=%u adv_status=%u name=%s",
               velapet_ble_result(),
               g_ble_state.powered,
               g_ble_state.advertising,
               g_ble_state.connected,
               g_ble_state.last_adv_status,
               VELAPET_BLE_DEVICE_NAME);
    if (g_ble_state.address_valid)
    {
        rt_kprintf(" address=%02x:%02x:%02x:%02x:%02x:%02x",
                   g_ble_state.local_address.addr[5], g_ble_state.local_address.addr[4],
                   g_ble_state.local_address.addr[3], g_ble_state.local_address.addr[2],
                   g_ble_state.local_address.addr[1], g_ble_state.local_address.addr[0]);
    }
    rt_kprintf("\n");
    return RT_EOK;
}
MSH_CMD_EXPORT(ble_test, BLE smoke test with status start or stop.);
