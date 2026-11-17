#include <assert.h>
#include <stdio.h>

#include "velapet_motion.h"

#define SAMPLES_PER_SECOND 25U

/* 每秒喂 25 个样本，|a| 在 1000 +/- std_mg 之间交替，标准差即 std_mg。 */
static void feed_second(velapet_motion_t *motion,
                        uint32_t *now_ms,
                        uint32_t std_mg,
                        uint16_t *step_counter,
                        uint32_t steps_this_second)
{
    uint32_t sample;

    if (step_counter != NULL)
    {
        *step_counter = (uint16_t)(*step_counter + steps_this_second);
        assert(velapet_motion_feed_steps(motion, *now_ms, *step_counter) == 0);
    }

    for (sample = 0U; sample < SAMPLES_PER_SECOND; ++sample)
    {
        int32_t offset = ((sample % 2U) == 0U) ? (int32_t)std_mg
                                               : -(int32_t)std_mg;
        assert(velapet_motion_feed_accel(motion, *now_ms + sample * 40U,
                                         1000 + offset, 0, 0) == 0);
    }

    *now_ms += 1000U;
    assert(velapet_motion_tick(motion, *now_ms) == 0);
}

static void feed_seconds(velapet_motion_t *motion,
                         uint32_t *now_ms,
                         uint32_t std_mg,
                         uint16_t *step_counter,
                         uint32_t steps_per_second,
                         uint32_t seconds)
{
    uint32_t index;

    for (index = 0U; index < seconds; ++index)
    {
        feed_second(motion, now_ms, std_mg, step_counter,
                    (step_counter != NULL) ? steps_per_second : 0U);
    }
}

static void test_init(void)
{
    velapet_motion_t motion;
    velapet_motion_config_t config;

    assert(velapet_motion_init(NULL, NULL, 0U) == -1);
    assert(velapet_motion_feed_accel(NULL, 0U, 0, 0, 0) == -1);
    assert(velapet_motion_feed_steps(NULL, 0U, 0U) == -1);
    assert(velapet_motion_feed_light(NULL, 0U, 0U) == -1);
    assert(velapet_motion_tick(NULL, 0U) == -1);

    velapet_motion_default_config(&config);
    assert(config.sedentary_limit_ms == 45U * 60U * 1000U);
    assert(config.inactivity_limit_ms == 2U * 60U * 60U * 1000U);
    assert(config.light_dark_raw == 0U);

    assert(velapet_motion_init(&motion, NULL, 500U) == 0);
    assert(motion.activity == VELAPET_ACTIVITY_UNKNOWN);
    assert(motion.wear == VELAPET_WEAR_UNKNOWN);
}

static void test_step_counter_wrap_and_reset(void)
{
    velapet_motion_t motion;
    velapet_motion_status_t status;

    assert(velapet_motion_init(&motion, NULL, 0U) == 0);

    assert(velapet_motion_feed_steps(&motion, 100U, 65530U) == 0);
    assert(velapet_motion_take_steps(&motion) == 0U);

    /* 16 位回绕：65530 -> 5 应为 11 步。 */
    assert(velapet_motion_feed_steps(&motion, 200U, 5U) == 0);
    assert(velapet_motion_take_steps(&motion) == 11U);

    /* 单次跳变超过 500 步视为计数清零，丢弃。 */
    assert(velapet_motion_feed_steps(&motion, 300U, 600U) == 0);
    assert(velapet_motion_take_steps(&motion) == 0U);

    assert(velapet_motion_feed_steps(&motion, 400U, 610U) == 0);
    assert(velapet_motion_take_steps(&motion) == 10U);

    /* 计数器重启到较小值后应重新建立基线。 */
    assert(velapet_motion_feed_steps(&motion, 500U, 65500U) == 0);
    assert(velapet_motion_take_steps(&motion) == 0U);
    assert(velapet_motion_feed_steps(&motion, 600U, 4U) == 0);
    assert(velapet_motion_take_steps(&motion) == 40U);

    velapet_motion_status(&motion, &status);
    assert(status.steps_today == 61U);
}

static void test_sedentary_and_break(void)
{
    velapet_motion_t motion;
    velapet_motion_status_t status;
    velapet_motion_config_t config;
    uint32_t now = 0U;
    uint32_t events;
    uint16_t counter = 1000U;

    velapet_motion_default_config(&config);
    assert(velapet_motion_init(&motion, &config, now) == 0);
    assert(velapet_motion_feed_steps(&motion, now, counter) == 0);

    /* 46 分钟静止：45 分钟时应产生久坐事件。 */
    feed_seconds(&motion, &now, 5U, NULL, 0U, 46U * 60U);

    events = velapet_motion_take_events(&motion);
    assert((events & VELAPET_MOTION_EVENT_SEDENTARY) != 0U);
    assert((events & VELAPET_MOTION_EVENT_INACTIVITY) == 0U);

    velapet_motion_status(&motion, &status);
    assert(status.activity == VELAPET_ACTIVITY_STILL);
    assert(status.sedentary_seconds >= 45U * 60U);
    assert(status.steps_today == 0U);

    /* 30 步断坐：久坐计时归零。 */
    feed_seconds(&motion, &now, 200U, &counter, 6U, 5U);
    velapet_motion_status(&motion, &status);
    assert(status.steps_today == 30U);
    assert(status.sedentary_seconds == 0U);
    assert(status.activity == VELAPET_ACTIVITY_WALKING);
}

