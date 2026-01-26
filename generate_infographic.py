# -*- coding: utf-8 -*-
"""
股市風險預警日報 - 深色專業財經風格 (智慧排版版)
"""

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import os
from datetime import datetime
import glob


# ========== 顏色配置 ==========
COLORS = {
    'background': '#1E1E2E',      # 深靛藍背景
    'title': '#FFFFFF',           # 主標題白色
    'subtitle': '#B0B0B0',        # 副標題淺灰
    'text': '#E8E8E8',            # 內文淺白
    'high_risk': '#FF4757',       # 高風險/一定公布 - 亮紅
    'maybe': '#FFA502',           # 可能/不確定 - 琥珀金
    'low_prob': '#7BED9F',        # 低機率公布 - 薄荷綠
    'low_risk': '#2ED573',        # 低風險/已公布 - 青綠
    'divider': '#3A3A4A',         # 分隔線深灰
    'footer_bg': '#1A1A2E',       # Footer Bar 背景
}


def setup_chinese_font():
    """設定支援繁體中文的字體"""
    font_candidates = [
        'Microsoft JhengHei',
        'SimHei',
        'Microsoft YaHei',
        'Noto Sans CJK TC',
    ]
    for font_name in font_candidates:
        try:
            font = FontProperties(family=font_name)
            fig, ax = plt.subplots(figsize=(1, 1))
            ax.text(0.5, 0.5, '測試', fontproperties=font)
            plt.close(fig)
            print(f"使用字體: {font_name}")
            return font_name
        except:
            continue
    return None


def load_and_clean_data(csv_path):
    """載入並清洗 CSV 資料"""
    df = pd.read_csv(csv_path, encoding='utf-8')
    if '代號' in df.columns:
        df['代號'] = df['代號'].astype(str).str.replace('="', '', regex=False).str.replace('"', '', regex=False)
    return df


def smart_balance_columns(categories):
    """
    智慧排版演算法：將分類分配到左右欄，使兩欄行數接近
    
    Parameters:
    -----------
    categories : list of tuples
        [(name, items, color), ...]
    
    Returns:
    --------
    left_column, right_column : 兩個列表
    """
    # 依資料量排序 (大到小)
    sorted_cats = sorted(categories, key=lambda x: len(x[1]), reverse=True)
    
    left_column = []
    right_column = []
    left_count = 0
    right_count = 0
    
    for cat in sorted_cats:
        cat_count = len(cat[1]) + 2  # +2 為標題佔用空間
        
        # 分配到行數較少的欄位
        if left_count <= right_count:
            left_column.append(cat)
            left_count += cat_count
        else:
            right_column.append(cat)
            right_count += cat_count
    
    return left_column, right_column


def draw_section(ax, x, y, title, items, title_color, item_color='#E8E8E8',
                 title_size=18, item_size=15, line_height=0.038):
    """繪製區塊（分欄對齊版本）"""
    # 區塊標題
    ax.text(x, y, title, fontsize=title_size, fontweight='bold', 
            color=title_color, ha='left', va='top', transform=ax.transAxes, zorder=10)
    
    # 標題底線
    ax.plot([x, x + 0.42], [y - 0.022, y - 0.022], 
            color=title_color, linewidth=2.5, alpha=0.8, transform=ax.transAxes, zorder=10)
    
    # 繪製項目列表（分欄對齊：代碼 | 名稱）
    item_y = y - 0.06  # 標題下方留白增加
    code_x = x + 0.01  # 代碼位置（稍微縮排）
    name_x = x + 0.13  # 名稱位置（固定間距）
    
    for item in items:
        # 分割代碼和名稱（假設格式為 "代碼 名稱"）
        parts = item.split(' ', 1)
        if len(parts) == 2:
            code, name = parts
            # 繪製代碼（灰色）
            ax.text(code_x, item_y, code, fontsize=item_size, color='#95A5A6',
                    ha='left', va='top', transform=ax.transAxes, zorder=10,
                    family='monospace')  # 使用等寬字體
            # 繪製名稱（原色）
            ax.text(name_x, item_y, name, fontsize=item_size, color=item_color,
                    ha='left', va='top', transform=ax.transAxes, zorder=10)
        else:
            # 如果格式不符，直接顯示
            ax.text(code_x, item_y, item, fontsize=item_size, color=item_color,
                    ha='left', va='top', transform=ax.transAxes, zorder=10)
        item_y -= line_height
    
    return item_y


