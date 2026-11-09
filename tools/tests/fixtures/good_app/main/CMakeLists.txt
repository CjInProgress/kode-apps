# The fixture app's one component.
idf_component_register(
    SRCS "good_app_main.c" "good_app_ao.c"
    INCLUDE_DIRS "."
    REQUIRES kode kui
)
