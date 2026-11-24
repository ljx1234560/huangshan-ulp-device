#include "velapet_motion.h"

#include <string.h>

/* 单次计步读数超过该值视为计数清零或异常，丢弃该增量。 */
#define VELAPET_MOTION_STEP_DELTA_LIMIT 500U

/* 时间跳跃过大时最多补算的秒数，避免异常时间戳造成长循环。 */
#define VELAPET_MOTION_MAX_CATCHUP_SECONDS 600U

static uint32_t isqrt64(uint64_t value)
{
    uint64_t root = 0U;
    uint64_t bit = 1ULL << 62;

    while (bit > value)
    {
        bit >>= 2;
    }
    while (bit != 0U)
    {
        if (value >= root + bit)
        {
            value -= root + bit;
            root = (root >> 1) + bit;
        }
        else
        {
            root >>= 1;
        }
        bit >>= 2;
    }
    return (uint32_t)root;
}

static uint32_t magnitude_mg(int32_t x_mg, int32_t y_mg, int32_t z_mg)
{
    int64_t square_sum = (int64_t)x_mg * (int64_t)x_mg +
                         (int64_t)y_mg * (int64_t)y_mg +
                         (int64_t)z_mg * (int64_t)z_mg;

    if (square_sum < 0)
    {
        return 0U;
    }
    return isqrt64((uint64_t)square_sum);
}

static void reset_frame(velapet_motion_t *motion)
{
    motion->frame_samples = 0U;
    motion->frame_sum_mg = 0U;
    motion->frame_sumsq_mg = 0U;
}

static uint32_t sum_steps_ring(const velapet_motion_t *motion)
{
    uint32_t total = 0U;
    size_t index;

    for (index = 0U; index < VELAPET_MOTION_STEP_RING_SIZE; ++index)
    {
        total += motion->steps_per_second[index];
    }
    return total;
}

void velapet_motion_default_config(velapet_motion_config_t *config)
{
    if (config == NULL)
    {
        return;
    }

    config->still_std_mg = 25U;
    config->moving_std_mg = 45U;
    config->walk_hold_ms = 10000U;
    config->walk_break_ms = 180000U;
    config->active_seconds_per_minute = 20U;
    config->sedentary_limit_ms = 45U * 60U * 1000U;
    config->inactivity_limit_ms = 2U * 60U * 60U * 1000U;
    config->sedentary_reset_steps = 30U;
    config->nonwear_still_ms = 10U * 60U * 1000U;
    config->light_dark_raw = 0U;
}

int velapet_motion_init(velapet_motion_t *motion,
                        const velapet_motion_config_t *config,
                        uint32_t now_ms)
{
    if (motion == NULL)
    {
        return -1;
    }

    memset(motion, 0, sizeof(*motion));
    if (config != NULL)
    {
        motion->config = *config;
    }
    else
    {
        velapet_motion_default_config(&motion->config);
    }

    motion->now_ms = now_ms;
    motion->last_second_ms = now_ms;
    motion->last_step_ms = now_ms;
    motion->next_sedentary_report_ms = motion->config.sedentary_limit_ms;
    motion->activity = VELAPET_ACTIVITY_UNKNOWN;
    motion->wear = VELAPET_WEAR_UNKNOWN;
    return 0;
}

static void rebase_inactivity(velapet_motion_t *motion, uint32_t now_ms)
{
    motion->last_step_ms = now_ms;
    motion->inactivity_reported = 0U;
}

