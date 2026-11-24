#include "ui_anim.h"

#include "ui_internal.h"
#include "ui_frame_seq.h"
#include "ui_pose_frame.h"
#include "ui_skin_image.h"

/* transform 样式（zoom/angle/pivot）需要 LVGL v8.2+；低版本自动降级。 */
#if LV_VERSION_MAJOR > 8 || (LV_VERSION_MAJOR == 8 && LV_VERSION_MINOR >= 2)
#define UI_ANIM_TRANSFORM 1
#endif
/* 语法检查/旧 SDK 调试用：定义后强制走降级分支。 */
#if defined(UI_ANIM_FORCE_NO_TRANSFORM)
#undef UI_ANIM_TRANSFORM
#endif

#define ZOOM_BASE       256  /* 100% */
#define ZOOM_BREATHE    8    /* 呼吸幅度 +3% */
#define ZOOM_HAPPY      20   /* 开心跳幅度 +8% */
#define TAP_WINDOW_MS   250  /* 单击/双击判别窗（规格第 3 节） */
#define TAP_LONG_PRESS  0    /* 长按由 LVGL 原生事件处理，此处不占 */

/* ---------------- 动画执行回调（签名匹配 lv_anim_exec_xcb_t，无需转换） ---------------- */

static void opa_exec_cb(void *var, int32_t v)
{
    lv_obj_set_style_opa((lv_obj_t *)var, (lv_opa_t)v, 0);
}

static void translate_x_exec_cb(void *var, int32_t v)
{
    lv_obj_set_style_translate_x((lv_obj_t *)var, (lv_coord_t)v, 0);
}

static void translate_y_exec_cb(void *var, int32_t v)
{
    lv_obj_set_style_translate_y((lv_obj_t *)var, (lv_coord_t)v, 0);
}

#ifdef UI_ANIM_TRANSFORM
static void zoom_exec_cb(void *var, int32_t v)
{
    lv_obj_set_style_transform_zoom((lv_obj_t *)var, (lv_coord_t)v, 0);
}

static void angle_exec_cb(void *var, int32_t v)
{
    lv_obj_set_style_transform_angle((lv_obj_t *)var, (lv_coord_t)v, 0);
}

static void set_pivot_center(lv_obj_t *obj)
{
    lv_obj_set_style_transform_pivot_x(obj, lv_obj_get_width(obj) / 2, 0);
    lv_obj_set_style_transform_pivot_y(obj, lv_obj_get_height(obj) / 2, 0);
}
#endif

/* ---------------- 结束回调：复位样式残留并重启呼吸 ---------------- */

static void restart_breathe_cb(lv_anim_t *a)
{
    lv_obj_t *obj = (lv_obj_t *)a->var;

    lv_obj_set_style_translate_y(obj, 0, 0);
#ifdef UI_ANIM_TRANSFORM
    lv_obj_set_style_transform_zoom(obj, ZOOM_BASE, 0);
#endif
    ui_anim_breathe(obj);
}

static void dance_ready_cb(lv_anim_t *a)
{
    lv_obj_t *obj = (lv_obj_t *)a->var;

    lv_obj_set_style_translate_y(obj, 0, 0);
#ifdef UI_ANIM_TRANSFORM
    lv_obj_set_style_transform_angle(obj, 0, 0);
    lv_obj_set_style_transform_zoom(obj, ZOOM_BASE, 0);
#endif
    ui_anim_breathe(obj);
}

static void cheer_ready_cb(lv_anim_t *a)
{
    lv_obj_set_style_translate_y((lv_obj_t *)a->var, 0, 0);
}

static void fade_ready_cb(lv_anim_t *a)
{
    lv_obj_set_style_translate_x((lv_obj_t *)a->var, 0, 0);
}

/* ---------------- 姿态帧分支：帧组就绪时部位动优先于整图变换 ---------------- */

