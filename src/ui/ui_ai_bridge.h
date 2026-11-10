#ifndef VELAPET_UI_AI_BRIDGE_H
#define VELAPET_UI_AI_BRIDGE_H

/*
 * UI <-> 端侧 AI 服务的桥接信箱（对照 handoff-frontend.md 第 3/5 节接口职责草案，
 * 待与组员四联合评审后冻结）。
 *
 * 生命周期规则（handoff 第 5 节）：
 * - UI 线程只调用 submit / poll_result / cancel_pending；三者均不阻塞。
 * - AI 服务线程只调用 take_request / push_result；数据按值复制，无悬空指针。
 * - 单在途请求：submit 在上一个请求完成前返回 BUSY，杜绝旧结果覆盖新请求。
 * - 结果按 request_id 匹配；不匹配（已取消/过期）的结果被丢弃。
 * - UI 不持有供应商 Key、不写 HTTP、不解析 AT；传输层由 AI 服务实现。
 *
 * 演示模式：编译期定义 VELAPET_UI_AI_MOCK 后，submit 的请求由本文件内部
 * 模拟应答（固定中文文案 + 延时），用于无 AI 服务时的页面验收。
 * 固件默认不定义该宏：未接入服务时 submit 返回 OFFLINE，页面显示离线提示。
 */

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* 后端约定：message 最多 240 个 Unicode 字符；手表请求 max_chars=50。
 * 缓冲按最坏 UTF-8 规划：80 字符回复至少 321 字节含 NUL（handoff 第 5 节）。 */
#define UI_AI_TEXT_MAX_CHARS 240U
#define UI_AI_TEXT_BYTES (UI_AI_TEXT_MAX_CHARS * 3U + 1U)
#define UI_AI_REPLY_BYTES 384U
#define UI_AI_ID_LEN 48U

typedef enum
{
    UI_AI_KIND_GREETING = 0, /* greeting */
    UI_AI_KIND_CHEER,        /* cheer */
    UI_AI_KIND_TASK,         /* task */
    UI_AI_KIND_LEVEL,        /* level */
    UI_AI_KIND_CUSTOM,       /* custom：自由文本 */
    UI_AI_KIND_COUNT
} ui_ai_kind_t;

typedef enum
{
    UI_AI_SUBMIT_OK = 0,
    UI_AI_SUBMIT_BUSY,    /* 已有在途请求 */
    UI_AI_SUBMIT_INVALID, /* 文本为空/超长 */
    UI_AI_SUBMIT_OFFLINE  /* 通道未就绪（未接服务且无 mock） */
} ui_ai_submit_t;

typedef enum
{
    UI_AI_SOURCE_CLOUD = 0,      /* 云模型成功 */
    UI_AI_SOURCE_LOCAL_FALLBACK, /* 后端降级文案（HTTP 200 也可能是它） */
    UI_AI_SOURCE_ERROR           /* 失败，reply 字段无效 */
} ui_ai_source_t;

typedef struct
{
    uint32_t request_id;
    ui_ai_kind_t kind;
    uint32_t max_chars;               /* 建议 50（handoff 第 5 节） */
    char text[UI_AI_TEXT_BYTES];      /* custom 的 UTF-8 文本；快捷类型为空 */
} ui_ai_request_t;

typedef struct
{
    uint32_t request_id;
    ui_ai_source_t source;
    int32_t error_code;           /* 0 = 成功 */
    char intent[16];              /* greeting/cheer/task/level/custom */
    char emotion[16];             /* 后端情绪标签，可为空 */
    char conversation_id[UI_AI_ID_LEN];
    char persona_id[UI_AI_ID_LEN];
    char reply[UI_AI_REPLY_BYTES];
} ui_ai_result_t;

/* ---- UI 线程调用 ---- */
ui_ai_submit_t ui_ai_submit(ui_ai_kind_t kind, const char *utf8_text);
/* 轮询取走一条已完成结果；无结果返回 0。聊天页定时器里调用。 */
int ui_ai_poll_result(ui_ai_result_t *out);
/* 丢弃在途请求（切页/退出时调用）；已下发到服务的结果会因 id 不匹配被丢弃。 */
void ui_ai_cancel_pending(void);

/* ---- AI 服务线程调用（组员四实现传输层后接入） ---- */
int ui_ai_bridge_take_request(ui_ai_request_t *out);
int ui_ai_bridge_push_result(const ui_ai_result_t *in);

/* ---- 状态查询 ---- */
/* 0 = 未接服务（真机） / 1 = 演示 mock / 2 = 服务已挂接（take 过至少一次） */
int ui_ai_mode(void);

#ifdef __cplusplus
}
#endif

#endif
