import obd

class ObdManager:

    KPA_TO_PSI_CONVERSION_FACTOR = 0.145038

    def __init__(self, demo_mode=False):
        self.demo_mode = demo_mode
        self.obd_connection = ""

    def init_obd_connection(self, serial_connection_id):
        if self.demo_mode:
            return

        if obd.scan_serial():
            if serial_connection_id in obd.scan_serial():
                self.obd_connection = obd.OBD(serial_connection_id)

    def has_obd_connection(self):
        if self.demo_mode:
            return True

        if self.obd_connection != "":
            if self.obd_connection.is_connected():
                return True
            else:
                return False
        else:
            return False

    def generate_obd_response(self, command):
        if self.demo_mode:
            if command == "SPEED":
                return "65 kph"
            elif command == "RPM":
                return "2500 RPM"
            elif command == "BOOST":
                return "5 PSI"
            elif command == "COOLANT_TEMP":
                return "95 C"
            elif command == "VOLTAGE":
                return "12.5 V"
            elif command == "DTC":
                return "[]"
            else:
                return "0"

        if self.has_obd_connection():
            if command == "RPM":
                obd_command = obd.commands.RPM
                obd_unit = str(obd.Unit.RPM)

            elif command == "BOOST":
                obd_command = obd.commands.INTAKE_PRESSURE
                obd_unit = str(obd.Unit.PSI)

            elif command == "SPEED":
                obd_command = obd.commands.SPEED
                obd_unit = "kph"

            elif command == "COOLANT_TEMP":
                obd_command = obd.commands.COOLANT_TEMP
                obd_unit = "C"

            elif command == "VOLTAGE":
                obd_command = obd.commands.CONTROL_MODULE_VOLTAGE
                obd_unit = "V"

            elif command == "DTC":
                obd_command = obd.commands.GET_DTC
                obd_unit = ""

            else:
                return "'" + command + "' is unrecognized OBD command"

            obd_response = self.obd_connection.query(obd_command)

            if command == "DTC":
                if obd_response.is_null():
                    return "[]"
                codes = [code for (code, desc) in obd_response.value]
                return str(codes)

            if not obd_response.is_null():
                value = float(obd_response.value.magnitude)

                if command == "BOOST":
                    value = value * self.KPA_TO_PSI_CONVERSION_FACTOR
                    value = round(value, 3)

                return str(value) + " " + obd_unit
            else:
                return "No OBD response"

        else:
            return "No OBD connection"