/* A reduced kode.h: three calls that return kode_status_t, for rule E13. */
kode_status_t kode_init(void);
kode_status_t kode_led_rgb(uint8_t r, uint8_t g, uint8_t b);
kode_status_t kode_nvs_set(const char *key, const char *value);
