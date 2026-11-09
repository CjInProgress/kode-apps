/* SPDX-License-Identifier: GPL-3.0-or-later */
/**
 * @file good_app_ao.h
 * @brief The fixture app's Active Object.
 */
#ifndef GOOD_APP_AO_H_
#define GOOD_APP_AO_H_

#ifdef __cplusplus
extern "C" {
#endif

/* ---- Calls ---- */

/**
 * @brief Start the Active Object; call it after kode_init() returns.
 */
void good_app_start(void);

#ifdef __cplusplus
}
#endif

#endif /* GOOD_APP_AO_H_ */
