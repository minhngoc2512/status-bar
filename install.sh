#!/bin/bash
# Install the Claude Code status indicator:
#   1. merge the hook entries into ~/.claude/settings.json (existing hooks kept)
#   2. install + start a systemd --user service
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Kiểm tra thư viện AppIndicator"
if ! python3 -c "import gi; gi.require_version('AyatanaAppIndicator3','0.1')" 2>/dev/null &&
	! python3 -c "import gi; gi.require_version('AppIndicator3','0.1')" 2>/dev/null; then
	echo "    THIẾU. Chạy lệnh này rồi chạy lại install.sh:"
	echo "    sudo apt install -y gir1.2-ayatanaappindicator3-0.1"
	exit 1
fi
echo "    OK"

echo "==> Merge hook vào ~/.claude/settings.json"
python3 "$HERE/merge_settings.py"

echo "==> Cài systemd user service"
mkdir -p ~/.config/systemd/user
sed "s|@HERE@|$HERE|g" "$HERE/claude-status.service" >~/.config/systemd/user/claude-status.service
systemctl --user daemon-reload
systemctl --user enable --now claude-status.service
sleep 1
systemctl --user --no-pager status claude-status.service | head -12

cat <<'EOF'

==> Xong.
    Icon đã nằm trên thanh trạng thái (góc phải màn hình).
    Hook chỉ áp dụng cho session Claude Code MỞ MỚI kể từ giờ.

    Thời tiết và crypto mặc định TẮT. Nhấp icon -> Cài đặt... để bật.

    Lệnh hữu ích:
      systemctl --user restart claude-status     # khởi động lại indicator
      systemctl --user stop claude-status        # tắt
      journalctl --user -u claude-status -f      # xem log

    Muốn cài lên máy khác thì đóng gói .deb:
      ./build-deb.sh
EOF
