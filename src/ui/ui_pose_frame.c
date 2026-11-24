#include "ui_pose_frame.h"

#include "ui_skin_image.h"

#include <stddef.h>

#if VELAPET_UI_POSE_FRAMES
#include "ui_pose_img_data.h"
#endif

int ui_pose_frames_ready(void)
{
#if VELAPET_UI_POSE_FRAMES
    return 1;
#else
    return 0;
#endif
}

const lv_img_dsc_t *const *ui_pose_frames(uint8_t skin_index,
                                          ui_pose_action_t action,
                                          uint8_t *count)
{
#if VELAPET_UI_POSE_FRAMES
    uint8_t n;

    if (skin_index >= UI_SKIN_COUNT || (unsigned)action >= UI_POSE_ACTION_COUNT)
    {
        return NULL;
    }
    n = ui_pose_count_table[skin_index][action];
    if (count != NULL)
    {
        *count = n;
    }
    if (n == 0U)
    {
        return NULL;
    }
    return ui_pose_frame_table[skin_index][action];
#else
    (void)skin_index;
    (void)action;
    if (count != NULL)
    {
        *count = 0U;
    }
    return NULL;
#endif
}
