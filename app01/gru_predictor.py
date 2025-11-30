import numpy as np
from datetime import datetime, timedelta
from sklearn.preprocessing import MinMaxScaler
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import GRU, Dense, Dropout
from tensorflow.keras.optimizers import Adam
import joblib
import os
import json
from django.conf import settings


class GRUPeriodPredictor:
    def __init__(self):
        self.model = None
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.sequence_length = 6
        self.model_dir = os.path.join(settings.BASE_DIR, 'gru_models')
        os.makedirs(self.model_dir, exist_ok=True)

    def get_user_model_path(self, user_id):
        return os.path.join(self.model_dir, f'user_{user_id}')

    def create_features(self, records):
        """从经期记录创建特征"""
        if len(records) < 2:
            return None, None

        sorted_records = sorted(records, key=lambda x: x.start_date)
        cycle_lengths = []

        for i in range(1, len(sorted_records)):
            prev_start = sorted_records[i - 1].start_date
            curr_start = sorted_records[i].start_date
            days_between = (curr_start - prev_start).days

            if 20 <= days_between <= 45:
                cycle_lengths.append(days_between)

        if len(cycle_lengths) < self.sequence_length + 1:
            return None, None

        features = []
        for i in range(len(cycle_lengths) - self.sequence_length):
            sequence = cycle_lengths[i:i + self.sequence_length]
            feature_vector = list(sequence)

            # 统计特征
            feature_vector.extend([
                np.mean(sequence), np.std(sequence),
                min(sequence), max(sequence), np.median(sequence)
            ])

            # 趋势特征
            if len(sequence) >= 2:
                trend = sequence[-1] - sequence[-2]
                feature_vector.append(trend)
            else:
                feature_vector.append(0)

            features.append(feature_vector)

        targets = cycle_lengths[self.sequence_length:]
        return np.array(features), np.array(targets)

    def build_model(self, input_shape):
        """构建GRU模型"""
        model = Sequential([
            GRU(50, return_sequences=True, input_shape=input_shape),
            Dropout(0.2),
            GRU(50, return_sequences=False),
            Dropout(0.2),
            Dense(25),
            Dense(1)
        ])

        model.compile(optimizer=Adam(learning_rate=0.001),
                      loss='mse',
                      metrics=['mae'])
        return model

    def train_model(self, user_id, records):
        """训练GRU模型"""
        print(f"🎯 开始训练用户{user_id}的GRU模型")

        X, y = self.create_features(records)
        if X is None or len(X) < 3:
            print(f"❌ 用户{user_id}数据不足，无法训练GRU模型")
            return False

        # 数据标准化
        X_scaled = self.scaler.fit_transform(X)
        X_reshaped = X_scaled.reshape((X_scaled.shape[0], 1, X_scaled.shape[1]))

        # 构建和训练模型
        self.model = self.build_model((1, X_scaled.shape[1]))

        history = self.model.fit(
            X_reshaped, y,
            epochs=100,
            batch_size=16,
            validation_split=0.2,
            verbose=0,
            callbacks=[tf.keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True)]
        )

        # 保存模型
        model_path = self.get_user_model_path(user_id)
        self.model.save(f"{model_path}.h5")
        joblib.dump(self.scaler, f"{model_path}_scaler.pkl")

        train_mae = history.history['mae'][-1]
        print(f"✅ 用户{user_id}的GRU模型训练完成，MAE: {train_mae:.2f}天")
        return True

    def load_model(self, user_id):
        """加载用户模型"""
        model_path = self.get_user_model_path(user_id)
        model_file = f"{model_path}.h5"
        scaler_file = f"{model_path}_scaler.pkl"

        if os.path.exists(model_file) and os.path.exists(scaler_file):
            try:
                self.model = tf.keras.models.load_model(model_file)
                self.scaler = joblib.load(scaler_file)
                return True
            except Exception as e:
                print(f"❌ 加载模型失败: {e}")
        return False

    def predict_next_cycle(self, user_id, records):
        """使用GRU预测下一个周期长度"""
        if not self.load_model(user_id):
            if not self.train_model(user_id, records):
                return self.fallback_prediction(records)

        X, _ = self.create_features(records)
        if X is None or len(X) == 0:
            return self.fallback_prediction(records)

        # 使用最新序列预测
        latest_sequence = X[-1:].reshape(1, -1)
        latest_sequence_scaled = self.scaler.transform(latest_sequence)
        latest_sequence_reshaped = latest_sequence_scaled.reshape((1, 1, latest_sequence_scaled.shape[1]))

        prediction = self.model.predict(latest_sequence_reshaped, verbose=0)[0][0]
        predicted_cycle = int(round(max(20, min(45, prediction))))

        print(f"🤖 GRU预测周期长度: {predicted_cycle}天")
        return predicted_cycle

    def fallback_prediction(self, records):
        """回退到加权平均法"""
        from . import calculate_weighted_average_cycle
        return calculate_weighted_average_cycle(records)


