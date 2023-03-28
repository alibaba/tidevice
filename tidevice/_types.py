# -*- coding: utf-8 -*-
"""Created on Fri Sep 24 2021 14:13:00 by codeskyblue
"""

import dataclasses
import typing
from dataclasses import dataclass

from ._proto import ConnectionType

_T = typing.TypeVar("_T")


def alias_field(name: str) -> dataclasses.Field:
    return dataclasses.field(metadata={"alias": name})


class _BaseInfo:

    def _asdict(self) -> dict:
        """ for simplejson """
        return self.__dict__.copy()

    @classmethod
    def from_json(cls: _T, data: dict) -> _T:
        kwargs = {}
        for field in dataclasses.fields(cls):
            possible_names = [field.name]
            if "alias" in field.metadata:
                possible_names.append(field.metadata["alias"])
            for name in possible_names:
                if name in data:
                    value = data[name]
                    if field.type != type(value):
                        value = field.type(value)
                    kwargs[field.name] = value
                    break
        return cls(**kwargs)

    def __repr__(self) -> str:
        attrs = []
        for k, v in self.__dict__.items():
            attrs.append(f"{k}={v!r}")
        return f"<{self.__class__.__name__} " + ", ".join(attrs) + ">"


@dataclass(frozen=True)
class DeviceInfo(_BaseInfo):
    udid: str = alias_field("SerialNumber")
    device_id: int = alias_field("DeviceID")
    conn_type: ConnectionType = alias_field("ConnectionType")
