from __future__ import annotations

from attr import dataclass
from enum import Enum
from .utils import UNKNOWN_STR, str2bool

class CGBFunctionality(Enum):
    """Some cartridges have special functionality in the Game Boy Color, or are Game Boy Color only"""
    CGBExtra = "Extra CGB Functions"
    CGBOnly = "CGB Only"
    CGBNone = "None"


class Mapper(Enum):
    Unknown = UNKNOWN_STR
    ROM_ONLY = "ROM ONLY"
    ROM_RAM = "ROM+RAM"
    MBC1 = "MBC1"
    MBC2 = "MBC2"
    MBC3 = "MBC3"
    MBC4 = "MBC4"
    MBC5 = "MBC5"
    MBC6 = "MBC6"
    MBC7 = "MBC7"
    MMM01 = "MMM01"
    HuC1 = "HuC1"
    HuC3 = "HuC3"
    TAMA5 = "TAMA5"
    GOWIN = "GOWIN"
    GBCAMERA = "Game Boy Camera"


@dataclass(frozen=True)
class CartHardware:
    """All the different hardware capabilities that can exist inside of a cartridge"""
    mapper: Mapper
    timer: bool = False
    ram: bool = False
    rumble: bool = False
    sensor: bool = False
    battery: bool = False

    @property
    def dict(self) -> dict:
        """Unstructure hardware data into a dict for JSON storage"""
        return {
            "mapper": self.mapper.value,
            "timer": f"{self.timer}",
            "ram": f"{self.ram}",
            "rumble": f"{self.rumble}",
            "sensor": f"{self.sensor}",
            "battery": f"{self.battery}",
        }

    @classmethod
    def from_dict(cls, ins: dict) -> CartHardware:
        """Structure hardware data from a dictionary"""
        return CartHardware(
            timer=str2bool(ins["timer"]),
            ram=str2bool(ins["ram"]),
            rumble=str2bool(ins["rumble"]),
            sensor=str2bool(ins["sensor"]),
            battery=str2bool(ins["battery"]),
            mapper=Mapper(ins["mapper"])
        )

    @classmethod
    def from_cart(cls, data: int) -> CartHardware:
        """Take the cart type byte and translate it into a cart type and mapper"""
        if data == 0:
            return CartHardware(
                mapper=Mapper.ROM_ONLY,
            )
        if data == 1:
            return CartHardware(
                mapper=Mapper.MBC1,
            )
        if data == 2:
            return CartHardware(mapper=Mapper.MBC1, ram=True)
        if data == 3:
            return CartHardware(mapper=Mapper.MBC1, ram=True, battery=True)
        if data == 5:
            return CartHardware(
                mapper=Mapper.MBC2,
            )
        if data == 6:
            return CartHardware(mapper=Mapper.MBC2, battery=True)
        if data == 8:
            return CartHardware(mapper=Mapper.ROM_RAM, ram=True)
        if data == 9:
            return CartHardware(
                mapper=Mapper.ROM_ONLY,
            )
        if data == 11:
            return CartHardware(
                mapper=Mapper.MMM01,
            )
        if data == 12:
            return CartHardware(mapper=Mapper.MMM01, ram=True)
        if data == 13:
            return CartHardware(mapper=Mapper.MMM01, ram=True, battery=True)
        if data == 15:
            return CartHardware(mapper=Mapper.MBC3, battery=True, timer=True)
        if data == 16:
            return CartHardware(mapper=Mapper.MBC3, battery=True, timer=True, ram=True)
        if data == 17:
            return CartHardware(
                mapper=Mapper.MBC3,
            )
        if data == 18:
            return CartHardware(mapper=Mapper.MBC3, ram=True)
        if data == 19:
            return CartHardware(mapper=Mapper.MBC3, ram=True, battery=True)
        if data == 21:
            return CartHardware(
                mapper=Mapper.MBC4,
            )
        if data == 22:
            return CartHardware(mapper=Mapper.MBC4, ram=True)
        if data == 23:
            return CartHardware(mapper=Mapper.MBC4, ram=True, battery=True)
        if data == 25:
            return CartHardware(
                mapper=Mapper.MBC5,
            )
        if data == 26:
            return CartHardware(mapper=Mapper.MBC5, ram=True)
        if data == 27:
            return CartHardware(mapper=Mapper.MBC5, ram=True, battery=True)
        if data == 28:
            return CartHardware(
                mapper=Mapper.MBC5,
                rumble=True,
            )
        if data == 29:
            return CartHardware(mapper=Mapper.MBC5, rumble=True, ram=True)
        if data == 30:
            return CartHardware(mapper=Mapper.MBC5, rumble=True, ram=True, battery=True)
        if data == 0x20:
            return CartHardware(
                mapper=Mapper.MBC6,
            )
        if data == 0x22:
            return CartHardware(
                mapper=Mapper.MBC7, rumble=True, sensor=True, ram=True, battery=True
            )
        if data == 252:
            return CartHardware(
                mapper=Mapper.GBCAMERA,
            )
        if data == 0xFD:
            return CartHardware(
                mapper=Mapper.TAMA5,
            )
        if data == 0xFE:
            return CartHardware(
                mapper=Mapper.HuC3,
            )
        if data == 0xFF:
            return CartHardware(mapper=Mapper.HuC1, ram=True, battery=True)
        return CartHardware(mapper=Mapper.Unknown)

    def __str__(self):
        return (
            f"{self.mapper.value}{'+RAM' if self.ram else ''}{'+Timer' if self.timer else ''}"
            f"{'+Rumble' if self.rumble else ''}{'+Battery' if self.battery else ''}"
            f"{'+Sensor' if self.sensor else ''}"
        )

