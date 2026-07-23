#!/usr/bin/env python3
"""Raspberry Pi internet connectivity watchdog.

Periodically pings a configured host and reflects reachability via two
LEDs (green = reachable, red = unreachable). Intended to run as a
long-lived systemd service so the GPIO output lines stay held open
between checks.
"""

import argparse
import configparser
import logging
import logging.handlers
import os
import signal
import subprocess
import sys
import threading

from gpiozero import LED

DEFAULT_CONFIG_PATH = "/etc/raspberry-watchdog/config.ini"

stop_event = threading.Event()


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"path to config.ini (default: {DEFAULT_CONFIG_PATH})",
    )
    return parser.parse_args()


def load_config(path):
    if not os.path.isfile(path):
        sys.exit(f"config file not found: {path}")

    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")

    try:
        return {
            "host": parser.get("network", "host"),
            "ping_count": parser.getint("network", "ping_count", fallback=3),
            "ping_timeout": parser.getint("network", "ping_timeout", fallback=2),
            "check_interval": parser.getint("network", "check_interval", fallback=60),
            "led_green_pin": parser.getint("gpio", "led_green_pin"),
            "led_red_pin": parser.getint("gpio", "led_red_pin"),
            "log_file": parser.get("logging", "log_file"),
            "log_level": parser.get("logging", "log_level", fallback="INFO"),
        }
    except (configparser.NoSectionError, configparser.NoOptionError) as exc:
        sys.exit(f"invalid config file: {exc}")


def setup_logging(log_file, log_level):
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    handler = logging.handlers.WatchedFileHandler(log_file)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    logger = logging.getLogger("watchdog")
    logger.setLevel(log_level.upper())
    logger.addHandler(handler)
    return logger


def check_connectivity(host, count, timeout):
    try:
        result = subprocess.run(
            ["ping", "-c", str(count), "-W", str(timeout), host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=count * timeout + 5,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False


def request_stop(signum, frame):
    stop_event.set()


def main():
    args = parse_args()
    config = load_config(args.config)
    logger = setup_logging(config["log_file"], config["log_level"])

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    green = LED(config["led_green_pin"])
    red = LED(config["led_red_pin"])

    logger.info(
        "watchdog started: host=%s interval=%ss green_pin=%s red_pin=%s",
        config["host"],
        config["check_interval"],
        config["led_green_pin"],
        config["led_red_pin"],
    )

    previous_reachable = None
    try:
        while not stop_event.is_set():
            reachable = check_connectivity(
                config["host"], config["ping_count"], config["ping_timeout"]
            )

            if reachable:
                green.on()
                red.off()
            else:
                green.off()
                red.on()

            if reachable != previous_reachable:
                if reachable:
                    logger.warning("connectivity restored: host=%s", config["host"])
                else:
                    logger.warning("connectivity lost: host=%s", config["host"])
                previous_reachable = reachable
            else:
                logger.info(
                    "check result: host=%s reachable=%s", config["host"], reachable
                )

            stop_event.wait(config["check_interval"])
    finally:
        logger.info("watchdog stopping")
        green.close()
        red.close()


if __name__ == "__main__":
    main()