def draw_column(ax, x, categories, start_y, title_size=28, item_size=22, line_height=0.05):
    """繪製整個欄位的所有區塊"""
    y = start_y
    section_gap = 0.04
    
    for name, items, color in categories:
        if len(items) > 0:
            y = draw_section(ax, x, y, name, items, color,
                           title_size=title_size, item_size=item_size, line_height=line_height)
            y -= section_gap
    
    return y


def calculate_dynamic_height(left_col, right_col, line_height=0.05):
    """計算所需的動態畫布高度"""
    base_height = 16
    header_ratio = 0.12
    footer_ratio = 0.08
    
    # 計算兩欄各自需要的高度
    left_items = sum(len(items) + 2 for _, items, _ in left_col)
    right_items = sum(len(items) + 2 for _, items, _ in right_col)
    max_items = max(left_items, right_items)
    
    # 計算需要的內容高度比例
    content_ratio = max_items * line_height + 0.1
    available_ratio = 1 - header_ratio - footer_ratio
    
    if content_ratio > available_ratio:
        scale = content_ratio / available_ratio
        return min(base_height * scale * 1.15, 28)  # 最大28
    
    return base_height


def get_taiwan_holidays():
    """
    取得台灣國定假日列表
    
    Returns:
    --------
    set of datetime.date
        台灣國定假日集合
    """
    holidays = set()
    
    # 2026年台灣國定假日
    holidays_2026 = [
        '2026-01-01',  # 元旦
        '2026-01-23',  # 補班日（實際上班）- 需移除
        '2026-01-27',  # 除夕前一日（調整放假）
        '2026-01-28',  # 除夕
        '2026-01-29',  # 春節初一
        '2026-01-30',  # 春節初二
        '2026-01-31',  # 春節初三
        '2026-02-01',  # 春節初四
        '2026-02-02',  # 春節初五
        '2026-02-28',  # 和平紀念日
        '2026-03-01',  # 和平紀念日補假
        '2026-04-03',  # 兒童節前一日（調整放假）
        '2026-04-04',  # 兒童節/清明節
        '2026-04-05',  # 清明節補假
        '2026-04-06',  # 清明節補假
        '2026-05-01',  # 勞動節
        '2026-06-25',  # 端午節
        '2026-06-26',  # 端午節補假
        '2026-10-01',  # 中秋節
        '2026-10-02',  # 中秋節補假
        '2026-10-09',  # 國慶日補假
        '2026-10-10',  # 國慶日
    ]
    
    # 2027年台灣國定假日（部分，可後續補充）
    holidays_2027 = [
        '2027-01-01',  # 元旦
        '2027-02-16',  # 除夕前一日
        '2027-02-17',  # 除夕
        '2027-02-18',  # 春節初一
        '2027-02-19',  # 春節初二
        '2027-02-20',  # 春節初三
        '2027-02-21',  # 春節初四
        '2027-02-22',  # 春節初五
        '2027-02-28',  # 和平紀念日
        '2027-04-04',  # 兒童節/清明節
        '2027-04-05',  # 清明節補假
        '2027-05-01',  # 勞動節
        '2027-06-14',  # 端午節
        '2027-09-21',  # 中秋節
        '2027-10-10',  # 國慶日
    ]
    
    # 補班日（這些日子要上班，不算假日）
    makeup_workdays = [
        '2026-01-23',  # 補班（補1/27）
    ]
    
    for date_str in holidays_2026 + holidays_2027:
        if date_str not in makeup_workdays:
            holidays.add(datetime.strptime(date_str, '%Y-%m-%d').date())
    
    return holidays


