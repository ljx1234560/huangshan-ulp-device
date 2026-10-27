#ifndef VELAPET_CORE_H
#define VELAPET_CORE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define VELAPET_NAME_LENGTH 32U
#define VELAPET_SKIN_ID_LENGTH 24U
#define VELAPET_MAX_UNLOCKED_SKINS 5U
#define VELAPET_TASK_COUNT 4U
#define VELAPET_DAY_UNKNOWN UINT32_MAX

#define VELAPET_SKIN_DEFAULT "default"
#define VELAPET_SKIN_SPORT_BLUE "sport_blue"
#define VELAPET_SKIN_FLAME_RED "flame_red"
#define VELAPET_SKIN_STAR_PURPLE "star_purple"
#define VELAPET_SKIN_RAINBOW "rainbow"

typedef enum
{
    VELAPET_TASK_DAILY_STEPS = 0,
    VELAPET_TASK_CONTINUOUS_WALK,
    VELAPET_TASK_CHECK_IN,
    VELAPET_TASK_SOCIAL
} velapet_task_type_t;

typedef enum
{
    VELAPET_TASK_NOT_STARTED = 0,
    VELAPET_TASK_IN_PROGRESS,
    VELAPET_TASK_COMPLETED,
    VELAPET_TASK_REWARD_CLAIMED
} velapet_task_status_t;

typedef struct
{
    velapet_task_type_t type;
    uint32_t target;
    uint32_t progress;
    uint32_t exp_reward;
    velapet_task_status_t status;
} velapet_task_t;

typedef struct
{
    char name[VELAPET_NAME_LENGTH];
    uint16_t level;
    uint32_t exp;
    uint32_t exp_to_next;
    uint64_t total_steps;
    uint32_t consecutive_days;
    uint32_t last_active_day;
    uint32_t last_checkin_day;
    uint32_t task_day;
    char current_skin[VELAPET_SKIN_ID_LENGTH];
    char unlocked_skins[VELAPET_MAX_UNLOCKED_SKINS][VELAPET_SKIN_ID_LENGTH];
    uint8_t unlocked_skin_count;
    velapet_task_t tasks[VELAPET_TASK_COUNT];
} velapet_state_t;

/* day_id is a caller-supplied monotonically increasing local calendar day. */
void velapet_state_init(velapet_state_t *state, uint32_t day_id);

/* Returns 1 when tasks were reset, 0 on the same day, and -1 for invalid or
 * backwards time. The caller decides how to obtain and persist day_id.
 */
int velapet_refresh_day(velapet_state_t *state, uint32_t day_id);

uint32_t velapet_exp_required(uint16_t level);
int velapet_add_exp(velapet_state_t *state, uint32_t amount);

int velapet_record_steps(velapet_state_t *state,
                         uint32_t day_id,
                         uint32_t steps);
int velapet_record_exercise_minutes(velapet_state_t *state,
                                    uint32_t day_id,
                                    uint32_t minutes);
int velapet_record_social(velapet_state_t *state, uint32_t day_id);

/* Returns the new streak, 0 when already checked in, and -1 on error. */
int velapet_check_in(velapet_state_t *state, uint32_t day_id);

/* Returns gained EXP, 0 when not claimable, and -1 on invalid input. */
int velapet_claim_task(velapet_state_t *state,
                       uint32_t day_id,
                       velapet_task_type_t type);

const velapet_task_t *velapet_get_task(const velapet_state_t *state,
                                       velapet_task_type_t type);
uint8_t velapet_completed_task_count(const velapet_state_t *state);

int velapet_is_skin_known(const char *skin_id);
int velapet_is_skin_unlocked(const velapet_state_t *state,
                             const char *skin_id);
int velapet_unlock_skin(velapet_state_t *state, const char *skin_id);
int velapet_switch_skin(velapet_state_t *state, const char *skin_id);
const char *velapet_get_title(uint16_t level);

#ifdef __cplusplus
}
#endif

#endif
