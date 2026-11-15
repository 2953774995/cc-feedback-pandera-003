#!/usr/bin/env python3
"""跨表引用完整性校验验收探针。

契约：
  from pandera.referential import ForeignKey, check_referential_integrity
  fk = ForeignKey(child="orders", parent="customers", child_key="customer_id", parent_key="id")
  report = check_referential_integrity({"orders": df1, "customers": df2}, [fk])
  report.ok -> bool；report.violations -> list，每条含
      .child_table .child_row .child_value .parent_table .parent_key
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

FAILED = 0
PASSED = 0


def check(code, desc, fn):
    global FAILED, PASSED
    try:
        fn()
        print(f"[PASS] {code} {desc}")
        PASSED += 1
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] {code} {desc}")
        print(f"        {type(exc).__name__}: {exc}")
        FAILED += 1


def main():
    try:
        from pandera.referential import (  # noqa: F401
            ForeignKey,
            check_referential_integrity,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] P0 导入 pandera.referential 失败：{type(exc).__name__}: {exc}")
        print("-" * 60)
        print("探针汇总：0/9 通过")
        return 1

    customers = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
    orders_ok = pd.DataFrame({"order_id": [10, 11, 12], "customer_id": [1, 2, 3]})
    orders_bad = pd.DataFrame({"order_id": [10, 11, 12], "customer_id": [1, 99, 3]})

    def p1():
        r = check_referential_integrity(
            {"orders": orders_ok, "customers": customers},
            [ForeignKey("orders", "customers", "customer_id", "id")])
        assert r.ok is True, r.ok
        assert len(r.violations) == 0, len(r.violations)

    def p2():
        r = check_referential_integrity(
            {"orders": orders_bad, "customers": customers},
            [ForeignKey("orders", "customers", "customer_id", "id")])
        assert r.ok is False
        assert len(r.violations) == 1, len(r.violations)
        v = r.violations[0]
        assert v.child_row == 1, v.child_row
        assert v.child_value == 99, v.child_value
        assert v.parent_table == "customers", v.parent_table

    def p3():
        items = pd.DataFrame({"sku": ["A", "B"], "region": ["n", "s"]})
        lines = pd.DataFrame({"sku": ["A", "X"], "region": ["n", "s"]})
        r = check_referential_integrity(
            {"lines": lines, "items": items},
            [ForeignKey("lines", "items", ["sku", "region"], ["sku", "region"])])
        assert r.ok is False
        assert r.violations[0].child_value == ("X", "s"), r.violations[0].child_value

    def p4():
        try:
            check_referential_integrity(
                {"orders": orders_ok},
                [ForeignKey("orders", "customers", "customer_id", "id")])
        except (KeyError, ValueError):
            return
        raise AssertionError("父表缺失时没有报错")

    def p5():
        empty = pd.DataFrame({"order_id": [], "customer_id": []})
        r = check_referential_integrity(
            {"orders": empty, "customers": customers},
            [ForeignKey("orders", "customers", "customer_id", "id")])
        assert r.ok is True

    def p6():
        dup_parent = pd.DataFrame({"id": [1, 1, 2], "name": ["a", "a2", "b"]})
        r = check_referential_integrity(
            {"orders": orders_ok, "customers": dup_parent},
            [ForeignKey("orders", "customers", "customer_id", "id")])
        assert r.ok is True

    def p7():
        regions = pd.DataFrame({"code": ["n", "s"]})
        shipments = pd.DataFrame({"order_id": [10, 11], "customer_id": [1, 55], "region": ["n", "zz"]})
        r = check_referential_integrity(
            {"shipments": shipments, "customers": customers, "regions": regions},
            [ForeignKey("shipments", "customers", "customer_id", "id"),
             ForeignKey("shipments", "regions", "region", "code")])
        assert len(r.violations) == 2, len(r.violations)

    def p8():
        str_parent = pd.DataFrame({"id": ["1", "2", "3"]})
        r = check_referential_integrity(
            {"orders": orders_ok, "customers": str_parent},
            [ForeignKey("orders", "customers", "customer_id", "id")])
        assert r.ok is False, "int 与 str 字面量相同不应视为匹配"
        assert len(r.violations) == 3, len(r.violations)

    check("P1", "全部命中时通过", p1)
    check("P2", "孤儿行被定位到行号与值", p2)
    check("P3", "复合键匹配", p3)
    check("P4", "缺父表时报错", p4)
    check("P5", "空子表通过", p5)
    check("P6", "父表重复键不影响完整性", p6)
    check("P7", "多个外键一起检查", p7)
    check("P8", "类型不同视为不匹配", p8)

    print("-" * 60)
    print(f"探针汇总：{PASSED}/{PASSED + FAILED} 通过")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
