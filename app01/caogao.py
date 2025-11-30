from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
import calendar as cal
from .models import PeriodRecord, UserProfile
from .predictor import get_three_stage_predictions  # 导入新的预测函数


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
    }

    # 如果用户已登录，添加用户信息到上下文
    if request.user.is_authenticated:
        try:
            context['user_profile'] = UserProfile.objects.get(user=request.user)
        except UserProfile.DoesNotExist:
            pass

    return render(request, 'index.html', context)


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


# 其他视图函数保持不变（登录、注册、设置等）
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


# 其他视图函数保持不变...
@login_required
def set_profile(request):
    """设置用户基础信息"""
    # ... 原有代码保持不变 ...


@login_required
def period_login(request):
    """用户登录"""
    # ... 原有代码保持不变 ...

# 其他辅助函数...