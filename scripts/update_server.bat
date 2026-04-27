@echo off
chcp 65001 >nul
echo ==========================================
echo TestOwl 云服务器代码更新脚本
echo 服务器: 121.41.36.197
echo ==========================================
echo.

echo [1/5] 正在连接到服务器并更新代码...
ssh -o StrictHostKeyChecking=no -o PasswordAuthentication=yes root@121.41.36.197 "cd /root/TestOwl && git pull origin main"

echo.
echo [2/5] 检查更新结果...

ssh root@121.41.36.197 "cd /root/TestOwl && git log --oneline -3"

echo.
echo [3/5] 重启服务...
ssh root@121.41.36.197 "cd /root/TestOwl && ./restart_services.sh"

echo.
echo [4/5] 检查服务状态...
ssh root@121.41.36.197 "systemctl status testowl testowl-api testowl-web --no-pager"

echo.
echo [5/5] 更新完成！
echo ==========================================
pause
