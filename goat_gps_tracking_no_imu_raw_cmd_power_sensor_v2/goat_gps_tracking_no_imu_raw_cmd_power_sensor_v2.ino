#include <WiFi.h>
#include <WiFiUdp.h>
#include "MotorControl.h"
#include <Bluepad32.h>
#include <SensorFusion.h>
#include <stdio.h>
#include <stdlib.h>
#include <Adafruit_INA228.h>

// power sensor
Adafruit_INA228 ina228 = Adafruit_INA228();
double power_mW, current_mA, busVoltage_V, shuntVoltage_mV, energy, charge, dieTemp;

int LEFT_MOTOR_PIN_FRONT = D10; /// THIS IS USUALLY D8
int RIGHT_MOTOR_PIN_FRONT = D8;
int LEFT_MOTOR_PIN_BACK = D0;
int RIGHT_MOTOR_PIN_BACK = D1;
int LEFT_MOTOR_PWM_CHANNEL = 0;
int RIGHT_MOTOR_PWM_CHANNEL = 1;

// extra motor
int WINCH_MOTOR_PIN = D9;
int WINCH_MOTOR_PWM_CHANNEL = 2;
int WINCH_PWM_FREQ = 50;  // Typical for servos
int WINCH_PWM_RESOLUTION = 8;  

MotorControl motorControl(LEFT_MOTOR_PWM_CHANNEL, RIGHT_MOTOR_PWM_CHANNEL, LEFT_MOTOR_PWM_CHANNEL, RIGHT_MOTOR_PWM_CHANNEL, WINCH_MOTOR_PWM_CHANNEL);


SF fusion;
// WiFi AP settings
const char *ssid = "SycamoreNet";  // WiFi network name
const char *password = "Sycam0re"; // WiFi password (8+ characters)

// UDP settings
WiFiUDP udp;
const int udpPort = 5005;
IPAddress laptopIP;
float vx = 0, vy = 0, vz = 0; // Velocity (m/s)
float prev_ax = 0, prev_ay = 0, prev_az = 0;
float gx, gy, gz, ax, ay, az, mx, my, mz;
float pitch, roll, yaw;
float deltat;
//float P = 1, Q = 0.01, R = 0.01;  // Kalman parameters, need tuned

// Kalman Filter Variables
float vx_kalman = 0, vy_kalman = 0, vz_kalman = 0; // Estimated velocity
float P[3] = {1, 1, 1};  // Covariance matrix (initialized)
float Q[3] = {0.001, 0.001, 0.001};  // Process noise covariance
float R[3] = {0.1, 0.1, 0.1};  // Measurement noise covariance

float mx_cal = -12.65, my_cal = 22.04, mz_cal = 4.00;

float ax_calib = 0, ay_calib = 0, az_calib = 0;
float gx_calib = 0, gy_calib = 0, gz_calib = 0;
float ax_offset, ay_offset, az_offset;
float gx_offset, gy_offset, gz_offset;
int cal_steps = 2000;
int cal = 0;
// Sampling rate (for testing transformation into body frame)
#define SAMPLE_FREQ 20  
float dt = 1.0 / SAMPLE_FREQ;
// Gravity constant
const float g = 9.81;
//

char packetBuffer[255];

double last_forward_veclocity_cmd;
double last_steering_veclocity_cmd;

