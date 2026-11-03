#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "velapet_service.h"

static void test_init(void)
{
    const velapet_snapshot_t *snap;

    assert(velapet_service_init(VELAPET_DAY_UNKNOWN) == -1);
    assert(velapet_service_snapshot() == NULL);

    assert(velapet_service_init(200U) == 0);
    snap = velapet_service_snapshot();
    assert(snap != NULL);
    assert(snap->level == 1U);
    assert(snap->exp == 0U);
    assert(snap->exp_percent == 0U);
    assert(snap->daily_percent == 0U);
    assert(snap->can_checkin == 1U);
    assert(strcmp(snap->current_skin, "default") == 0);
    assert(snap->unlocked_skin_count == 1U);
    assert(snap->task_count == VELAPET_TASK_COUNT);
    assert(snap->tasks[0].title[0] != '\0');
    assert(snap->tasks[0].unit[0] != '\0');
    assert(snap->tasks[0].target == 3000U);
    assert(velapet_service_raw_state() != NULL);
}

static void test_task_flow(void)
{
    const velapet_snapshot_t *snap;

    assert(velapet_service_claim(VELAPET_TASK_DAILY_STEPS) == 0);
    assert(velapet_service_record_steps(1200U) == 1);

    snap = velapet_service_snapshot();
    assert(snap->tasks[0].progress == 1200U);
    assert(snap->tasks[0].status == VELAPET_TASK_IN_PROGRESS);
    assert(snap->daily_percent == 40U);
    assert(snap->total_steps == 1200U);

    assert(velapet_service_record_steps(1800U) == 1);
    snap = velapet_service_snapshot();
    assert(snap->tasks[0].progress == 3000U);
    assert(snap->tasks[0].status == VELAPET_TASK_COMPLETED);
    assert(snap->daily_percent == 100U);
    assert(snap->total_steps == 3000U);

    assert(velapet_service_claim(VELAPET_TASK_DAILY_STEPS) == 20);
    assert(velapet_service_claim(VELAPET_TASK_DAILY_STEPS) == 0);

    snap = velapet_service_snapshot();
    assert(snap->exp == 20U);
    assert(snap->tasks[0].status == VELAPET_TASK_REWARD_CLAIMED);
    assert(velapet_service_last_levelup() == 0U);
}

static void test_checkin(void)
{
    const velapet_snapshot_t *snap;

    snap = velapet_service_snapshot();
    assert(snap->can_checkin == 1U);

    assert(velapet_service_checkin() == 1);
    snap = velapet_service_snapshot();
    assert(snap->consecutive_days == 1U);
    assert(snap->can_checkin == 0U);
    assert(velapet_service_checkin() == 0);
    assert(velapet_service_claim(VELAPET_TASK_CHECK_IN) == 10);
}

static void test_skin(void)
{
    const velapet_snapshot_t *snap;

    assert(velapet_service_switch_skin(NULL) == -1);
    assert(velapet_service_switch_skin("rainbow") == -1);
    assert(velapet_service_switch_skin("default") == 0);
    snap = velapet_service_snapshot();
    assert(strcmp(snap->current_skin, "default") == 0);
}

static void test_levelup_event(void)
{
    velapet_state_t tmp;

    velapet_state_init(&tmp, 300U);
    assert(velapet_add_exp(&tmp, 95U) == 0);
    assert(velapet_service_restore(&tmp, 300U) == 0);

    assert(velapet_service_record_steps(3000U) == 1);
    assert(velapet_service_claim(VELAPET_TASK_DAILY_STEPS) == 20);
    assert(velapet_service_last_levelup() == 2U);

    velapet_service_ack_levelup();
    assert(velapet_service_last_levelup() == 0U);

    assert(velapet_service_snapshot()->level == 2U);
}

static void test_day_rollover(void)
{
    const velapet_snapshot_t *snap;

    assert(velapet_service_set_day(300U) == 0);
    assert(velapet_service_set_day(301U) == 1);

    snap = velapet_service_snapshot();
    assert(snap->tasks[0].progress == 0U);
    assert(snap->daily_percent == 0U);
    assert(snap->can_checkin == 1U);

    assert(velapet_service_set_day(301U) == 0);
    assert(velapet_service_set_day(300U) == -1);
}

int main(void)
{
    test_init();
    test_task_flow();
    test_checkin();
    test_skin();
    test_levelup_event();
    test_day_rollover();

    printf("VELAPET_SERVICE_TEST result=PASS cases=6\n");
    return 0;
}