static void test_walk_and_active_minutes(void)
{
    velapet_motion_t motion;
    velapet_motion_status_t status;
    velapet_motion_config_t config;
    uint32_t now = 0U;
    uint32_t events;
    uint16_t counter = 0U;

    velapet_motion_default_config(&config);
    assert(velapet_motion_init(&motion, &config, now) == 0);
    assert(velapet_motion_feed_steps(&motion, now, counter) == 0);

    /* 连续行走 10 分钟，每秒 1 步。 */
    feed_seconds(&motion, &now, 200U, &counter, 1U, 10U * 60U);

    events = velapet_motion_take_events(&motion);
    assert((events & VELAPET_MOTION_EVENT_WALK_MINUTE) != 0U);
    assert((events & VELAPET_MOTION_EVENT_ACTIVE_MINUTE) != 0U);

    velapet_motion_status(&motion, &status);
    assert(status.activity == VELAPET_ACTIVITY_WALKING);
    assert(status.walk_minutes_today == 10U);
    assert(status.active_minutes_today == 10U);
    assert(status.steps_today == 600U);
    assert(velapet_motion_take_steps(&motion) == 600U);

    /* 停止 3 分钟以上，未满一分钟的行走部分被丢弃。 */
    feed_seconds(&motion, &now, 5U, NULL, 0U, 200U);
    /* 再走 40 秒，不足一分钟，不增加行走分钟。 */
    feed_seconds(&motion, &now, 200U, &counter, 1U, 40U);
    velapet_motion_status(&motion, &status);
    assert(status.walk_minutes_today == 10U);
}

static void test_light_activity_minutes(void)
{
    velapet_motion_t motion;
    velapet_motion_status_t status;
    uint32_t now = 0U;

    assert(velapet_motion_init(&motion, NULL, now) == 0);

    /* 1 分钟手部活动但无步数：算活动分钟，不算行走。 */
    feed_seconds(&motion, &now, 100U, NULL, 0U, 60U);

    velapet_motion_status(&motion, &status);
    assert(status.activity == VELAPET_ACTIVITY_LIGHT);
    assert(status.active_minutes_today == 1U);
    assert(status.walk_minutes_today == 0U);
}

static void test_nonwear_suppresses_sedentary(void)
{
    velapet_motion_t motion;
    velapet_motion_status_t status;
    velapet_motion_config_t config;
    uint32_t now = 0U;
    uint32_t second;
    uint32_t events;

    velapet_motion_default_config(&config);
    config.light_dark_raw = 100U;
    assert(velapet_motion_init(&motion, &config, now) == 0);

    /* 46 分钟静止且光照暗：判为非佩戴，久坐计时暂停。 */
    for (second = 0U; second < 46U * 60U; ++second)
    {
        assert(velapet_motion_feed_light(&motion, now, 10U) == 0);
        feed_second(&motion, &now, 5U, NULL, 0U);
    }

    events = velapet_motion_take_events(&motion);
    assert((events & VELAPET_MOTION_EVENT_SEDENTARY) == 0U);

    velapet_motion_status(&motion, &status);
    assert(status.wear == VELAPET_WEAR_NOT_WORN);

    /* 光照恢复后重新判为佩戴，且久坐计时从零附近继续。 */
    assert(velapet_motion_feed_light(&motion, now, 500U) == 0);
    velapet_motion_status(&motion, &status);
    assert(status.wear == VELAPET_WEAR_WORN);
    assert(status.sedentary_seconds < 5U);
}

static void test_day_reset(void)
{
    velapet_motion_t motion;
    velapet_motion_status_t status;
    uint32_t now = 0U;
    uint16_t counter = 0U;

    assert(velapet_motion_init(&motion, NULL, now) == 0);
    assert(velapet_motion_feed_steps(&motion, now, counter) == 0);
    feed_seconds(&motion, &now, 200U, &counter, 1U, 120U);

    velapet_motion_status(&motion, &status);
    assert(status.steps_today == 120U);

    velapet_motion_reset_day(&motion, now);
    velapet_motion_status(&motion, &status);
    assert(status.steps_today == 0U);
    assert(status.active_minutes_today == 0U);
    assert(status.walk_minutes_today == 0U);
    assert(status.sedentary_seconds == 0U);

    /* 日切后计步器基线保留，只统计新增步数。 */
    assert(velapet_motion_feed_steps(&motion, now + 1000U, (uint16_t)(counter + 5U)) == 0);
    assert(velapet_motion_take_steps(&motion) == 5U);
    velapet_motion_status(&motion, &status);
    assert(status.steps_today == 5U);
}

int main(void)
{
    test_init();
    test_step_counter_wrap_and_reset();
    test_sedentary_and_break();
    test_walk_and_active_minutes();
    test_light_activity_minutes();
    test_nonwear_suppresses_sedentary();
    test_day_reset();

    printf("VELAPET_MOTION_TEST result=PASS cases=7\n");
    return 0;
}
