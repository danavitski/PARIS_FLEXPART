#!/usr/bin/env python

from dataclasses import dataclass
from typing import List
from loguru import logger
from pandas import Timestamp
from typing import Union


@dataclass
class Namelist:
    def __setattr__(self, key, value):
        super().__setattr__(key, value)
        # General case: regular setattr
        if key not in self.fields:
            return

        # If we're dealing with a field:
        # If it's the default value, don't change it
        default = self.__dataclass_fields__[key].default
        if value != default:
            vartype = self.__annotations__[key]
            try:
                super().__setattr__(key, vartype(value))
            except TypeError as e:
                logger.critical(f'Cannot convert value "{value}" for key "{key}" to type {self.__annotations__[key]}')
                raise e

    @property
    def fields(self) -> List[str]:
        return list(self.__annotations__.keys())

    def update(self, fields: dict) -> None:
        for k, v in fields.items():
            if k.upper() in self.fields:
                setattr(self, k.upper(), v)

    def write(self, filename: str, name: str = None, mode: str = 'w', prefix : str = '') -> str:
        """
        Write fields to a namelist file.
        :param filename: path to the namelist file
        :param name: name of the namelist
        :param mode: 'w' or 'a' (create a new file or append it)
        :param prefix: prefix common to all keys (e.g. "P" in the "Species" dataframe)
        :return:
        """
        with open(filename, mode) as fid:
            fid.write(f'&{name}\n')
            for key in self.fields:
                if isinstance(self[key], str):
                    # Wrap strings in quotes
                    value = f'"{self[key]}"'
                elif hasattr(self[key], '__iter__'):
                    # if value is an iterable, then write it as a comma-separated list
                    value = ", ".join([str(_) for _ in self[key]])
                else:
                    # otherwise, just write the key
                    value = self[key]
                fid.write(f' {prefix}{key} = {value}\n')
            fid.write(' /\n\n')
        return filename

    def __setitem__(self, key: str, value):
        if key.upper() in self.fields:
            self.__setattr__(key.upper(), value)
        else:
            raise KeyError(f"Attribute {key} not defined in {self}")

    def __getitem__(self, item: str):
        if item in self.fields:
            return getattr(self, item)
        else:
            raise KeyError(f"Attribute {item} not defined in {self}")

    @classmethod
    def read(cls, filename: str, name: str = '') -> "Namelist":
        data = cls()
        with open(filename, 'r') as fid:
            begin = False
            end = False
            for line in fid:
                line = line.strip().strip(',')
                # Check for the end of the namelist
                end = end or line.startswith('/')

                # If we are afte the start and before the end, read the fields
                if begin and not end:
                    key, val = line.split('=')
                    key = key.strip()
                    if key.upper() in data.fields:
                        data[key] = val.strip().strip('"').strip("'")

                # Check for the start of the namelist
                begin = begin or line.startswith(f'&{name}')

        return data


class FloatList(list):
    def __init__(self, arg):
        super().__init__([float(_) for _ in arg])


class IntList(list):
    def __init__(self, arg):
        super().__init__([int(_) for _ in arg])


class FTime:
    def __init__(self, arg: Union[str, int, Timestamp]):
        if isinstance(arg, str):
            arg = '20000101' + arg  # Add a dummy date, we only want the time anyway
        self.value = Timestamp(arg)

    def __repr__(self):
        return self.value.strftime('%H%M%S')


class FDate:
    def __init__(self, arg: Union[str, int, Timestamp]):
        self.value = Timestamp(arg)

    def __repr__(self):
        return self.value.strftime('%Y%m%d')


