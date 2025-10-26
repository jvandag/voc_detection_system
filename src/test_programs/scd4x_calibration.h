#include <Wire.h>
#include <SensirionI2cScd4x.h>

SensirionI2cScd4x scd4x;

bool recalibrate(uint16_t reference_ppm = 400);