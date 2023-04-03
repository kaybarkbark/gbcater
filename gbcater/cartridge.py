from __future__ import annotations

from attr import dataclass

import csv
import typing
import hashlib

from pathlib import Path

from .cart_hardware import CartHardware, CGBFunctionality, Mapper
from .utils import str2bool, UNKNOWN_STR


@dataclass(frozen=True)
class Cart:
    """Hold all the metadata about a cartridge"""

    CART_TITLE_ADDR = 0x134
    CART_TITLE_LEN = 16
    MFG_CODE_ADDR = 0x13F
    MFG_CODE_LEN = 4
    CGB_FLAG_ADDR = 0x143
    LIC_CODE_ADDR = 0x144
    LIC_CODE_LEN = 2
    SGB_FLAG_ADDR = 0x146
    CART_TYPE_ADDR = 0x147
    ROM_BANK_SHIFT_ADDR = 0x148
    RAM_BANK_COUNT_ADDR = 0x149
    DEST_CODE_ADDR = 0x14A
    LGC_LIC_CODE_ADDR = 0x14B
    MASK_ROM_VER_ADDR = 0x14C

    ROM_BANKSIZE = 0x4000
    RAM_BANKSIZE = 0x1000

    hardware: CartHardware
    rom_banks: int
    ram_banks: int
    ram_size: int
    title: str
    cgb_func: CGBFunctionality
    sgb_flag: bool
    region: str
    mask_rom_ver: int
    licensee: str
    old_licensee_flag: bool
    md5sum: str

    @property
    def rom_size(self) -> int:
        """ROM size is predictable and can always be calculated by how many banks exist"""
        return self.rom_banks * self.ROM_BANKSIZE

    def __str__(self):
        return (
            f"{self.title}: {self.hardware}. ROM: {self.rom_size} Bytes ({self.rom_banks} Banks). "
            f"RAM {self.ram_size} Bytes ({self.ram_banks} Banks). "
            f"Lic. By {self.licensee} {' (Old Lic. Code)' if self.old_licensee_flag else ''}"
            f"{' !Wierd!' if self.is_weird else ''}"
        )

    @property
    def is_weird(self) -> bool:
        """
        This should be set if the metadata is off or not being reported correctly. Ex: Unknown mapper, huge ROM or RAM
        sizes, unknown publisher, etc
        """
        if UNKNOWN_STR in self.hardware.mapper.value:
            return True
        if UNKNOWN_STR in self.licensee:
            return True
        if self.rom_banks > 512:
            return True
        if self.ram_banks > 16:
            return True
        return False


    @property
    def dict(self) -> dict:
        """Unstructure cart data into a dictionary for JSON storage"""
        return {
            f"{self.title}": {
                "rom_banks": f"{self.rom_banks}",
                "rom_size_bytes": f"{self.rom_size}",
                "ram_banks": f"{self.ram_banks}",
                "ram_size_bytes": f"{self.ram_size}",
                "cgb_func": f"{self.cgb_func.value}",
                "sgb_flag": f"{self.sgb_flag}",
                "region": self.region,
                "mask_rom_ver": f"{self.mask_rom_ver}",
                "licensee": self.licensee,
                "old_lic_flag": self.old_licensee_flag,
                "md5sum": self.md5sum,
                "hardware": self.hardware.dict,
                "weird": f"{self.is_weird}",
            }
        }

    @classmethod
    def from_dict(cls, ins: dict) -> Cart:
        """Structure data from a dict into a Cartridge"""
        title = ins.keys()[0]
        return Cart(
            title=title,
            rom_banks=int(ins[title]["rom_banks"]),
            ram_banks=int(ins[title]["ram_banks"]),
            ram_size=int(ins[title]["ram_size_bytes"]),
            cgb_func=CGBFunctionality(ins[title]["cgb_func"]),
            sgb_flag=str2bool(ins[title]["sgb_flag"]),
            region=ins[title]["region"],
            mask_rom_ver=int(ins[title]["mask_rom_ver"]),
            licensee=ins[title]["licensee"],
            md5sum=ins[title]["md5sum"],
            old_licensee_flag=str2bool(ins[title]["old_lic_flag"]),
            hardware=CartHardware.from_dict(ins[title]["hardware"])
        )

    @classmethod
    def from_bytes(cls, cart_data: bytes) -> Cart:
        """Generate cartridge from raw bytes from ROM"""
        hardware = CartHardware.from_cart(cart_data[cls.CART_TYPE_ADDR])
        ramsize, rambanks = cls.calculate_ram_size(
            data=cart_data, mapper=hardware.mapper
        )
        if cart_data[cls.CGB_FLAG_ADDR] == 0x80:
            cgb_func = CGBFunctionality.CGBExtra
        elif cart_data[cls.CGB_FLAG_ADDR] == 0xC0:
            cgb_func = CGBFunctionality.CGBOnly
        else:
            cgb_func = CGBFunctionality.CGBNone
        licensee, old_licensee_flag = cls.get_licensee_code(data=cart_data)
        return Cart(
            hardware=hardware,
            rom_banks=2 << cart_data[cls.ROM_BANK_SHIFT_ADDR],
            ram_size=ramsize,
            ram_banks=rambanks,
            title=cls.get_title(data=cart_data),
            cgb_func=cgb_func,
            sgb_flag=cart_data[cls.SGB_FLAG_ADDR] == 0x3,
            region="Japan"
            if not cart_data[cls.DEST_CODE_ADDR]
            else f"Non-Japan ({hex(cart_data[cls.DEST_CODE_ADDR])})",
            mask_rom_ver=cart_data[cls.MASK_ROM_VER_ADDR],
            licensee=licensee,
            old_licensee_flag=old_licensee_flag,
            md5sum=hashlib.md5(cart_data).hexdigest()
        )

    @classmethod
    def get_licensee_code(cls, data: bytes) -> typing.Tuple[str, bool]:
        """Get the licensee code, and a flag for if this cart uses the old licensee code"""
        raw_lgcy_lic_code = data[cls.LGC_LIC_CODE_ADDR]
        lgcy_lic_code = cls.OLD_LICENSEE_CODE.get(raw_lgcy_lic_code)
        if lgcy_lic_code is None:
            return f"{UNKNOWN_STR}({hex(raw_lgcy_lic_code)})", True
        elif raw_lgcy_lic_code == 0x33:
            raw_lic_code = data[
                cls.LIC_CODE_ADDR : cls.LIC_CODE_ADDR + cls.LIC_CODE_LEN
            ]
            cleaned_lic_code = cls.strip_nonprintable_bytes(raw_lic_code)
            lic_code = cls.LICENSEE_CODE.get(cleaned_lic_code)
            if lic_code is None:
                return f"{UNKNOWN_STR}({raw_lic_code},{cleaned_lic_code})", False
            return lic_code, False
        return lgcy_lic_code, True

    @classmethod
    def get_title(cls, data: bytes) -> str:
        """Pull the title out of the cart data, try to make it as printable as possible"""
        return cls.strip_nonprintable_bytes(data[0x134 : 0x134 + cls.CART_TITLE_LEN])

    @staticmethod
    def strip_nonprintable_bytes(data: bytes) -> str:
        """Strip everything that is not printable ascii"""
        ret = ""
        for datum in data:
            if ord(" ") <= datum <= ord("~"):
                ret += chr(datum)
        return ret

    @classmethod
    def from_rom_file(cls, file: Path) -> Cart:
        """Generate a cartridge from a ROM file"""
        return cls.from_bytes(file.read_bytes())

    @classmethod
    def calculate_ram_size(cls, data: bytes, mapper: Mapper) -> typing.Tuple[int, int]:
        """Calculate the RAM size of a cart. This is kind of random, so it needs to be a LUT"""
        ram_size = data[cls.RAM_BANK_COUNT_ADDR]
        # Handle MBC2 w/ battery backed RAM. Only 256 bytes, split among 512 4 bit memory locations
        if mapper == Mapper.MBC2:
            return 256, 1
        if ram_size == 2:
            return 2048, 1
        if ram_size == 3:
            return cls.RAM_BANKSIZE * 4, 4
        if ram_size == 4:
            return cls.RAM_BANKSIZE * 16, 16
        if ram_size == 5:
            return cls.RAM_BANKSIZE * 8, 8
        return 0, 0

    OLD_LICENSEE_CODE = {
        0x00: "None",
        0x01: "Nintendo",
        0x08: "Capcom",
        0x09: "Hot-B",
        0x0A: "Jaleco",
        0x0B: "Coconuts",
        0x0C: "Elite Systems",
        0x13: "Electronic Arts",
        0x18: "Hudsonsoft",
        0x19: "ITC Entertainment",
        0x1A: "Yanoman",
        0x1D: "Clary",
        0x1F: "Virgin",
        0x20: "KSS",
        0x24: "PCM Complete",
        0x25: "San-X ",
        0x28: "Kotobuki Systems ",
        0x29: "Seta",
        0x30: "Infogrames",
        0x31: "Nintendo",
        0x32: "Bandai",
        0x33: "USES NEW LIC CODE (GBC)",
        0x34: "Konami",
        0x35: "Hector",
        0x38: "Capcom",
        0x39: "Banpresto",
        0x3C: "*Entertainment i",
        0x3E: "Gremlin",
        0x41: "Ubisoft",
        0x42: "Atlus",
        0x44: "Malibu",
        0x46: "Angel",
        0x47: "Spectrum Holobyte",
        0x49: "IREM",
        0x4A: "Virgin",
        0x4D: "mMalibu",
        0x4F: "U.S Gold",
        0x50: "Absolute",
        0x51: "Acclaim",
        0x52: "Activision",
        0x53: "American Sammy",
        0x54: "Gametek",
        0x55: "Park Plac",
        0x56: "LJN",
        0x57: "Matchbox",
        0x59: "Milton Bradley",
        0x5A: "Mindscape",
        0x5B: "Romstar",
        0x5C: "Naxat Soft",
        0x5D: "Tradewest",
        0x60: "Titus",
        0x6b: "Laser Beam Entertainment",
        0x61: "Virgin",
        0x67: "Ocean",
        0x69: "Electronic Arts",
        0x6E: "Elite Systems",
        0x6F: "Electro Brain",
        0x70: "Infogrammes",
        0x71: "Interplay",
        0x72: "Broderbund",
        0x73: "Sculptered Soft",
        0x75: "The Sales Curve",
        0x78: "THQ",
        0x79: "Accolade",
        0x7A: "Triffix Entertainment",
        0x7C: "Microprose",
        0x7F: "Kemco",
        0x80: "Misawa Entertainment",
        0x83: "LOZC",
        0x86: "Tokuma sShoten Intermedia",
        0x8B: "Bullet-Proof Aoftware",
        0x8C: "Vic Tokai",
        0x8E: "APE",
        0x8F: "I'MAX",
        0x91: "Chun Soft",
        0x92: "Video System",
        0x93: "Tsuburava",
        0x95: "Varie",
        0x96: "Yonezawas Pal",
        0x97: "Kaneko",
        0x99: "Arc",
        0x9A: "Nihon Bussan",
        0x9B: "Tecmo",
        0x9C: "Imagineer",
        0x9D: "Banpresto",
        0x9F: "Nova",
        0xA1: "Hori Electric",
        0xA2: "Bandai",
        0xA4: "Konami",
        0xA6: "Kawada",
        0xA7: "Takara",
        0xA9: "Technos Japan",
        0xAA: "Broderbund",
        0xAC: "Toei Animation",
        0xAD: "Toho",
        0xAF: "Namco",
        0xB0: "Acclaim",
        0xB1: "ascii or nexoft",
        0xB2: "Bandai",
        0xB4: "Enix",
        0xB6: "HAL",
        0xB7: "SNK",
        0xB9: "Pony Canyon",
        0xBA: "Culture Brain",
        0xBB: "Sunsoft",
        0xBD: "Sony Imagesoft",
        0xBF: "Sammy",
        0xC0: "Taito",
        0xC2: "Kemco",
        0xC3: "Squaresoft",
        0xC4: "Tokuma Shoten Intermedia",
        0xC5: "Data East",
        0xC6: "Tonkin house",
        0xC8: "Koei",
        0xC9: "UFL",
        0xCA: "Ultra",
        0xCB: "Vap",
        0xCC: "Use",
        0xCD: "Meldac",
        0xCE: "Pony Canyon",
        0xCF: "Angel",
        0xD0: "Taito",
        0xD1: "Sofel",
        0xD2: "Quest",
        0xD3: "Sigma Enterprises",
        0xD4: "Ask Kodansha",
        0xD6: "Naxat Aoft",
        0xD7: "Copya Aystems",
        0xD9: "Banpresto",
        0xDA: "Tomy",
        0xDB: "LJN",
        0xDD: "NCS",
        0xDE: "Human",
        0xDF: "Altron",
        0xE0: "Jaleco",
        0xE1: "Towachiki",
        0xE2: "Uutaka",
        0xE3: "Barie",
        0xE5: "Epoch",
        0xE7: "Athena",
        0xE8: "Asmik",
        0xE9: "Natsume",
        0xEA: "King Records",
        0xEB: "Atlus",
        0xEC: "Epic/Sony records",
        0xEE: "IGS",
        0xF0: "a wave",
        0xF3: "Extreme Entertainment",
        0xFF: "LJN",
    }
    """Dict of all the legacy licensee codes. This licensee field type was only used pre-GBC"""

    LICENSEE_CODE = {
        "00": "none",
        "01": "Nintendo R&D1",
        "08": "Capcom",
        "13": "Electronic Arts",
        "18": "Hudson Soft",
        "19": "B-AI",
        "20": "KSS",
        "22": "POW",
        "24": "PCM Complete",
        "25": "San-X",
        "28": "Kemco Japan",
        "29": "Seta",
        "30": "Viacom",
        "31": "Nintendo",
        "32": "Bandai",
        "33": "Ocean/Acclaim",
        "34": "Konami",
        "35": "Hector",
        "37": "Taito",
        "38": "Hudson",
        "39": "Banpresto",
        "41": "UbiSoft",
        "42": "Atlus",
        "44": "Malibu",
        "46": "Angel",
        "47": "Bullet-Proof",
        "49": "IREM",
        "4D": "Nintendo",
        "50": "Absolute",
        "51": "Acclaim",
        "52": "Activision",
        "53": "American Sammy",
        "54": "Konami",
        "55": "Hi Tech Entertainment",
        "56": "LJN",
        "57": "Matchbox",
        "58": "Mattel",
        "59": "Milton Bradley",
        "5A": "Mindscape",
        "5G": "Majesco",
        "5K": "Hasbro Interactive",
        "5Q": "Lego",
        "60": "Titus",
        "61": "Virgin",
        "64": "LucasArts",
        "67": "Ocean",
        "69": "Electronic Arts",
        "6L": "Bay Area Multimedia (BAM) Entertainment",
        "70": "Infogrames",
        "71": "Interplay",
        "72": "Broderbund",
        "73": "Sculptured",
        "75": "SCI",
        "78": "THQ",
        "79": "Accolade",
        "7F": "Kemco",
        "80": "Misawa",
        "83": "LOZC",
        "86": "Tokuma Shoten",
        "87": "Tsukuda Ori",
        "91": "Chunsoft",
        "92": "Video System",
        "93": "Ocean/Acclaim",
        "95": "Varie",
        "96": "Yonezawas Pal",
        "97": "Kaneko",
        "99": "Pack In Soft",
        "BB": "Sunsoft",
        "A4": "Konami",
        "E9": "Victor Interactive Software"
    }
    """GBC licensee and later GB licensee codes. Many are unpopulated, please populate if you know them!"""


