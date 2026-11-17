#ifndef VELAPET_AI_CHAT_H
#define VELAPET_AI_CHAT_H

#include "vp_net_chat.h"

int velapet_ai_chat_init(const vp_net_chat_adapter_t *adapter);
int velapet_ai_chat_ready(void);
/* UI thread submits a value copy while holding the mailbox critical section. */
void velapet_ai_chat_capture(uint32_t request_id, const velapet_snapshot_t *context);
/* AI thread only: process at most one request. No LVGL calls. */
int velapet_ai_chat_work_once(void);

#endif