void processPS4(char* packetBuffer){
  char* token = strtok(packetBuffer, ",");
  float leftX, leftY, rightX, rightY;
  int recoveryState;
  double leftWheelCommand; double rightWheelCommand;
  double forwardCommand; double steeringCommand; double winchCommand;


  //int buttonStates[14];  // Adjust based on the number of buttons
  /// left axis is to move forward and backwards
  /// right axis is to move sideways
  if (token != NULL) leftX = -atof(token);  // Convert to float
  token = strtok(NULL, ",");
  if (token != NULL) leftY = -atof(token);
  token = strtok(NULL, ",");
  if (token != NULL) rightX = atof(token);
  token = strtok(NULL, ",");
  if (token != NULL) rightY = atof(token);

  // Parse button states
  // int i = 0;
  // while ((token = strtok(NULL, ",")) != NULL && i < 14) {  // Adjust button count as needed
  //     buttonStates[i] = atoi(token);  // Convert to integer (0 or 1)
  //     i++;
  // }

  // Parse recovery state
  token = strtok(NULL, ",");
  if (token != NULL) recoveryState = atoi(token);
  token = strtok(NULL, ",");
  if (token != NULL) leftWheelCommand = atof(token);
  token = strtok(NULL, ",");
  if (token != NULL) rightWheelCommand = atof(token);

  // double forwardCommand = abs(leftY) < 0.2 ? 0 : leftY;  /// it is either 0 or 1
  // double steeringCommand = abs(rightX) < 0.2 ? 0 : rightX;

  Serial.println("Commands left, right: ");
  Serial.println(leftWheelCommand);
  Serial.println(rightWheelCommand);
  // testing switch statement functionality
  switch (recoveryState) {
    case 0: // stationary
      forwardCommand = 0;
      steeringCommand = 0;
      winchCommand = 0;
      break;
    case 1: // forward
      forwardCommand = 1;
      steeringCommand = 0;
      winchCommand = 0;
      break;
    case 2: // turn
      forwardCommand = 0.5;
      steeringCommand = 1;
      winchCommand = 0;
      break;
    case 3: // backward
      forwardCommand = -1;
      steeringCommand = 0;
      winchCommand = 0;
      break;
    case 4: // turn
      forwardCommand = 0.5;
      steeringCommand = -1;
      winchCommand = 0;
      break;
    case 5: // compression of the frame
      forwardCommand = 0;
      steeringCommand = 0;
      winchCommand = 1;
      break;
    case 6: // uncompression of the frame, needs to be checked depending on how the motor are plugged
      forwardCommand = 0;
      steeringCommand = 0;
      winchCommand = -1;
      break;
    default:
      break;
    }

  /// buffering for later data logging
  last_forward_veclocity_cmd = forwardCommand;
  last_steering_veclocity_cmd = steeringCommand;
  Serial.println("Commands forwardCommand, steeringCommand: ");
  Serial.println(forwardCommand);
  Serial.println(steeringCommand);
  if (recoveryState==9){  ///// the case 9 is the raw or free control of the wheels
    Serial.println("Right and left wheel control activated");
    motorControl.updateRightLeft(leftWheelCommand, rightWheelCommand);
  }
  else{
    motorControl.update(forwardCommand, steeringCommand, winchCommand);
  }
}


void getINA228Data(){
  Serial.print("Current: ");
  current_mA = ina228.getCurrent_mA();
  Serial.print(current_mA);
  Serial.println(" mA");

  Serial.print("Bus Voltage: ");
  busVoltage_V = ina228.getBusVoltage_V();
  Serial.print(busVoltage_V);
  Serial.println(" V");

  Serial.print("Shunt Voltage: ");
  shuntVoltage_mV = ina228.getShuntVoltage_mV();
  Serial.print(shuntVoltage_mV);
  Serial.println(" mV");

  Serial.print("Power: ");
  power_mW = ina228.getPower_mW();
  Serial.print(power_mW);
  Serial.println(" mW");

  Serial.print("Energy: ");
  energy = ina228.readEnergy();
  Serial.print(energy);
  Serial.println(" J");
  
  Serial.print("Charge: ");
  charge = ina228.readCharge();
  Serial.print(charge);
  Serial.println(" C");

  Serial.print("Temperature: ");
  dieTemp = ina228.readDieTemp();
  Serial.print(dieTemp);
  Serial.println(" *C");

  Serial.println();
}