/* 各动作帧时长（ms）：呼吸 ~8FPS、跳舞 ~10FPS、开心/欢呼帧少稍慢便于感知。 */
static uint16_t pose_frame_ms(ui_pose_action_t action)
{
    switch (action)
    {
    case UI_POSE_DANCE:
        return 100U; /* 6 帧 x 100ms x 4 轮 ~= 2.4s */
    case UI_POSE_HAPPY:
        return 150U; /* 2 帧 x 150ms x 2 轮 = 0.6s，与整图版节奏一致 */
    case UI_POSE_CHEER:
        return 120U;
    case UI_POSE_BREATHE:
    default:
        return 120U; /* 2 帧 ~= 8FPS，缓慢自然 */
    }
}

/* 当前皮肤有该动作帧组则切帧播放并返回 1；否则返回 0 走整图回退。 */
static int pose_play(lv_obj_t *obj, ui_pose_action_t action, int32_t loops,
                     void (*done_cb)(lv_obj_t *))
{
    const velapet_snapshot_t *snap = velapet_service_snapshot();
    const lv_img_dsc_t *const *frames;
    uint8_t count = 0U;
    int skin_index;
    ui_frame_seq_cfg_t cfg;

    if (obj == NULL || snap == NULL)
    {
        return 0;
    }
    skin_index = ui_skin_image_index_of(snap->current_skin);
    if (skin_index < 0)
    {
        return 0;
    }
    frames = ui_pose_frames((uint8_t)skin_index, action, &count);
    if (frames == NULL)
    {
        return 0;
    }
    cfg.frames = frames;
    cfg.count = count;
    cfg.frame_ms = pose_frame_ms(action);
    cfg.loops = loops;
    cfg.done_cb = done_cb;
    ui_frame_seq_play(obj, &cfg);
    return 1;
}

/* 帧版动作结束：复位可能的样式残留并重启呼吸（帧模式下呼吸也是帧组）。 */
static void pose_done_restart_breathe(lv_obj_t *obj)
{
    lv_obj_set_style_translate_y(obj, 0, 0);
#ifdef UI_ANIM_TRANSFORM
    lv_obj_set_style_transform_zoom(obj, ZOOM_BASE, 0);
    lv_obj_set_style_transform_angle(obj, 0, 0);
#endif
    ui_anim_breathe(obj);
}

/* ---------------- 对外动作 ---------------- */

void ui_anim_breathe(lv_obj_t *obj)
{
    lv_anim_t a;

    if (obj == NULL)
    {
        return;
    }
    lv_anim_del(obj, NULL);
    if (pose_play(obj, UI_POSE_BREATHE, -1, NULL))
    {
        return;
    }
    /* Keep opacity and zoom fixed: repeated full-object redraws flicker on
     * the current SiFli display path. A small vertical drift is cheaper. */
    lv_anim_init(&a);
    lv_anim_set_var(&a, obj);
    lv_anim_set_values(&a, 0, -2);
    lv_anim_set_time(&a, 1500);
    lv_anim_set_playback_time(&a, 1500);
    lv_anim_set_repeat_count(&a, LV_ANIM_REPEAT_INFINITE);
    lv_anim_set_exec_cb(&a, translate_y_exec_cb);
    lv_anim_start(&a);
}

void ui_anim_happy(lv_obj_t *obj)
{
    lv_anim_t a;

    if (obj == NULL)
    {
        return;
    }
    lv_anim_del(obj, NULL);
    ui_frame_seq_stop(obj);
    if (pose_play(obj, UI_POSE_HAPPY, 2, pose_done_restart_breathe))
    {
        /* TODO 震动接入：硬件线 vp_input 就绪后在动作起点触发短震。 */
        return;
    }
#ifdef UI_ANIM_TRANSFORM
    set_pivot_center(obj);
    lv_anim_init(&a);
    lv_anim_set_var(&a, obj);
    lv_anim_set_values(&a, ZOOM_BASE, ZOOM_BASE + ZOOM_HAPPY);
    lv_anim_set_time(&a, 150);
    lv_anim_set_playback_time(&a, 150);
    lv_anim_set_repeat_count(&a, 2);
    lv_anim_set_exec_cb(&a, zoom_exec_cb);
    lv_anim_set_ready_cb(&a, restart_breathe_cb);
    lv_anim_start(&a);
#else
    lv_anim_init(&a);
    lv_anim_set_var(&a, obj);
    lv_anim_set_values(&a, 0, -12);
    lv_anim_set_time(&a, 150);
    lv_anim_set_playback_time(&a, 150);
    lv_anim_set_repeat_count(&a, 2);
    lv_anim_set_exec_cb(&a, translate_y_exec_cb);
    lv_anim_set_ready_cb(&a, restart_breathe_cb);
    lv_anim_start(&a);
#endif
}

