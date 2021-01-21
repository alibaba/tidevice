# coding: utf-8
#
# Created: codeskyblue 2020/06/01
#

import struct
from collections import namedtuple
from functools import partial


class Field(object):
    def __init__(self, name, default=None, format=None):
        assert format, "format should not empty"
        self._name = name
        self._format = format
        self._default = default
        self._struct = struct.Struct(format)

    @property
    def name(self):
        return self._name

    @property
    def format(self):
        return self._format

    @property
    def default(self):
        return self._default

    @property
    def size(self):
        return self._struct.size

    def to_field(self):
        return Field(self._name, self._format, self._default)


class Byte(Field):
    """
    Byte("padding")[6]
    """
    def __init__(self, name, default=None, format=None):
        super().__init__(name, default, format="s")

    def __item__(self, n: int):
        self._format = str(n)+"s"
        return self

Bool = partial(Field, format="?")
U8 = UInt8 = partial(Field, format="B")
U16 = UInt16 = partial(Field, format="H")
U32 = UInt32 = partial(Field, format="I")
U64 = UInt64 = partial(Field, format="Q")


class Struct(object):
    def __init__(self, typename: str, *fields, byteorder="<"):
        self._fields = [self._convert_field(f) for f in fields]
        self._typename = typename
        self._fmt = byteorder + ''.join([f.format for f in self._fields])
        self._field_names = []
        for f in self._fields:
            if f.name in self._field_names:
                raise ValueError("Struct has duplicated name", f.name)
            self._field_names.append(f.name)

    @property
    def size(self):
        return struct.Struct(self._fmt).size

    def _convert_field(self, fvalue):
        if isinstance(fvalue, Field):
            return fvalue
        else:
            raise ValueError("Unknown type:", fvalue)

    def parse(self, buffer: bytes):
        values = struct.unpack(self._fmt, buffer)
        return namedtuple(self._typename, self._field_names)(*values)

    def build(self, *args, **kwargs) -> bytearray:
        if args:
            assert len(args) == 1
            assert isinstance(args[0], dict)
            kwargs = args[0]

        buffer = bytearray()
        for f in self._fields:
            value = kwargs.get(f.name)
            if value is None:
                if f.default is None:
                    raise ValueError("missing required field", f.name, value,
                                 f.default)
                value = f.default
            buffer.extend(struct.pack(f.format, value))
        return buffer


def _example():
    Message = Struct("Message",
        U32("length"),
        U16("magic", 0x1234))
    m = Message.parse(b"\x12\x00\x00\x00\x12\x35")
    assert m.length == 0x12
    assert m.magic == 0x3512

    buf = Message.build(length=7)
    assert buf == b'\x07\x00\x00\x00\x34\x12'


if __name__ == "__main__":
    _example()