static void update_wear(velapet_motion_t *motion, uint32_t now_ms)
{
    velapet_wear_t previous = motion->wear;

    if (motion->activity != VELAPET_ACTIVITY_STILL)
    {
        motion->wear = VELAPET_WEAR_WORN;
    }
    else if (motion->config.light_dark_raw > 0U && motion->has_light != 0U)
    {
        if (motion->last_light_raw >= motion->config.light_dark_raw)
        {
            motion->wear = VELAPET_WEAR_WORN;
        }
        else if (motion->still_ms >= motion->config.nonwear_still_ms)
        {
            motion->wear = VELAPET_WEAR_NOT_WORN;
        }
    }

    if (previous == VELAPET_WEAR_NOT_WORN && motion->wear != VELAPET_WEAR_NOT_WORN)
    {
        rebase_inactivity(motion, now_ms);
    }
    else if (previous != VELAPET_WEAR_NOT_WORN &&
             motion->wear == VELAPET_WEAR_NOT_WORN)
    {
        /* 摘下后不再累计久坐，重新佩戴时从头计时。 */
        motion->sedentary_ms = 0U;
        motion->next_sedentary_report_ms = motion->config.sedentary_limit_ms;
    }
}

static void update_walk(velapet_motion_t *motion)
{
    if (motion->activity == VELAPET_ACTIVITY_WALKING)
    {
        motion->not_walking_ms = 0U;
        motion->walk_credit_ms += 1000U;
        while (motion->walk_credit_ms >= 60000U)
        {
            motion->walk_credit_ms -= 60000U;
            ++motion->walk_minutes_today;
            motion->events |= VELAPET_MOTION_EVENT_WALK_MINUTE;
        }
    }
    else
    {
        if (motion->not_walking_ms < motion->config.walk_break_ms)
        {
            motion->not_walking_ms += 1000U;
        }
        if (motion->not_walking_ms >= motion->config.walk_break_ms)
        {
            motion->walk_credit_ms = 0U;
        }
    }
}

static void update_active_window(velapet_motion_t *motion)
{
    uint32_t required_ms;

    motion->window_ms += 1000U;
    if (motion->activity == VELAPET_ACTIVITY_WALKING ||
            motion->activity == VELAPET_ACTIVITY_LIGHT)
    {
        motion->window_active_ms += 1000U;
    }

    if (motion->window_ms >= 60000U)
    {
        required_ms = motion->config.active_seconds_per_minute * 1000U;
        if (motion->window_active_ms >= required_ms)
        {
            ++motion->active_minutes_today;
            motion->events |= VELAPET_MOTION_EVENT_ACTIVE_MINUTE;
        }
        motion->window_ms = 0U;
        motion->window_active_ms = 0U;
    }
}

static void update_sedentary(velapet_motion_t *motion, uint32_t steps_last_minute)
{
    uint32_t limit = motion->config.sedentary_limit_ms;

    if (limit == 0U)
    {
        return;
    }

    if (steps_last_minute >= motion->config.sedentary_reset_steps)
    {
        motion->sedentary_ms = 0U;
        motion->next_sedentary_report_ms = limit;
    }

    if (motion->activity == VELAPET_ACTIVITY_WALKING)
    {
        motion->sedentary_ms = 0U;
        motion->next_sedentary_report_ms = limit;
    }
    else if (motion->activity == VELAPET_ACTIVITY_STILL &&
             motion->wear != VELAPET_WEAR_NOT_WORN)
    {
        if (motion->sedentary_ms <= UINT32_MAX - 1000U)
        {
            motion->sedentary_ms += 1000U;
        }
        if (motion->sedentary_ms >= motion->next_sedentary_report_ms)
        {
            motion->events |= VELAPET_MOTION_EVENT_SEDENTARY;
            motion->next_sedentary_report_ms += limit;
        }
    }
}

