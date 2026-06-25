"""
Financial Analyzer CLI 入口
默认执行六维全量分析，无需指定模式

用法:
  python3 run.py 600519                          # 六维全量分析（默认）
  python3 run.py --json 600519                   # JSON格式输出
  python3 run.py --valuation 600519              # 仅估值专项
  python3 run.py --timing 600519                 # 仅择时专项
  python3 run.py --risk 600519                   # 仅风控专项
"""

import os
import sys
import json
import argparse

# 自动定位 skill 目录，无论从哪里调用都能正确 import
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)


def main():
    parser = argparse.ArgumentParser(description="Financial Analyzer v2")
    parser.add_argument("symbol", help="股票/ETF代码")
    parser.add_argument("--valuation", action="store_true", help="仅估值专项")
    parser.add_argument("--timing", action="store_true", help="仅择时专项")
    parser.add_argument("--risk", action="store_true", help="仅风控专项")
    parser.add_argument("--json", action="store_true", help="JSON输出（默认Markdown报告）")
    args = parser.parse_args()

    from analyzer import FinancialAnalyzer
    analyzer = FinancialAnalyzer()

    # 专项模式 or 默认全量六维分析
    if args.valuation:
        result = analyzer.valuation_analysis(args.symbol)
    elif args.timing:
        result = analyzer.timing_analysis(args.symbol)
    elif args.risk:
        result = analyzer.risk_check(args.symbol)
    else:
        result = analyzer.deep_analysis(args.symbol)

    # 输出
    if args.json:
        def default_serializer(o):
            import numpy as np
            if isinstance(o, (np.integer,)):
                return int(o)
            if isinstance(o, (np.floating,)):
                return float(o)
            if isinstance(o, np.ndarray):
                return o.tolist()
            return str(o)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=default_serializer))
    else:
        report = analyzer.format_report(result)
        print(report)


if __name__ == "__main__":
    main()
