#ifndef MOTOR_CONTROL_H
#define MOTOR_CONTROL_H

#include <Arduino.h>

class MotorControl {
  const int SERVO_MIN = 500;
  const int SERVO_MAX = 2500;
  const int PWM_TIMER_12_BIT = 12;
  const int PWM_BASE_FREQ = 333;
  const int PWM_LEFT_CHANNEL;
  const int PWM_RIGHT_CHANNEL;
  const int WINCH_CHANNEL;

public:
  MotorControl(int leftChannelFront, int rightChannelFront, int leftChannelBack, int rightChannelBack, int winchChannel);
  void begin(int leftPinFront, int rightPinFront, int leftPinBack, int rightPinBack, int WinchPin);
  void update(double forwardVelocityCommand, double steeringVelocityCommand, double winchCommand);
  void updateRightLeft(double leftWheelCommand, double rightWheelCommand);
  
private:
  void ledcAnalogWrite(uint8_t channel, uint32_t value, uint32_t valueMax = 255);
};

#endif