void ui_anim_dance(lv_obj_t *obj)
{
    lv_anim_t a;

    if (obj == NULL)
    {
        return;
    }
    lv_anim_del(obj, NULL);
    ui_frame_seq_stop(obj);
    if (pose_play(obj, UI_POSE_DANCE, 4, pose_done_restart_breathe))
    {
        return;
    }
#ifdef UI_ANIM_TRANSFORM
    set_pivot_center(obj);
    /* 摇摆：±15°（0.1° 单位），300ms 单程 × 3 轮。 */
    lv_anim_init(&a);
    lv_anim_set_var(&a, obj);
    lv_anim_set_values(&a, -150, 150);
    lv_anim_set_time(&a, 300);
    lv_anim_set_playback_time(&a, 300);
    lv_anim_set_repeat_count(&a, 3);
    lv_anim_set_exec_cb(&a, angle_exec_cb);
    lv_anim_set_ready_cb(&a, dance_ready_cb);
    lv_anim_start(&a);
    /* 弹跳：0 -> -12 -> 0，与摇摆同步。 */
    lv_anim_init(&a);
    lv_anim_set_var(&a, obj);
    lv_anim_set_values(&a, 0, -12);
    lv_anim_set_time(&a, 300);
    lv_anim_set_playback_time(&a, 300);
    lv_anim_set_repeat_count(&a, 3);
    lv_anim_set_exec_cb(&a, translate_y_exec_cb);
    lv_anim_start(&a);
#else
    lv_anim_init(&a);
    lv_anim_set_var(&a, obj);
    lv_anim_set_values(&a, -12, 12);
    lv_anim_set_time(&a, 300);
    lv_anim_set_playback_time(&a, 300);
    lv_anim_set_repeat_count(&a, 3);
    lv_anim_set_exec_cb(&a, translate_y_exec_cb);
    lv_anim_set_ready_cb(&a, dance_ready_cb);
    lv_anim_start(&a);
#endif
}

void ui_anim_cheer(lv_obj_t *obj)
{
    lv_anim_t a;

    if (obj == NULL)
    {
        return;
    }
    lv_anim_del(obj, NULL);
    ui_frame_seq_stop(obj);
    if (pose_play(obj, UI_POSE_CHEER, 2, pose_done_restart_breathe))
    {
        return;
    }
    lv_anim_init(&a);
    lv_anim_set_var(&a, obj);
    lv_anim_set_values(&a, 0, -24);
    lv_anim_set_time(&a, 150);
    lv_anim_set_playback_time(&a, 150);
    lv_anim_set_repeat_count(&a, 2);
    lv_anim_set_exec_cb(&a, translate_y_exec_cb);
    lv_anim_set_ready_cb(&a, cheer_ready_cb);
    lv_anim_start(&a);
}

void ui_anim_fade_in(lv_obj_t *obj, lv_coord_t from_x)
{
    lv_anim_t a;

    if (obj == NULL)
    {
        return;
    }
    lv_anim_del(obj, NULL);
    lv_obj_set_style_opa(obj, LV_OPA_0, 0);
    lv_anim_init(&a);
    lv_anim_set_var(&a, obj);
    lv_anim_set_values(&a, LV_OPA_0, LV_OPA_COVER);
    lv_anim_set_time(&a, 220);
    lv_anim_set_exec_cb(&a, opa_exec_cb);
    lv_anim_start(&a);
    if (from_x != 0)
    {
        lv_obj_set_style_translate_x(obj, from_x, 0);
        lv_anim_init(&a);
        lv_anim_set_var(&a, obj);
        lv_anim_set_values(&a, from_x, 0);
        lv_anim_set_time(&a, 220);
        lv_anim_set_exec_cb(&a, translate_x_exec_cb);
        lv_anim_set_ready_cb(&a, fade_ready_cb);
        lv_anim_start(&a);
    }
}

