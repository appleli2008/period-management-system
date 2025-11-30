from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
from .models import PeriodRecord, UserProfile, PeriodPrediction
from .predictor import get_three_stage_predictions  # 导入新的预测函数
import calendar as cal
import json


def index(request):
    """首页 - 使用三阶段预测算法"""
    # 检查用户是否已登录但未设置基础信息
    if request.user.is_authenticated:
        try:
            profile = UserProfile.objects.get(user=request.user)
        except UserProfile.DoesNotExist:
            return redirect('set_profile')

    # 获取当前日期
    today = timezone.now().date()
    year = request.GET.get('year', today.year)
    month = request.GET.get('month', today.month)

    # 验证年份和月份参数
    try:
        year = int(year)
        month = int(month)
        if month < 1 or month > 12:
            year = today.year
            month = today.month
    except (ValueError, TypeError):
        year = today.year
        month = today.month

    # 生成日历数据
    calendar_data = generate_calendar(year, month)

    # 如果用户已登录，获取经期记录和预测
    period_dates = []
    period_records = []
    current_prediction_dates = []
    next_prediction_dates = []

    if request.user.is_authenticated:
        try:
            profile = UserProfile.objects.get(user=request.user)
            # 获取用户的经期记录（未删除的）
            records = PeriodRecord.objects.filter(user=request.user, is_deleted=False)
            period_records = list(records.order_by('-start_date'))

            # 获取实际经期日期
            for record in records:
                current_date = record.start_date
                while current_date <= record.end_date:
                    period_info = {
                        'date': current_date,
                        'is_predicted': record.is_predicted,
                        'is_confirmed': not record.is_predicted
                    }
                    period_dates.append(period_info)
                    current_date += timedelta(days=1)

            # 使用三阶段预测算法
            if records.exists() and profile.cycle_length and profile.period_length:
                current_prediction_dates, next_prediction_dates = get_three_stage_predictions(
                    user=request.user,
                    records=period_records,
                    profile=profile,
                    year=year,
                    month=month
                )

                print(f"=== 视图层预测结果 ===")
                print(f"目标月份: {year}年{month}月")
                print(f"当前预测天数: {len(current_prediction_dates)}")
                print(f"下次预测天数: {len(next_prediction_dates)}")

        except UserProfile.DoesNotExist:
            print("用户没有基础信息，跳过预测")
            pass

    # 标记日历中的日期状态
    for week in calendar_data:
        for day in week:
            if day['date']:
                # 重置状态
                day.update({
                    'is_period': False,
                    'is_predicted_period': False,
                    'is_confirmed_period': False,
                    'is_current_prediction': False,
                    'is_next_prediction': False,
                    'is_today': day['date'] == today,
                    'is_future': day['date'] > today
                })

                # 检查是否是实际经期
                for period_info in period_dates:
                    if day['date'] == period_info['date']:
                        day['is_period'] = True
                        day['is_predicted_period'] = period_info['is_predicted']
                        day['is_confirmed_period'] = period_info['is_confirmed']
                        break

                # 检查是否是当前预测周期
                for pred_date in current_prediction_dates:
                    if day['date'] == pred_date:
                        day['is_current_prediction'] = True
                        break

                # 检查是否是下次预测周期
                for next_pred_date in next_prediction_dates:
                    if day['date'] == next_pred_date:
                        day['is_next_prediction'] = True
                        break

    # 计算上下月导航
    if month == 1:
        prev_year, prev_month = year - 1, 12
        next_year, next_month = year, 2
    elif month == 12:
        prev_year, prev_month = year, 11
        next_year, next_month = year + 1, 1
    else:
        prev_year, prev_month = year, month - 1
        next_year, next_month = year, month + 1

    # 准备上下文数据
    context = {
        'calendar_data': calendar_data,
        'current_year': year,
        'current_month': month,
        'month_name': cal.month_name[month],
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'period_records': period_records,
        'today': today,
        'range_15_23': list(range(15, 24)),
        'range_24_32': list(range(24, 33)),
        'range_33_41': list(range(33, 42)),
        'range_42_45': list(range(42, 46)),
        'range_1_10': list(range(1, 11)),
    }

    # 如果用户已登录，添加用户信息到上下文
    if request.user.is_authenticated:
        try:
            context['user_profile'] = UserProfile.objects.get(user=request.user)
        except UserProfile.DoesNotExist:
            pass

    return render(request, 'index.html', context)


