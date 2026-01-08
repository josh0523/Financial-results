# 权证过滤功能实现总结

## 问题描述
用户发现像 30061 这类权证（warrant）会被系统抓取到，但权证不会有自结公布（自行公布财报），因此需要从分析中移除。

## 解决方案
实现了自动过滤权证的功能，通过股票代码的位数来识别：
- **一般股票**：4位数代码（如 2330、1234）
- **权证**：5位或更多位数代码（如 30061、12345）

## 实现细节

### 1. 在 `attention/utils.py` 中新增函数
```python
def is_warrant(code: str) -> bool:
    """
    检查股票代码是否为权证。
    权证通常有5位或更多数字，而一般股票为4位数字。
    """
    if not code:
        return False
    digits = ''.join(c for c in code if c.isdigit())
    return len(digits) >= 5
```

### 2. 在 `attention/analysis.py` 中应用过滤
在 `build_report()` 函数的主循环中：
```python
for (market, code), items in grouped.items():
    # 跳过权证 - 它们不会有自结公布
    if is_warrant(code):
        continue
    # ... 继续处理正常股票
```

## 测试结果
✅ 权证 30061 在原始数据中存在（4条记录）
✅ 权证 30061 在最终报告中被成功过滤（0条记录）
✅ 正常股票（4位代码）保留在报告中
✅ CSV输出文件也不包含权证

## 影响范围
- 所有通过 TSE 和 OTC 抓取的数据都会自动过滤权证
- 不影响现有功能和其他股票的分析
- 文档已更新（README.md）说明此功能
