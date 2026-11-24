#ifndef VELAPET_MOTION_H
#define VELAPET_MOTION_H

/*
 * 平台无关运动模型：输入带时间戳的传感器数据，输出稳定的活动事件。
 *
 * 约束：
 * - 不访问 OS、时钟、I2C 或文件系统；所有时间由调用方以毫秒传入。
 * - 不分配内存；调用方静态分配 velapet_motion_t。
 * - 时间比较均为 uint32 毫秒差，支持 32 位回绕（单次间隔需 < 24 天）。
 * - 硬件计步器为主数据源，加速度用于活动强度与静止判断。
 */

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define VELAPET_MOTION_STEP_RING_SIZE 60U

typedef enum
{
    VELAPET_ACTIVITY_UNKNOWN = 0,
    VELAPET_ACTIVITY_STILL,
    VELAPET_ACTIVITY_LIGHT,
    VELAPET_ACTIVITY_WALKING
} velapet_activity_t;

typedef enum
{
    VELAPET_WEAR_UNKNOWN = 0,
    VELAPET_WEAR_WORN,
    VELAPET_WEAR_NOT_WORN
} velapet_wear_t;

/* 事件位掩码，由 velapet_motion_take_events() 读取并清除。 */
#define VELAPET_MOTION_EVENT_ACTIVE_MINUTE 0x0001U
#define VELAPET_MOTION_EVENT_WALK_MINUTE 0x0002U
#define VELAPET_MOTION_EVENT_SEDENTARY 0x0004U
#define VELAPET_MOTION_EVENT_INACTIVITY 0x0008U

typedef struct
{
    uint32_t still_std_mg;             /* 判静止的加速度标准差上限 */
    uint32_t moving_std_mg;            /* 从静止进入活动需要达到的标准差 */
    uint32_t walk_hold_ms;             /* 一次步数增量维持“行走”状态的时间 */
    uint32_t walk_break_ms;            /* 行走会话中断多久后丢弃未满一分钟部分 */
    uint32_t active_seconds_per_minute;/* 每分钟多少活动秒算一个活动分钟 */
    uint32_t sedentary_limit_ms;       /* 久坐提醒阈值 */
    uint32_t inactivity_limit_ms;      /* 久不运动提醒阈值 */
    uint32_t sedentary_reset_steps;    /* 60 秒内达到该步数即断坐 */
    uint32_t nonwear_still_ms;         /* 静止且光照暗持续多久判非佩戴 */
    uint32_t light_dark_raw;           /* 低于该原始值视为暗；0 关闭光照判佩戴 */
} velapet_motion_config_t;

typedef struct
{
    velapet_activity_t activity;
    velapet_wear_t wear;
    uint32_t steps_today;
    uint32_t active_minutes_today;
    uint32_t walk_minutes_today;
    uint32_t sedentary_seconds;
    uint32_t seconds_since_step;
    uint32_t moving_seconds_last_minute;
} velapet_motion_status_t;

typedef struct
{
    velapet_motion_config_t config;

    uint32_t now_ms;
    uint32_t last_second_ms;
    uint32_t last_step_ms;

    uint16_t last_step_counter;
    uint8_t has_step_counter;
    uint8_t has_steps_ever;

    uint32_t steps_today;
    uint32_t pending_steps;
    uint32_t steps_this_second;

    uint8_t steps_per_second[VELAPET_MOTION_STEP_RING_SIZE];
    uint8_t step_ring_index;

    uint32_t frame_samples;
    uint64_t frame_sum_mg;
    uint64_t frame_sumsq_mg;

    velapet_activity_t activity;
    velapet_wear_t wear;
    uint8_t has_light;
    uint32_t last_light_raw;

    uint32_t still_ms;
    uint32_t sedentary_ms;
    uint32_t next_sedentary_report_ms;
    uint8_t inactivity_reported;
    uint32_t walk_credit_ms;
    uint32_t not_walking_ms;
    uint32_t active_minutes_today;
    uint32_t walk_minutes_today;
    uint32_t window_ms;
    uint32_t window_active_ms;

    uint32_t events;
} velapet_motion_t;

/* 填充默认阈值。未标定的光照阈值默认为 0（关闭光照判佩戴）。 */
void velapet_motion_default_config(velapet_motion_config_t *config);

/* config 可为 NULL，此时使用默认配置。成功返回 0。 */
int velapet_motion_init(velapet_motion_t *motion,
                        const velapet_motion_config_t *config,
                        uint32_t now_ms);

/* 加速度单样本，单位 mg。适配器建议 25 Hz 连续喂入。 */
int velapet_motion_feed_accel(velapet_motion_t *motion,
                              uint32_t now_ms,
                              int32_t x_mg,
                              int32_t y_mg,
                              int32_t z_mg);

/* 计步器 16 位累计值。内部处理回绕与计数清零；建议 2 秒轮询一次。 */
int velapet_motion_feed_steps(velapet_motion_t *motion,
                              uint32_t now_ms,
                              uint16_t counter);

/* 环境光原始计数。阈值标定前只记录，不参与判定。 */
int velapet_motion_feed_light(velapet_motion_t *motion,
                              uint32_t now_ms,
                              uint32_t raw);

/* 无新样本时推进时间（每秒调用一次即可）。 */
int velapet_motion_tick(velapet_motion_t *motion, uint32_t now_ms);

/* 跨天：清零当日计数与计时器，保留计步器基线与佩戴状态。 */
void velapet_motion_reset_day(velapet_motion_t *motion, uint32_t now_ms);

/* 取走累计未上报的步数增量。 */
uint32_t velapet_motion_take_steps(velapet_motion_t *motion);

/* 读取并清除事件位掩码（VELAPET_MOTION_EVENT_*）。 */
uint32_t velapet_motion_take_events(velapet_motion_t *motion);

void velapet_motion_status(const velapet_motion_t *motion,
                           velapet_motion_status_t *status);

#ifdef __cplusplus
}
#endif

#endif
