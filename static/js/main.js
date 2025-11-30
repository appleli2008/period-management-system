$(document).ready(function() {
    console.log("=== 文档加载完成 - 经期管理系统已启动 ===");

    // 日期点击功能
    $(document).on('click', '.clickable-day', function(event) {
        console.log("=== 日期点击事件开始 ===");
        event.stopPropagation();

        var $this = $(this);
        var dateStr = $this.data('date');
        var day = $this.data('day');
        var isCurrentMonth = $this.data('current-month');

        console.log("点击的日期数据:", {
            dateStr: dateStr,
            day: day,
            isCurrentMonth: isCurrentMonth
        });

        // 检查是否为有效日期
        if (!dateStr || dateStr === '' || dateStr === 'None') {
            console.log("无效日期，跳过");
            return;
        }

        // 检查是否为当前月
        if (isCurrentMonth === false || isCurrentMonth === 'false') {
            console.log("非当前月日期，跳过");
            return;
        }

        console.log("处理有效日期:", dateStr);

        try {
            // 安全解析日期
            var dateParts = dateStr.split('-');
            if (dateParts.length !== 3) {
                console.error("日期格式错误:", dateStr);
                return;
            }

            var year = parseInt(dateParts[0]);
            var month = parseInt(dateParts[1]) - 1;
            var day = parseInt(dateParts[2]);

            var date = new Date(year, month, day);
            if (isNaN(date.getTime())) {
                console.error("无效的日期对象");
                return;
            }

            // 格式化日期显示
            var formattedDate = date.getFullYear() + '年' +
                               (date.getMonth() + 1) + '月' +
                               date.getDate() + '日 (' +
                               getWeekday(date.getDay()) + ')';

            console.log("格式化日期:", formattedDate);

            // 显示选中的日期
            $('#selectedDateText').text(formattedDate);

            // 获取该日期的经期信息
            $.get('/period/info/', {date: dateStr}, function(data) {
                if (data.success) {
                    updateDatePanel(dateStr, data);
                } else {
                    console.error("获取经期信息失败:", data.message);
                    // 显示基本操作
                    showBasicDatePanel(dateStr);
                }
            }).fail(function() {
                // 如果请求失败，显示基本操作
                showBasicDatePanel(dateStr);
            });

        } catch (error) {
            console.error("日期处理错误:", error);
            // 显示基本操作作为后备
            showBasicDatePanel(dateStr);
        }
    });

    // 更新日期面板内容 - 修复版本（解决重复按钮问题）
    function updateDatePanel(dateStr, data) {
        console.log("更新日期面板:", dateStr, data);

        var actionsHtml = '';
        var hasStartButton = false; // 修复：添加标志变量，防止重复添加

        if (isUserAuthenticated) {
            // 修复：使用标志变量确保只添加一次"标记经期开始"按钮
            if (data.is_start_possible && !hasStartButton) {
                actionsHtml += '<button class="btn btn-pink btn-sm mb-2" id="setPeriodStart" data-date="' + dateStr + '">标记经期开始</button>';
                hasStartButton = true; // 标记已添加
            }

            // 经期记录调整选项
            if (data.end_candidate_records && data.end_candidate_records.length > 0) {
                actionsHtml += '<div class="period-adjustment-options">';
                actionsHtml += '<p class="adjustment-title"><strong>调整经期记录：</strong></p>';

                data.end_candidate_records.forEach(function(record, index) {
                    var predictionStatus = record.is_predicted ? ' (预测)' : ' (确认)';

                    actionsHtml += '<div class="record-adjustment">';
                    actionsHtml += '<p class="record-info">' + record.start_date + ' 开始' + predictionStatus + '</p>';

                    // 设置为开始日期
                    actionsHtml += '<button class="btn btn-pink btn-xs set-start-date" ' +
                                  'data-record-id="' + record.id + '" ' +
                                  'data-date="' + dateStr + '">设为开始日期</button>';

                    // 调整为整个期间（包含结束日期调整功能）
                    actionsHtml += '<button class="btn btn-pink btn-xs adjust-period" ' +
                                  'data-record-id="' + record.id + '" ' +
                                  'data-start-date="' + record.start_date + '" ' +
                                  'data-end-date="' + dateStr + '">调整为 ' + record.start_date + ' 至 ' + dateStr + '</button>';

                    actionsHtml += '</div>';

                    if (index < data.end_candidate_records.length - 1) {
                        actionsHtml += '<hr class="record-separator">';
                    }
                });

                actionsHtml += '</div>';
            } else {
                // 修复：移除重复的按钮添加逻辑
                // 这里不再重复添加"标记经期开始"按钮
                if (!data.is_start_possible) {
                    actionsHtml += '<p class="text-muted">该日期已有经期记录</p>';
                }
            }
        } else {
            actionsHtml += '<p class="text-muted">请先登录以使用经期记录功能</p>';
        }

        // 修复：检查是否已经添加了开始按钮，如果没有但可以开始，则添加
        if (isUserAuthenticated && data.is_start_possible && !hasStartButton) {
            actionsHtml += '<button class="btn btn-pink btn-sm mb-2" id="setPeriodStart" data-date="' + dateStr + '">标记经期开始</button>';
        }

        actionsHtml += '<button class="btn btn-default btn-sm mt-2" id="clearDate">关闭</button>';

        $('#dateActions').html(actionsHtml);
        showDatePanel();

        // 绑定新按钮的事件
        bindDatePanelEvents(dateStr);
    }

    // 基本操作（后备方案）- 修复版本
    function showBasicDatePanel(dateStr) {
        console.log("显示基本日期面板:", dateStr);

        var date = new Date(dateStr);
        var formattedDate = date.getFullYear() + '年' +
                           (date.getMonth() + 1) + '月' +
                           date.getDate() + '日 (' +
                           getWeekday(date.getDay()) + ')';

        $('#selectedDateText').text(formattedDate);

        var actionsHtml = '';
        var hasStartButton = false; // 修复：添加标志变量

        if (isUserAuthenticated) {
            // 修复：确保只添加一个"标记经期开始"按钮
            if (!hasStartButton) {
                actionsHtml += '<button class="btn btn-pink btn-sm mb-2" id="setPeriodStart" data-date="' + dateStr + '">标记经期开始</button>';
                hasStartButton = true;
            }

            // 修复：确保只添加一个"标记经期结束"按钮
            actionsHtml += '<button class="btn btn-pink btn-sm mb-2" id="setPeriodEnd" data-date="' + dateStr + '">标记经期结束</button>';
        } else {
            actionsHtml += '<p class="text-muted">请先登录以使用经期记录功能</p>';
        }

        actionsHtml += '<button class="btn btn-default btn-sm" id="clearDate">关闭</button>';

        $('#dateActions').html(actionsHtml);
        showDatePanel();

        // 绑定事件
        bindDatePanelEvents(dateStr);
    }

    // 显示日期面板
    function showDatePanel() {
        console.log("显示面板");
        $('#datePanel').show();
        $('#overlay').show();
    }

    // 绑定日期面板事件
    function bindDatePanelEvents(dateStr) {
        // 标记经期开始
        $('#setPeriodStart').off('click').on('click', function() {
            var date = $(this).data('date');
            console.log("标记经期开始:", date);
            setPeriodStart(date);
        });

        // 标记经期结束
        $('#setPeriodEnd').off('click').on('click', function() {
            var date = $(this).data('date');
            console.log("标记经期结束:", date);
            setPeriodEnd(date);
        });

        // 设置为开始日期
        $('.set-start-date').off('click').on('click', function() {
            var recordId = $(this).data('record-id');
            var startDate = $(this).data('date');
            console.log("设置开始日期:", recordId, startDate);
            adjustPeriod(recordId, startDate, null, 'start');
        });

        // 调整整个期间
        $('.adjust-period').off('click').on('click', function() {
            var recordId = $(this).data('record-id');
            var startDate = $(this).data('start-date');
            var endDate = $(this).data('end-date');
            console.log("调整整个期间:", recordId, startDate, endDate);
            adjustPeriod(recordId, startDate, endDate, 'both');
        });

        // 关闭面板
        $('#clearDate').off('click').on('click', closeDatePanel);
    }

    // 关闭日期面板
    function closeDatePanel() {
        console.log("关闭面板");
        $('#datePanel').hide();
        $('#overlay').hide();
        $('.clickable-day').removeClass('selected');
    }

    // 关闭按钮事件
    $('#closePanel').click(closeDatePanel);
    $('#overlay').click(closeDatePanel);

    // 标记经期开始
    function setPeriodStart(dateStr) {
        console.log("标记经期开始:", dateStr);

        $.ajax({
            url: '/period/start/',
            type: 'POST',
            data: {
                'csrfmiddlewaretoken': getCSRFToken(),
                'start_date': dateStr
            },
            success: function(data) {
                if (data.success) {
                    alert('经期开始标记成功！');
                    closeDatePanel();
                    location.reload();
                } else {
                    alert('标记失败: ' + data.message);
                }
            },
            error: function(xhr, status, error) {
                alert('请求失败: ' + error);
            }
        });
    }

    // 标记经期结束
    function setPeriodEnd(dateStr) {
        console.log("标记经期结束:", dateStr);

        $.ajax({
            url: '/period/end/',
            type: 'POST',
            data: {
                'csrfmiddlewaretoken': getCSRFToken(),
                'end_date': dateStr
            },
            success: function(data) {
                if (data.success) {
                    alert('经期结束日期已成功更新！');
                    closeDatePanel();
                    location.reload();
                } else {
                    alert('标记失败: ' + data.message);
                }
            },
            error: function(xhr, status, error) {
                alert('请求失败: ' + error);
            }
        });
    }

    // 调整经期记录
    function adjustPeriod(recordId, startDate, endDate, action) {
        console.log("调整经期记录:", recordId, startDate, endDate, action);

        var requestData = {
            'csrfmiddlewaretoken': getCSRFToken(),
            'record_id': recordId,
            'action': action
        };

        if (startDate) requestData.start_date = startDate;
        if (endDate) requestData.end_date = endDate;

        $.ajax({
            url: '/period/adjust/',
            type: 'POST',
            data: requestData,
            success: function(data) {
                if (data.success) {
                    alert('经期记录已成功调整！');
                    closeDatePanel();
                    location.reload();
                } else {
                    alert('调整失败: ' + data.message);
                }
            },
            error: function(xhr, status, error) {
                alert('请求失败: ' + error);
            }
        });
    }

    // 获取CSRF令牌
    function getCSRFToken() {
        var csrfToken = $('input[name="csrfmiddlewaretoken"]').val();
        if (!csrfToken) {
            var cookieMatch = document.cookie.match(/csrftoken=([^;]+)/);
            csrfToken = cookieMatch ? cookieMatch[1] : '';
        }
        return csrfToken;
    }

    // 将星期数字转换为中文
    function getWeekday(day) {
        var weekdays = ['日', '一', '二', '三', '四', '五', '六'];
        return '星期' + weekdays[day];
    }

    // 删除账户功能 - 修复版本
    function setupAccountDeletion() {
    // 删除账户按钮点击事件
    $('#deleteAccountBtn').click(function() {
        // 显示删除确认模态框
        $('#deleteAccountModal').modal('show');
    });

    // 确认删除按钮点击事件
    $('#confirmDeleteAccount').click(function() {
        var password = $('#deleteAccountPassword').val().trim();

        // 验证密码是否输入
        if (!password) {
            alert('请输入密码确认删除操作');
            $('#deleteAccountPassword').focus();
            return;
        }

        // 显示加载状态
        $('#confirmDeleteAccount').prop('disabled', true).html('验证中...');

        // 发送删除请求
        $.ajax({
            url: '/period/delete-account/',
            type: 'POST',
            data: {
                'csrfmiddlewaretoken': getCSRFToken(),
                'password': password,
                'confirm_delete': 'true'  // 添加确认标志
            },
            success: function(data) {
                if (data.success) {
                    alert('✅ 账户删除成功！感谢您使用我们的服务。');
                    // 重定向到首页
                    window.location.href = '/';
                } else {
                    alert('❌ ' + data.message);
                    // 重新启用按钮
                    $('#confirmDeleteAccount').prop('disabled', false).html('确认删除');
                }
            },
            error: function(xhr, status, error) {
                alert('❌ 请求失败: ' + error);
                // 重新启用按钮
                $('#confirmDeleteAccount').prop('disabled', false).html('确认删除');
            }
        });
    });

    // 取消删除按钮
    $('#cancelDeleteAccount').click(function() {
        // 清空密码框
        $('#deleteAccountPassword').val('');
        // 隐藏模态框
        $('#deleteAccountModal').modal('hide');
    });

    // 密码框回车事件
    $('#deleteAccountPassword').keypress(function(e) {
        if (e.which == 13) { // 回车键
            $('#confirmDeleteAccount').click();
        }
    });

    // 模态框关闭时清空密码
    $('#deleteAccountModal').on('hidden.bs.modal', function() {
        $('#deleteAccountPassword').val('');
        $('#confirmDeleteAccount').prop('disabled', false).html('确认删除');
    });
}

    // 保存基础信息
    $('#saveProfile').click(function() {
        var formData = $('#profileForm').serialize();

        $.ajax({
            url: '/period/set-profile-ajax/',
            type: 'POST',
            data: formData,
            success: function(data) {
                if (data.success) {
                    alert('基础信息保存成功');
                    $('#profileModal').modal('hide');
                    location.reload();
                } else {
                    alert('保存失败: ' + data.message);
                }
            },
            error: function(xhr, status, error) {
                alert('请求失败: ' + error);
            }
        });
    });

    // 删除经期记录
    $(document).on('click', '.delete-record', function(e) {
        e.preventDefault();
        e.stopPropagation();

        var recordId = $(this).data('record-id');
        console.log("删除记录:", recordId);

        if (!confirm('确定要删除这条经期记录吗？')) {
            return;
        }

        $.ajax({
            url: '/period/delete/' + recordId + '/',
            type: 'POST',
            data: {
                'csrfmiddlewaretoken': getCSRFToken()
            },
            success: function(data) {
                if (data.success) {
                    alert('记录删除成功');
                    location.reload();
                } else {
                    alert('删除失败: ' + data.message);
                }
            },
            error: function(xhr, status, error) {
                alert('请求失败: ' + error);
            }
        });
    });

    console.log("=== 所有事件绑定完成 ===");
});