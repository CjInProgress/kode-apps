/* SPDX-License-Identifier: GPL-3.0-or-later */
/**
 * @file good_app_main.c
 * @brief The fixture app's entry point: the system, then its one Active Object.
 */
#include "good_app_ao.h"

#include "kode.h"

KODE_APP_MANIFEST("Good App", "tools");

void app_main(void)
{
    (void)kode_init();
    good_app_start();
}