def folder_to_csv(folder: Path, output: Path):
    """
    Take a folder full of ROMs and catalogue them all. Useful for downloading packs from archive.org for data mining
    """
    with open(output, "w") as csvfile:
        csvwriter = csv.writer(csvfile, delimiter=",")
        csvwriter.writerow(
            [
                "Filename",
                "Title",
                "Cart Type",
                "Mapper Type",
                "ROM Banks",
                "RAM Banks",
                "RAM Size",
                "ROM Size",
                "Battery",
                "Timer",
                "Rumble",
                "Sensor",
                "Licensee",
                "Old Licensee Code",
                "CGB Functionality",
                "SGB Functionality",
                "Mask ROM Ver",
                "Region",
                "MD5 Hash",
                "Weird/Bad/Missing Data",
            ]
        )
        print(f"Discovered {len(list(folder.glob('**/*')))} files")
        for file in folder.glob("**/*"):
            if (
                file.suffix == ".gb" or file.suffix == ".bin" or file.suffix == ".gbc"
            ) and file.is_file:
                cart = Cart.from_rom_file(file=file)
                print(f"Cataloguing {cart}...")
                csvwriter.writerow(
                    [
                        file.name.strip(","),
                        cart.title.strip(","),
                        str(cart.hardware),
                        cart.hardware.mapper.value,
                        str(cart.rom_banks),
                        str(cart.ram_banks),
                        hex(cart.ram_size),
                        hex(cart.rom_size),
                        str(cart.hardware.battery),
                        str(cart.hardware.timer),
                        str(cart.hardware.rumble),
                        str(cart.hardware.sensor),
                        cart.licensee,
                        cart.old_licensee_flag,
                        cart.cgb_func.value,
                        str(cart.sgb_flag),
                        cart.mask_rom_ver,
                        cart.region,
                        cart.md5sum,
                        str(cart.is_weird)
                    ]
                )