"""Settings for the minimal runtime, not the historical application's options."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    profile: str = "native-foundation"
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.profile != "native-foundation":
            raise ValueError("only the native-foundation profile is implemented")
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("unsupported settings schema")

