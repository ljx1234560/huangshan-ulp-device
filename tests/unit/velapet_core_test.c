#include "velapet_core.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static void test_default_state(void)
{
    velapet_state_t state;
    const velapet_task_t *steps;

    velapet_state_init(&state, 100U);
    steps = velapet_get_task(&state, VELAPET_TASK_DAILY_STEPS);

    assert(strcmp(state.name, "NOVA") == 0);
    assert(state.level == 1U);
    assert(state.exp == 0U);
    assert(state.exp_to_next == 100U);
    assert(state.task_day == 100U);
    assert(state.last_checkin_day == VELAPET_DAY_UNKNOWN);
    assert(strcmp(state.current_skin, VELAPET_SKIN_DEFAULT) == 0);
    assert(velapet_is_skin_unlocked(&state, VELAPET_SKIN_DEFAULT) == 1);
    assert(velapet_is_skin_unlocked(&state, VELAPET_SKIN_SPORT_BLUE) == 0);
    assert(steps != NULL);
    assert(steps->target == 3000U);
    assert(steps->status == VELAPET_TASK_NOT_STARTED);
}

static void test_daily_tasks_and_rewards(void)
{
    velapet_state_t state;
    const velapet_task_t *steps;

    velapet_state_init(&state, 200U);
    assert(velapet_record_steps(&state, 200U, 2999U) == 1);
    steps = velapet_get_task(&state, VELAPET_TASK_DAILY_STEPS);
    assert(steps->progress == 2999U);
    assert(steps->status == VELAPET_TASK_IN_PROGRESS);

    assert(velapet_record_steps(&state, 200U, 10U) == 1);
    assert(state.total_steps == 3009U);
    assert(steps->progress == 3000U);
    assert(steps->status == VELAPET_TASK_COMPLETED);
    assert(velapet_claim_task(&state, 200U, VELAPET_TASK_DAILY_STEPS) == 20);
    assert(velapet_claim_task(&state, 200U, VELAPET_TASK_DAILY_STEPS) == 0);

    assert(velapet_record_exercise_minutes(&state, 200U, 10U) == 1);
    assert(velapet_claim_task(&state, 200U,
                              VELAPET_TASK_CONTINUOUS_WALK) == 30);
    assert(velapet_check_in(&state, 200U) == 1);
    assert(velapet_check_in(&state, 200U) == 0);
    assert(velapet_claim_task(&state, 200U, VELAPET_TASK_CHECK_IN) == 10);
    assert(velapet_record_social(&state, 200U) == 1);
    assert(velapet_claim_task(&state, 200U, VELAPET_TASK_SOCIAL) == 15);
    assert(velapet_completed_task_count(&state) == VELAPET_TASK_COUNT);
    assert(state.exp == 75U);

    assert(velapet_add_exp(&state, 25U) == 1);
    assert(state.level == 2U);
    assert(state.exp == 0U);
    assert(state.exp_to_next == 250U);
    assert(velapet_is_skin_unlocked(&state, VELAPET_SKIN_SPORT_BLUE) == 1);
    assert(strcmp(state.current_skin, VELAPET_SKIN_DEFAULT) == 0);
    assert(velapet_switch_skin(&state, VELAPET_SKIN_SPORT_BLUE) == 0);
}

static void test_day_refresh_and_streak(void)
{
    velapet_state_t state;
    const velapet_task_t *steps;

    velapet_state_init(&state, 300U);
    assert(velapet_check_in(&state, 300U) == 1);
    assert(velapet_record_steps(&state, 300U, 1000U) == 1);

    assert(velapet_check_in(&state, 301U) == 2);
    steps = velapet_get_task(&state, VELAPET_TASK_DAILY_STEPS);
    assert(state.task_day == 301U);
    assert(steps->progress == 0U);
    assert(steps->status == VELAPET_TASK_NOT_STARTED);

    assert(velapet_check_in(&state, 302U) == 3);
    assert(velapet_is_skin_unlocked(&state, VELAPET_SKIN_RAINBOW) == 1);
    assert(velapet_check_in(&state, 304U) == 1);
    assert(velapet_refresh_day(&state, 303U) == -1);
}

static void test_level_and_skin_rules(void)
{
    velapet_state_t state;

    velapet_state_init(&state, 400U);
    assert(velapet_switch_skin(&state, VELAPET_SKIN_FLAME_RED) == -1);
    assert(velapet_unlock_skin(&state, "unknown") == -1);

    assert(velapet_add_exp(&state, 100U + 250U + 350U + 450U) == 4);
    assert(state.level == 5U);
    assert(state.exp == 0U);
    assert(velapet_is_skin_unlocked(&state, VELAPET_SKIN_SPORT_BLUE) == 1);
    assert(velapet_is_skin_unlocked(&state, VELAPET_SKIN_FLAME_RED) == 1);
    assert(velapet_is_skin_unlocked(&state, VELAPET_SKIN_STAR_PURPLE) == 0);
    assert(strcmp(velapet_get_title(5U), "egg_baby") == 0);
    assert(strcmp(velapet_get_title(6U), "young_pet") == 0);
    assert(strcmp(velapet_get_title(11U), "sport_star") == 0);
    assert(strcmp(velapet_get_title(21U), "vela_legend") == 0);
}

static void test_invalid_input(void)
{
    velapet_state_t state;

    velapet_state_init(&state, 500U);
    assert(velapet_record_steps(&state, 500U, 0U) == -1);
    assert(velapet_record_exercise_minutes(&state, 499U, 1U) == -1);
    assert(velapet_add_exp(&state, 0U) == -1);
    assert(velapet_claim_task(&state, 500U,
                              (velapet_task_type_t)99) == -1);
    assert(velapet_get_task(NULL, VELAPET_TASK_DAILY_STEPS) == NULL);
}

int main(void)
{
    test_default_state();
    test_daily_tasks_and_rewards();
    test_day_refresh_and_streak();
    test_level_and_skin_rules();
    test_invalid_input();

    puts("VELAPET_CORE_TEST result=PASS cases=5");
    return 0;
}
