#include "ui_frame_seq.h"

#include <string.h>

/* 固定槽位表：当前 UI 同时最多 2 个舞台（主页/形象页），留裕量到 4。 */
#define FRAME_SEQ_SLOTS 4U

typedef struct
{
    lv_obj_t *img;
    lv_timer_t *timer;
    const lv_img_dsc_t *const *frames;
    const void *base_src;   /* play 时的源，stop/播完恢复 */
    uint16_t frame_ms;
    uint8_t count;
    uint8_t index;
    int32_t loops_left;     /* -1 = 无限 */
    void (*done_cb)(lv_obj_t *img);
} frame_seq_slot_t;

static frame_seq_slot_t g_slots[FRAME_SEQ_SLOTS];

static frame_seq_slot_t *slot_of(const lv_obj_t *img)
{
    unsigned i;

    for (i = 0U; i < FRAME_SEQ_SLOTS; ++i)
    {
        if (g_slots[i].img == img)
        {
            return &g_slots[i];
        }
    }
    return NULL;
}

static frame_seq_slot_t *slot_free(void)
{
    unsigned i;

    for (i = 0U; i < FRAME_SEQ_SLOTS; ++i)
    {
        if (g_slots[i].img == NULL)
        {
            return &g_slots[i];
        }
    }
    return NULL;
}

/* 结束播放：恢复基础帧并回调。img 可能已被删除，回调只对存活对象调用。 */
static void slot_finish(frame_seq_slot_t *slot)
{
    lv_obj_t *img = slot->img;
    void (*done_cb)(lv_obj_t *img) = slot->done_cb;

    lv_timer_del(slot->timer);
    slot->timer = NULL;
    slot->img = NULL;
    if (img != NULL && slot->base_src != NULL)
    {
        lv_img_set_src(img, slot->base_src);
    }
    if (done_cb != NULL && img != NULL)
    {
        done_cb(img);
    }
}

/* 对象销毁：只清理，不恢复源、不回调（对象已不存在）。 */
static void slot_cleanup(frame_seq_slot_t *slot)
{
    lv_timer_del(slot->timer);
    slot->timer = NULL;
    slot->img = NULL;
}

static void frame_tick_cb(lv_timer_t *timer)
{
    frame_seq_slot_t *slot = (frame_seq_slot_t *)timer->user_data;

    slot->index = (uint8_t)((slot->index + 1U) % slot->count);
    if (slot->index == 0U && slot->loops_left >= 0)
    {
        slot->loops_left -= 1;
        if (slot->loops_left == 0)
        {
            slot_finish(slot);
            return;
        }
    }
    lv_img_set_src(slot->img, slot->frames[slot->index]);
}

/* LV_EVENT_DELETE：lv_obj 删除时 timer 若不删会指向已释放内存。 */
static void frame_delete_cb(lv_event_t *e)
{
    frame_seq_slot_t *slot = slot_of(lv_event_get_target(e));

    if (slot != NULL && slot->timer != NULL)
    {
        slot_cleanup(slot);
    }
}

void ui_frame_seq_play(lv_obj_t *img, const ui_frame_seq_cfg_t *cfg)
{
    frame_seq_slot_t *slot;

    if (img == NULL || cfg == NULL || cfg->frames == NULL ||
        cfg->count == 0U || cfg->frame_ms == 0U || cfg->loops == 0)
    {
        return;
    }
    slot = slot_of(img);
    if (slot != NULL)
    {
        ui_frame_seq_stop(img);
    }
    slot = slot_free();
    if (slot == NULL)
    {
        return;
    }
    slot->img = img;
    slot->frames = cfg->frames;
    slot->count = cfg->count;
    slot->frame_ms = cfg->frame_ms;
    slot->loops_left = (cfg->loops < 0) ? -1 : cfg->loops;
    slot->done_cb = cfg->done_cb;
    slot->index = 0U;
    slot->base_src = lv_img_get_src(img);
    lv_img_set_src(img, cfg->frames[0]);
    lv_obj_add_event_cb(img, frame_delete_cb, LV_EVENT_DELETE, NULL);
    slot->timer = lv_timer_create(frame_tick_cb, cfg->frame_ms, slot);
}

void ui_frame_seq_stop(lv_obj_t *img)
{
    frame_seq_slot_t *slot;

    if (img == NULL)
    {
        return;
    }
    slot = slot_of(img);
    if (slot == NULL || slot->timer == NULL)
    {
        return;
    }
    lv_obj_remove_event_cb(img, frame_delete_cb);
    slot_finish(slot);
}

int ui_frame_seq_active(const lv_obj_t *img)
{
    frame_seq_slot_t *slot;

    if (img == NULL)
    {
        return 0;
    }
    slot = slot_of(img);
    return (slot != NULL && slot->timer != NULL) ? 1 : 0;
}
