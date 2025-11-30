from datetime import datetime, timedelta
from django.utils import timezone
import numpy as np
from .models import PeriodRecord, UserProfile


def get_period_predictions(user, records, profile, year, month):
    """
    修复版：调整阶段划分，更早使用实际数据
    """
    # 获取实际记录数量（非预测记录）
    actual_records = [r for r in records if not r.is_predicted]
    actual_count = len(actual_records)

    print(f"预测调试: 总记录{len(records)}个, 实际记录{actual_count}个")

    # 根据实际记录数量选择算法
    if actual_count <= 1:
        # 0-1个实际记录：使用基础预测
        return stage1_basic_prediction(profile, records, year, month)
    else:
        # 2+个实际记录：使用实际数据预测
        return stage2_actual_data_prediction(records, profile, year, month)

def stage1_basic_prediction(profile, records, year, month):
    """
    修复版：考虑所有可用记录，而不仅仅是第一个
    """
    if not profile.cycle_length or not profile.period_length:
        return [], []

    print(f"=== stage1调试: 目标 {year}年{month}月 ===")

    # 获取用户所有实际经期记录（非预测记录）
    actual_records = [r for r in records if not r.is_predicted]
    actual_records.sort(key=lambda x: x.start_date)  # 按时间顺序排序

    print(f"stage1调试: 找到 {len(actual_records)} 个实际记录")
    for i, record in enumerate(actual_records):
        print(f"stage1调试: 记录{i + 1}: {record.start_date} 至 {record.end_date}")

    # 如果没有记录，使用预设周期
    if not actual_records:
        reference_date = timezone.now().date()
        cycle_length = profile.cycle_length
        print(f"stage1调试: 无实际记录，使用预设周期{cycle_length}天")

    # 如果只有一个记录，使用预设周期
    elif len(actual_records) == 1:
        reference_date = actual_records[0].start_date
        cycle_length = profile.cycle_length
        print(f"stage1调试: 只有1个记录，使用预设周期{cycle_length}天")

    # 如果有多个记录，计算实际平均周期
    else:
        # 使用最近的记录作为参考
        reference_date = actual_records[-1].start_date  # 最后一个记录是最新的

        # 计算实际周期长度
        cycle_lengths = []
        for i in range(1, len(actual_records)):
            prev_start = actual_records[i - 1].start_date
            curr_start = actual_records[i].start_date
            days_between = (curr_start - prev_start).days
            if 15 <= days_between <= 60:  # 合理范围
                cycle_lengths.append(days_between)
                print(f"stage1调试: 周期{i}: {prev_start} 到 {curr_start} = {days_between}天")

        if cycle_lengths:
            # 使用实际平均周期
            avg_cycle = sum(cycle_lengths) / len(cycle_lengths)
            cycle_length = int(round(avg_cycle))
            print(f"stage1调试: 实际平均周期: {avg_cycle:.1f}天 -> 使用{cycle_length}天")
        else:
            # 如果没有合理的周期数据，使用预设周期
            cycle_length = profile.cycle_length
            print(f"stage1调试: 无合理周期数据，使用预设周期{cycle_length}天")

    # 计算下一个周期的开始日期
    next_start = reference_date + timedelta(days=cycle_length)
    print(f"stage1调试: {reference_date} + {cycle_length}天 = {next_start}")

    # 目标月份范围
    target_start = datetime(year, month, 1).date()
    if month == 12:
        target_end = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        target_end = datetime(year, month + 1, 1).date() - timedelta(days=1)

    print(f"stage1调试: 目标月份范围 {target_start} 到 {target_end}")

    # 区分历史月份和未来月份的处理
    today = timezone.now().date()

    if target_end < today:
        # 历史月份：不调整预测日期
        print(f"stage1调试: 目标月份是过去月份，不调整预测日期")
    else:
        # 当前/未来月份：确保预测日期是未来的
        original_next_start = next_start
        while next_start <= today:
            next_start += timedelta(days=cycle_length)

        if original_next_start != next_start:
            print(f"stage1调试: 调整预测日期从 {original_next_start} 到 {next_start}")

    # 计算预测周期的结束日期
    next_end = next_start + timedelta(days=profile.period_length - 1)

    # 生成连续的预测日期
    predicted_dates = generate_continuous_dates(next_start, next_end, year, month)

    print(f"stage1调试: 预测日期 {predicted_dates}")

    return predicted_dates, []  # 暂时不预测下个周期


