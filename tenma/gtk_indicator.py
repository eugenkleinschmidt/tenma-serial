#!/usr/bin/python
"""
gtk_indicator is a small gtk graphical tool to control a Tenma DC power
supply from a desktop environment.
Copyright (C) 2017 Jordi Castells.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>
"""

import glob
import signal
import sys

import gi
import pkg_resources
import serial

gi.require_version("Gtk", "3.0")
gi.require_version("AppIndicator3", "0.1")
gi.require_version("Notify", "0.7")

from gi.repository import AppIndicator3 as appindicator  # noqa E402
from gi.repository import Gtk as gtk  # noqa E402
from gi.repository import Notify as notify  # noqa E402

from .tenma_dc_lib import (  # noqa E402
    Tenma72Base,
    instantiate_tenma_class_from_device_response,
)

APPINDICATOR_ID = "Tenma DC Power"


def serial_ports() -> list[str]:
    """
    Lists serial port names
    Shamesly ripped from stackOverflow.

    :raises EnvironmentError:
        On unsupported or unknown platforms
    :returns:
        A list of the serial ports available on the system
    """
    if sys.platform.startswith("win"):
        ports = ["COM%s" % (i + 1) for i in range(256)]
    elif sys.platform.startswith("linux") or sys.platform.startswith("cygwin"):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob("/dev/tty[A-Za-z]*")
    elif sys.platform.startswith("darwin"):
        ports = glob.glob("/dev/tty.*")
    else:
        raise OSError("Unsupported platform")

    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result