def get_dynamic_predictions(user, records, profile, year, month):
    """
    最终修复版：集成验证和调试
    """
    print(f"=== 智能预测计算开始 ===")

    # 首先验证预测方法
    cycle_count = validate_prediction_method(records)

    # 获取实际记录
    actual_records = [r for r in records if not r.is_predicted]
    sorted_actual = sorted(actual_records, key=lambda x: x.start_date)

    if not actual_records:
        return [], []

    latest_record = sorted_actual[-1]
    reference_date = latest_record.end_date

    # 根据周期数量选择方法
    if cycle_count < 3:
        # 固定间隔方法
        cycle_length = profile.cycle_length
        method_note = f"固定间隔（{cycle_count}个周期）"
        print(f"🎯 使用方法: {method_note}")
    else:
        # 加权平均方法
        cycle_length = calculate_weighted_average_cycle(sorted_actual)
        method_note = f"加权平均（基于{cycle_count}个周期）"
        print(f"🎯 使用方法: {method_note}")

    # 计算预测
    period_length = profile.period_length
    prediction_start = reference_date + timedelta(days=cycle_length)
    prediction_end = prediction_start + timedelta(days=period_length - 1)

    print(f"🔮 最终预测: {prediction_start} 至 {prediction_end}")
    print(f"📝 方法说明: {method_note}")

    # 生成日期
    predicted_dates = generate_dates_in_month(prediction_start, prediction_end, year, month)
    print(f"✅ 在目标月份内的预测天数: {len(predicted_dates)}")

    return predicted_dates, []

def calculate_weighted_average_cycle(records):
    """
    计算加权平均周期长度
    近期周期权重更高
    """
    print(f"=== 加权平均计算开始 ===")

    # 确保记录按时间排序
    sorted_records = sorted(records, key=lambda x: x.start_date)

    if len(sorted_records) < 2:
        print("❌ 需要至少2个记录才能计算周期")
        return 28  # 默认值

    # 计算每个周期长度
    cycle_lengths = []
    for i in range(1, len(sorted_records)):
        prev_start = sorted_records[i - 1].start_date
        curr_start = sorted_records[i].start_date
        days_between = (curr_start - prev_start).days

        # 只保留合理范围的周期（15-45天）
        if 15 <= days_between <= 45:
            cycle_lengths.append(days_between)
            print(f"周期{i}: {prev_start} 到 {curr_start} = {days_between}天")

    if not cycle_lengths:
        print("❌ 无有效周期数据")
        return 28  # 默认值

    print(f"有效周期数据: {cycle_lengths}")

    # 如果周期数量少于2个，使用简单平均
    if len(cycle_lengths) < 2:
        avg_cycle = sum(cycle_lengths) / len(cycle_lengths)
        print(f"周期数不足，使用简单平均: {avg_cycle:.1f}天")
        return int(round(avg_cycle))

    # 加权平均计算：近期周期权重更高
    weights = []
    n = len(cycle_lengths)

    # 指数衰减权重：最近的数据权重最高
    for i in range(n):
        # 权重衰减因子：0.7^(n-i-1)
        weight = 0.7 ** (n - i - 1)
        weights.append(weight)
        print(f"周期{i + 1}权重: {weight:.3f}")

    # 归一化权重
    total_weight = sum(weights)
    normalized_weights = [w / total_weight for w in weights]

    # 计算加权平均
    weighted_sum = 0
    for length, weight in zip(cycle_lengths, normalized_weights):
        weighted_sum += length * weight
        print(f"周期{length}天 × 权重{weight:.3f} = {length * weight:.2f}")

    weighted_avg = weighted_sum
    cycle_length = int(round(weighted_avg))

    # 限制在合理范围内
    cycle_length = max(20, min(60, cycle_length))

    print(f"📊 加权平均计算: {weighted_avg:.2f} → {cycle_length}天")
    print(f"📈 最终周期长度: {cycle_length}天")

    return cycle_length


