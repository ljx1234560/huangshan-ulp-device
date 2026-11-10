#include "ui_skin_image.h"

#include "ui_skin_img_data.h"

#include <string.h>

const char *const ui_skin_ids[UI_SKIN_COUNT] = {
    "default", "sport_blue", "flame_red", "star_purple", "rainbow"
};

int ui_skin_image_index_of(const char *skin_id)
{
    uint8_t index;

    if (skin_id == NULL)
    {
        return -1;
    }
    for (index = 0U; index < UI_SKIN_COUNT; ++index)
    {
        if (strcmp(ui_skin_ids[index], skin_id) == 0)
        {
            return (int)index;
        }
    }
    return -1;
}

#if VELAPET_UI_SKIN_IMAGES

const lv_img_dsc_t *ui_skin_image_full(uint8_t index)
{
    if ((unsigned)index >= UI_SKIN_COUNT)
    {
        return NULL;
    }
    return &ui_skin_img_full[index];
}

const lv_img_dsc_t *ui_skin_image_thumb(uint8_t index)
{
    if ((unsigned)index >= UI_SKIN_COUNT)
    {
        return NULL;
    }
    return &ui_skin_img_thumb[index];
}

int ui_skin_images_ready(void)
{
    return 1;
}

#else /* 几何替身模式 */

const lv_img_dsc_t *ui_skin_image_full(uint8_t index)
{
    (void)index;
    return NULL;
}

const lv_img_dsc_t *ui_skin_image_thumb(uint8_t index)
{
    (void)index;
    return NULL;
}

int ui_skin_images_ready(void)
{
    return 0;
}

#endif
