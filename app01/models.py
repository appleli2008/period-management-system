from django.db import models
from django.contrib.auth.models import User
from datetime import timedelta


class PeriodRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)
    is_predicted = models.BooleanField(default=False)  # 是否为预测记录
    is_confirmed = models.BooleanField(default=False)  # 是否已确认

    def __str__(self):
        status = "预测" if self.is_predicted else "确认"
        return f"{self.user.username} - {self.start_date} 至 {self.end_date} ({status})"

    def get_next_prediction(self, cycle_length, period_length):
        """根据当前记录预测下一次经期"""
        next_start = self.start_date + timedelta(days=cycle_length)
        next_end = next_start + timedelta(days=period_length - 1)
        return next_start, next_end

    class Meta:
        ordering = ['-start_date']


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    cycle_length = models.IntegerField(default=28, verbose_name="月经间隔天数")
    period_length = models.IntegerField(default=5, verbose_name="经期持续天数")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - 周期{self.cycle_length}天，经期{self.period_length}天"


class PeriodPrediction(models.Model):
    """经期预测记录"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    predicted_start = models.DateField()
    predicted_end = models.DateField()
    based_on_record = models.ForeignKey(PeriodRecord, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_confirmed = models.BooleanField(default=False)  # 是否已确认（用户标记了经期开始）

    def __str__(self):
        status = "已确认" if self.is_confirmed else "预测中"
        return f"{self.user.username} - 预测{self.predicted_start}至{self.predicted_end} ({status})"

    class Meta:
        ordering = ['predicted_start']