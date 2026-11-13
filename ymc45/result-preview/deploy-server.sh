#!/bin/sh
set -eu
site=/www/wwwroot/ymc45-preview
config=/www/server/panel/vhost/nginx/ymc45-preview-8088.conf
test ! -e "$site"
test ! -e "$config"
! ss -ltn | awk '{print $4}' | grep -q ':8088$'
mkdir -p "$site"
tar -xzf /tmp/ymc45-preview-static.tar.gz -C "$site"
chmod -R a+rX "$site"
cp /tmp/ymc45-preview-nginx.conf "$config"
if ! nginx -t; then
  rm "$config"
  exit 1
fi
nginx -s reload
ufw allow 8088/tcp
curl -fsS http://127.0.0.1:8088/ | head -n 8
curl -s -o /dev/null -w '博客 HTTP 状态：%{http_code}\n' -H 'Host: ymcblog.cn' http://127.0.0.1/
rm /tmp/ymc45-preview-static.tar.gz /tmp/ymc45-preview-nginx.conf /tmp/ymc45-preview-deploy.sh