def stage2_actual_data_prediction(records, profile, year, month):
    """
    阶段2：基于实际记录数据进行预测
    适用于有2个以上实际记录的用户
    """
    # 获取实际记录并按时间排序
    actual_records = [r for r in records if not r.is_predicted]
    actual_records.sort(key=lambda x: x.start_date)

    print(f"=== stage2调试: 基于{len(actual_records)}个实际记录预测 ===")

    # 计算实际周期长度
    cycle_lengths = []
    for i in range(1, len(actual_records)):
        prev_start = actual_records[i - 1].start_date
        curr_start = actual_records[i].start_date
        days_between = (curr_start - prev_start).days
        if 20 <= days_between <= 60:  # 合理范围
            cycle_lengths.append(days_between)
            print(f"stage2调试: 周期{len(cycle_lengths)}: {days_between}天")

    if not cycle_lengths:
        # 如果没有合理周期数据，回退到阶段1
        return stage1_basic_prediction(profile, records, year, month)

    # 计算加权平均（近期周期权重更高）
    weights = [0.5 ** i for i in range(len(cycle_lengths))]
    total_weight = sum(weights)
    weighted_avg = sum(length * weight for length, weight in zip(cycle_lengths, weights)) / total_weight
    cycle_length = int(round(weighted_avg))

    print(f"stage2调试: 加权平均周期: {weighted_avg:.1f}天 -> 使用{cycle_length}天")

    # 使用最近的实际记录作为参考
    latest_record = actual_records[-1]
    reference_date = latest_record.start_date
    next_start = reference_date + timedelta(days=cycle_length)

    print(f"stage2调试: 基于{reference_date} + {cycle_length}天 = {next_start}")

    # 确保预测日期是未来的（仅对当前/未来月份）
    today = timezone.now().date()
    target_start = datetime(year, month, 1).date()

    if target_start > today:  # 未来月份
        while next_start <= today:
            next_start += timedelta(days=cycle_length)
            print(f"stage2调试: 调整到未来日期: {next_start}")

    # 生成预测日期
    next_end = next_start + timedelta(days=profile.period_length - 1)
    predicted_dates = generate_continuous_dates(next_start, next_end, year, month)

    print(f"stage2调试: 预测日期: {predicted_dates}")

    return predicted_dates, []


def stage3_weighted_trend(records, profile, year, month):
    """
    阶段3：加权移动平均 + 趋势调整
    适用于6-10条记录的用户
    """
    if len(records) < 3:
        return stage2_moving_average(records, profile, year, month)

    # 计算周期长度
    cycle_lengths = []
    for i in range(1, len(records)):
        prev_start = records[i].start_date
        curr_start = records[i - 1].start_date
        days_between = (curr_start - prev_start).days
        if 15 <= days_between <= 45:
            cycle_lengths.append((days_between, i))  # 保存周期长度和索引

    if not cycle_lengths:
        return stage2_moving_average(records, profile, year, month)

    # 加权平均：近期的周期权重更高
    weights = []
    weighted_sum = 0
    total_weight = 0

    for i, (cycle_len, idx) in enumerate(cycle_lengths):
        # 权重：最近的周期权重最高 (指数衰减)
        weight = 0.5 ** (len(cycle_lengths) - i - 1)
        weights.append(weight)
        weighted_sum += cycle_len * weight
        total_weight += weight

    avg_cycle_length = weighted_sum / total_weight

    # 趋势检测：最近3个周期 vs 前3个周期
    if len(cycle_lengths) >= 6:
        recent_avg = sum(cycle_len for cycle_len, _ in cycle_lengths[:3]) / 3
        earlier_avg = sum(cycle_len for cycle_len, _ in cycle_lengths[3:6]) / 3
        trend = recent_avg - earlier_avg

        # 趋势调整：如果趋势明显，进行微调
        if abs(trend) >= 2:  # 趋势明显（变化≥2天）
            trend_adjustment = trend * 0.3  # 调整幅度为趋势的30%
            avg_cycle_length += trend_adjustment

    # 使用最近一次经期开始日期进行预测
    latest_record = records[0]
    next_start = latest_record.start_date + timedelta(days=int(avg_cycle_length))

    # 确保预测日期是未来的
    today = timezone.now().date()
    while next_start <= today:
        next_start += timedelta(days=avg_cycle_length)

    # 计算预测周期的结束日期
    next_end = next_start + timedelta(days=profile.period_length - 1)

    # 计算下个周期
    next_next_start = next_start + timedelta(days=avg_cycle_length)
    next_next_end = next_next_start + timedelta(days=profile.period_length - 1)

    # 生成连续的预测日期
    predicted_dates = generate_continuous_dates(next_start, next_end, year, month)
    next_prediction_dates = generate_continuous_dates(next_next_start, next_next_end, year, month)

    return predicted_dates, next_prediction_dates