def validate_prediction_stage(records):
    """
    验证预测阶段是否正确
    """
    actual_records = [r for r in records if not r.is_predicted]
    cycle_count = len(actual_records) - 1

    stages = {
        (0, 2): ("阶段1", "固定周期"),
        (3, 5): ("阶段2", "加权平均"),
        (6, float('inf')): ("阶段3", "GRU神经网络")
    }

    for (min_cycle, max_cycle), (stage, method) in stages.items():
        if min_cycle <= cycle_count <= max_cycle:
            return stage, method, cycle_count

    return "未知", "未知", cycle_count


    # 在预测函数中添加验证
    stage, method, cycle_count = validate_prediction_stage(records)
    print(f"✅ 预测阶段验证: {stage} - {method} (周期数: {cycle_count})")

def mark_calendar_dates(calendar_data, records, current_prediction_dates, next_prediction_dates, year, month):
    """
    关键函数：正确标记日历日期，确保颜色显示不消失
    保持与index.html模板完全兼容的数据结构
    """
    print("=== 开始标记日历日期 ===")

    # 准备经期日期列表
    period_dates = []
    for record in records:
        current_date = record.start_date
        while current_date <= record.end_date:
            period_dates.append({
                'date': current_date,
                'is_predicted': record.is_predicted,
                'is_confirmed': not record.is_predicted
            })
            current_date += timedelta(days=1)

    print(f"经期日期数量: {len(period_dates)}")
    print(f"当前预测日期数量: {len(current_prediction_dates)}")
    print(f"下次预测日期数量: {len(next_prediction_dates)}")

    today = timezone.now().date()
    marked_calendar_data = []

    # 标记每个日期
    for week_index, week in enumerate(calendar_data):
        marked_week = []
        for day_index, day in enumerate(week):
            marked_day = day.copy()  # 复制原始数据

            if marked_day['date']:
                # 重置所有标记
                marked_day.update({
                    'is_period': False,
                    'is_predicted_period': False,
                    'is_confirmed_period': False,
                    'is_current_prediction': False,
                    'is_next_prediction': False,
                    'is_today': marked_day['date'] == today,
                    'is_future': marked_day['date'] > today
                })

                # 标记经期日期（最高优先级）
                for period_info in period_dates:
                    if marked_day['date'] == period_info['date']:
                        marked_day['is_period'] = True
                        marked_day['is_predicted_period'] = period_info['is_predicted']
                        marked_day['is_confirmed_period'] = period_info['is_confirmed']
                        break

                # 如果不是经期，标记预测日期
                if not marked_day['is_period']:
                    # 标记当前预测
                    for pred_date in current_prediction_dates:
                        if marked_day['date'] == pred_date:
                            marked_day['is_current_prediction'] = True
                            break

                    # 标记下次预测
                    if not marked_day['is_current_prediction']:
                        for next_pred_date in next_prediction_dates:
                            if marked_day['date'] == next_pred_date:
                                marked_day['is_next_prediction'] = True
                                break

            marked_week.append(marked_day)
        marked_calendar_data.append(marked_week)

    # 调试：统计标记结果
    period_count = sum(1 for week in marked_calendar_data for day in week
                       if day.get('is_period'))
    current_pred_count = sum(1 for week in marked_calendar_data for day in week
                             if day.get('is_current_prediction'))
    next_pred_count = sum(1 for week in marked_calendar_data for day in week
                          if day.get('is_next_prediction'))

    print(f"标记完成 - 经期: {period_count}, 当前预测: {current_pred_count}, 下次预测: {next_pred_count}")

    return marked_calendar_data

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


