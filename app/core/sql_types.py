from datetime import date, datetime
from decimal import Decimal

type SqlValue = str | int | float | bool | Decimal | date | datetime | list[str] | tuple[str, ...] | None

type SqlParams = dict[str, SqlValue]