# 全局GRU预测器实例
gru_predictor = GRUPeriodPredictor()


def get_three_stage_predictions(user, records, profile, year, month):
    """
    三阶段预测算法：
    阶段1 (1-3周期): 固定周期
    阶段2 (4-6周期): 加权平均
    阶段3 (7+周期): GRU神经网络
    """
    print(f"=== 三阶段预测算法启动 ===")

    # 获取实际记录
    actual_records = [r for r in records if not r.is_predicted]
    if not actual_records:
        return [], []

    sorted_actual = sorted(actual_records, key=lambda x: x.start_date)
    cycle_count = len(sorted_actual) - 1

    print(f"📊 记录分析: {len(actual_records)}个记录, {cycle_count}个完整周期")

    # 使用最新记录作为参考
    latest_record = sorted_actual[-1]
    reference_date = latest_record.end_date

    # 三阶段算法选择
    if cycle_count < 3:
        # 阶段1：固定周期
        cycle_length = profile.cycle_length
        method = f"固定周期（{cycle_count}个周期）"
    elif cycle_count < 7:
        # 阶段2：加权平均
        cycle_length = calculate_weighted_average_cycle(sorted_actual)
        method = f"加权平均（{cycle_count}个周期）"
    else:
        # 阶段3：GRU神经网络
        try:
            cycle_length = gru_predictor.predict_next_cycle(user.id, sorted_actual)
            method = f"GRU神经网络（{cycle_count}个周期）"
        except Exception as e:
            print(f"❌ GRU预测失败: {e}，回退到加权平均")
            cycle_length = calculate_weighted_average_cycle(sorted_actual)
            method = f"加权平均（回退）"

    period_length = profile.period_length

    print(f"🔧 预测方法: {method}")
    print(f"⏱️ 预测周期: {cycle_length}天")

    # 计算预测周期
    prediction_start = reference_date + timedelta(days=cycle_length)
    prediction_end = prediction_start + timedelta(days=period_length - 1)

    next_prediction_start = prediction_start + timedelta(days=cycle_length)
    next_prediction_end = next_prediction_start + timedelta(days=period_length - 1)

    # 生成目标月份内的日期
    current_dates = generate_dates_in_month(prediction_start, prediction_end, year, month)
    next_dates = generate_dates_in_month(next_prediction_start, next_prediction_end, year, month)

    print(f"✅ 当前预测在目标月份内: {len(current_dates)}天")
    print(f"✅ 下次预测在目标月份内: {len(next_dates)}天")

    return current_dates, next_dates


def calculate_weighted_average_cycle(records):
    """计算加权平均周期长度"""
    if len(records) < 2:
        return 28

    cycle_lengths = []
    for i in range(1, len(records)):
        prev_start = records[i - 1].start_date
        curr_start = records[i].start_date
        days_between = (curr_start - prev_start).days

        if 20 <= days_between <= 45:
            cycle_lengths.append(days_between)

    if not cycle_lengths:
        return 28

    # 加权平均：近期数据权重更高
    n = len(cycle_lengths)
    weights = [0.5 ** (n - i - 1) for i in range(n)]
    total_weight = sum(weights)
    normalized_weights = [w / total_weight for w in weights]

    weighted_avg = sum(length * weight for length, weight in zip(cycle_lengths, normalized_weights))
    return int(round(max(20, min(45, weighted_avg))))


def generate_dates_in_month(start_date, end_date, year, month):
    """生成指定月份内的日期列表"""
    target_start = datetime(year, month, 1).date()
    if month == 12:
        target_end = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        target_end = datetime(year, month + 1, 1).date() - timedelta(days=1)

    if end_date < target_start or start_date > target_end:
        return []

    overlap_start = max(start_date, target_start)
    overlap_end = min(end_date, target_end)

    dates = []
    current_date = overlap_start
    while current_date <= overlap_end:
        dates.append(current_date)
        current_date += timedelta(days=1)

    return dates