def generate_predictions(user, profile, year, month):
    """
    生成经期预测
    """
    predicted_dates = []  # 当前预测周期
    next_prediction_dates = []  # 下一次预测周期

    if not profile.cycle_length or not profile.period_length:
        return predicted_dates, next_prediction_dates

    # 获取用户最近的经期记录
    latest_records = PeriodRecord.objects.filter(
        user=user,
        is_deleted=False
    ).order_by('-start_date')

    if not latest_records.exists():
        return predicted_dates, next_prediction_dates

    # 获取最近的确认记录
    confirmed_records = latest_records.filter(is_predicted=False)
    if confirmed_records.exists():
        latest_confirmed = confirmed_records[0]
    else:
        # 如果没有确认记录，使用最近的预测记录
        latest_confirmed = latest_records[0]

    cycle_length = profile.cycle_length
    period_length = profile.period_length

    # 从结束日期开始计算间隔
    current_prediction_start = latest_confirmed.end_date + timedelta(days=cycle_length)
    current_prediction_end = current_prediction_start + timedelta(days=period_length - 1)

    # 下一次预测周期
    next_prediction_start = current_prediction_start + timedelta(days=cycle_length)
    next_prediction_end = next_prediction_start + timedelta(days=period_length - 1)

    # 检查预测周期是否在当前月份内
    current_month_start = datetime(year, month, 1).date()
    if month == 12:
        current_month_end = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        current_month_end = datetime(year, month + 1, 1).date() - timedelta(days=1)

    # 添加当前预测周期的日期
    if not (current_prediction_end < current_month_start or current_prediction_start > current_month_end):
        start_date = max(current_prediction_start, current_month_start)
        end_date = min(current_prediction_end, current_month_end)

        current_date = start_date
        while current_date <= end_date:
            predicted_dates.append(current_date)
            current_date += timedelta(days=1)

    # 添加下一次预测周期的日期
    if not (next_prediction_end < current_month_start or next_prediction_start > current_month_end):
        start_date = max(next_prediction_start, current_month_start)
        end_date = min(next_prediction_end, current_month_end)

        current_date = start_date
        while current_date <= end_date:
            next_prediction_dates.append(current_date)
            current_date += timedelta(days=1)

    return predicted_dates, next_prediction_dates


def generate_calendar(year, month):
    """生成日历数据"""
    cal_obj = cal.Calendar(firstweekday=6)
    month_days = cal_obj.monthdatescalendar(year, month)

    calendar_data = []
    today = timezone.now().date()

    for week in month_days:
        week_data = []
        for date in week:
            day_data = {
                'date': date,
                'day': date.day,
                'current_month': date.month == month,
                'is_period': False,
                'is_predicted': False,
                'is_current_prediction': False,
                'is_next_prediction': False,
                'is_today': date == today,
                'is_future': date > today
            }
            week_data.append(day_data)
        calendar_data.append(week_data)

    return calendar_data


def period_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        # 验证邮箱格式
        if not email or '@' not in email:
            return render(request, 'period_login.html', {
                'error': '请输入有效的邮箱地址',
                'email': email
            })

        # 查找用户并验证
        try:
            user = User.objects.get(email=email)  # 问题在这里
            if user.check_password(password):
                login(request, user)
                return redirect('index')
            else:
                return render(request, 'period_login.html', {
                    'error': '密码错误',
                    'email': email
                })
        except User.DoesNotExist:
            return render(request, 'period_login.html', {
                'error': '该邮箱未注册',
                'email': email
            })

    return render(request, 'period_login.html')


