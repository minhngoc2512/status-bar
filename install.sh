#!/bin/bash
# Install the Claude Code status indicator:
#   1. merge the hook entries into ~/.claude/settings.json (existing hooks kept)
#   2. install + start a systemd --user service
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

installed() { dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -q "install ok installed"; }

# Running this on top of the packaged install is the one way to get the machine
# into a genuinely confusing state: the unit written to ~/.config/systemd/user
# shadows the packaged one, so systemd quietly launches the source tree instead,
# and every Claude Code event ends up spooled twice.
for pkg in status-bar claude-status; do
	if installed "$pkg"; then
		if [[ ${1:-} != "--force" ]]; then
			cat >&2 <<MSG

==> DỪNG: gói '$pkg' đã được cài qua apt.

    Bản cài từ thư mục này sẽ:
      - ghi unit vào ~/.config/systemd/user/, CHE unit của gói, nên systemd
        chạy mã trong thư mục checkout chứ không phải mã đã cài;
      - nối hook trỏ vào $HERE/hooks/emit.sh.

    Muốn dùng bản đã cài qua apt (khuyến nghị) thì không cần làm gì thêm:
      systemctl --user restart claude-status

    Muốn chuyển hẳn sang chạy từ thư mục này thì gỡ gói trước:
      sudo apt remove $pkg
      ./install.sh

    Biết mình đang làm gì và vẫn muốn tiếp tục:
      ./install.sh --force

MSG
			exit 1
		fi
		echo "==> '$pkg' đã cài qua apt, nhưng có --force nên vẫn tiếp tục"
	fi
done

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
