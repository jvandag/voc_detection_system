#pragma once
#include <Arduino.h>
#include <SensirionI2cScd4x.h>
#include <Wire.h>

void scd4x_init();
void scd4x_single_shot_avg(uint16_t &co2_ppm, float &temp_cel, float &rel_hum);