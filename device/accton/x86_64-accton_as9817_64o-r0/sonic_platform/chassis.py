#############################################################################
# Edgecore
#
# Module contains an implementation of SONiC Platform Base API and
# provides the Chassis information which are available in the platform
#
#############################################################################

import sys

try:
    from sonic_platform_base.chassis_base import ChassisBase
    from .helper import APIHelper
    from .event import SfpEvent
except ImportError as e:
    raise ImportError(str(e) + "- required module not found")

NUM_FAN_TRAY = 4
NUM_PSU = 2
NUM_THERMAL = 13
NUM_PORT = 66
NUM_COMPONENT = 5

HOST_REBOOT_CAUSE_PATH = "/host/reboot-cause/"
PMON_REBOOT_CAUSE_PATH = "/usr/share/sonic/platform/api_files/reboot-cause/"
REBOOT_CAUSE_FILE = "reboot-cause.txt"
PREV_REBOOT_CAUSE_FILE = "previous-reboot-cause.txt"
SYSLED_FNODE= "/sys/devices/platform/as9817_64_led/led_alarm"
SYSLED_MODES = {
    "0" : "STATUS_LED_COLOR_OFF",
    "10" : "STATUS_LED_COLOR_RED",
}

class Chassis(ChassisBase):
    """Platform-specific Chassis class"""

    def __init__(self):
        ChassisBase.__init__(self)
        self._api_helper = APIHelper()
        self.is_host = self._api_helper.is_host()

        self.config_data = {}

        self.__initialize_fan()
        self.__initialize_psu()
        self.__initialize_thermals()
        self.__initialize_components()
        self.__initialize_sfp()
        self.__initialize_eeprom()

    def __initialize_sfp(self):
        from sonic_platform.sfp import Sfp
        intf_name = self._api_helper.get_intf_name()
        for index in range(NUM_PORT):
            sfp = Sfp(index, intf_name.get(index + 1, "Unknown"))
            self._sfp_list.append(sfp)
        self._sfpevent = SfpEvent(self._sfp_list)
        self.sfp_module_initialized = True

    def __initialize_fan(self):
        from sonic_platform.fan_drawer import FanDrawer
        for fant_index in range(NUM_FAN_TRAY):
            fandrawer = FanDrawer(fant_index)
            self._fan_drawer_list.append(fandrawer)
            self._fan_list.extend(fandrawer._fan_list)

    def __initialize_psu(self):
        from sonic_platform.psu import Psu
        for index in range(NUM_PSU):
            psu = Psu(index)
            self._psu_list.append(psu)

    def __initialize_thermals(self):
        from sonic_platform.thermal import Thermal
        for index in range(NUM_THERMAL):
            thermal = Thermal(index)
            self._thermal_list.append(thermal)

    def __initialize_eeprom(self):
        from sonic_platform.eeprom import Tlv
        self._eeprom = Tlv()

    def __initialize_components(self):
        from sonic_platform.component import Component
        for index in range(NUM_COMPONENT):
            component = Component(index)
            self._component_list.append(component)

    def get_name(self):
        """
        Retrieves the name of the device
            Returns:
            string: The name of the device
        """
        return self._eeprom.get_model()

    def get_presence(self):
        """
        Retrieves the presence of the Chassis
        Returns:
            bool: True if Chassis is present, False if not
        """
        return True

    def get_status(self):
        """
        Retrieves the operational status of the device
        Returns:
            A boolean value, True if device is operating properly, False if not
        """
        return True

    def get_base_mac(self):
        """
        Retrieves the base MAC address for the chassis
        Returns:
            A string containing the MAC address in the format
            'XX:XX:XX:XX:XX:XX'
        """
        return self._eeprom.get_mac()

    def get_model(self):
        """
        Retrieves the model number (or part number) of the device
        Returns:
            string: Model/part number of device
        """
        return self._eeprom.get_pn()

    def get_serial(self):
        """
        Retrieves the hardware serial number for the chassis
        Returns:
            A string containing the hardware serial number for this chassis.
        """
        return self._eeprom.get_serial()

    def get_revision(self):
        """
        Retrieves the hardware revision number for the chassis
        Returns:
            A string containing the hardware revision number for this chassis.
        """
        return self._eeprom.get_revision()

    def get_system_eeprom_info(self):
        """
        Retrieves the full content of system EEPROM information for the chassis
        Returns:
            A dictionary where keys are the type code defined in
            OCP ONIE TlvInfo EEPROM format and values are their corresponding
            values.
        """
        return self._eeprom.get_eeprom()

    def get_reboot_cause(self):
        """
        Retrieves the cause of the previous reboot

        Returns:
            A tuple (string, string) where the first element is a string
            containing the cause of the previous reboot. This string must be
            one of the predefined strings in this class. If the first string
            is "REBOOT_CAUSE_HARDWARE_OTHER", the second string can be used
            to pass a description of the reboot cause.
        """
        description = 'None'

        reboot_cause_path = (HOST_REBOOT_CAUSE_PATH + REBOOT_CAUSE_FILE) \
            if self.is_host \
            else (PMON_REBOOT_CAUSE_PATH + REBOOT_CAUSE_FILE)
        prev_reboot_cause_path = (HOST_REBOOT_CAUSE_PATH + PREV_REBOOT_CAUSE_FILE) \
            if self.is_host \
            else (PMON_REBOOT_CAUSE_PATH + PREV_REBOOT_CAUSE_FILE)

        sw_reboot_cause      = self._api_helper.read_txt_file(reboot_cause_path) or "Unknown"
        prev_sw_reboot_cause = self._api_helper.read_txt_file(prev_reboot_cause_path) or "Unknown"

        if sw_reboot_cause != "Unknown":
            reboot_cause = self.REBOOT_CAUSE_NON_HARDWARE
            description = sw_reboot_cause
        elif prev_reboot_cause_path != "Unknown":
            reboot_cause = self.REBOOT_CAUSE_NON_HARDWARE
            description = prev_sw_reboot_cause

        return (reboot_cause, description)

    def get_change_event(self, timeout=0):
        # SFP event
        if not self.sfp_module_initialized:
            self.__initialize_sfp()

        return self._sfpevent.get_sfp_event(timeout)

    def get_sfp(self, index):
        """
        Retrieves sfp represented by (1-based) index <index>
        Args:
            index: An integer, the index (1-based) of the sfp to retrieve.
            The index should be the sequence of a physical port in a chassis,
            starting from 1.
            For example, 1 for Ethernet0, 2 for Ethernet4 and so on.
        Returns:
            An object dervied from SfpBase representing the specified sfp
        """
        sfp = None
        if not self.sfp_module_initialized:
            self.__initialize_sfp()

        try:
            # The index will start from 1
            sfp = self._sfp_list[index-1]
        except IndexError:
            sys.stderr.write("SFP index {} out of range (1-{})\n".format(
                             index, len(self._sfp_list)))
        return sfp

    def get_port_or_cage_type(self, index):
        from sonic_platform_base.sfp_base import SfpBase

        if index in range(1, 65):
            return (SfpBase.SFP_PORT_TYPE_BIT_QSFP | SfpBase.SFP_PORT_TYPE_BIT_QSFP_PLUS | 
                    SfpBase.SFP_PORT_TYPE_BIT_QSFP28 | SfpBase.SFP_PORT_TYPE_BIT_QSFPDD | 
                    SfpBase.SFP_PORT_TYPE_BIT_OSFP)
        else:
            return SfpBase.SFP_PORT_TYPE_BIT_SFP | SfpBase.SFP_PORT_TYPE_BIT_SFP_PLUS | SfpBase.SFP_PORT_TYPE_BIT_SFP28

    def get_position_in_parent(self):
        """
        Retrieves 1-based relative physical position in parent device. If the agent cannot determine the parent-relative position
        for some reason, or if the associated value of entPhysicalContainedIn is '0', then the value '-1' is returned
        Returns:
            integer: The 1-based relative physical position in parent device or -1 if cannot determine the position
        """
        return -1

    def is_replaceable(self):
        """
        Indicate whether this device is replaceable.
        Returns:
            bool: True if it is replaceable.
        """
        return False

    def initizalize_system_led(self):
        return True

    def get_status_led(self):
        val = self._api_helper.read_txt_file(SYSLED_FNODE)
        return SYSLED_MODES[val] if val in SYSLED_MODES else "UNKNOWN"

    def set_status_led(self, color):
        mode = None
        for key, val in SYSLED_MODES.items():
            if val == color:
                mode = key
                break
        if mode is None:
            return False
        else:
            return self._api_helper.write_txt_file(SYSLED_FNODE, mode)


