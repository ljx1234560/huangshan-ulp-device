#ifndef VELAPET_SERVICE_H
#define VELAPET_SERVICE_H

/*
 * 端侧业务服务：UI 的唯一数据入口。
 *
 * 规则（见 AGENTS.md 第 4 节跨层契约）：
 * - UI 只读快照，不持有业务状态，不直接调用 velapet_core。
 * - 快照返回的是内部拷贝，调用方不得修改；下一次操作后旧指针内容会变化。
 * - 所有动作成功后自动刷新快照，UI 随后调用 snapshot() 重新取值得最新数据。
 * - 本服务不取时间：day_id 由上层（系统时钟/RTC）提供，见 set_day()。
 */

#include <stddef.h>
#include <stdint.h>

#include "velapet_core.h"

#ifdef __cplusplus
extern "C" {
#endif

#define VELAPET_TASK_TITLE_LEN 32U
#define VELAPET_TASK_UNIT_LEN 8U

typedef struct
{
    velapet_task_type_t type;
    char title[VELAPET_TASK_TITLE_LEN]; /* 中文标题，UI 直接显示 */
    char unit[VELAPET_TASK_UNIT_LEN];   /* 单位：步 / 分钟 / 天 / 次 */
    uint32_t target;
    uint32_t progress;
    uint32_t exp_reward;
    velapet_task_status_t status;
} velapet_task_view_t;

typedef struct
{
    char name[VELAPET_NAME_LENGTH];
    uint16_t level;
    uint32_t exp;
    uint32_t exp_to_next;
    uint8_t exp_percent;   /* 0..100，经验条直接用 */
    uint8_t daily_percent; /* 0..100，今日步数任务完成度 */
    uint64_t total_steps;
    uint32_t consecutive_days;
    uint8_t can_checkin; /* 1 = 今日未签到 */

    char title[16]; /* 内核称号 ID（如 egg_baby），UI 转中文显示 */

    char current_skin[VELAPET_SKIN_ID_LENGTH];
    uint8_t unlocked_skin_count;
    char unlocked_skins[VELAPET_MAX_UNLOCKED_SKINS][VELAPET_SKIN_ID_LENGTH];

    uint8_t task_count;
    velapet_task_view_t tasks[VELAPET_TASK_COUNT];
} velapet_snapshot_t;

/* 初始化。day_id 为当日序号（同一天必须得到同一个值）。成功返回 0。 */
int velapet_service_init(uint32_t day_id);

/* 日切：跨天后调用。返回 1 = 任务已重置，0 = 同一天，-1 = 错误（如时间回退）。 */
int velapet_service_set_day(uint32_t day_id);

/* 读取快照。未初始化返回 NULL。 */
const velapet_snapshot_t *velapet_service_snapshot(void);

/* 动作。checkin 返回 >0 新连签天数，0 = 今日已签，-1 = 错误。
 * claim 返回 >0 获得经验，0 = 尚不可领，-1 = 错误。 */
int velapet_service_checkin(void);
int velapet_service_claim(velapet_task_type_t type);
int velapet_service_switch_skin(const char *skin_id);

/* 数据上报。返回 1 = 已更新，0 = 该任务已领奖不再统计，-1 = 错误。 */
int velapet_service_record_steps(uint32_t steps);
int velapet_service_record_exercise_minutes(uint32_t minutes);
int velapet_service_record_social(void);

/* 升级事件：返回本次跨过的最高等级，0 表示没有待处理升级。UI 弹完庆祝后 ack。 */
uint16_t velapet_service_last_levelup(void);
void velapet_service_ack_levelup(void);

/* 仅供持久化层使用：导出/恢复原始状态。UI 不得调用。 */
const velapet_state_t *velapet_service_raw_state(void);
int velapet_service_restore(const velapet_state_t *state, uint32_t day_id);

#ifdef __cplusplus
}
#endif

#endif