static void finalize_second(velapet_motion_t *motion, uint32_t boundary_ms)
{
    uint8_t has_frame = (motion->frame_samples > 0U) ? 1U : 0U;
    uint8_t moving = 0U;
    uint8_t step_recent;
    uint32_t steps_last_minute;
    uint32_t std_limit_mg;

    motion->steps_per_second[motion->step_ring_index] =
        (uint8_t)((motion->steps_this_second > UINT8_MAX) ?
                  UINT8_MAX : motion->steps_this_second);
    motion->steps_this_second = 0U;
    motion->step_ring_index = (uint8_t)
        ((motion->step_ring_index + 1U) % VELAPET_MOTION_STEP_RING_SIZE);
    steps_last_minute = sum_steps_ring(motion);

    if (has_frame != 0U)
    {
        uint64_t samples = motion->frame_samples;
        int64_t mean = (int64_t)(motion->frame_sum_mg / samples);
        int64_t variance =
            (int64_t)(motion->frame_sumsq_mg / samples) - (mean * mean);

        if (variance < 0)
        {
            variance = 0;
        }
        std_limit_mg = (motion->activity == VELAPET_ACTIVITY_WALKING ||
                        motion->activity == VELAPET_ACTIVITY_LIGHT)
                           ? motion->config.still_std_mg
                           : motion->config.moving_std_mg;
        moving = ((uint64_t)variance >=
                  (uint64_t)std_limit_mg * (uint64_t)std_limit_mg) ? 1U : 0U;
    }
    reset_frame(motion);

    step_recent = (motion->has_steps_ever != 0U &&
                   (uint32_t)(boundary_ms - motion->last_step_ms) <
                   motion->config.walk_hold_ms) ? 1U : 0U;

    if (has_frame == 0U && step_recent == 0U)
    {
        return;
    }

    if (step_recent != 0U)
    {
        motion->activity = VELAPET_ACTIVITY_WALKING;
    }
    else if (moving != 0U)
    {
        motion->activity = VELAPET_ACTIVITY_LIGHT;
    }
    else
    {
        motion->activity = VELAPET_ACTIVITY_STILL;
    }

    if (motion->activity == VELAPET_ACTIVITY_STILL)
    {
        if (motion->still_ms <= UINT32_MAX - 1000U)
        {
            motion->still_ms += 1000U;
        }
    }
    else
    {
        motion->still_ms = 0U;
    }

    update_wear(motion, boundary_ms);
    update_walk(motion);
    update_active_window(motion);
    update_sedentary(motion, steps_last_minute);
}

static void check_inactivity(velapet_motion_t *motion, uint32_t now_ms)
{
    if (motion->config.inactivity_limit_ms == 0U ||
            motion->wear == VELAPET_WEAR_NOT_WORN)
    {
        return;
    }
    if (motion->inactivity_reported == 0U &&
            (uint32_t)(now_ms - motion->last_step_ms) >=
            motion->config.inactivity_limit_ms)
    {
        motion->inactivity_reported = 1U;
        motion->events |= VELAPET_MOTION_EVENT_INACTIVITY;
    }
}

static void advance(velapet_motion_t *motion, uint32_t now_ms)
{
    uint32_t caught_up = 0U;

    if ((int32_t)(now_ms - motion->last_second_ms) < 0)
    {
        motion->last_second_ms = now_ms;
        reset_frame(motion);
    }

    while ((uint32_t)(now_ms - motion->last_second_ms) >= 1000U)
    {
        finalize_second(motion, motion->last_second_ms + 1000U);
        motion->last_second_ms += 1000U;
        ++caught_up;
        if (caught_up >= VELAPET_MOTION_MAX_CATCHUP_SECONDS)
        {
            motion->last_second_ms = now_ms;
            reset_frame(motion);
            break;
        }
    }

    motion->now_ms = now_ms;
    check_inactivity(motion, now_ms);
}

int velapet_motion_feed_accel(velapet_motion_t *motion,
                              uint32_t now_ms,
                              int32_t x_mg,
                              int32_t y_mg,
                              int32_t z_mg)
{
    uint32_t magnitude;

    if (motion == NULL)
    {
        return -1;
    }

    advance(motion, now_ms);
    magnitude = magnitude_mg(x_mg, y_mg, z_mg);
    motion->frame_sum_mg += magnitude;
    motion->frame_sumsq_mg += (uint64_t)magnitude * magnitude;
    ++motion->frame_samples;
    return 0;
}

