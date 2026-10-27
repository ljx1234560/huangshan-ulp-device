#include "velapet_core.h"

#include <limits.h>
#include <string.h>

typedef struct
{
    velapet_task_type_t type;
    uint32_t target;
    uint32_t reward;
} velapet_task_definition_t;

static const velapet_task_definition_t g_task_definitions[VELAPET_TASK_COUNT] =
{
    {VELAPET_TASK_DAILY_STEPS, 3000U, 20U},
    {VELAPET_TASK_CONTINUOUS_WALK, 10U, 30U},
    {VELAPET_TASK_CHECK_IN, 1U, 10U},
    {VELAPET_TASK_SOCIAL, 1U, 15U}
};

static const char *const g_skin_ids[VELAPET_MAX_UNLOCKED_SKINS] =
{
    VELAPET_SKIN_DEFAULT,
    VELAPET_SKIN_SPORT_BLUE,
    VELAPET_SKIN_FLAME_RED,
    VELAPET_SKIN_STAR_PURPLE,
    VELAPET_SKIN_RAINBOW
};

static void copy_string(char *destination, size_t capacity, const char *source)
{
    size_t length;

    if (destination == NULL || capacity == 0U)
    {
        return;
    }

    if (source == NULL)
    {
        destination[0] = '\0';
        return;
    }

    length = strlen(source);
    if (length >= capacity)
    {
        length = capacity - 1U;
    }
    memcpy(destination, source, length);
    destination[length] = '\0';
}

static velapet_task_t *find_task(velapet_state_t *state,
                                 velapet_task_type_t type)
{
    size_t index;

    if (state == NULL)
    {
        return NULL;
    }

    for (index = 0U; index < VELAPET_TASK_COUNT; ++index)
    {
        if (state->tasks[index].type == type)
        {
            return &state->tasks[index];
        }
    }
    return NULL;
}

static void reset_tasks(velapet_state_t *state, uint32_t day_id)
{
    size_t index;

    for (index = 0U; index < VELAPET_TASK_COUNT; ++index)
    {
        state->tasks[index].type = g_task_definitions[index].type;
        state->tasks[index].target = g_task_definitions[index].target;
        state->tasks[index].progress = 0U;
        state->tasks[index].exp_reward = g_task_definitions[index].reward;
        state->tasks[index].status = VELAPET_TASK_NOT_STARTED;
    }
    state->task_day = day_id;
}

static int update_task(velapet_state_t *state,
                       velapet_task_type_t type,
                       uint32_t delta)
{
    velapet_task_t *task;
    uint32_t remaining;

    if (state == NULL || delta == 0U)
    {
        return -1;
    }

    task = find_task(state, type);
    if (task == NULL)
    {
        return -1;
    }
    if (task->status == VELAPET_TASK_REWARD_CLAIMED)
    {
        return 0;
    }

    remaining = task->target - task->progress;
    task->progress += (delta < remaining) ? delta : remaining;
    task->status = (task->progress >= task->target)
                       ? VELAPET_TASK_COMPLETED
                       : VELAPET_TASK_IN_PROGRESS;
    return 1;
}

static void apply_level_reward(velapet_state_t *state)
{
    if (state->level >= 2U)
    {
        (void)velapet_unlock_skin(state, VELAPET_SKIN_SPORT_BLUE);
    }
    if (state->level >= 5U)
    {
        (void)velapet_unlock_skin(state, VELAPET_SKIN_FLAME_RED);
    }
    if (state->level >= 10U)
    {
        (void)velapet_unlock_skin(state, VELAPET_SKIN_STAR_PURPLE);
    }
}

void velapet_state_init(velapet_state_t *state, uint32_t day_id)
{
    if (state == NULL)
    {
        return;
    }

    memset(state, 0, sizeof(*state));
    copy_string(state->name, sizeof(state->name), "NOVA");
    state->level = 1U;
    state->exp_to_next = velapet_exp_required(state->level);
    state->last_active_day = day_id;
    state->last_checkin_day = VELAPET_DAY_UNKNOWN;
    copy_string(state->current_skin, sizeof(state->current_skin),
                VELAPET_SKIN_DEFAULT);
    (void)velapet_unlock_skin(state, VELAPET_SKIN_DEFAULT);
    reset_tasks(state, day_id);
}

int velapet_refresh_day(velapet_state_t *state, uint32_t day_id)
{
    if (state == NULL || day_id == VELAPET_DAY_UNKNOWN)
    {
        return -1;
    }
    if (day_id == state->task_day)
    {
        return 0;
    }
    if (state->task_day != VELAPET_DAY_UNKNOWN && day_id < state->task_day)
    {
        return -1;
    }

    reset_tasks(state, day_id);
    return 1;
}

uint32_t velapet_exp_required(uint16_t level)
{
    if (level <= 1U)
    {
        return 100U;
    }
    return ((uint32_t)level * 100U) + 50U;
}

int velapet_add_exp(velapet_state_t *state, uint32_t amount)
{
    int levels_gained = 0;

    if (state == NULL || amount == 0U)
    {
        return -1;
    }

    if (UINT32_MAX - state->exp < amount)
    {
        state->exp = UINT32_MAX;
    }
    else
    {
        state->exp += amount;
    }

    while (state->exp >= state->exp_to_next && state->level < UINT16_MAX)
    {
        state->exp -= state->exp_to_next;
        ++state->level;
        ++levels_gained;
        state->exp_to_next = velapet_exp_required(state->level);
        apply_level_reward(state);
    }
    return levels_gained;
}