def stage4_lightgbm_prediction(records, profile, year, month):
    """
    阶段4：LightGBM机器学习预测
    适用于10条以上记录的用户

    注意：这是简化版本，实际使用时需要训练数据和模型
    """
    # 如果没有足够数据，回退到阶段3
    if len(records) < 10:
        return stage3_weighted_trend(records, profile, year, month)

    try:
        # 提取特征
        features = extract_features_for_ml(records)

        # 这里应该是调用训练好的LightGBM模型
        # 由于我们没有实际训练模型，这里使用增强的加权平均作为替代

        # 使用更复杂加权和趋势检测
        cycle_lengths = []
        for i in range(1, min(12, len(records))):  # 最多使用12个周期
            prev_start = records[i].start_date
            curr_start = records[i - 1].start_date
            days_between = (curr_start - prev_start).days
            if 15 <= days_between <= 45:
                cycle_lengths.append((days_between, i))

        if not cycle_lengths:
            return stage3_weighted_trend(records, profile, year, month)

        # 复杂加权：近期权重更高，且考虑波动性
        weights = []
        weighted_sum = 0
        total_weight = 0

        for i, (cycle_len, idx) in enumerate(cycle_lengths):
            # 更复杂的权重计算
            weight = 0.7 ** (len(cycle_lengths) - i - 1)  # 衰减更慢
            weights.append(weight)
            weighted_sum += cycle_len * weight
            total_weight += weight

        avg_cycle_length = weighted_sum / total_weight

        # 高级趋势检测
        if len(cycle_lengths) >= 4:
            # 使用线性回归检测趋势
            x = list(range(len(cycle_lengths)))
            y = [cycle_len for cycle_len, _ in cycle_lengths]

            # 简单线性趋势计算
            n = len(x)
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(x[i] * y[i] for i in range(n))
            sum_x2 = sum(xi * xi for xi in x)

            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)

            # 根据趋势调整预测
            trend_adjustment = slope * len(cycle_lengths) * 0.5
            avg_cycle_length += trend_adjustment

        # 季节性调整（简单版本）
        current_month = datetime.now().month
        seasonal_adjustment = calculate_seasonal_adjustment(current_month)
        avg_cycle_length += seasonal_adjustment

        # 使用最近一次经期开始日期进行预测
        latest_record = records[0]
        next_start = latest_record.start_date + timedelta(days=int(avg_cycle_length))

        # 确保预测日期是未来的
        today = timezone.now().date()
        while next_start <= today:
            next_start += timedelta(days=avg_cycle_length)

        # 计算预测周期的结束日期
        next_end = next_start + timedelta(days=profile.period_length - 1)

        # 计算下个周期
        next_next_start = next_start + timedelta(days=avg_cycle_length)
        next_next_end = next_next_start + timedelta(days=profile.period_length - 1)

        # 生成连续的预测日期
        predicted_dates = generate_continuous_dates(next_start, next_end, year, month)
        next_prediction_dates = generate_continuous_dates(next_next_start, next_next_end, year, month)

        return predicted_dates, next_prediction_dates

    except Exception as e:
        # 如果机器学习预测失败，回退到阶段3
        print(f"LightGBM预测失败，回退到阶段3: {e}")
        return stage3_weighted_trend(records, profile, year, month)


def generate_continuous_dates(start_date, end_date, year, month):
    """
    生成从开始到结束的连续日期列表
    确保生成连续的日期，如您图片中显示的24-28日
    """
    dates = []
    current_date = start_date

    # 目标月份范围
    target_start = datetime(year, month, 1).date()
    if month == 12:
        target_end = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        target_end = datetime(year, month + 1, 1).date() - timedelta(days=1)

    # 生成连续日期，但只包含在目标月份内的
    while current_date <= end_date:
        if target_start <= current_date <= target_end:
            dates.append(current_date)
        current_date += timedelta(days=1)

    return dates


def extract_features_for_ml(records):
    """
    为机器学习模型提取特征
    """
    features = {}

    if len(records) < 2:
        return features

    # 基础统计特征
    cycle_lengths = []
    for i in range(1, min(12, len(records))):
        prev_start = records[i].start_date
        curr_start = records[i - 1].start_date
        days_between = (curr_start - prev_start).days
        if 15 <= days_between <= 45:
            cycle_lengths.append(days_between)

    if cycle_lengths:
        features['recent_3_avg'] = np.mean(cycle_lengths[:3]) if len(cycle_lengths) >= 3 else np.mean(cycle_lengths)
        features['recent_6_avg'] = np.mean(cycle_lengths[:6]) if len(cycle_lengths) >= 6 else np.mean(cycle_lengths)
        features['std_dev'] = np.std(cycle_lengths)
        features['max_cycle'] = max(cycle_lengths)
        features['min_cycle'] = min(cycle_lengths)
        features['last_cycle'] = cycle_lengths[0] if cycle_lengths else 28

    # 趋势特征
    if len(cycle_lengths) >= 4:
        recent_avg = np.mean(cycle_lengths[:3])
        earlier_avg = np.mean(cycle_lengths[3:6]) if len(cycle_lengths) >= 6 else np.mean(cycle_lengths[3:])
        features['trend'] = recent_avg - earlier_avg

    # 季节性特征
    current_month = datetime.now().month
    features['month'] = current_month
    features['season'] = (current_month % 12) // 3 + 1  # 1-4季度

    return features


def calculate_seasonal_adjustment(month):
    """
    简单的季节性调整
    基于月份对周期长度进行微调
    """
    # 简单季节性调整表（可根据实际数据调整）
    seasonal_adjustments = {
        1: 0.5,  # 1月：略微延长
        2: 0.3,  # 2月
        3: 0.0,  # 3月：无调整
        4: -0.2,  # 4月：略微缩短
        5: -0.3,  # 5月
        6: -0.5,  # 6月
        7: -0.3,  # 7月
        8: 0.0,  # 8月
        9: 0.2,  # 9月
        10: 0.4,  # 10月
        11: 0.5,  # 11月
        12: 0.3  # 12月
    }

    return seasonal_adjustments.get(month, 0.0)