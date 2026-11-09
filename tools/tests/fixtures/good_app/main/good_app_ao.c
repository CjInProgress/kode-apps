/* SPDX-License-Identifier: GPL-3.0-or-later */
/**
 * @file good_app_ao.c
 * @brief The fixture app's Active Object: one state that logs every button.
 */
#include "good_app_ao.h"

#include "kode_ao.h"
#include "kode_log.h"

#define TAG "good.ao"   /**< This file's log tag. */

/** @brief The Active Object. */
typedef struct {
    QActive super;   /**< The QP/C base. */
} GoodApp;

static GoodApp     s_good;                                               /**< The one instance. */
static QEvtPtr     s_queue[KQP_AO_QUEUE_LEN];                            /**< Its event queue. */
static StackType_t s_stack[KQP_AO_STACK_BYTES / sizeof(StackType_t)];    /**< Its stack. */

static QState GoodApp_idle(GoodApp * const me, QEvt const * const e);

/**
 * @brief The initial transition: subscribe, then wait.
 * @param me  The Active Object.
 * @param par Unused.
 * @return The transition to the idle state.
 */
static QState GoodApp_initial(GoodApp * const me, void const * const par)
{
    (void)par;
    QActive_subscribe(&me->super, BUTTON_SIG);
    return Q_TRAN(&GoodApp_idle);
}

/**
 * @brief The one state: log each button event.
 * @param me The Active Object.
 * @param e  The event.
 * @return Q_HANDLED() for a button, Q_SUPER() otherwise.
 */
static QState GoodApp_idle(GoodApp * const me, QEvt const * const e)
{
    QState status;

    (void)me;
    if ( BUTTON_SIG == e->sig )
    {
        KLOG_I(TAG, "a button");
        status = Q_HANDLED();
    }
    else
    {
        status = Q_SUPER(&QHsm_top);
    }
    return status;
}

void good_app_start(void)
{
    QActive_ctor(&s_good.super, Q_STATE_CAST(&GoodApp_initial));
    QActive_setAttr(&s_good.super, TASK_NAME_ATTR, "good_app");
    QACTIVE_START(&s_good.super, KODE_PRIO_USER_LOW, s_queue, KQP_AO_QUEUE_LEN,
                  s_stack, sizeof(s_stack), (void *)0);
}
