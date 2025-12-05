#include "MotorControl.h"
#include <Arduino.h>

MotorControl::MotorControl(int leftChannelFront, int rightChannelFront, int leftChannelBack, int rightChannelBack, int winchChannel)
  : PWM_LEFT_CHANNEL(leftChannelFront), PWM_RIGHT_CHANNEL(rightChannelBack), WINCH_CHANNEL(winchChannel){}

void MotorControl::begin(int leftPinFront, int rightPinFront, int leftPinBack, int rightPinBack, int winchPin) {
  ledcSetup(PWM_LEFT_CHANNEL, PWM_BASE_FREQ, PWM_TIMER_12_BIT);
  ledcAttachPin(leftPinFront, PWM_LEFT_CHANNEL);
  ledcAttachPin(leftPinBack, PWM_LEFT_CHANNEL);

  ledcSetup(PWM_RIGHT_CHANNEL, PWM_BASE_FREQ, PWM_TIMER_12_BIT);
  ledcAttachPin(rightPinFront, PWM_RIGHT_CHANNEL);
  ledcAttachPin(rightPinBack, PWM_RIGHT_CHANNEL);

  ledcSetup(WINCH_CHANNEL, PWM_BASE_FREQ, PWM_TIMER_12_BIT);
  ledcAttachPin(winchPin, WINCH_CHANNEL);
}

void MotorControl::update(double forwardVelocityCommand, double steeringVelocityCommand, double winchCommand) {
  double leftWheelCommand = forwardVelocityCommand + steeringVelocityCommand;
  double rightWheelCommand = forwardVelocityCommand - steeringVelocityCommand;

  double maxValue = max(max(abs(leftWheelCommand), abs(rightWheelCommand)), 1.0);

  leftWheelCommand = leftWheelCommand / maxValue;
  rightWheelCommand = rightWheelCommand / maxValue;

  int leftMotorPulsewidth = map(leftWheelCommand*1000, -1000, 1000, SERVO_MIN, SERVO_MAX);
  int rightMotorPulsewidth = map(rightWheelCommand*1000, -1000, 1000, SERVO_MIN, SERVO_MAX);
  int winchMotorPulserwidth = map(winchCommand*1000, -1000, 1000, SERVO_MIN, SERVO_MAX);

  uint16_t leftMotorDutyCycle = map(leftMotorPulsewidth, 0, 1e6/PWM_BASE_FREQ, 0, 4095);
  uint16_t rightMotorDutyCycle = map(rightMotorPulsewidth, 0, 1e6/PWM_BASE_FREQ, 0, 4095);
  uint16_t winchMotorDutyCycle = map(winchMotorPulserwidth, 0, 1e6/PWM_BASE_FREQ, 0, 4095);

  ledcAnalogWrite(PWM_LEFT_CHANNEL, leftMotorDutyCycle, 4095);
  ledcAnalogWrite(PWM_RIGHT_CHANNEL, rightMotorDutyCycle, 4095);
  ledcAnalogWrite(WINCH_CHANNEL, winchMotorDutyCycle, 4095);
}

void MotorControl::updateRightLeft(double leftWheelCommand, double rightWheelCommand) {
  //// updates right and left motors based on a custom command, not steering or forward commands  
  //// TODO : maybe change this : weird shit
  //double maxValue = max(max(abs(leftWheelCommand), abs(rightWheelCommand)), 1.0);

  //leftWheelCommand = leftWheelCommand / maxValue;
  //rightWheelCommand = rightWheelCommand / maxValue;

  int leftMotorPulsewidth = map(leftWheelCommand*1000, -1000, 1000, SERVO_MIN, SERVO_MAX);
  int rightMotorPulsewidth = map(rightWheelCommand*1000, -1000, 1000, SERVO_MIN, SERVO_MAX);

  uint16_t leftMotorDutyCycle = map(leftMotorPulsewidth, 0, 1e6/PWM_BASE_FREQ, 0, 4095);
  uint16_t rightMotorDutyCycle = map(rightMotorPulsewidth, 0, 1e6/PWM_BASE_FREQ, 0, 4095);

  ledcAnalogWrite(PWM_LEFT_CHANNEL, leftMotorDutyCycle, 4095);
  ledcAnalogWrite(PWM_RIGHT_CHANNEL, rightMotorDutyCycle, 4095);
}

void MotorControl::ledcAnalogWrite(uint8_t channel, uint32_t value, uint32_t valueMax) {
  uint32_t duty = (4095 / valueMax) * min(value, valueMax);
  ledcWrite(channel, duty);
}
