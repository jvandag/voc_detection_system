#include <Wire.h>
#include <SensirionI2cScd4x.h>
#include "../feather_v2_config.hh"

SensirionI2cScd4x scd4x;

bool recalibrate(uint16_t reference_ppm = 400);