def period_register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        # 修复：注册时也进行大小写规范化
        email_normalized = email.lower().strip()  # 转换为小写并去除空格

        # 验证邮箱是否已存在（大小写不敏感）
        if User.objects.filter(email__iexact=email_normalized).exists():
            return render(request, 'period_register.html', {
                'error': '该邮箱已被注册',
                'username': username,
                'email': email
            })

        # 验证密码是否匹配
        if password != confirm_password:
            return render(request, 'period_register.html', {
                'error': '两次输入的密码不一致',
                'username': username,
                'email': email
            })

        # 创建用户（使用规范化的邮箱）
        try:
            user = User.objects.create_user(
                username=username,
                email=email_normalized,  # 使用规范化的邮箱
                password=password
            )
            user.save()

            # 登录用户
            login(request, user)

            # 重定向到设置基础信息页面
            return redirect('set_profile')
        except Exception as e:
            return render(request, 'period_register.html', {
                'error': '注册失败，请稍后重试',
                'username': username,
                'email': email
            })

    return render(request, 'period_register.html')


def period_logout(request):
    logout(request)
    return redirect('index')


@login_required
def set_profile(request):
    """设置用户基础信息 - 修复版本"""
    # 检查用户是否已有基础信息
    try:
        profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        profile = None

    # 创建15-45的范围列表
    range_15_45 = list(range(15, 46))  # 15到45（包含45）

    if request.method == 'POST':
        cycle_length = request.POST.get('cycle_length')
        period_length = request.POST.get('period_length')

        # 验证数据
        try:
            cycle_length = int(cycle_length)
            period_length = int(period_length)

            if cycle_length not in range_15_45:
                return render(request, 'set_profile.html', {
                    'error': '月经间隔天数必须在15-45天之间',
                    'cycle_length': cycle_length,
                    'period_length': period_length,
                    'profile': profile,
                    'range_15_45': range_15_45  # 传递范围到模板
                })

            if not (1 <= period_length <= 10):
                return render(request, 'set_profile.html', {
                    'error': '经期持续天数必须在1-10天之间',
                    'cycle_length': cycle_length,
                    'period_length': period_length,
                    'profile': profile,
                    'range_15_45': range_15_45
                })

            # 保存或更新用户基础信息
            if profile:
                profile.cycle_length = cycle_length
                profile.period_length = period_length
                profile.save()
            else:
                profile = UserProfile.objects.create(
                    user=request.user,
                    cycle_length=cycle_length,
                    period_length=period_length
                )

            return redirect('index')
        except ValueError:
            return render(request, 'set_profile.html', {
                'error': '请输入有效的数字',
                'cycle_length': cycle_length,
                'period_length': period_length,
                'profile': profile,
                'range_15_45': range_15_45
            })

    return render(request, 'set_profile.html', {
        'profile': profile,
        'range_15_45': range_15_45
    })


@login_required
def set_profile_ajax(request):
    """通过AJAX设置基础信息"""
    if request.method == 'POST':
        cycle_length = request.POST.get('cycle_length')
        period_length = request.POST.get('period_length')

        try:
            cycle_length = int(cycle_length)
            period_length = int(period_length)

            if not (15 <= cycle_length <= 45):
                return JsonResponse({
                    'success': False,
                    'message': '月经间隔天数必须在15-45天之间'
                })

            if not (1 <= period_length <= 10):
                return JsonResponse({
                    'success': False,
                    'message': '经期持续天数必须在1-10天之间'
                })

            # 保存或更新用户基础信息
            try:
                profile = UserProfile.objects.get(user=request.user)
                profile.cycle_length = cycle_length
                profile.period_length = period_length
                profile.save()
            except UserProfile.DoesNotExist:
                profile = UserProfile.objects.create(
                    user=request.user,
                    cycle_length=cycle_length,
                    period_length=period_length
                )

            return JsonResponse({'success': True, 'message': '基础信息保存成功'})
        except ValueError:
            return JsonResponse({'success': False, 'message': '请输入有效的数字'})

    return JsonResponse({'success': False, 'message': '无效请求'})