// SETUP LOOP
void setup() {
  Serial.begin(115200);
  // Start WiFi in AP mode
  // WiFi.mode(WIFI_AP);
  // WiFi.softAP(ssid, password);
  WiFi.begin(ssid, password);
  // delay(20);
  // Serial.println("Access Point Started");
  // Serial.print("Specified IP Address: ");
  // Serial.println(WiFi.softAPIP()); // Print ESP32 AP IP specified above

  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nConnected to WiFi!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP()); // Print assigned IP Address

  motorControl.begin(LEFT_MOTOR_PIN_FRONT, RIGHT_MOTOR_PIN_FRONT, LEFT_MOTOR_PIN_BACK, RIGHT_MOTOR_PIN_BACK, WINCH_MOTOR_PIN);

  // Start UDP listener
  udp.begin(udpPort);
  Serial.println("Waiting for UDP packets...");

  // INA228 setup
  if (!ina228.begin()) {
    Serial.println("Couldn't find INA228 chip");
    while (1)
      ;
  }
  Serial.println("Found INA228 chip");
  // set shunt resistance and max current
  ina228.setShunt(0.015, 10.0);

  ina228.setAveragingCount(INA228_COUNT_16);
  uint16_t counts[] = {1, 4, 16, 64, 128, 256, 512, 1024};
  Serial.print("Averaging counts: ");
  Serial.println(counts[ina228.getAveragingCount()]);

  // set the time over which to measure the current and bus voltage
  ina228.setVoltageConversionTime(INA228_TIME_150_us);
  Serial.print("Voltage conversion time: ");
  switch (ina228.getVoltageConversionTime()) {
  case INA228_TIME_50_us:
    Serial.print("50");
    break;
  case INA228_TIME_84_us:
    Serial.print("84");
    break;
  case INA228_TIME_150_us:
    Serial.print("150");
    break;
  case INA228_TIME_280_us:
    Serial.print("280");
    break;
  case INA228_TIME_540_us:
    Serial.print("540");
    break;
  case INA228_TIME_1052_us:
    Serial.print("1052");
    break;
  case INA228_TIME_2074_us:
    Serial.print("2074");
    break;
  case INA228_TIME_4120_us:
    Serial.print("4120");
    break;
  }
  Serial.println(" uS");

  ina228.setCurrentConversionTime(INA228_TIME_280_us);
  Serial.print("Current conversion time: ");
  switch (ina228.getCurrentConversionTime()) {
  case INA228_TIME_50_us:
    Serial.print("50");
    break;
  case INA228_TIME_84_us:
    Serial.print("84");
    break;
  case INA228_TIME_150_us:
    Serial.print("150");
    break;
  case INA228_TIME_280_us:
    Serial.print("280");
    break;
  case INA228_TIME_540_us:
    Serial.print("540");
    break;
  case INA228_TIME_1052_us:
    Serial.print("1052");
    break;
  case INA228_TIME_2074_us:
    Serial.print("2074");
    break;
  case INA228_TIME_4120_us:
    Serial.print("4120");
    break;
  }
  Serial.println(" uS");

  delay(5000);

}

// MAIN LOOP
void loop() {

  getINA228Data();

  int packetSize = udp.parsePacket();

  if (packetSize) {
    int len = udp.read(packetBuffer, sizeof(packetBuffer) - 1);
    if (len > 0) {
        packetBuffer[len] = '\0';  // Null-terminate string
    }

    Serial.print("Received: ");
    Serial.println(packetBuffer);  // Print joystick data
    processPS4(packetBuffer);

    laptopIP = udp.remoteIP();
  }

  // Send IMU Data to Laptop (if IP is known)
  // if (laptopIP != IPAddress(0, 0, 0, 0)) {
  
    String stateData = String(last_forward_veclocity_cmd, 1) + "," +
                       String(last_steering_veclocity_cmd, 1)  + "," +
                       String(power_mW, 1) + "," +
                       String(current_mA, 1) + "," +
                       String(busVoltage_V, 1) + "," +
                       String(shuntVoltage_mV, 1) + "," +
                       String(energy, 1) + "," +
                       String(charge, 1) + "," +
                       String(dieTemp, 1);

    // // Send UDP packet to the laptop
    udp.beginPacket(laptopIP, udpPort);
    udp.print(stateData);
    udp.endPacket();

  Serial.println("Sent sensor data: " + stateData);
  // } else {
  //   Serial.println("No UDP client found, skipping data send.");
  //  }

  delay(50);  // Send data at ~20Hz


}