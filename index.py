#!/usr/bin/env python3

from argparse import Namespace
import asyncio
import logging
import os

from joycontrol import logging_default as log, utils
from joycontrol.memory import FlashMemory
from joycontrol.controller import Controller
from joycontrol.protocol import controller_protocol_factory
from joycontrol.server import create_hid_server
from joycontrol.controller_state import ControllerState, button_push, button_press, button_release

from inputs import get_gamepad, get_key

async def xbox(controller_state):
    # Handle controller inputs
    while True:
        events = get_gamepad()
        for event in events:
            if event.ev_type == "Key": # Buttons and bumpers
                function = (button_press if event.state == 1 else button_release)
                dictionary = {
                    "BTN_EAST": "a",  # Need to find a way to swap these easily
                    "BTN_SOUTH": "b",
                    "BTN_WEST": "x",
                    "BTN_NORTH": "y",
                    "BTN_TR": "r",
                    "BTN_TL": "l",
                    "BTN_SELECT": "minus",
                    "BTN_START": "plus",
                    "BTN_MODE": "home"
                }

                await function(controller_state, dictionary[event.code])
            if event.code in ["ABS_X", "ABS_Y", "ABS_RX", "ABS_RY"]: # Sticks
                if event.code in ["ABS_Y", "ABS_RY"]:
                    event.state = (event.state + 1) * -1
                value = (event.state + 32768) >> 4
                if event.code == "ABS_X":
                    controller_state.l_stick_state.set_h(value)
                if event.code == "ABS_Y":
                    controller_state.l_stick_state.set_v(value)
                if event.code == "ABS_RX":
                    controller_state.r_stick_state.set_h(value)
                if event.code == "ABS_RY":
                    controller_state.r_stick_state.set_v(value)
                await asyncio.sleep(0)
            if event.code in ["ABS_Z", "ABS_RZ"]: # Triggers
                value = event.state >> 9
                function = (button_press if value == 1 else button_release)
                dictionary = {
                    "ABS_Z": "zl",
                    "ABS_RZ": "zr"
                }

                await function(controller_state, dictionary[event.code])
            if event.code in ["ABS_HAT0X", "ABS_HAT0Y"]: # D-Pad
                if event.code == "ABS_HAT0X":
                    if event.state == 0:
                        await button_release(controller_state, "left", "right")
                    if event.state == 1:
                        await button_press(controller_state, "right")
                    if event.state == -1:
                        await button_press(controller_state, "left")
                if event.code == "ABS_HAT0Y":
                    if event.state == 0:
                        await button_release(controller_state, "up", "down")
                    if event.state == 1:
                        await button_press(controller_state, "down")
                    if event.state == -1:
                        await button_press(controller_state, "up")

async def main(args):
    # parse the spi flash
    if args.spi_flash:
        with open(args.spi_flash, 'rb') as spi_flash_file:
            spi_flash = FlashMemory(spi_flash_file.read())
    else:
        # Create memory containing default controller stick calibration
        spi_flash = FlashMemory()

    # Get controller name to emulate from arguments
    controller = Controller.from_arg(args.controller)

    with utils.get_output(path=args.log, default=None) as capture_file:
        # prepare the the emulated controller
        factory = controller_protocol_factory(controller, spi_flash=spi_flash)
        ctl_psm, itr_psm = 17, 19
        transport, protocol = await create_hid_server(factory, reconnect_bt_addr=args.reconnect_bt_addr,
                                                      ctl_psm=ctl_psm,
                                                      itr_psm=itr_psm, capture_file=capture_file,
                                                      device_id=args.device_id)

        controller_state = protocol.get_controller_state()

        await controller_state.connect()

        ## RUN CONTROLLER CODE HERE
        await xbox(controller_state)

        await transport.close()

if __name__ == '__main__':
    # check if root
    if not os.geteuid() == 0:
        raise PermissionError('Script must be run as root!')

    # setup logging
    #log.configure(console_level=logging.ERROR)
    log.configure()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        main(Namespace(controller='PRO_CONTROLLER', device_id=None, log=None, nfc=None, reconnect_bt_addr=None, spi_flash=None))
    )