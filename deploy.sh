#!/bin/zsh
# 一键更新：编译 Markdown → 提交 → 推送
# 用法：./deploy.sh "这次改了什么"
set -e
cd "$(dirname "$0")/milkdragon"
python3 build.py
cd ..
git add -A
if ! git diff --cached --quiet; then
  git commit -m "${1:-更新内容}"
fi
git push
echo "✓ 已推送，线上约 30 秒后生效，二维码不用换"