def get_next_trading_day(date):
    """
    計算下一個交易日（只跳過週末）
    
    Parameters:
    -----------
    date : datetime.date
        基準日期
    
    Returns:
    --------
    datetime.date
        下一個交易日
    """
    from datetime import timedelta
    
    next_day = date + timedelta(days=1)
    
    # 跳過週末（週六=5, 週日=6）
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    
    return next_day


def generate_risk_report(csv_path, output_path=None):
    """生成股市風險預警日報圖卡 - 深色專業風格"""
    
    # 設定中文字體
    font_name = setup_chinese_font()
    if font_name:
        plt.rcParams['font.family'] = font_name
        plt.rcParams['axes.unicode_minus'] = False
    
    # 載入資料
    df = load_and_clean_data(csv_path)
    
    # 從檔名提取預測日期（結束日期 + 下一個交易日）
    import re
    basename = os.path.basename(csv_path)
    # 嘗試從檔名提取日期範圍 (e.g., attention_20260113_20260120.csv)
    match = re.search(r'(\d{8})_(\d{8})', basename)
    if match:
        end_date_str = match.group(2)  # 20260120
        end_date = datetime.strptime(end_date_str, '%Y%m%d').date()
        prediction_date = get_next_trading_day(end_date)  # 計算下一個交易日
        report_date = prediction_date.strftime('%Y-%m-%d')
        weekday_name = ['週一', '週二', '週三', '週四', '週五', '週六', '週日'][prediction_date.weekday()]
        print(f"預測公布日期: {report_date} ({weekday_name}) [基於分析期間至 {end_date_str}]")
    elif '最後注意日' in df.columns and len(df) > 0:
        # 備用方案：使用 CSV 中的最後注意日 + 下一個交易日
        last_date = df['最後注意日'].iloc[0]
        if isinstance(last_date, str):
            last_date = datetime.strptime(last_date, '%Y-%m-%d').date()
        prediction_date = get_next_trading_day(last_date)
        report_date = prediction_date.strftime('%Y-%m-%d')
    else:
        report_date = datetime.now().strftime('%Y-%m-%d')
    
    # 依風險評級分類
    df_high = df[df['風險評級'] == '高風險']
    df_may = df[df['風險評級'] == '可能公布']
    df_uncertain = df[df['風險評級'] == '不確定公布']
    df_low = df[df['風險評級'] == '低風險']
    df_low_prob = df[df['風險評級'] == '低機率公布']
    
    # 建立項目清單
    items_high = [f"{row['代號']} {row['名稱']}" for _, row in df_high.iterrows()]
    items_may = [f"{row['代號']} {row['名稱']}" for _, row in df_may.iterrows()]
    items_uncertain = [f"{row['代號']} {row['名稱']}" for _, row in df_uncertain.iterrows()]
    items_low = [f"{row['代號']} {row['名稱']}" for _, row in df_low.iterrows()]
    items_low_prob = [f"{row['代號']} {row['名稱']}" for _, row in df_low_prob.iterrows()]
    
    # 準備分類資料 (名稱, 項目列表, 顏色) - 不包含低風險
    categories = [
        ('● 一定公布', items_high, COLORS['high_risk']),
        ('○ 可能公布', items_may, COLORS['maybe']),
        ('△ 不確定公布', items_uncertain, COLORS['maybe']),
        ('□ 低機率公布', items_low_prob, COLORS['low_prob']),
    ]
    
    # 過濾掉空的分類
    categories = [(n, i, c) for n, i, c in categories if len(i) > 0]
    
    # 智慧排版：自動平衡左右欄
    left_column, right_column = smart_balance_columns(categories)
    
    print(f"左欄分類: {[n for n, _, _ in left_column]}")
    print(f"右欄分類: {[n for n, _, _ in right_column]}")
    
    # 字體設定 (30pt+)
    title_size = 30
    item_size = 24
    line_height = 0.053  # 增加10% (原0.048 * 1.1 ≈ 0.053)
    
    # 計算動態畫布高度
    fig_height = calculate_dynamic_height(left_column, right_column, line_height)
    print(f"動態畫布高度: {fig_height:.1f}")
    
    # 建立圖表
    fig, ax = plt.subplots(figsize=(9, fig_height))
    
    # 深靛藍背景（單色）
    ax.set_facecolor(COLORS['background'])
    fig.patch.set_facecolor(COLORS['background'])
    
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    
    # ===== 頂部區域 =====
    # 主標題 (加大間距)
    ax.text(0.5, 0.975, '注意自結預測日報', fontsize=44, fontweight='bold', 
            color=COLORS['title'], ha='center', va='top', transform=ax.transAxes,
            zorder=10)
    
    # 副標題 (統計) - 間距拉開
    stats_parts = []
    if items_high: stats_parts.append(f"一定公布 {len(items_high)}")
    if items_may: stats_parts.append(f"可能 {len(items_may)}")
    if items_uncertain: stats_parts.append(f"不確定 {len(items_uncertain)}")
    if items_low_prob: stats_parts.append(f"低機率 {len(items_low_prob)}")
    stats = ' · '.join(stats_parts)
    
    # 統計資訊背景框（儀表板樣式）
    stats_bg = plt.Rectangle((0.12, 0.917), 0.76, 0.022, 
                            facecolor='#2F3640', alpha=0.5, 
                            transform=ax.transAxes, zorder=9,
                            clip_on=False)
    ax.add_patch(stats_bg)
    
    ax.text(0.5, 0.928, stats, fontsize=16, color=COLORS['subtitle'],
            ha='center', va='center', transform=ax.transAxes, zorder=10)
    
    # 日期 (調整位置)
    ax.text(0.95, 0.975, report_date, fontsize=18, color=COLORS['title'], fontweight='bold',
            ha='right', va='top', transform=ax.transAxes, zorder=10)
    
    # 分隔線
    ax.plot([0.05, 0.95], [0.895, 0.895], color=COLORS['divider'], linewidth=2, 
            transform=ax.transAxes, zorder=10)
    
    # ===== 雙欄位內容 =====
    content_top = 0.87
    left_x = 0.05
    right_x = 0.52
    
    # 繪製左欄
    draw_column(ax, left_x, left_column, content_top, 
                title_size=title_size, item_size=item_size, line_height=line_height)
    
    # 繪製右欄
    draw_column(ax, right_x, right_column, content_top,
                title_size=title_size, item_size=item_size, line_height=line_height)
    
    # ===== 底部 Footer Bar =====
    # Footer 背景條
    footer_rect = plt.Rectangle((0, 0), 1, 0.04, 
                               facecolor=COLORS['footer_bg'], alpha=0.6,
                               transform=ax.transAxes, zorder=5)
    ax.add_patch(footer_rect)
    
    # Footer 文字
    ax.text(0.5, 0.02, '自結公布預測 | 僅供參考', fontsize=14, 
            color=COLORS['subtitle'], alpha=0.9,
            ha='center', va='center', transform=ax.transAxes, zorder=10)
    
    # 儲存圖片
    if output_path is None:
        base_dir = os.path.dirname(csv_path)
        date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(base_dir, f'risk_report_{date_str}.png')
    
    plt.tight_layout(pad=0.5)
    plt.savefig(output_path, dpi=120, facecolor=COLORS['background'], 
                edgecolor='none', bbox_inches='tight')
    plt.close()
    
    print(f"圖表已儲存至: {output_path}")
    return output_path


def main():
    """主程式"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, 'output')
    attention_files = glob.glob(os.path.join(output_dir, 'attention_*.csv'))
    
    if not attention_files:
        print("錯誤: 找不到 attention CSV 檔案")
        return
    
    latest_file = max(attention_files, key=os.path.getmtime)
    print(f"處理檔案: {latest_file}")
    generate_risk_report(latest_file)


if __name__ == '__main__':
    main()
