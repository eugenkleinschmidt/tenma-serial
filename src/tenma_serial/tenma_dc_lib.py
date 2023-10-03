#    Copyright (C) 2017,2019,2020 Jordi Castells
#
#
#   this file is part of tenma-serial
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>

"""
This module controls a Tenma 72-XXXX programmable DC power supply, either from USB or Serial.

Supported models:

* 72_2545 -> Tested on HW
* 72_2535 -> Set as manufacturer manual (not tested)
* 72_2540 -> Set as manufacturer manual (not tested)
* 72_2550 -> Tested on HW
* 72-2705 -> Tested on HW
* 72_2930 -> Set as manufacturer manual (not tested)
* 72_2940 -> Set as manufacturer manual (not tested)
* 72_13320 -> Set as manufacturer manual (not tested)
* 72_13330 -> Tested on HW

Other units from Korad or Vellman might work as well since
they use the same serial protocol.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Generator, Literal

import serial

ChannelModeType = Literal["C.V", "C.C"]


class TrackingModeType(IntEnum):
    Independent = 0
    TrackingSeries = 1
    TrackingParallel = 2


@dataclass
class Mode:
    ch1_mode: ChannelModeType
    ch2_mode: ChannelModeType
    tracking_mode: TrackingModeType
    beep_enabled: bool = False
    lock_enabled: bool = False
    out1_enabled: bool = False
    out2_enabled: bool = False


class TenmaError(Exception):
    pass


def instantiate_tenma_class_from_device_response(
    device: str, debug: bool = False
) -> Tenma72Base:
    """
    Get a proper Tenma subclass depending on the version response from the unit.

    The subclasses mainly deal with the limit checks for each
    unit.
    """
    # First instantiate base to retrieve version
    power_supply = Tenma72Base(device, debug=debug)
    ver = power_supply.get_version()
    if not ver:
        if debug:
            print("No version found, retrying with newline EOL")
        ver = power_supply.get_version(serial_eol="\n")
    power_supply.close()

    for cls in find_subclasses_recursively(Tenma72Base):
        for match_string in cls.MATCH_STR:
            if match_string in ver:
                return cls(device, debug=debug)

    print("Could not detect Tenma power supply model, assuming 72_2545")
    return Tenma722545(device, debug=debug)


def find_subclasses_recursively(
    cls: type[Tenma72Base],
) -> Generator[type[Tenma72Base], type[Tenma72Base], None]:
    """Find all subclasses of a given class recursively."""
    for subclass in cls.__subclasses__():
        yield from find_subclasses_recursively(subclass)
        yield subclass


class Tenma72Base:
    MATCH_STR = [""]

    # 72Base sets some defaults. Subclasses should define
    # custom limits
    NCHANNELS = 1
    NCONFS = 5
    MAX_MA = 5000
    MAX_MV = 30000
    SERIAL_EOL = ""

    def __init__(self, serial_port: str, debug: bool = False) -> None:
        """Control a Tenma 72-XXXX DC bench power supply.

        Defaults in this class assume a 72-2540, use
        subclasses for other models
        """
        self.ser = serial.Serial(
            port=serial_port,
            baudrate=9600,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )

        self.DEBUG = debug

    def set_port(self, serial_port: str) -> None:
        """
        Set up the serial port with a new COM/tty device.

        :param serial_port: COM/tty device
        """
        self.ser = serial.Serial(
            port=serial_port,
            baudrate=9600,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )

    def _send_command(self, command: str) -> None:
        """
        Send a command to the serial port of a power supply.

        :param command: Command to send
        """
        if self.DEBUG:
            print(">> ", command.strip())
        command = command + self.SERIAL_EOL
        self.ser.write(command.encode("ascii"))
        # Give it time to process
        time.sleep(0.2)

    def _read_bytes(self) -> bytearray:
        """
        Read serial output as a stream of bytes.

        :return: Bytes read as a list of integers
        """
        out = bytearray()
        while self.ser.in_waiting > 0:
            out.append(ord(self.ser.read(1)))

        if self.DEBUG:
            print("<< ", [f"0x{v:02x}" for v in out])

        return out

    def __read_output(self) -> str:
        """
        Read serial otput as a string.

        :return: Data read as a string
        """
        out = ""
        while self.ser.in_waiting > 0:
            out += self.ser.read(1).decode("ascii")

        if self.DEBUG:
            print("<< ", out.strip())

        return out

    def check_channel(self, channel: int) -> None:
        """
        Check that the given channel is valid for the power supply.

        :param channel: Channel to check
        :raises TenmaError: If the channel is outside the range for the power supply
        """
        if channel > self.NCHANNELS:
            raise TenmaError(
                f"Channel CH{channel} not in range ({self.NCHANNELS} channels supported)"
            )

    def check_voltage(self, channel: int, mv: int) -> None:
        """
        Check that the given voltage is valid for the power supply.

        :param channel: Channel to check
        :param mv: Voltage to check
        :raises TenmaError: If the voltage is outside the range for the power supply
        """
        if mv > self.MAX_MV:
            raise TenmaError(
                f"Trying to set CH{channel} voltage to {mv}mV, the maximum is {self.MAX_MV}mV"
            )

    def check_current(self, channel: int, ma: int) -> None:
        """
        Check that the given current is valid for the power supply.

        :param channel: Channel to check
        :param ma: current to check
        :raises TenmaError: If the current is outside the range for the power supply
        """
        if ma > self.MAX_MA:
            raise TenmaError(
                f"Trying to set CH{channel} current to {ma}mA, the maximum is {self.MAX_MA}mA"
            )

    def get_version(self, serial_eol: str = "") -> str:
        """
        Return a single string with the version of the Tenma Device and Protocol user.

        :param serial_eol: End of line terminator, defaults to ""
        :return: The version string from the power supply
        """
        self._send_command(f"*IDN?{serial_eol}")
        return self.__read_output()

    def get_status(self) -> Mode:
        """
        Return the power supply status of type Status.

        * ch1Mode: "C.V | C.C"
        * ch2Mode: "C.V | C.C"
        * tracking:
            * 00=Independent
            * 01=Tracking series
            * 11=Tracking parallel
        * BeepEnabled: True | False
        * lockEnabled: True | False
        * outEnabled: True | False

        :return: Status values of type Status
        """
        self._send_command("STATUS?")
        status_bytes = self._read_bytes()

        status = status_bytes[0]

        ch1mode = status & 0x01
        ch2mode = status & 0x02
        tracking = (status & 0x0C) >> 2
        beep = status & 0x10
        lock = status & 0x20
        out = status & 0x40

        return Mode(
            ch1_mode="C.V" if ch1mode else "C.C",
            ch2_mode="C.V" if ch2mode else "C.C",
            tracking_mode=TrackingModeType(tracking),
            beep_enabled=bool(beep),
            lock_enabled=bool(lock),
            out1_enabled=bool(out),
        )

    def read_current(self, channel: int) -> float:
        """
        Read the current setting for the given channel.

        :param channel: Channel to read the current of
        :return: Current for the channel in Amps as a float
        """
        self.check_channel(channel)
        command_check = f"ISET{channel}?"
        self._send_command(command_check)
        # 72-2550 appends sixth byte from *IDN? to current reading due to firmware bug
        return float(self.__read_output()[:5])

    def set_current(self, channel: int, ma: int) -> float:
        """
        Set the current of the specified channel.

        :param channel: Channel to set the current of
        :param ma: Current to set the channel to, in mA
        :raises TenmaError: If the current does not match what was set
        :return: The current the channel was set to in Amps as a float
        """
        self.check_channel(channel)
        self.check_current(channel, ma)

        amps = float(ma) / 1000.0
        command = f"ISET{channel}:{amps:.3f}"

        self._send_command(command)
        read_current = self.read_current(channel)
        read_milliamps = int(read_current * 1000)

        if read_milliamps != ma:
            raise TenmaError(f"Set {ma}mA, but read {read_milliamps}mA")
        return float(read_current)

    def read_voltage(self, channel: int) -> float:
        """
        Read the voltage setting for the given channel.

        :param channel: Channel to read the voltage of
        :return: Voltage for the channel in Volts as a float
        """
        self.check_channel(channel)

        command_check = f"VSET{channel}?"
        self._send_command(command_check)
        return float(self.__read_output())

    def set_voltage(self, channel: int, mv: int) -> float:
        """
        Set the voltage of the specified channel.

        :param channel: Channel to set the voltage of
        :param mv: voltage to set the channel to, in mV
        :raises TenmaError: If the voltage does not match what was set
        :return: The voltage the channel was set to in Volts as a float
        """
        self.check_channel(channel)
        self.check_voltage(channel, mv)

        volts = float(mv) / 1000.0
        command = f"VSET{channel}:{volts:.2f}"

        self._send_command(command)
        read_volts = self.read_voltage(channel)
        read_millivolts = int(read_volts * 1000)

        if read_millivolts != int(mv):
            raise TenmaError(f"Set {mv}mV, but read {read_millivolts}mV")
        return float(read_volts)

    def running_current(self, channel: int) -> float:
        """
        Return the current read of a running channel.

        :param channel: Channel to get the running current for
        :return: The running current of the channel in Amps as a float
        """
        self.check_channel(channel)

        command = f"IOUT{channel}?"
        self._send_command(command)
        return float(self.__read_output())

    def running_voltage(self, channel: int) -> float:
        """
        Return the voltage read of a running channel.

        :param channel: Channel to get the running voltage for
        :return: The running voltage of the channel in volts as a float
        """
        self.check_channel(channel)

        command = f"VOUT{channel}?"
        self._send_command(command)
        return float(self.__read_output())

    def save_conf(self, conf: int) -> None:
        """
        Save current configuration into Memory.

        Does not work as one would expect. SAV(4) will not save directly to memory 4.
        We actually need to recall memory 4, set configuration and then SAV(4)

        :param conf: Memory index to store to
        :raises TenmaError: If the memory index is outside the range
        """
        if conf > self.NCONFS:
            raise TenmaError(f"Trying to set M{conf} with only {self.NCONFS} slots")

        command = f"SAV{conf}"
        self._send_command(command)

    def save_conf_flow(self, conf: int, channel: int) -> None:
        """
        Perform a full save flow for the unit.

        Since save_conf only calls the SAV<NR1> command, and that does not
        work as advertised, or expected, at least in 72_2540.

        This will:
         * turn off the output
         * Read the voltage that is set
         * recall memory conf
         * Save to that memory conf

        :param conf: Memory index to store to
        :param channel: Channel with output to store
        """
        self.off()

        # Read current voltage
        volt = self.read_voltage(channel)
        curr = self.read_current(channel)

        # Load conf (ensure we're on a the proper conf)
        self.recall_conf(conf)

        # Load the new conf in the panel
        self.set_voltage(channel, int(volt * 1000))
        # Load the new conf in the panel
        self.set_current(channel, int(curr * 1000))

        self.save_conf(conf)  # Save current status in current memory

        if self.DEBUG:
            print("Saved to Memory", conf)
            print("Voltage:", volt)
            print("Current:", curr)

    def recall_conf(self, conf: int) -> None:
        """Load existing configuration in Memory. Same as pressing any Mx button on the unit."""
        if conf > self.NCONFS:
            raise TenmaError(f"Trying to recall M{conf} with only {self.NCONFS} confs")
        self._send_command("RCL{confg}")

    def set_ocp(self, enable: bool = True) -> None:
        """
        Enable or disable OCP.

        There's no feedback from the serial connection to determine
        whether OCP was set or not.

        :param enable: Boolean to enable or disable
        """
        enable_flag = 1 if enable else 0
        command = f"OCP{enable_flag}"
        self._send_command(command)

    def set_ovp(self, enable: bool = True) -> None:
        """
        Enable or disable OVP.

        There's no feedback from the serial connection to determine
        whether OVP was set or not.

        :param enable: Boolean to enable or disable
        """
        enable_flag = 1 if enable else 0
        command = f"OVP{enable_flag}"
        self._send_command(command)

    def set_beep(self, enable: bool = True) -> None:
        """
        Enable or disable BEEP.

        There's no feedback from the serial connection to determine
        whether BEEP was set or not.

        :param enable: Boolean to enable or disable
        """
        enable_flag = 1 if enable else 0
        command = f"BEEP{enable_flag}"
        self._send_command(command)

    def on(self) -> None:
        """Turn on the output."""
        command = "OUT1"
        self._send_command(command)

    def off(self) -> None:
        """Turn off the output."""
        command = "OUT0"
        self._send_command(command)

    def close(self) -> None:
        """Close the serial port."""
        self.ser.close()

    def set_lock(self, enable: bool = True) -> None:
        """
        Set the front-panel lock on or off.

        :param enable: Enable lock, defaults to True
        :raises NotImplementedError Not implemented in this base class
        """
        raise NotImplementedError("Not supported by all models")

    def set_tracking(self, tracking_mode: TrackingModeType) -> None:
        """
        Set the tracking mode of the power supply outputs.

        :param tracking_mode: Tracking mode
        :raises NotImplementedError Not implemented in this base class
        """
        raise NotImplementedError("Not supported by all models")

    def start_auto_voltage_step(
        self,
        channel: int,
        start_millivolts: int,
        stop_millivolts: int,
        step_millivolts: int,
        step_time: int,
    ) -> None:
        """
        Start an automatic voltage step from Start mV to Stop mV, incrementing by Step mV every Time seconds.

        :param channel: Channel to start voltage step on
        :param start_millivolts: Starting voltage in mV
        :param stop_millivolts: End voltage in mV
        :param step_millivolts: Amount to increase voltage by in mV
        :param step_time: Time to wait before each increase, in Seconds
        :raises NotImplementedError Not implemented in this base class
        """
        raise NotImplementedError("Not supported by all models")

    def stop_auto_voltage_step(self, channel: int) -> None:
        """
        Stop the auto voltage step on the specified channel.

        :param channel: Channel to stop the auto voltage step on
        :raises NotImplementedError Not implemented in this base class
        """
        raise NotImplementedError("Not supported by all models")

    def start_auto_current_step(
        self,
        channel: int,
        start_milliamps: int,
        stop_milliamps: int,
        step_milliamps: int,
        step_time: int,
    ) -> None:
        """
        Start an automatic current step from Start mA to Stop mA, incrementing by Step mA every Time seconds.

        :param channel: Channel to start current step on
        :param start_milliamps: Starting current in mA
        :param stop_milliamps: End current in mA
        :param step_milliamps: Amount to increase current by in mA
        :param step_time: Time to wait before each increase, in Seconds
        :raises NotImplementedError Not implemented in this base class
        """
        raise NotImplementedError("Not supported by all models")

    def stop_auto_current_step(self, channel: int) -> None:
        """
        Stop the auto current step on the specified channel.

        :param channel: Channel to stop the auto current step on
        :raises NotImplementedError Not implemented in this base class
        """
        raise NotImplementedError("Not supported by all models")

    def set_manual_voltage_step(self, channel: int, step_millivolts: int) -> None:
        """
        Set the manual step voltage of the channel.

        When a VUP or VDOWN command is sent to the power supply channel, that channel
        will step up or down by step_millivolts mV.

        :param channel: Channel to set the step voltage for
        :param step_millivolts: Voltage to step up or down by when triggered
        :raises NotImplementedError Not implemented in this base class
        """
        raise NotImplementedError("Not supported by all models")

    def step_voltage_up(self, channel: int) -> None:
        """
        Increse the voltage by the configured step voltage on the specified channel.

        Call "set_manual_voltage_step" to set the step voltage.

        :param channel: Channel to increase the voltage for
        :raises NotImplementedError Not implemented in this base class
        """
        raise NotImplementedError("Not supported by all models")

    def step_voltage_down(self, channel: int) -> None:
        """
        Decrese the voltage by the configured step voltage on the specified channel.

        all "set_manual_voltage_step" to set the step voltage.

        :param channel: Channel to decrease the voltage for
        :raises NotImplementedError Not implemented in this base class
        """
        raise NotImplementedError("Not supported by all models")

    def set_manual_current_step(self, channel: int, step_milliamps: int) -> None:
        """
        Set the manual step current of the channel.

        When a IUP or IDOWN command is sent to the power supply channel, that channel
        will step up or down by step_milliamps mA.

        :param channel: Channel to set the step current for
        :param step_milliamps: Current to step up or down by when triggered
        :raises NotImplementedError Not implemented in this base class
        """
        raise NotImplementedError("Not supported by all models")

    def step_current_up(self, channel: int) -> None:
        """
        Increse the current by the configured step current on the specified channel.

        Call "set_manual_current_step" to set the step current.

        :param channel: Channel to increase the current for
        :raises NotImplementedError Not implemented in this base class
        """
        raise NotImplementedError("Not supported by all models")

    def step_current_down(self, channel: int) -> None:
        """
        Decrese the current by the configured step current on the specified channel.

        Call "set_manual_current_step" to set the step current.

        :param channel: Channel to decrease the current for
        :raises NotImplementedError Not implemented in this base class
        """
        raise NotImplementedError("Not supported by all models")


#
#
# Subclasses defining limits for each unit
# #\ :  Added for sphinx to pickup and document
# this constants
#
#
class Tenma722540(Tenma72Base):
    MATCH_STR = ["72-2540"]
    #:
    NCHANNELS = 1
    #: Only 4 physical buttons. But 5 memories are available
    NCONFS = 5
    #:
    MAX_MA = 5000
    #:
    MAX_MV = 30000


class Tenma722535(Tenma72Base):
    #:
    MATCH_STR = ["72-2535"]
    #:
    NCHANNELS = 1
    #:
    NCONFS = 5
    #:
    MAX_MA = 3000
    #:
    MAX_MV = 30000


class Tenma722545(Tenma72Base):
    #:
    MATCH_STR = ["72-2545"]
    #:
    NCHANNELS = 1
    #:
    NCONFS = 5
    #:
    MAX_MA = 2000
    #:
    MAX_MV = 60000


class Tenma722550(Tenma72Base):
    #: Tenma 72-2550 is also manufactured as Korad KA 6003P
    MATCH_STR = ["72-2550", "KORADKA6003P"]
    #:
    NCHANNELS = 1
    #:
    NCONFS = 5
    #:
    MAX_MA = 3000
    #:
    MAX_MV = 60000


class Tenma722930(Tenma72Base):
    #:
    MATCH_STR = ["72-2930"]
    #:
    NCHANNELS = 1
    #:
    NCONFS = 5
    #:
    MAX_MA = 10000
    #:
    MAX_MV = 30000


class Tenma722705(Tenma72Base):
    #:
    MATCH_STR = ["72-2705"]
    #:
    NCHANNELS = 1
    #:
    NCONFS = 5
    #:
    MAX_MA = 3100
    #:
    MAX_MV = 31000


class Tenma722940(Tenma72Base):
    #:
    MATCH_STR = ["72-2940"]
    #:
    NCHANNELS = 1
    #:
    NCONFS = 5
    #:
    MAX_MA = 5000
    #:
    MAX_MV = 60000


class Tenma7213320(Tenma72Base):
    #:
    MATCH_STR = ["72-13320"]
    #:
    NCHANNELS = 3
    #: This unit does actually support 10 slots (0-9) but it's not avialable from the front panel
    NCONFS = 0
    #:
    MAX_MA = 3000
    #:
    MAX_MV = 30000
    #:
    SERIAL_EOL = "\n"

    def get_status(self) -> Mode:
        """
        Return the power supply status as a dictionary of values.

        * ch1Mode: "C.V | C.C"
        * ch2Mode: "C.V | C.C"
        * tracking:
            * 00=Independent
            * 01=Tracking series
            * 10=Tracking parallel
        * out1Enabled: True | False
        * out2Enabled: True | False

        :return: Dictionary of status values
        """
        self._send_command("STATUS?")
        status_bytes = self._read_bytes()

        # 72-13330 sends two bytes back, the second being '\n'
        status = status_bytes[0]

        ch1mode = status & 0x01
        ch2mode = status & 0x02
        tracking = (status & 0x0C) >> 2
        out1 = status & 0x40
        out2 = status & 0x80

        return Mode(
            ch1_mode="C.V" if ch1mode else "C.C",
            ch2_mode="C.V" if ch2mode else "C.C",
            tracking_mode=TrackingModeType(tracking),
            out1_enabled=bool(out1),
            out2_enabled=bool(out2),
        )

    def read_current(self, channel: int) -> float:
        """
        Read the current setting for the given channel.

        :param channel: Channel to read the current of
        :return: Current for the channel in Amps as a float
        :raises TenmaError: If trying to read the current of Channel 3
        """
        if channel == 3:
            raise TenmaError("Channel CH3 does not support reading current")
        return super().read_current(channel)

    def running_current(self, channel: int) -> float:
        """
        Return the current read of a running channel.

        :param channel: Channel to get the running current for
        :return: The running current of the channel in Amps as a float
        :raises TenmaError: If trying to read the current of Channel 3
        """
        if channel == 3:
            raise TenmaError("Channel CH3 does not support reading current")
        return super().running_current(channel)

    def set_voltage(self, channel: int, mv: int) -> float:
        """
        Set the voltage of the specified channel.

        :param channel: Channel to set the voltage of
        :param mv: voltage to set the channel to, in mV
        :raises TenmaError: If the voltage does not match what was set,
        or if trying to set an invalid voltage on Channel 3
        :return: The voltage the channel was set to in Volts as a float
        """
        if channel == 3 and mv not in [2500, 3300, 5000]:
            raise TenmaError("Channel CH3 can only be set to 2500mV, 3300mV or 5000mV")
        return super().set_voltage(channel, mv)

    def set_ocp(self, enable: bool = True) -> None:
        """
        Enable or disable OCP.

        There's no feedback from the serial connection to determine
        whether OCP was set or not.

        :param enable: Boolean to enable or disable
        :raises NotImplementedError: This model doesn't support OCP
        """
        raise NotImplementedError("This model does not support OCP")

    def set_ovp(self, enable: bool = True) -> None:
        """
        Enable or disable OVP.

        There's no feedback from the serial connection to determine
        whether OVP was set or not.

        :param enable: Boolean to enable or disable
        :raises NotImplementedError: This model doesn't support OVP
        """
        raise NotImplementedError("This model does not support OVP")

    def on(self, channel: int | None = None) -> None:
        """
        Turn on the output(s).

        :param channel: Channel to turn on, defaults to None (turn all channels on)
        """
        if channel is None:
            command = "OUT12:1"
        else:
            self.check_channel(channel)
            command = f"OUT{channel}:1"

        self._send_command(command)

    def off(self, channel: int | None = None) -> None:
        """
        Turn off the output(s).

        :param channel: Channel to turn on, defaults to None (turn all channels off)
        """
        if channel is None:
            command = "OUT12:0"
        else:
            self.check_channel(channel)
            command = f"OUT{channel}:0"
        self._send_command(command)

    def set_lock(self, enable: bool = True) -> None:
        """
        Set the front-panel lock on or off.

        :param enable: Enable lock, defaults to True
        """
        enable_flag = 1 if enable else 0
        self._send_command(f"LOCK{enable_flag}")

    def set_tracking(self, tracking_mode: TrackingModeType) -> None:
        """
        Set the tracking mode of the power supply outputs.

        0: Independent
        1: Series
        2: Parallel.

        :param tracking_mode: one of 0, 1 or 2
        """
        self._send_command(f"TRACK{tracking_mode}")

    def start_auto_voltage_step(
        self,
        channel: int,
        start_millivolts: int,
        stop_millivolts: int,
        step_millivolts: int,
        step_time: int,
    ) -> None:
        """
        Start an automatic voltage step from Start mV to Stop mV, incrementing by Step mV every Time seconds.

        :param channel: Channel to start voltage step on
        :param start_millivolts: Starting voltage in mV
        :param stop_millivolts: End voltage in mV
        :param step_millivolts: Amount to increase voltage by in mV
        :param step_time: Time to wait before each increase, in Seconds
        :raises TenmaError: If the channel or voltage is invalid
        """
        self.check_channel(channel)
        self.check_voltage(channel, stop_millivolts)
        # TODO: improve this check for when we're stepping down in voltage
        if step_millivolts > stop_millivolts:
            raise TenmaError(
                f"Channel CH{channel} step voltage {step_millivolts}V"
                f" higher than stop voltage {stop_millivolts}V"
            )

        start_volts = float(start_millivolts) / 1000.0
        stop_volts = float(stop_millivolts) / 1000.0
        step_volts = float(step_millivolts) / 1000.0

        command = f"VASTEP{channel}:{start_volts},{stop_volts},{step_volts},{step_time}"
        self._send_command(command)

    def stop_auto_voltage_step(self, channel: int) -> None:
        """
        Stop the auto voltage step on the specified channel.

        :param channel: Channel to stop the auto voltage step on
        """
        self.check_channel(channel)
        self._send_command(f"VASTOP{channel}")

    def start_auto_current_step(
        self,
        channel: int,
        start_milliamps: int,
        stop_milliamps: int,
        step_milliamps: int,
        step_time: int,
    ) -> None:
        """
        Start an automatic current step from Start mA to Stop mA incrementing by Step mA every Time seconds.

        :param channel: Channel to start current step on
        :param start_milliamps: Starting current in mA
        :param stop_milliamps: End current in mA
        :param step_milliamps: Amount to increase current by in mA
        :param step_time: Time to wait before each increase, in Seconds
        :raises TenmaError: If the channel or current is invalid
        """
        self.check_channel(channel)
        self.check_current(channel, stop_milliamps)
        if step_milliamps > stop_milliamps:
            raise TenmaError(
                f"Channel CH{channel} step current {step_milliamps}mA higher"
                f" than stop current {stop_milliamps}mA"
            )

        start_amps = float(start_milliamps) / 1000.0
        stop_amps = float(stop_milliamps) / 1000.0
        step_amps = float(step_milliamps) / 1000.0

        command = f"IASTEP{channel}:{start_amps},{stop_amps},{step_amps},{step_time}"
        self._send_command(command)

    def stop_auto_current_step(self, channel: int) -> None:
        """
        Stop the auto current step on the specified channel.

        :param channel: Channel to stop the auto current step on
        """
        self.check_channel(channel)
        self._send_command(f"IASTOP{channel}")

    def set_manual_voltage_step(self, channel: int, step_millivolts: int) -> None:
        """
        Set the manual step voltage of the channel.

        When a VUP or VDOWN command is sent to the power supply channel, that channel
        will step up or down by step_millivolts mV.

        :param channel: Channel to set the step voltage for
        :param step_millivolts: Voltage to step up or down by when triggered
        """
        self.check_channel(channel)
        self.check_voltage(channel, step_millivolts)
        step_volts = float(step_millivolts) / 1000.0
        command = f"VSTEP{channel}:{step_volts}"
        self._send_command(command)

    def step_voltage_up(self, channel: int) -> None:
        """
        Increse the voltage by the configured step voltage on the specified channel.

        Call "set_manual_voltage_step" to set the step voltage.

        :param channel: Channel to increase the voltage for
        """
        self.check_channel(channel)
        self._send_command(f"VUP{channel}")

    def step_voltage_down(self, channel: int) -> None:
        """
        Decrese the voltage by the configured step voltage on the specified channel.

        Call "set_manual_voltage_step" to set the step voltage.

        :param channel: Channel to decrease the voltage for
        """
        self.check_channel(channel)
        self._send_command(f"VDOWN{channel}")

    def set_manual_current_step(self, channel: int, step_milliamps: int) -> None:
        """
        Set the manual step current of the channel.

        When a IUP or IDOWN command is sent to the power supply channel, that channel
        will step up or down by step_milliamps mA.

        :param channel: Channel to set the step current for
        :param step_milliamps: Current to step up or down by when triggered
        """
        self.check_channel(channel)
        self.check_current(channel, step_milliamps)
        step_amps = float(step_milliamps) / 1000.0
        command = f"ISTEP{channel}:{step_amps}"
        self._send_command(command)

    def step_current_up(self, channel: int) -> None:
        """
        Increse the current by the configured step current on the specified channel.

        Call "set_manual_current_step" to set the step current.

        :param channel: Channel to increase the current for
        """
        self.check_channel(channel)
        self._send_command(f"IUP{channel}")

    def step_current_down(self, channel: int) -> None:
        """
        Decrese the current by the configured step current on the specified channel.

        Call "set_manual_current_step" to set the step current.

        :param channel: Channel to decrease the current for
        """
        self.check_channel(channel)
        self._send_command(f"IDOWN{channel}")


class Tenma7213330(Tenma7213320):
    #:
    MATCH_STR = ["72-13330"]
    #:
    NCHANNELS = 3
    #: This unit does actually support 10 slots (0-9) but it's not avialable from the front panel
    NCONFS = 0
    #:
    MAX_MA = 5000
    #:
    MAX_MV = 30000
    #:
    SERIAL_EOL = "\n"