int velapet_record_steps(velapet_state_t *state,
                         uint32_t day_id,
                         uint32_t steps)
{
    if (state == NULL || steps == 0U || velapet_refresh_day(state, day_id) < 0)
    {
        return -1;
    }

    if (UINT64_MAX - state->total_steps < steps)
    {
        state->total_steps = UINT64_MAX;
    }
    else
    {
        state->total_steps += steps;
    }
    state->last_active_day = day_id;
    return update_task(state, VELAPET_TASK_DAILY_STEPS, steps);
}

int velapet_record_exercise_minutes(velapet_state_t *state,
                                    uint32_t day_id,
                                    uint32_t minutes)
{
    if (state == NULL || minutes == 0U ||
            velapet_refresh_day(state, day_id) < 0)
    {
        return -1;
    }

    state->last_active_day = day_id;
    return update_task(state, VELAPET_TASK_CONTINUOUS_WALK, minutes);
}

int velapet_record_social(velapet_state_t *state, uint32_t day_id)
{
    if (state == NULL || velapet_refresh_day(state, day_id) < 0)
    {
        return -1;
    }

    state->last_active_day = day_id;
    return update_task(state, VELAPET_TASK_SOCIAL, 1U);
}

int velapet_check_in(velapet_state_t *state, uint32_t day_id)
{
    if (state == NULL || velapet_refresh_day(state, day_id) < 0)
    {
        return -1;
    }
    if (state->last_checkin_day == day_id)
    {
        return 0;
    }

    if (state->last_checkin_day != VELAPET_DAY_UNKNOWN &&
            state->last_checkin_day != UINT32_MAX &&
            state->last_checkin_day + 1U == day_id)
    {
        ++state->consecutive_days;
    }
    else
    {
        state->consecutive_days = 1U;
    }

    state->last_checkin_day = day_id;
    state->last_active_day = day_id;
    (void)update_task(state, VELAPET_TASK_CHECK_IN, 1U);
    if (state->consecutive_days >= 3U)
    {
        (void)velapet_unlock_skin(state, VELAPET_SKIN_RAINBOW);
    }
    return (int)state->consecutive_days;
}

int velapet_claim_task(velapet_state_t *state,
                       uint32_t day_id,
                       velapet_task_type_t type)
{
    velapet_task_t *task;
    uint32_t reward;

    if (state == NULL || velapet_refresh_day(state, day_id) < 0)
    {
        return -1;
    }

    task = find_task(state, type);
    if (task == NULL)
    {
        return -1;
    }
    if (task->status != VELAPET_TASK_COMPLETED)
    {
        return 0;
    }

    reward = task->exp_reward;
    task->status = VELAPET_TASK_REWARD_CLAIMED;
    (void)velapet_add_exp(state, reward);
    return (int)reward;
}

const velapet_task_t *velapet_get_task(const velapet_state_t *state,
                                       velapet_task_type_t type)
{
    size_t index;

    if (state == NULL)
    {
        return NULL;
    }
    for (index = 0U; index < VELAPET_TASK_COUNT; ++index)
    {
        if (state->tasks[index].type == type)
        {
            return &state->tasks[index];
        }
    }
    return NULL;
}

uint8_t velapet_completed_task_count(const velapet_state_t *state)
{
    uint8_t count = 0U;
    size_t index;

    if (state == NULL)
    {
        return 0U;
    }
    for (index = 0U; index < VELAPET_TASK_COUNT; ++index)
    {
        if (state->tasks[index].status == VELAPET_TASK_COMPLETED ||
                state->tasks[index].status == VELAPET_TASK_REWARD_CLAIMED)
        {
            ++count;
        }
    }
    return count;
}

int velapet_is_skin_known(const char *skin_id)
{
    size_t index;

    if (skin_id == NULL || skin_id[0] == '\0')
    {
        return 0;
    }
    for (index = 0U; index < VELAPET_MAX_UNLOCKED_SKINS; ++index)
    {
        if (strcmp(g_skin_ids[index], skin_id) == 0)
        {
            return 1;
        }
    }
    return 0;
}

int velapet_is_skin_unlocked(const velapet_state_t *state,
                             const char *skin_id)
{
    uint8_t index;

    if (state == NULL || !velapet_is_skin_known(skin_id))
    {
        return 0;
    }
    for (index = 0U; index < state->unlocked_skin_count &&
            index < VELAPET_MAX_UNLOCKED_SKINS; ++index)
    {
        if (strcmp(state->unlocked_skins[index], skin_id) == 0)
        {
            return 1;
        }
    }
    return 0;
}

int velapet_unlock_skin(velapet_state_t *state, const char *skin_id)
{
    if (state == NULL || !velapet_is_skin_known(skin_id))
    {
        return -1;
    }
    if (velapet_is_skin_unlocked(state, skin_id))
    {
        return 0;
    }
    if (state->unlocked_skin_count >= VELAPET_MAX_UNLOCKED_SKINS)
    {
        return -1;
    }

    copy_string(state->unlocked_skins[state->unlocked_skin_count],
                sizeof(state->unlocked_skins[state->unlocked_skin_count]),
                skin_id);
    ++state->unlocked_skin_count;
    return 0;
}

int velapet_switch_skin(velapet_state_t *state, const char *skin_id)
{
    if (!velapet_is_skin_unlocked(state, skin_id))
    {
        return -1;
    }

    copy_string(state->current_skin, sizeof(state->current_skin), skin_id);
    return 0;
}

const char *velapet_get_title(uint16_t level)
{
    if (level <= 5U)
    {
        return "egg_baby";
    }
    if (level <= 10U)
    {
        return "young_pet";
    }
    if (level <= 20U)
    {
        return "sport_star";
    }
    return "vela_legend";
}