@dataclass
class Command(Namelist):
    LDIRECT: int = -1
    IBDATE: FDate = None
    IBTIME: FTime = None
    IEDATE: FDate = None
    IETIME: FTime = None
    LOUTSTEP: int = None
    LOUTAVER: int = None
    LOUTSAMPLE: int = None
    ITSPLIT: int = 99999999
    LSYNCTIME: int = None
    CTL: float = None
    IFINE: int = None
    IOUT: int = 9
    IPOUT: int = 0
    LSUBGRID: int = 1
    LCONVECTION: int = 1
    LAGESPECTRA: int = 0
    IPIN: int = 0
    IOUTPUTFOREACHRELEASE: int = 1
    IFLUX: int = 0
    MDOMAINFILL: int = 0
    IND_SOURCE: int = 1
    IND_RECEPTOR: int = 1
    MQUASILAG: int = 0
    NESTED_OUTPUT: int = 0
    LINIT_COND: int = 0
    SURF_ONLY: int = 0
    CBLFLAG: int = 0
    OHFIELDS_PATH: str = ''


@dataclass
class Outgrid(Namelist):
    OUTLON0: float
    OUTLAT0: float
    #    OUTLON1 : float
    #    OUTLAT1 : float
    NUMXGRID: int
    NUMYGRID: int
    DXOUT: float
    DYOUT: float
    OUTHEIGHTS: FloatList


@dataclass
class Release(Namelist):
    IDATE1: FDate
    ITIME1: FTime
    LAT1: float
    LON1: float
    Z1: float
    ZKIND: int
    MASS: float
    PARTS: int
    COMMENT: str
    IDATE2: FDate = None
    ITIME2: FTime = None
    LAT2: float = None
    LON2: float = None
    Z2: float = None

    def __post_init__(self):
        if self.IDATE2 is None:
            self.IDATE2 = self.IDATE1.value
        if self.ITIME2 is None:
            self.ITIME2 = self.ITIME1.value
        if self.LAT2 is None:
            self.LAT2 = self.LAT1
        if self.LON2 is None:
            self.LON2 = self.LON1
        if self.Z2 is None:
            self.Z2 = self.Z1


@dataclass
class ReleasesHeader(Namelist):
    NSPEC: int
    SPECNUM_REL: IntList


class FormattedString:
    """
    Generic class to enforce a specific string format when printing the variable.
    When provided as type in a Namelist dataclass, this ensures that the variable will
    be printed using that file format when writing the namelist file.
    Usage:
        the following:
        ```
            f = FormattedString(format)
            s = print(f(value))
        ```
        if equivalent to `s = f'{value:format}'.

        In a `Namelist` object use as:
        ```
        @dataclass
        class File(Namelist):
            var : FormattedString(format) [ = defaultValue]
        ```
    """
    def __init__(self, fmt, value=None):
        self.fmt = fmt
        self.value = value

    def __call__(self, value):
        return FormattedString(self.fmt, value)

    def __repr__(self):
        if self.value is not None :
            fmt = '{:' + self.fmt + '}'
            return fmt.format(self.value)
        else :
            return ''

@dataclass
class Species(Namelist):
    species: str = ""
    decay: FormattedString('18.1f') = -999.9
    weta_gas: FormattedString('18.1e') = -9.9e-9
    wetb_gas: FormattedString('18.2f') = 0.0
    crain_aero: FormattedString('18.1e') = -9.9e-9
    csnow_aero: FormattedString('18.2f') = -9.9e-9
    ccn_aero: FormattedString('18.1e') = -9.9e-9
    in_aero: FormattedString('18.2f') = -9.9e-9
    reldiff: FormattedString('18.1f') = -9.9
    henry: FormattedString('18.1e') = 0.0
    f0: FormattedString('18.1f') = 0.0
    density: FormattedString('18.1e') = -9.9e9
    dquer : FormattedString('18.1e') = 0.0
    dsigma: FormattedString('18.1e') = 0.0
    dryvel: FormattedString('18.2f') = -9.99
    ohcconst: FormattedString('18.2e') = -9.99
    ohdconst: FormattedString('8.2f') = -9.9e-9
    ohnconst: FormattedString('8.2f') = 2.0
    weightmolar: FormattedString('18.2f') = -999.9
