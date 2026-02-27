# This files connects to the obd reader and can return the values for RPM and BOOST.
# Basis of a class to manage connections and requests. 

import obd

class ObdManager:

    KPA_TO_PSI_CONVERSION_FACTOR = 0.145038
    # Car sensors often report pressure in kPa, but humans prefer PSI. Convert to PSI

    def __init__(self):
        self.obd_connection = ""

    def init_obd_connection(self, serial_connection_id):
        if obd.scan_serial():
            if serial_connection_id in obd.scan_serial():
                self.obd_connection = obd.OBD(serial_connection_id)

    def has_obd_connection(self):
        if self.obd_connection != "":
            if self.obd_connection.is_connected():
                return True
            else:
                return False
        else:
            return False

    def generate_obd_response(self, command):
        if self.has_obd_connection():
            if command == "RPM":
                obd_command = obd.commands.RPM # obd.commands will return the code for RPM needed to communicate w/ car
                obd_unit = str(obd.Unit.RPM)
            elif command == "BOOST":
                # Boost = extra air pressure created by a turbocharger or supercharger
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
                #DTC = Diagnostic Trouble Code
                obd_command = obd.commands.GET_DTC
                obd_unit = ""  # list of codes, no unit
            else:
                return "'" + command + "' is unrecognized OBD command"
            

            # 
            obd_response = self.obd_connection.query(obd_command)
            # DTC returns a list, not a number
            if command == "DTC":
                if obd_response.is_null():
                    return "[]"
                codes = [code for (code, desc) in obd_response.value]
                return str(codes)
            
            if not obd_response.is_null():
                value = float(obd_response.value.magnitude)

                # Only BOOST needs kPa -> psi conversion
            if command == "BOOST":
                value = value * self.KPA_TO_PSI_CONVERSION_FACTOR
                value = round(value, 3)
                return str(value) + " " + obd_unit
            
            else:
                return "No OBD response"
