# Copyright (C) 2017 Jordi Castells
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>
# @author Jordi Castells

"""Command line tenma control program for Tenma72XXXX bank power supply."""
import argparse

from .tenma_dc_lib import (
    Tenma72Base,
    TenmaError,
    instantiate_tenma_class_from_device_response,
)


def main() -> None:  # noqa C901
    parser = argparse.ArgumentParser(
        description="Control a Tenma 72-2540 power supply connected to a serial port"
    )
    parser.add_argument("device", default="/dev/ttyUSB0")
    parser.add_argument("-v", "--voltage", help="set mV", required=False, type=int)
    parser.add_argument("-c", "--current", help="set mA", required=False, type=int)
    parser.add_argument(
        "-C",
        "--channel",
        help="channel to set (if not provided, 1 will be used)",
        required=False,
        type=int,
        default=1,
    )
    parser.add_argument(
        "-s",
        "--save",
        help="Save current configuration to Memory",
        required=False,
        type=int,
    )
    parser.add_argument(
        "-r",
        "--recall",
        help="Load configuration from Memory",
        required=False,
        type=int,
    )
    parser.add_argument(
        "-S",
        "--status",
        help="Retrieve and print system status",
        required=False,
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--ocp-enable",
        dest="ocp",
        help="Enable overcurrent protection",
        required=False,
        action="store_true",
        default=None,
    )
    parser.add_argument(
        "--ocp-disable",
        dest="ocp",
        help="Disable overcurrent pritection",
        required=False,
        action="store_false",
        default=None,
    )
    parser.add_argument(
        "--ovp-enable",
        dest="ovp",
        help="Enable overvoltage protection",
        required=False,
        action="store_true",
        default=None,
    )
    parser.add_argument(
        "--ovp-disable",
        dest="ovp",
        help="Disable overvoltage pritection",
        required=False,
        action="store_false",
        default=None,
    )
    parser.add_argument(
        "--beep-enable",
        dest="beep",
        help="Enable beeps from unit",
        required=False,
        action="store_true",
        default=None,
    )
    parser.add_argument(
        "--beep-disable",
        dest="beep",
        help="Disable beeps from unit",
        required=False,
        action="store_false",
        default=None,
    )
    parser.add_argument(
        "--on", help="Set output to on", action="store_true", default=False
    )
    parser.add_argument(
        "--off", help="Set output to off", action="store_true", default=False
    )
    parser.add_argument(
        "--verbose", help="Chatty program", action="store_true", default=False
    )
    parser.add_argument(
        "--debug", help="print serial commands", action="store_true", default=False
    )
    parser.add_argument(
        "--script",
        help="runs from script. Only print result of query, no version",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--running_current",
        help="returns the running output current",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--running_voltage",
        help="returns the running output voltage",
        action="store_true",
        default=False,
    )
    args = vars(parser.parse_args())

    t: Tenma72Base | None = None
    try:
        verbose = args["verbose"]
        t = instantiate_tenma_class_from_device_response(args["device"], args["debug"])
        if not args["script"]:
            print("VERSION: ", t.get_version())

        # On saving, we want to move to the proper memory 1st, then
        # perform the current/voltage/options setting
        # and after that, perform the save
        if args["save"]:
            if verbose:
                print("Recalling Memory", args["save"])

            t.off()  # Turn off for safety
            t.recall_conf(args["save"])

        # Now, with memory, or no memory handling, perform the changes
        if args["ocp"] is not None:
            if verbose:
                if args["ocp"]:
                    print("Enable overcurrent protection")
                else:
                    print("Disable overcurrent protection")

            t.set_ocp(args["ocp"])

        if args["ovp"] is not None:
            if verbose:
                if args["ovp"]:
                    print("Enable overvoltage protection")
                else:
                    print("Disable overvoltage protection")

            t.set_ovp(args["ovp"])

        if args["beep"] is not None:
            if verbose:
                if args["beep"]:
                    print("Enable unit beep")
                else:
                    print("Disable unit beep")

            t.set_beep(args["beep"])

        if args["voltage"]:
            if verbose:
                print("Setting voltage to ", args["voltage"])
            t.set_voltage(args["channel"], args["voltage"])

        if args["current"]:
            if verbose:
                print("Setting current to ", args["current"])
            t.set_current(args["channel"], args["current"])

        if args["save"]:
            if verbose:
                print("Saving to Memory", args["save"])

            t.save_conf_flow(args["save"], args["channel"])

        if args["recall"]:
            if verbose:
                print("Loading from Memory: ", args["recall"])

            t.recall_conf(args["recall"])
            volt = t.read_voltage(args["channel"])
            curr = t.read_current(args["channel"])

            print("Loaded from Memory: ", args["recall"])
            print("Voltage:", volt)
            print("Current:", curr)

        if args["off"]:
            if verbose:
                print("Turning OUTPUT off")
            t.off()

        if args["on"]:
            if verbose:
                print("Turning OUTPUT on")
            t.on()

        if args["status"]:
            if verbose:
                print("Retrieving status")
            print(t.get_status())

        if args["running_current"]:
            if verbose:
                print("Retrieving running Current")
            print(t.running_current(args["channel"]))

        if args["running_voltage"]:
            if verbose:
                print("Retrieving running Voltage")
            print(t.running_voltage(args["channel"]))

    except TenmaError as e:
        print("Lib ERROR: ", repr(e))
    finally:
        if verbose:
            print("Closing connection")
        if t:
            t.close()


if __name__ == "__main__":
    main()
