#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Wed Mar 22 2023 15:29:45 by codeskyblue
"""

__all__ = ["ScreenInfo", "BatteryInfo", "StorageInfo"]

from dataclasses import dataclass


@dataclass
class ScreenInfo:
    width: int
    height: int
    scale: float


@dataclass
class BatteryInfo:
    level: int
    is_charging: bool
    external_charge_capable: bool
    external_connected: bool
    fully_charged: bool
    gas_gauge_capability: bool
    has_battery: bool


@dataclass
class StorageInfo:
    disk_size: int
    used: int
    free: int