int velapet_motion_feed_steps(velapet_motion_t *motion,
                              uint32_t now_ms,
                              uint16_t counter)
{
    uint32_t delta = 0U;

    if (motion == NULL)
    {
        return -1;
    }

    advance(motion, now_ms);

    if (motion->has_step_counter == 0U)
    {
        motion->has_step_counter = 1U;
    }
    else
    {
        delta = (uint16_t)(counter - motion->last_step_counter);
        if (delta > VELAPET_MOTION_STEP_DELTA_LIMIT)
        {
            delta = 0U;
        }
    }
    motion->last_step_counter = counter;

    if (delta == 0U)
    {
        return 0;
    }

    if (motion->steps_today > UINT32_MAX - delta)
    {
        motion->steps_today = UINT32_MAX;
    }
    else
    {
        motion->steps_today += delta;
    }
    motion->pending_steps += delta;
    motion->steps_this_second += delta;
    motion->last_step_ms = now_ms;
    motion->has_steps_ever = 1U;
    motion->inactivity_reported = 0U;
    if (motion->wear == VELAPET_WEAR_NOT_WORN)
    {
        motion->wear = VELAPET_WEAR_WORN;
    }
    return 0;
}

int velapet_motion_feed_light(velapet_motion_t *motion,
                              uint32_t now_ms,
                              uint32_t raw)
{
    if (motion == NULL)
    {
        return -1;
    }

    advance(motion, now_ms);
    motion->last_light_raw = raw;
    motion->has_light = 1U;
    if (motion->config.light_dark_raw > 0U &&
            raw >= motion->config.light_dark_raw &&
            motion->wear == VELAPET_WEAR_NOT_WORN)
    {
        motion->wear = VELAPET_WEAR_WORN;
        rebase_inactivity(motion, now_ms);
    }
    return 0;
}

int velapet_motion_tick(velapet_motion_t *motion, uint32_t now_ms)
{
    if (motion == NULL)
    {
        return -1;
    }

    advance(motion, now_ms);
    return 0;
}

void velapet_motion_reset_day(velapet_motion_t *motion, uint32_t now_ms)
{
    if (motion == NULL)
    {
        return;
    }

    motion->steps_today = 0U;
    motion->pending_steps = 0U;
    motion->steps_this_second = 0U;
    memset(motion->steps_per_second, 0, sizeof(motion->steps_per_second));
    motion->step_ring_index = 0U;

    motion->active_minutes_today = 0U;
    motion->walk_minutes_today = 0U;
    motion->window_ms = 0U;
    motion->window_active_ms = 0U;
    motion->walk_credit_ms = 0U;
    motion->not_walking_ms = 0U;

    motion->sedentary_ms = 0U;
    motion->next_sedentary_report_ms = motion->config.sedentary_limit_ms;
    motion->still_ms = 0U;
    motion->inactivity_reported = 0U;
    motion->last_step_ms = now_ms;
    motion->events = 0U;
}

uint32_t velapet_motion_take_steps(velapet_motion_t *motion)
{
    uint32_t steps;

    if (motion == NULL)
    {
        return 0U;
    }

    steps = motion->pending_steps;
    motion->pending_steps = 0U;
    return steps;
}

uint32_t velapet_motion_take_events(velapet_motion_t *motion)
{
    uint32_t events;

    if (motion == NULL)
    {
        return 0U;
    }

    events = motion->events;
    motion->events = 0U;
    return events;
}

void velapet_motion_status(const velapet_motion_t *motion,
                           velapet_motion_status_t *status)
{
    if (status == NULL)
    {
        return;
    }

    memset(status, 0, sizeof(*status));
    if (motion == NULL)
    {
        return;
    }

    status->activity = motion->activity;
    status->wear = motion->wear;
    status->steps_today = motion->steps_today;
    status->active_minutes_today = motion->active_minutes_today;
    status->walk_minutes_today = motion->walk_minutes_today;
    status->sedentary_seconds = motion->sedentary_ms / 1000U;
    status->seconds_since_step =
        (uint32_t)(motion->now_ms - motion->last_step_ms) / 1000U;
    status->moving_seconds_last_minute = motion->window_active_ms / 1000U;
}
