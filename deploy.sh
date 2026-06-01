#!/bin/bash
# ============================================
# TestOwl 服务器端一键部署脚本
# 功能: 备份 → 拉代码 → 重启 → 验证 → 失败回滚
# 用法: bash deploy.sh
# ============================================
set -e

PROJECT_DIR="/root/testowl"
BACKUP_DIR="$PROJECT_DIR/backups"
LOG_FILE="$PROJECT_DIR/deploy.log"
SERVICE_NAME="testowl"

cd "$PROJECT_DIR"

echo "========================================" | tee -a "$LOG_FILE"
echo "  TestOwl 部署开始 - $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# ── Step 1: 备份当前版本 ──
echo "" | tee -a "$LOG_FILE"
echo "[1/6] 备份当前版本..." | tee -a "$LOG_FILE"
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/testowl_$(date +%Y%m%d_%H%M%S).tar.gz"
tar czf "$BACKUP_FILE" \
    --exclude='backups' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='uploads' \
    --exclude='.git' \
    . 2>/dev/null
echo "  备份完成: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))" | tee -a "$LOG_FILE"

# 记录当前 commit
PREV_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
echo "  当前版本: $PREV_COMMIT" | tee -a "$LOG_FILE"

# ── Step 2: 拉取最新代码 ──
echo "" | tee -a "$LOG_FILE"
echo "[2/6] 拉取最新代码..." | tee -a "$LOG_FILE"
git pull origin main 2>&1 | tee -a "$LOG_FILE"
NEW_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
echo "  新版本: $NEW_COMMIT" | tee -a "$LOG_FILE"

if [ "$PREV_COMMIT" == "$NEW_COMMIT" ]; then
    echo "  代码无变化，跳过部署" | tee -a "$LOG_FILE"
    exit 0
fi

# ── Step 3: 安装依赖（仅当 requirements.txt 有变化） ──
echo "" | tee -a "$LOG_FILE"
echo "[3/6] 检查依赖..." | tee -a "$LOG_FILE"
if git diff --name-only "$PREV_COMMIT" "$NEW_COMMIT" | grep -q "requirements.txt"; then
    echo "  requirements.txt 有变化，安装依赖..." | tee -a "$LOG_FILE"
    pip install -r requirements.txt 2>&1 | tee -a "$LOG_FILE"
else
    echo "  依赖无变化，跳过" | tee -a "$LOG_FILE"
fi

# ── Step 4: 重启服务 ──
echo "" | tee -a "$LOG_FILE"
echo "[4/6] 重启服务..." | tee -a "$LOG_FILE"
systemctl restart "$SERVICE_NAME"
sleep 2
systemctl is-active --quiet "$SERVICE_NAME" && echo "  服务重启成功 ✓" | tee -a "$LOG_FILE" || {
    echo "  ❌ 服务重启失败！开始回滚..." | tee -a "$LOG_FILE"
    bash "$PROJECT_DIR/rollback.sh" "$BACKUP_FILE"
    exit 1
}

# ── Step 5: 验证 ──
echo "" | tee -a "$LOG_FILE"
echo "[5/6] 验证服务..." | tee -a "$LOG_FILE"

# 5a 健康检查端点
HEALTH_RESP=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health 2>/dev/null || echo "000")
if [ "$HEALTH_RESP" == "200" ]; then
    echo "  MCP 健康检查通过 ✓" | tee -a "$LOG_FILE"
else
    echo "  ❌ MCP 健康检查失败 (HTTP $HEALTH_RESP)！回滚..." | tee -a "$LOG_FILE"
    bash "$PROJECT_DIR/rollback.sh" "$BACKUP_FILE"
    exit 1
fi

# 5b 代码校验
echo "[6/6] 代码结构校验..." | tee -a "$LOG_FILE"
python3 scripts/check_health.py 2>&1 | tee -a "$LOG_FILE"
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo "  代码校验通过 ✓" | tee -a "$LOG_FILE"
else
    echo "  ⚠ 代码校验有告警，但服务已启动" | tee -a "$LOG_FILE"
fi

# ── Step 6: 清理旧备份（保留最近7天） ──
echo "" | tee -a "$LOG_FILE"
echo "清理旧备份（保留7天）..." | tee -a "$LOG_FILE"
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete 2>/dev/null
echo "  清理完成" | tee -a "$LOG_FILE"

# ── 完成 ──
echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "  部署成功！" | tee -a "$LOG_FILE"
echo "  旧版本: $PREV_COMMIT → 新版本: $NEW_COMMIT" | tee -a "$LOG_FILE"
echo "  备份文件: $BACKUP_FILE" | tee -a "$LOG_FILE"
echo "  如需回滚: bash rollback.sh $BACKUP_FILE" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
