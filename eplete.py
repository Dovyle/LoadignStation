import time
import socket
import serial.tools.list_ports
import serial
import threading
import winsound

pressCredit = False


def find_arduino_port():
    # Get a list of all available COM ports
    available_ports = serial.tools.list_ports.comports()

    for port in available_ports:
        # Check if the description or manufacturer contains 'Arduino'
        if 'USB-SERIAL CH340' in port.description or 'USB-SERIAL CH340' in port.manufacturer or 'USB Serial Device' in port.description or 'USB Serial Device' in port.manufacturer:
            return port.device

    # If no Arduino is found, return None
    return None


def find_arduino_baud_rate(port):
    # Try different baud rates to find the one used by the Arduino
    baud_rates_to_try = [115200]  # Add more if needed

    for baud_rate in baud_rates_to_try:
        print("{}--{}".format(port, baud_rate))
        try:
            arduino = serial.Serial(port, baud_rate, timeout=0.1)
            time.sleep(2)
            arduino.write(b'handshake\n')
            response = arduino.readline().decode("utf-8")

            if response == "hehehehe\r\n":
                # print("Arduino Response: {}".format(response))
                return baud_rate

            arduino.close()
        except serial.SerialException:
            print("Error in the serial port")

    # If no valid baud rate is found, return None
    # print("Baud rate: {}".format(baud_rate))
    return None


def handshake():
    arduino_port = find_arduino_port()
    # arduino_port = "COM2"
    if arduino_port:
        print(f"Arduino found on {arduino_port}")

        baud_rate = find_arduino_baud_rate(arduino_port)
        if baud_rate:
            print("Baud rate detected: {}".format(baud_rate))

            # Now you can establish the serial connection with the Arduino using the detected port and baud rate
            arduino = serial.Serial(arduino_port, baud_rate, timeout=2)
            time.sleep(2)
            arduino.write(b'rfidcheck\n')
            response = arduino.readline().decode("utf-8")
            print("\n{}".format(response))
            return arduino
        else:
            print("Unable to detect baud rate.")
    else:
        print("Arduino not found.")

    return None


def waitTag(arduino):
    while True:
        tag_id = arduino.readline()
        tag_id = tag_id.replace(b'\r', b'').replace(b'\n', b'')
        tag_id = tag_id.decode("utf-8")
        if tag_id:
            print("Tag ID: {}".format(tag_id))
            return tag_id

        # return None


def validateTag(tag_id, arduino, skt, node_ip, node_port):
    UDP_IP = node_ip
    UDP_PORT = int(node_port)
    frequency = 2500
    duration = 500
    skt.settimeout(5)
    try:
        msg = "TAG,{}".format(tag_id)
        skt.sendto(msg.encode(), (UDP_IP, UDP_PORT))
        time.sleep(1)
        status, addr = skt.recvfrom(1024)
        if status.decode("utf-8") == "Rider":
            winsound.Beep(frequency, 500)
            time.sleep(1)
            print("\nTAG Valid per SERVER...")
            arduino.write(b'Rider\n')
            # time.sleep(2)
            response = arduino.readline()
            response = response.replace(b'\r', b'').replace(b'\n', b'')
            print("TAG Validity - Arduino response: {}".format(response))
            if response.decode("utf-8") == "Input cash":
                return 'Valid'
        elif status.decode("utf-8") == "Driver":
            winsound.Beep(frequency, 500)
            time.sleep(1)
            print("\nTAG Valid per SERVER...")
            arduino.write(b'Driver\n')
            response = arduino.readline()
            response = response.replace(b'\r', b'').replace(b'\n', b'')
            print("TAG Validity - Arduino response: {}".format(response))
            if response.decode("utf-8") == "Driver here":
                return 'Valid'
        else:
            arduino.write(b'Invalid\n')
            print('TAG invalid..')
            winsound.Beep(frequency, 200)
            winsound.Beep(frequency, 200)
            return 'Invalid'
    except socket.error as msg:
        arduino.write(b'Invalid\n')
        return 'Invalid'

    return None


def listenWebApp(skt):
    isExit = False
    global pressCredit

    print("Listen for button CREDIT Press...")
    while not isExit:
        try:
            command, netDev = skt.recvfrom(1024)
            command = command.decode("utf-8")
            if command == "Done":
                isExit = True
                pressCredit = True
        except socket.timeout:
            pass

    print("Listening to dummy Web App ended...")


def rcvMoney(arduino, skt, node_ip, node_port):
    UDP_IP = node_ip
    UDP_PORT = int(node_port)
    global pressCredit
    pressCredit = False

    print("Waiting for money...")
    webApp = threading.Thread(target=listenWebApp, args=(skt,))
    webApp.start()

    while not pressCredit:
        pulseCount = arduino.readline()
        pulseCount = pulseCount.replace(b'\r', b'').replace(b'\n', b'')
        if pulseCount:
            pulseCount = int(pulseCount.decode("utf-8"))

            # compute amount
            amount = pulseCount * 10
            msg = "LOAD,{}".format(amount)
            # print("Sent to Web App: {}".format(msg))
            # send to Web App
            skt.sendto(msg.encode(), (UDP_IP, UDP_PORT))

    print("Receive amount from Arduino end...")


def resetState(arduino):
    while True:
        arduino.write(b'Done\n')
        # time.sleep(1)
        msg = arduino.readline()
        msg = msg.replace(b'\r', b'').replace(b'\n', b'')
        msg = msg.decode("utf-8")
        print("Reset Arduino response: {}\n".format(msg))
        if msg == "Done Acknowledge":
            return


def KioskLogic(arduino, skt, node_ip, node_port):
    op_state = "WAIT_TAG"
    while True:
        if op_state == "WAIT_TAG":
            tag_id = waitTag(arduino)
            op_state = "VALIDATE_TAG"

        elif op_state == "VALIDATE_TAG":
            if tag_id:
                status = validateTag(tag_id, arduino, skt, node_ip, node_port)
                if status == "Valid":
                    op_state = "WAIT_MONEY"
                else:
                    op_state = "WAIT_TAG"
            else:
                op_state = "WAIT_TAG"

        elif op_state == "WAIT_MONEY":
            rcvMoney(arduino, skt, node_ip, node_port)
            op_state = "RESET"

        elif op_state == "RESET":
            resetState(arduino)
            op_state = "WAIT_TAG"


if __name__ == "__main__":
    arduino = None
    while not arduino:
        arduino = handshake()
    skt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    f = open('connection.txt', "r")
    net_info = f.read()
    print('Server info: {}'.format(net_info))
    node_ip, node_port = net_info.split(',')
    KioskLogic(arduino, skt, node_ip, node_port)