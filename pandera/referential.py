"""跨表引用完整性（外键）校验。

在单表 schema 校验之外，提供跨数据集的引用完整性检查：

    from pandera.referential import ForeignKey, check_referential_integrity

    fk = ForeignKey(
        child="orders", parent="customers",
        child_key="customer_id", parent_key="id",
    )
    report = check_referential_integrity(
        {"orders": orders_df, "customers": customers_df}, [fk]
    )
    report.ok          # 全部命中时为 True
    report.violations  # 每个孤儿行一条，带子表行号与取值

约定：
- ``child_key`` / ``parent_key`` 既可以是单个列名，也可以是列名列表（复合键）。
- 行号 ``child_row`` 是子表中的位置序号，从 0 开始。
- 键比较对类型敏感：int ``1`` 与 str ``"1"`` 不视为同一键。
- 空子表视为通过；父表重复键不影响完整性判定。
- 引用了 ``tables`` 中不存在的表（或表中不存在的列）时抛出 ``KeyError``。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Sequence, Tuple, Union

__all__ = [
    "ForeignKey",
    "ReferentialViolation",
    "ReferentialReport",
    "check_referential_integrity",
]

KeySpec = Union[str, Sequence[str]]


def _normalize_key_spec(spec: KeySpec, *, which: str) -> List[str]:
    """把单个列名或列名列表统一成列名列表。"""
    if isinstance(spec, str):
        return [spec]
    columns = list(spec)
    if not columns:
        raise ValueError(f"{which} 不能为空")
    for col in columns:
        if not isinstance(col, str):
            raise TypeError(f"{which} 中的列名必须是字符串，得到 {col!r}")
    return columns


@dataclass(frozen=True)
class ForeignKey:
    """一条跨表外键约束：child 表的 child_key 列必须在 parent 表的 parent_key 列中存在。"""

    child: str
    parent: str
    child_key: KeySpec
    parent_key: KeySpec


@dataclass(frozen=True)
class ReferentialViolation:
    """一条引用完整性违规：子表某行的键在父表中找不到。"""

    child_table: str
    child_row: int
    child_value: Any
    parent_table: str
    parent_key: Tuple[str, ...]


@dataclass
class ReferentialReport:
    """一次跨表校验的结果。"""

    violations: List[ReferentialViolation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


def _typed_key(values: Tuple[Any, ...]) -> Tuple[Tuple[type, Any], ...]:
    # 连同类型一起比较，避免 int 1 与 str "1" 这类字面量相同被误判为命中。
    return tuple((type(v), v) for v in values)


def _check_single_fk(
    tables: Mapping[str, Any],
    fk: ForeignKey,
) -> List[ReferentialViolation]:
    if fk.child not in tables:
        raise KeyError(f"子表 {fk.child!r} 不在 tables 中")
    if fk.parent not in tables:
        raise KeyError(f"父表 {fk.parent!r} 不在 tables 中")

    child_df = tables[fk.child]
    parent_df = tables[fk.parent]

    child_cols = _normalize_key_spec(fk.child_key, which="child_key")
    parent_cols = _normalize_key_spec(fk.parent_key, which="parent_key")
    if len(child_cols) != len(parent_cols):
        raise ValueError(
            f"child_key 与 parent_key 列数不一致：{child_cols} vs {parent_cols}"
        )

    for col in child_cols:
        if col not in child_df.columns:
            raise KeyError(f"子表 {fk.child!r} 缺少列 {col!r}")
    for col in parent_cols:
        if col not in parent_df.columns:
            raise KeyError(f"父表 {fk.parent!r} 缺少列 {col!r}")

    parent_keys = {
        _typed_key(tuple(row))
        for row in parent_df[parent_cols].itertuples(index=False, name=None)
    }

    violations: List[ReferentialViolation] = []
    single = len(child_cols) == 1
    for row_no, row in enumerate(
        child_df[child_cols].itertuples(index=False, name=None)
    ):
        values = tuple(row)
        if _typed_key(values) in parent_keys:
            continue
        violations.append(
            ReferentialViolation(
                child_table=fk.child,
                child_row=row_no,
                child_value=values[0] if single else values,
                parent_table=fk.parent,
                parent_key=tuple(parent_cols),
            )
        )
    return violations


def check_referential_integrity(
    tables: Mapping[str, Any],
    fks: Sequence[ForeignKey],
) -> ReferentialReport:
    """对一组表批量检查外键约束，返回合并后的报告。

    :param tables: 表名到 DataFrame 的映射。
    :param fks: 要检查的 ForeignKey 列表，全部检查，违规合并到同一报告。
    """
    violations: List[ReferentialViolation] = []
    for fk in fks:
        violations.extend(_check_single_fk(tables, fk))
    return ReferentialReport(violations=violations)
