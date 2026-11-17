#ifndef VP_NET_CHAT_H
#define VP_NET_CHAT_H

#include "ui_ai_bridge.h"
#include "velapet_service.h"

#define VP_NET_CHAT_TIMEOUT_MS 35000U
#define VP_NET_CHAT_REPLY_TIMEOUT (-1)
#define VP_NET_CHAT_REPLY_OFFLINE (-2)
#define VP_NET_CHAT_REPLY_INVALID (-3)

/*
 * Hardware transport adapter. An exchange sends POST /api/v1/chat through
 * the relay, mapping kind to prompt_type and context to the backend schema.
 * No LVGL calls; all pointers are borrowed until exchange returns. Enforce the
 * deadline, parse UTF-8/JSON and map cloud/fallback/error before returning.
 * A usable fallback returns 0 even if the backend includes an error code.
 * Ready must be a nonblocking, thread-safe cached link/relay status.
 */
typedef struct
{
    int (*ready)(void);
    int (*exchange)(const ui_ai_request_t *request,
                    const velapet_snapshot_t *context,
                    ui_ai_result_t *result, uint32_t timeout_ms);
} vp_net_chat_adapter_t;

/* Hardware provides this when a product transport is linked.
 * A NULL return leaves official mode offline. Adapter lifetime is static. */
const vp_net_chat_adapter_t *vp_net_chat_platform(void);

#endif
