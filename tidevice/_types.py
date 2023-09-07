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


@dataclass(frozen=True)
class XCTestResult(_BaseInfo):
    """Representing the XCTest result printed at the end of test.

    At the end of an XCTest, the test process will print following information:

        Test Suite 'MoblySignInTests' passed at 2023-09-03 16:35:39.214.
                Executed 1 test, with 0 failures (0 unexpected) in 3.850 (3.864) seconds
        Test Suite 'MoblySignInTests.xctest' passed at 2023-09-03 16:35:39.216.
                 Executed 1 test, with 0 failures (0 unexpected) in 3.850 (3.866) seconds
        Test Suite 'Selected tests' passed at 2023-09-03 16:35:39.217.
                 Executed 1 test, with 0 failures (0 unexpected) in 3.850 (3.869) seconds
    """

    MESSAGE = (
        "Test Suite '{test_suite_name}' passed at {end_time}.\n"
        "\t Executed {run_count} test, with {failure_count} failures ({unexpected_count} unexpected) in {test_duration:.3f} ({total_duration:.3f}) seconds"
    )

    test_suite_name: str = alias_field('TestSuiteName')
    end_time: str = alias_field('EndTime')
    run_count: int = alias_field('RunCount')
    failure_count: int = alias_field('FailureCount')
    unexpected_count: int = alias_field('UnexpectedCount')
    test_duration: float = alias_field('TestDuration')
    total_duration: float = alias_field('TotalDuration')

    def __repr__(self) -> str:
        return self.MESSAGE.format(
            test_suite_name=self.test_suite_name, end_time=self.end_time,
            run_count=self.run_count, failure_count=self.failure_count,
            unexpected_count=self.unexpected_count,
            test_duration=self.test_duration,
            total_duration=self.total_duration,
        )
