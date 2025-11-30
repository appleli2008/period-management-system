from datetime import datetime, timedelta
from django.utils import timezone
from .models import PeriodRecord, UserProfile


def get_period_predictions(user, records, profile, year, month):
    """
    简化版：只预测当前预测和下次预测两个周期
    """
    print(f"=== 简化预测逻辑启动 ===")
    print(f"目标月份: {year}年{month}月")

    # 获取实际记录（非预测记录）
    actual_records = [r for r in records if not r.is_predicted]

    if not actual_records:
        print("无实际记录，无法进行预测")
        return [], []

    # 使用最近的记录
    latest_record = actual_records[-1]
    reference_date = latest_record.end_date  # 从结束日期开始

    print(f"参考记录: {latest_record.start_date} 至 {latest_record.end_date}")
    print(f"参考日期（结束日）: {reference_date}")

    # 计算预测周期
    cycle_length = profile.cycle_length
    period_length = profile.period_length

    print(f"周期设置: {cycle_length}天周期, {period_length}天经期")

    # 只计算两个预测周期：
    # 1. 当前预测（下一个周期）
    current_prediction_start = reference_date + timedelta(days=cycle_length)
    current_prediction_end = current_prediction_start + timedelta(days=period_length - 1)

    # 2. 下次预测（下下个周期）
    next_prediction_start = current_prediction_start + timedelta(days=cycle_length)
    next_prediction_end = next_prediction_start + timedelta(days=period_length - 1)

    print(f"当前预测周期: {current_prediction_start} 至 {current_prediction_end}")
    print(f"下次预测周期: {next_prediction_start} 至 {next_prediction_end}")

    # 目标月份范围
    target_month_start = datetime(year, month, 1).date()
    if month == 12:
        target_month_end = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        target_month_end = datetime(year, month + 1, 1).date() - timedelta(days=1)

    print(f"目标月份: {target_month_start} 至 {target_month_end}")

    # 生成目标月份内的日期
    current_prediction_dates = generate_dates_in_month(current_prediction_start, current_prediction_end, year, month)
    next_prediction_dates = generate_dates_in_month(next_prediction_start, next_prediction_end, year, month)

    print(f"当前预测在目标月份内: {len(current_prediction_dates)}天")
    print(f"下次预测在目标月份内: {len(next_prediction_dates)}天")

    return current_prediction_dates, next_prediction_dates


def calculate_weighted_average(cycle_lengths):
    """计算加权平均周期长度"""
    n = len(cycle_lengths)

    if n == 0:
        return 28  # 默认周期

    if n == 1:
        return cycle_lengths[0]

    # 指数衰减权重：最近的数据权重最高
    weights = []
    for i in range(n):
        weight = 0.5 ** (n - i - 1)
        weights.append(weight)

    # 归一化权重
    total_weight = sum(weights)
    normalized_weights = [w / total_weight for w in weights]

    # 计算加权平均
    weighted_sum = sum(length * weight for length, weight in zip(cycle_lengths, normalized_weights))
    weighted_avg = weighted_sum

    # 四舍五入到整数，确保在合理范围内
    cycle_length = int(round(weighted_avg))
    cycle_length = max(20, min(60, cycle_length))  # 限制在20-60天范围内

    print(f"加权平均计算: {cycle_lengths} * {normalized_weights} = {weighted_avg:.1f} -> {cycle_length}天")

    return cycle_length


def calculate_prediction_cycles(reference_date, cycle_length, period_length, year, month, prediction_method):
    """
    修复版：优化调整逻辑，避免过度调整
    """
    print(f"=== 计算预测周期（修复版）===")
    print(f"参考日期（结束日期）: {reference_date}")
    print(f"周期长度: {cycle_length}天")
    print(f"经期长度: {period_length}天")

    # 计算第一个预测周期（从结束日期开始）
    prediction_start = reference_date + timedelta(days=cycle_length)
    prediction_end = prediction_start + timedelta(days=period_length - 1)

    print(f"基础预测: {prediction_start} 至 {prediction_end}")

    # 修复：优化调整逻辑
    today = timezone.now().date()
    target_month_start = datetime(year, month, 1).date()

    # 计算目标月份的范围
    if month == 12:
        target_month_end = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        target_month_end = datetime(year, month + 1, 1).date() - timedelta(days=1)

    print(f"目标月份范围: {target_month_start} 至 {target_month_end}")

    # 智能调整：找到最接近目标月份的预测
    adjustments = 0
    max_adjustments = 6  # 最多调整6个周期（约半年）

    # 如果预测在目标月份之后，需要向前调整
    while prediction_start > target_month_end and adjustments < max_adjustments:
        prediction_start -= timedelta(days=cycle_length)
        prediction_end = prediction_start + timedelta(days=period_length - 1)
        adjustments += 1
        print(f"向前调整{adjustments}次: {prediction_start} 至 {prediction_end}")

    # 如果预测在目标月份之前，需要向后调整（但确保是未来的日期）
    while (prediction_end < target_month_start or prediction_start <= today) and adjustments < max_adjustments:
        prediction_start += timedelta(days=cycle_length)
        prediction_end = prediction_start + timedelta(days=period_length - 1)
        adjustments += 1
        print(f"向后调整{adjustments}次: {prediction_start} 至 {prediction_end}")

    if adjustments > 0:
        print(f"最终调整{adjustments}次后: {prediction_start} 至 {prediction_end}")

    # 计算下一次预测周期
    next_prediction_start = prediction_start + timedelta(days=cycle_length)
    next_prediction_end = next_prediction_start + timedelta(days=period_length - 1)

    print(f"下一次预测: {next_prediction_start} 至 {next_prediction_end}")

    # 生成目标月份内的日期
    predicted_dates = generate_dates_in_month(prediction_start, prediction_end, year, month)
    next_prediction_dates = generate_dates_in_month(next_prediction_start, next_prediction_end, year, month)

    print(f"目标月份内预测: {len(predicted_dates)}天")
    print(f"目标月份内下次预测: {len(next_prediction_dates)}天")
    print(f"预测方法: {prediction_method}")

    return predicted_dates, next_prediction_dates


def generate_dates_in_month(start_date, end_date, year, month):
    """
    生成指定月份内的日期列表
    """
    dates = []

    # 目标月份范围
    target_start = datetime(year, month, 1).date()
    if month == 12:
        target_end = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        target_end = datetime(year, month + 1, 1).date() - timedelta(days=1)

    # 检查是否有重叠
    if end_date < target_start or start_date > target_end:
        return dates

    # 计算重叠部分
    overlap_start = max(start_date, target_start)
    overlap_end = min(end_date, target_end)

    # 生成连续日期
    current_date = overlap_start
    while current_date <= overlap_end:
        dates.append(current_date)
        current_date += timedelta(days=1)

    return dates