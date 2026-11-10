#include "velapet_service.h"

#include <stdio.h>
#include <string.h>

typedef struct
{
    const char *title;
    const char *unit;
} velapet_task_text_t;

/* 顺序必须与 velapet_task_type_t 一致。 */
static const velapet_task_text_t g_task_text[VELAPET_TASK_COUNT] = {
    {"今日步数", "步"},
    {"连续步行", "分钟"},
    {"每日签到", "天"},
    {"互动打卡", "次"},
};

static velapet_state_t g_state;
static velapet_snapshot_t g_snapshot;
static uint32_t g_day = VELAPET_DAY_UNKNOWN;
static int g_ready = 0;
static uint16_t g_levelup_pending = 0;

static void copy_text(char *dst, size_t cap, const char *src)
{
    if (dst == NULL || cap == 0U)
    {
        return;
    }
    snprintf(dst, cap, "%s", (src != NULL) ? src : "");
}

static uint8_t percent_of(uint32_t value, uint32_t total)
{
    uint64_t pct;

    if (total == 0U)
    {
        return 0U;
    }
    pct = ((uint64_t)value * 100U) / (uint64_t)total;
    return (uint8_t)((pct > 100U) ? 100U : pct);
}

static void fill_tasks(void)
{
    size_t index;
    uint32_t daily_percent = 0U;

    g_snapshot.task_count = (uint8_t)VELAPET_TASK_COUNT;

    for (index = 0U; index < VELAPET_TASK_COUNT; ++index)
    {
        const velapet_task_t *task = &g_state.tasks[index];
        velapet_task_view_t *view = &g_snapshot.tasks[index];

        view->type = task->type;
        view->target = task->target;
        view->progress = task->progress;
        view->exp_reward = task->exp_reward;
        view->status = task->status;
        if ((size_t)task->type < VELAPET_TASK_COUNT)
        {
            copy_text(view->title, sizeof(view->title),
                      g_task_text[task->type].title);
            copy_text(view->unit, sizeof(view->unit),
                      g_task_text[task->type].unit);
        }

        if (task->type == VELAPET_TASK_DAILY_STEPS)
        {
            daily_percent = percent_of(task->progress, task->target);
        }
    }

    g_snapshot.daily_percent = (uint8_t)daily_percent;
}

const velapet_snapshot_t *velapet_service_snapshot(void)
{
    size_t index;

    if (!g_ready)
    {
        return NULL;
    }

    memset(&g_snapshot, 0, sizeof(g_snapshot));

    copy_text(g_snapshot.name, sizeof(g_snapshot.name), g_state.name);
    g_snapshot.level = g_state.level;
    copy_text(g_snapshot.title, sizeof(g_snapshot.title),
              velapet_get_title(g_state.level));
    g_snapshot.exp = g_state.exp;
    g_snapshot.exp_to_next = g_state.exp_to_next;
    g_snapshot.exp_percent = percent_of(g_state.exp, g_state.exp_to_next);
    g_snapshot.total_steps = g_state.total_steps;
    g_snapshot.consecutive_days = g_state.consecutive_days;
    g_snapshot.can_checkin = (g_state.last_checkin_day != g_day) ? 1U : 0U;

    copy_text(g_snapshot.current_skin, sizeof(g_snapshot.current_skin),
              g_state.current_skin);

    if (g_state.unlocked_skin_count > VELAPET_MAX_UNLOCKED_SKINS)
    {
        g_snapshot.unlocked_skin_count = (uint8_t)VELAPET_MAX_UNLOCKED_SKINS;
    }
    else
    {
        g_snapshot.unlocked_skin_count = g_state.unlocked_skin_count;
    }
    for (index = 0U; index < g_snapshot.unlocked_skin_count; ++index)
    {
        copy_text(g_snapshot.unlocked_skins[index],
                  sizeof(g_snapshot.unlocked_skins[index]),
                  g_state.unlocked_skins[index]);
    }

    fill_tasks();
    return &g_snapshot;
}

int velapet_service_init(uint32_t day_id)
{
    if (day_id == VELAPET_DAY_UNKNOWN)
    {
        return -1;
    }

    velapet_state_init(&g_state, day_id);
    g_day = day_id;
    g_ready = 1;
    g_levelup_pending = 0U;
    (void)velapet_service_snapshot();
    return 0;
}

int velapet_service_restore(const velapet_state_t *state, uint32_t day_id)
{
    if (state == NULL || day_id == VELAPET_DAY_UNKNOWN)
    {
        return -1;
    }

    g_state = *state;
    g_day = day_id;
    g_ready = 1;
    g_levelup_pending = 0U;
    (void)velapet_service_snapshot();
    return 0;
}

int velapet_service_set_day(uint32_t day_id)
{
    int result;

    if (!g_ready || day_id == VELAPET_DAY_UNKNOWN)
    {
        return -1;
    }

    result = velapet_refresh_day(&g_state, day_id);
    if (result < 0)
    {
        return -1;
    }
    g_day = day_id;
    return result;
}

int velapet_service_checkin(void)
{
    uint16_t level_before;
    int streak;

    if (!g_ready)
    {
        return -1;
    }

    level_before = g_state.level;
    streak = velapet_check_in(&g_state, g_day);
    if (streak > 0 && g_state.level > level_before)
    {
        g_levelup_pending = g_state.level;
    }
    return streak;
}

int velapet_service_claim(velapet_task_type_t type)
{
    uint16_t level_before;
    int reward;

    if (!g_ready)
    {
        return -1;
    }

    level_before = g_state.level;
    reward = velapet_claim_task(&g_state, g_day, type);
    if (reward > 0 && g_state.level > level_before)
    {
        g_levelup_pending = g_state.level;
    }
    return reward;
}

int velapet_service_switch_skin(const char *skin_id)
{
    if (!g_ready || skin_id == NULL)
    {
        return -1;
    }
    return velapet_switch_skin(&g_state, skin_id);
}

int velapet_service_record_steps(uint32_t steps)
{
    if (!g_ready)
    {
        return -1;
    }
    return velapet_record_steps(&g_state, g_day, steps);
}

int velapet_service_record_exercise_minutes(uint32_t minutes)
{
    if (!g_ready)
    {
        return -1;
    }
    return velapet_record_exercise_minutes(&g_state, g_day, minutes);
}

int velapet_service_record_social(void)
{
    if (!g_ready)
    {
        return -1;
    }
    return velapet_record_social(&g_state, g_day);
}

uint16_t velapet_service_last_levelup(void)
{
    return g_levelup_pending;
}

void velapet_service_ack_levelup(void)
{
    g_levelup_pending = 0U;
}

const velapet_state_t *velapet_service_raw_state(void)
{
    return g_ready ? &g_state : NULL;
}
