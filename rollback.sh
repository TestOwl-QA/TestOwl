#!/bin/bash
# ============================================
# TestOwl 回滚脚本
# 用法: bash rollback.sh [备份文件路径]
#       bash rollback.sh  # 不指定则列出可用备份
# ============================================

PROJECT_DIR="/root/testowl"
BACKUP_DIR="$PROJECT_DIR/backups"
SERVICE_NAME="testowl"

if [ -z "$1" ]; then
    echo "可用备份文件:"
    ls -lh "$BACKUP_DIR"/*.tar.gz 2>/dev/null || echo "  (无备份文件)"
    echo ""
    echo "回滚用法: bash rollback.sh backups/testowl_20260601_120000.tar.gz"
    exit 0
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ 备份文件不存在: $BACKUP_FILE"
    exit 1
fi

echo "========================================"
echo "  TestOwl 回滚"
echo "========================================"
echo "备份文件: $BACKUP_FILE"
echo ""

# 停止服务
echo "[1/4] 停止服务..."
systemctl stop "$SERVICE_NAME"
sleep 1

# 恢复代码
echo "[2/4] 恢复代码..."
cd "$PROJECT_DIR"
tar xzf "$BACKUP_FILE" 2>/dev/null
echo "  代码已恢复"

# 重启服务
echo "[3/4] 重启服务..."
systemctl start "$SERVICE_NAME"
sleep 2

# 验证
echo "[4/4] 验证..."
if systemctl is-active --quiet "$SERVICE_NAME"; then
    HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health 2>/dev/null || echo "000")
    if [ "$HEALTH" == "200" ]; then
        echo "  ✓ 回滚成功，服务正常运行"
    else
        echo "  ⚠ 服务已启动但健康检查返回 HTTP $HEALTH"
    fi
else
    echo "  ❌ 服务启动失败！请手动检查"
    exit 1
fi

echo ""
echo "========================================"
echo "  回滚完成"
echo "========================================"