@login_required
def get_period_info(request):
    """获取日期相关的经期信息 - 修复版本"""
    if request.method == 'GET':
        date_str = request.GET.get('date')

        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            user = request.user

            # 检查是否可以开始新的经期
            is_start_possible = True

            # 检查是否已有包含该日期的经期记录
            existing_records = PeriodRecord.objects.filter(
                user=user,
                start_date__lte=date,
                end_date__gte=date,
                is_deleted=False
            )

            if existing_records.exists():
                is_start_possible = False

            # 查找可以标记结束的经期记录
            # 条件：开始日期在过去14天内，且是预测状态或结束日期在今天之后
            end_candidate_records = []
            fourteen_days_ago = date - timedelta(days=14)

            records_for_end = PeriodRecord.objects.filter(
                user=user,
                start_date__gte=fourteen_days_ago,
                start_date__lte=date,
                is_deleted=False
            )

            for record in records_for_end:
                # 允许调整任何在14天内的记录
                end_candidate_records.append({
                    'id': record.id,
                    'start_date': record.start_date.strftime('%Y-%m-%d'),
                    'current_end_date': record.end_date.strftime('%Y-%m-%d'),
                    'is_predicted': record.is_predicted,
                    'can_adjust': True  # 所有记录都可以调整
                })

            return JsonResponse({
                'success': True,
                'date': date_str,
                'is_start_possible': is_start_possible,
                'end_candidate_records': end_candidate_records
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': '无效请求'})


@login_required
def adjust_period(request):
    """调整经期记录 - 新功能：允许调整任何经期记录"""
    if request.method == 'POST':
        record_id = request.POST.get('record_id')
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        action = request.POST.get('action')  # 'start', 'end', 或 'both'

        try:
            record = PeriodRecord.objects.get(id=record_id, user=request.user)

            if action == 'start' and start_date_str:
                new_start = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                if new_start > record.end_date:
                    return JsonResponse({
                        'success': False,
                        'message': '开始日期不能晚于结束日期'
                    })
                record.start_date = new_start

            elif action == 'end' and end_date_str:
                new_end = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                if new_end < record.start_date:
                    return JsonResponse({
                        'success': False,
                        'message': '结束日期不能早于开始日期'
                    })
                record.end_date = new_end
                record.is_predicted = False  # 标记为已确认

            elif action == 'both' and start_date_str and end_date_str:
                new_start = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                new_end = datetime.strptime(end_date_str, '%Y-%m-%d').date()

                if new_start > new_end:
                    return JsonResponse({
                        'success': False,
                        'message': '开始日期不能晚于结束日期'
                    })

                record.start_date = new_start
                record.end_date = new_end
                record.is_predicted = False

            else:
                return JsonResponse({
                    'success': False,
                    'message': '无效的操作或日期'
                })

            record.save()

            return JsonResponse({
                'success': True,
                'message': '经期记录已成功调整',
                'start_date': record.start_date.strftime('%Y-%m-%d'),
                'end_date': record.end_date.strftime('%Y-%m-%d')
            })
        except PeriodRecord.DoesNotExist:
            return JsonResponse({'success': False, 'message': '记录不存在'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': '无效请求'})


@login_required
def add_period_start(request):
    """标记经期开始 - 增强版，触发GRU模型训练"""
    if request.method == 'POST':
        start_date_str = request.POST.get('start_date')

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            user = request.user
            profile = UserProfile.objects.get(user=user)

            # 计算预测结束日期
            period_length = profile.period_length
            predicted_end_date = start_date + timedelta(days=period_length - 1)

            # 创建经期记录
            period = PeriodRecord.objects.create(
                user=user,
                start_date=start_date,
                end_date=predicted_end_date,
                is_predicted=False
            )

            # 检查是否需要训练GRU模型
            try:
                records = PeriodRecord.objects.filter(
                    user=user,
                    is_deleted=False
                ).order_by('start_date')

                actual_records = [r for r in records if not r.is_predicted]
                cycle_count = len(actual_records) - 1

                # 当周期数达到7个时训练GRU模型
                if cycle_count >= 7:
                    print(f"🤖 触发GRU模型训练，周期数: {cycle_count}")
                    from .predictor import gru_predictor
                    success = gru_predictor.train_model(user.id, actual_records)
                    if success:
                        print("✅ GRU模型训练完成")
                    else:
                        print("❌ GRU模型训练失败")

            except Exception as e:
                print(f"GRU模型训练跳过: {e}")

            return JsonResponse({
                'success': True,
                'message': '经期开始标记成功！',
                'start_date': start_date_str,
                'end_date': predicted_end_date.strftime('%Y-%m-%d')
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': '无效请求'})


def update_predictions(user, confirmed_start_date):
    """更新预测记录 - 当用户确认经期开始时调用"""
    try:
        profile = UserProfile.objects.get(user=user)
        cycle_length = profile.cycle_length
        period_length = profile.period_length

        # 计算新的预测
        next_prediction_start = confirmed_start_date + timedelta(days=cycle_length)
        next_prediction_end = next_prediction_start + timedelta(days=period_length - 1)

        # 这里可以保存预测记录到数据库，用于历史跟踪
        # 当前实现中，预测是实时计算的，所以不需要保存

    except UserProfile.DoesNotExist:
        # 用户没有基础信息，无法更新预测
        pass


# 在views.py中找到预测相关函数，修改如下：

@login_required
def get_prediction_info(request):
    """获取预测信息 - 修改为从经期结束日开始计算"""
    if request.method == 'GET':
        try:
            user = request.user
            profile = UserProfile.objects.get(user=user)

            # 获取最近的经期记录
            latest_records = PeriodRecord.objects.filter(
                user=user,
                is_deleted=False
            ).order_by('-start_date')

            predictions = []

            if latest_records.exists():
                # 获取最近的确认记录
                confirmed_records = latest_records.filter(is_predicted=False)
                if confirmed_records.exists():
                    latest_confirmed = confirmed_records[0]
                else:
                    latest_confirmed = latest_records[0]

                cycle_length = profile.cycle_length
                period_length = profile.period_length

                # 修改：从结束日期开始计算间隔
                # 原逻辑：prediction_start = latest_confirmed.start_date + timedelta(days=cycle_length)
                # 新逻辑：从经期结束日开始计算
                prediction_start = latest_confirmed.end_date + timedelta(days=cycle_length)
                prediction_end = prediction_start + timedelta(days=period_length - 1)

                predictions.append({
                    'cycle': 1,
                    'start_date': prediction_start.strftime('%Y-%m-%d'),
                    'end_date': prediction_end.strftime('%Y-%m-%d'),
                    'is_current': True,
                    'calculation_note': f"基于{latest_confirmed.end_date}结束 + {cycle_length}天间隔"
                })

                # 可以继续生成更多预测周期
                for i in range(2, 4):  # 生成2-3个额外周期
                    next_prediction_start = prediction_start + timedelta(days=cycle_length * (i - 1))
                    next_prediction_end = next_prediction_start + timedelta(days=period_length - 1)

                    predictions.append({
                        'cycle': i,
                        'start_date': next_prediction_start.strftime('%Y-%m-%d'),
                        'end_date': next_prediction_end.strftime('%Y-%m-%d'),
                        'is_current': False
                    })

            return JsonResponse({
                'success': True,
                'predictions': predictions,
                'cycle_length': profile.cycle_length,
                'period_length': profile.period_length,
                'calculation_method': '从经期结束日开始计算间隔'
            })
        except UserProfile.DoesNotExist:
            return JsonResponse({'success': False, 'message': '请先设置基础信息'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': '无效请求'})


@login_required
def add_period_end(request):
    """标记经期结束 - 修复版本，允许灵活设置结束日期"""
    if request.method == 'POST':
        # 支持两种方式：通过记录ID或通过开始日期查找
        record_id = request.POST.get('record_id')
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')

        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            user = request.user

            # 查找要更新的记录
            if record_id:
                # 方式1：通过记录ID查找
                record = PeriodRecord.objects.get(id=record_id, user=user)
            elif start_date_str:
                # 方式2：通过开始日期查找最近的记录
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                # 查找开始日期在最近30天内的记录
                records = PeriodRecord.objects.filter(
                    user=user,
                    start_date__gte=start_date - timedelta(days=30),
                    start_date__lte=start_date + timedelta(days=1),
                    is_deleted=False
                ).order_by('-start_date')

                if records.exists():
                    record = records[0]  # 取最近的记录
                else:
                    return JsonResponse({
                        'success': False,
                        'message': '未找到对应的经期记录'
                    })
            else:
                return JsonResponse({
                    'success': False,
                    'message': '请提供记录ID或开始日期'
                })

            # 验证结束日期是否合理
            if end_date < record.start_date:
                return JsonResponse({
                    'success': False,
                    'message': '结束日期不能早于开始日期'
                })

            if end_date > record.start_date + timedelta(days=14):  # 最多14天
                return JsonResponse({
                    'success': False,
                    'message': '经期持续时间过长，请检查日期'
                })

            # 更新记录
            record.end_date = end_date
            record.is_predicted = False  # 标记为已确认
            record.save()

            return JsonResponse({
                'success': True,
                'message': '经期结束日期已成功更新',
                'start_date': record.start_date.strftime('%Y-%m-%d'),
                'end_date': end_date_str
            })
        except PeriodRecord.DoesNotExist:
            return JsonResponse({'success': False, 'message': '记录不存在'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': '无效请求'})


@login_required
def delete_period(request, record_id):
    """删除经期记录（软删除）"""
    if request.method == 'POST':
        try:
            record = PeriodRecord.objects.get(id=record_id, user=request.user)
            record.is_deleted = True
            record.save()
            return JsonResponse({'success': True, 'message': '记录删除成功'})
        except PeriodRecord.DoesNotExist:
            return JsonResponse({'success': False, 'message': '记录不存在'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': '无效请求'})


@login_required
def period_edit(request):
    """编辑用户信息"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')

        # 检查邮箱是否已被其他用户使用
        if User.objects.filter(email=email).exclude(id=request.user.id).exists():
            return render(request, 'period_edit.html', {
                'error': '该邮箱已被其他用户使用',
                'username': username,
                'email': request.user.email
            })

        # 更新用户信息
        user = request.user
        user.username = username
        user.email = email
        user.save()

        return redirect('index')

    # GET请求时显示当前用户信息
    return render(request, 'period_edit.html', {
        'username': request.user.username,
        'email': request.user.email
    })


@login_required
def period_delete(request):
    """删除用户账户"""
    if request.method == 'POST':
        request.user.delete()
        logout(request)
        return redirect('index')

    return render(request, 'period_delete.html')


@login_required
def period_delete(request):
    """删除账户页面 - 修复密码验证"""
    if request.method == 'POST':
        # 获取表单数据
        password = request.POST.get('password', '').strip()

        # 验证密码
        if not password:
            return render(request, 'period_delete.html', {
                'error': '请输入密码确认删除操作'
            })

        # 验证密码是否正确
        user = request.user
        if not authenticate(username=user.username, password=password):
            return render(request, 'period_delete.html', {
                'error': '密码错误，请重新输入'
            })

        # 执行删除操作
        try:
            username = user.username
            user.delete()
            logout(request)

            # 删除成功，重定向到首页
            return redirect('index')
        except Exception as e:
            return render(request, 'period_delete.html', {
                'error': f'删除失败: {str(e)}'
            })

    # GET请求，显示删除页面
    return render(request, 'period_delete.html')


# 或者如果是AJAX方式，使用这个版本：
@login_required
def period_delete_ajax(request):
    """AJAX方式删除账户"""
    if request.method == 'POST':
        password = request.POST.get('password', '').strip()

        if not password:
            return JsonResponse({
                'success': False,
                'message': '请输入密码确认删除操作'
            })

        user = request.user
        if not authenticate(username=user.username, password=password):
            return JsonResponse({
                'success': False,
                'message': '密码错误，删除操作已取消'
            })

        try:
            user.delete()
            logout(request)
            return JsonResponse({
                'success': True,
                'message': '账户已成功删除'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'删除失败: {str(e)}'
            })

    return JsonResponse({
        'success': False,
        'message': '无效的请求方法'
    })