void ui_anim_stop(lv_obj_t *obj)
{
    if (obj == NULL)
    {
        return;
    }
    lv_anim_del(obj, NULL);
    ui_frame_seq_stop(obj);
    lv_obj_set_style_translate_x(obj, 0, 0);
    lv_obj_set_style_translate_y(obj, 0, 0);
    lv_obj_set_style_opa(obj, LV_OPA_COVER, 0);
#ifdef UI_ANIM_TRANSFORM
    lv_obj_set_style_transform_angle(obj, 0, 0);
    lv_obj_set_style_transform_zoom(obj, ZOOM_BASE, 0);
#endif
}

/* ---------------- 单击/双击判别器 ---------------- */

typedef struct
{
    lv_obj_t *obj;
    uint32_t last_tick;
    lv_timer_t *pending;
    void (*single_cb)(lv_obj_t *obj);
    void (*double_cb)(lv_obj_t *obj);
} tap_ctx_t;

static void tap_pending_cb(lv_timer_t *timer)
{
    tap_ctx_t *ctx = (tap_ctx_t *)timer->user_data;

    lv_timer_del(timer);
    ctx->pending = NULL;
    if (ctx->single_cb != NULL)
    {
        ctx->single_cb(ctx->obj);
    }
}

/* obj 销毁时清理：挂起的单击定时器必须同时删除，否则回调访问已释放内存。 */
static void tap_delete_cb(lv_event_t *e)
{
    tap_ctx_t *ctx = (tap_ctx_t *)lv_event_get_user_data(e);

    if (ctx->pending != NULL)
    {
        lv_timer_del(ctx->pending);
        ctx->pending = NULL;
    }
    lv_mem_free(ctx);
}

static void tap_clicked_cb(lv_event_t *e)
{
    tap_ctx_t *ctx = (tap_ctx_t *)lv_event_get_user_data(e);
    uint32_t now = lv_tick_get();

    if (ctx->last_tick != 0U && (now - ctx->last_tick) < TAP_WINDOW_MS)
    {
        if (ctx->pending != NULL)
        {
            lv_timer_del(ctx->pending);
            ctx->pending = NULL;
        }
        ctx->last_tick = 0U;
        if (ctx->double_cb != NULL)
        {
            ctx->double_cb(ctx->obj);
        }
    }
    else
    {
        if (ctx->pending != NULL)
        {
            lv_timer_del(ctx->pending);
        }
        ctx->last_tick = now;
        ctx->pending = lv_timer_create(tap_pending_cb, TAP_WINDOW_MS, ctx);
        lv_timer_set_repeat_count(ctx->pending, 1);
    }
}

void ui_anim_bind_tap(lv_obj_t *obj,
                      void (*single_cb)(lv_obj_t *obj),
                      void (*double_cb)(lv_obj_t *obj))
{
    tap_ctx_t *ctx;

    if (obj == NULL)
    {
        return;
    }
    ctx = (tap_ctx_t *)lv_mem_alloc(sizeof(tap_ctx_t));
    if (ctx == NULL)
    {
        return;
    }
    ctx->obj = obj;
    ctx->last_tick = 0U;
    ctx->pending = NULL;
    ctx->single_cb = single_cb;
    ctx->double_cb = double_cb;
    lv_obj_add_event_cb(obj, tap_clicked_cb, LV_EVENT_CLICKED, ctx);
    lv_obj_add_event_cb(obj, tap_delete_cb, LV_EVENT_DELETE, ctx);
}