class GtkController:
    def __init__(self) -> None:
        self.serial_port = "No Port"
        self.serialMenu: gtk.Menu | None = None
        self.memoryMenu: gtk.Menu | None = None

        self.T: Tenma72Base | None = None
        self.itemSet: list[gtk.MenuItem] = []
        pass

    def port_selected(self, source: gtk.MenuItem) -> None:
        old_port = self.serial_port
        self.serial_port = source.get_label()

        try:
            if not self.T:
                self.T = instantiate_tenma_class_from_device_response(self.serial_port)
            else:
                self.T.set_port(self.serial_port)
        except Exception as e:
            self.set_item_set_status(False)
            notify.Notification.new(
                "<b>ERROR</b>", repr(e), gtk.STOCK_DIALOG_ERROR
            ).show()
            self.serial_port = old_port
            return

        ver = self.T.get_version()
        if not ver:
            notify.Notification.new(
                "<b>ERROR</b>",
                "No response on %s" % self.serial_port,
                gtk.STOCK_DIALOG_ERROR,
            ).show()
            self.serial_port = old_port
            self.set_item_set_status(False)
            return
        else:
            notify.Notification.new("<b>CONNECTED TO</b>", ver, None).show()
            self.set_item_set_status(True)

        self.item_connectedPort.set_label(self.serial_port)
        self.item_unit_version.set_label(ver[:20])
        self.memoryMenu = self.build_memory_submenu(None, self.T.NCONFS)

    def memory_selected(self, source):
        """Select one of the multiple memories."""
        if self.T:
            try:
                memory_index = source.get_label()
                self.T.off()
                self.T.recall_conf(int(memory_index))
            except Exception as e:
                notify.Notification.new(
                    "<b>ERROR</b>", repr(e), gtk.STOCK_DIALOG_ERROR
                ).show()

    def build_memory_submenu(self, source, nmemories: int):
        """
        Build a submenu containing a list of INTS
        with the available memories for the unit.
        """
        if not self.memoryMenu:
            self.memoryMenu = gtk.Menu()

        for entry in self.memoryMenu.get_children():
            self.memoryMenu.remove(entry)

        for m_index in range(1, nmemories + 1):
            menu_entry = gtk.MenuItem(m_index)
            menu_entry.connect("activate", self.memory_selected)
            self.memoryMenu.append(menu_entry)
            menu_entry.show()

        return self.memoryMenu

    def build_serial_submenu(self, source):
        """
        Build the serialSubmenu assuming that it is un runtime (remove,
        existing entries and call show in all new entries).
        """
        if not self.serialMenu:
            self.serialMenu = gtk.Menu()

        for entry in self.serialMenu.get_children():
            self.serialMenu.remove(entry)

        for serial_port in serial_ports():
            menu_entry = gtk.MenuItem(serial_port)
            menu_entry.connect("activate", self.port_selected)
            self.serialMenu.append(menu_entry)
            menu_entry.show()

        sep = gtk.SeparatorMenuItem()
        self.serialMenu.append(sep)
        sep.show()

        menu_entry = gtk.MenuItem("Reload")
        menu_entry.connect("activate", self.build_serial_submenu)
        self.serialMenu.append(menu_entry)
        menu_entry.show()

        return self.serialMenu

    def set_item_set_status(self, on_off: bool) -> None:
        if on_off:
            [i.set_sensitive(True) for i in self.itemSet]
        else:
            [i.set_sensitive(False) for i in self.itemSet]

    def build_gtk_menu(self) -> gtk.Menu:
        serial_menu = self.build_serial_submenu(None)
        memory_menu = self.build_memory_submenu(None, 0)

        menu = gtk.Menu()

        self.item_connectedPort = gtk.MenuItem(self.serial_port)
        self.item_connectedPort.set_right_justified(True)
        self.item_connectedPort.set_sensitive(False)

        self.item_unit_version = gtk.MenuItem("unknown version")
        self.item_unit_version.set_right_justified(True)
        self.item_unit_version.set_sensitive(False)

        item_quit = gtk.MenuItem("Quit")
        item_quit.connect("activate", self.quit)

        item_serial_menu = gtk.MenuItem("Serial")
        item_serial_menu.set_submenu(serial_menu)

        item_memory_menu = gtk.MenuItem("Memory")
        item_memory_menu.set_submenu(memory_menu)

        item_on = gtk.MenuItem("on")
        item_on.connect("activate", self.tenma_turn_on)

        item_off = gtk.MenuItem("off")
        item_off.connect("activate", self.tenma_turn_off)

        item_reset = gtk.MenuItem("RESET")
        item_reset.connect("activate", self.tenma_reset)

        menu.append(self.item_connectedPort)
        menu.append(self.item_unit_version)
        menu.append(item_serial_menu)

        sep = gtk.SeparatorMenuItem()
        menu.append(sep)

        menu.append(item_memory_menu)

        sep = gtk.SeparatorMenuItem()
        menu.append(sep)

        menu.append(item_on)
        menu.append(item_off)
        menu.append(item_reset)

        sep = gtk.SeparatorMenuItem()
        menu.append(sep)

        menu.append(item_quit)

        menu.show_all()

        self.itemSet.extend([item_on, item_off, item_reset, item_memory_menu])
        self.set_item_set_status(False)

        return menu

    def quit(self) -> None:  # noqa A003
        gtk.main_quit(self)

    def tenma_turn_on(self) -> None:
        if self.T:
            try:
                self.T.on()
            except Exception as e:
                notify.Notification.new(
                    "<b>ERROR</b>", repr(e), gtk.STOCK_DIALOG_ERROR
                ).show()

    def tenma_turn_off(self) -> None:
        if self.T:
            try:
                self.T.off()
            except Exception as e:
                notify.Notification.new(
                    "<b>ERROR</b>", repr(e), gtk.STOCK_DIALOG_ERROR
                ).show()

    def tenma_reset(self) -> None:
        if self.T:
            try:
                self.T.off()
                self.T.on()
            except Exception as e:
                notify.Notification.new(
                    "<b>ERROR</b>", repr(e), gtk.STOCK_DIALOG_ERROR
                ).show()


def main() -> None:
    notify.init(APPINDICATOR_ID)
    controller = GtkController()
    indicator = appindicator.Indicator.new(
        APPINDICATOR_ID,
        pkg_resources.resource_filename(__name__, "logo.png"),
        appindicator.IndicatorCategory.SYSTEM_SERVICES,
    )
    indicator.set_status(appindicator.IndicatorStatus.ACTIVE)
    indicator.set_menu(controller.build_gtk_menu())
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    gtk.main()


if __name__ == "__main__":
    main()
