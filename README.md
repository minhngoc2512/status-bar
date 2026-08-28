# claude-status

Ba chỉ báo GTK trên thanh trạng thái Ubuntu/GNOME, chạy chung một tiến trình:

| | |
| :--- | :--- |
| **Claude Code** | trạng thái mọi session: đang xử lý / chờ confirm / task nền / lỗi / rảnh |
| **Thời tiết** | nhiệt độ + điều kiện hiện tại, tự dò vị trí theo IP hoặc chọn thành phố |
| **Crypto** | giá và biến động 24h từ API công khai của Binance |
| **Phần cứng** | tải + nhiệt độ CPU, RAM, GPU (tải/nhiệt/VRAM/xung), tốc độ mạng |

```
◐ working 2     ← 2 session Claude đang chạy (spinner quay)
● confirm       ← có session đang chờ bạn duyệt (nhấp nháy)
☔ 28°C         ← thời tiết
📈 BTC 79,659 ▲1.18%
🔲 CPU 20%  81°C  RAM 74%  GPU 14% 48°C  ↓2.4K ↑1.7K
```

Mỗi chỉ báo **bật/tắt độc lập** trong cửa sổ Cài đặt. Thời tiết, crypto và phần cứng mặc
định **tắt** — cài mới hoặc nâng cấp đều không đổi hành vi sẵn có.

Không cần API key. Không cần thư viện Python ngoài stdlib + PyGObject.

---

## Môi trường hỗ trợ

**Đã test trực tiếp**

| | |
| :--- | :--- |
| OS | Ubuntu 22.04.5 LTS |
| Desktop | GNOME Shell 42.9, phiên **X11** |
| Python | 3.10.12 |
| AppIndicator | `gir1.2-ayatanaappindicator3-0.1` 0.5.90 + extension `ubuntu-appindicators@ubuntu.com` |
| Phần cứng | AMD Ryzen 5 4600H (`k10temp`), NVIDIA GTX 1650 Ti Mobile (driver 580, NVML) |

**Yêu cầu tối thiểu**

- Python **3.8+** (dùng `Path.unlink(missing_ok=)`), chỉ stdlib — không `pip install` gì cả
- `python3-gi` + `gir1.2-gtk-3.0` (GTK **3**, không phải GTK 4)
- `gir1.2-ayatanaappindicator3-0.1` — thiếu thì code tự lùi về `gir1.2-appindicator3-0.1` cũ
- Trên GNOME: extension AppIndicator. Ubuntu Desktop cài sẵn (`ubuntu-appindicators`);
  GNOME thuần cần `sudo apt install gnome-shell-extension-appindicator`
- Mạng ra ngoài: `api.open-meteo.com`, `geocoding-api.open-meteo.com`, `ipwho.is`,
  `ipapi.co`, `ip-api.com` (HTTP), `api.binance.com` — chỉ khi bật thời tiết/crypto
- Theo dõi phần cứng chỉ đọc `/proc` và `/sys`, không cần quyền root. GPU cần thêm:
  driver NVIDIA (dùng `libnvidia-ml.so`, tức NVML), hoặc card AMD/Intel phơi
  `amdgpu`/`i915` trong `/sys/class/drm`. Không có gì đọc được thì phần GPU tự tắt.

**Kỳ vọng chạy được nhưng chưa test**

- Ubuntu 20.04 / 24.04 / 25.04 — đủ gói phụ thuộc trong repo chính
- GPU AMD (`amdgpu`) và Intel (`i915`) qua sysfs — code có, nhưng máy test chỉ có NVIDIA
- Phiên **Wayland** — AppIndicator đi qua D-Bus (StatusNotifierItem), không phụ thuộc X
- Debian 11+, Linux Mint, Pop!_OS
- KDE Plasma, XFCE (+ `xfce4-statusnotifier-plugin`), Cinnamon, MATE, Budgie —
  đều nói StatusNotifierItem

**Không chạy được**: GNOME không bật extension AppIndicator (icon sẽ không hiện ở đâu cả),
môi trường không có D-Bus session, hoặc chỉ có GTK 4.

---

## Cài đặt

### Cách 1 — apt repository (khuyến nghị)

```bash
curl -fsSL https://minhngoc2512.github.io/status-bar/status-bar-archive-keyring.asc \
  | sudo gpg --dearmor -o /usr/share/keyrings/status-bar-archive-keyring.gpg

echo "deb [signed-by=/usr/share/keyrings/status-bar-archive-keyring.gpg] https://minhngoc2512.github.io/status-bar/ ./" \
  | sudo tee /etc/apt/sources.list.d/status-bar.list

sudo apt update
sudo apt install status-bar
```

`apt upgrade` sẽ tự cập nhật từ đó về sau.

> **Tên gói là `status-bar`, nhưng lệnh và cấu hình vẫn là `claude-status`.**
> Đổi tên chương trình và thư mục `~/.config` sẽ làm mọi bản cài sẵn có mất cấu hình
> mà chẳng được gì. Gói cài cả hai lệnh — `status-bar` là symlink tới `claude-status`.

### Cách 2 — tải thẳng gói `.deb`

Lấy từ [Releases](https://github.com/minhngoc2512/status-bar/releases), hoặc tự build:

```bash
./build-deb.sh
```

Sinh ra `dist/status-bar_<version>_all.deb` (~50 KB, `Architecture: all`).
Chỉ cần `dpkg-deb` (gói `dpkg-dev`), không cần debhelper.

```bash
sudo apt install ./status-bar_2.2.0_all.deb
```

`apt` sẽ tự kéo `python3-gi`, `gir1.2-gtk-3.0` và các gói khuyến nghị.
Sau khi cài, **chạy dưới user của bạn, không dùng sudo**:

```bash
claude-status-hooks          # nối hook vào ~/.claude/settings.json
systemctl --user start claude-status
```

Gói cài vào:

```
/usr/lib/claude-status/          mã nguồn + icons + hooks/emit.sh
/usr/bin/claude-status           launcher
/usr/bin/status-bar              symlink tới launcher
/usr/bin/claude-status-hooks     merge hook cho user đang gọi
/usr/lib/systemd/user/claude-status.service
/usr/share/applications/claude-status.desktop
/usr/share/icons/hicolor/scalable/apps/claude-status.svg
```

`postinst` chạy `systemctl --global enable claude-status.service`, nên service tự bật cho
mọi user ở lần đăng nhập đồ hoạ kế tiếp. Gỡ:

```bash
sudo apt remove status-bar     # giữ config + hook entry
sudo apt purge status-bar      # kèm hướng dẫn dọn thủ công
```

### Cách 3 — chạy thẳng từ thư mục checkout

```bash
./install.sh
```

Backup `~/.claude/settings.json`, merge hook vào (giữ nguyên hook sẵn có), rồi cài + bật
systemd user service trỏ vào thư mục hiện tại.

Hook chỉ áp dụng cho **session Claude Code mở mới** sau khi cài.

---

## Cài đặt trong app

Nhấp icon bất kỳ → **Cài đặt…** (hoặc **Settings…**). Cửa sổ có 3 tab:

**Chung** — bật/tắt từng chỉ báo, ngôn ngữ (English / Tiếng Việt), thông báo khi cần
confirm, hiệu ứng động, hiện/ẩn chữ trạng thái cạnh icon.

**Thời tiết** — chọn *tự dò theo IP* hoặc *tự chọn vị trí* (gõ tên thành phố → bấm Tìm →
chọn trong danh sách), đơn vị °C/°F, chu kỳ cập nhật 5–180 phút, hiện/ẩn nhiệt độ cạnh icon.

**Crypto** — danh sách mã đang theo dõi, ô **Thêm cặp** có gợi ý (gõ `BNB` → hiện
`BNBUSDT`, `BNBUSDC`, `BNBBTC`… bấm để thêm), mã nào hiện trên thanh trạng thái,
chu kỳ 15–600 giây, hiện/ẩn giá và biến động 24h, endpoint API.

**Hệ thống** — chọn chỉ số nào hiện trên thanh trạng thái (tải CPU, nhiệt CPU, RAM, tải GPU,
nhiệt GPU, tốc độ mạng), chu kỳ 1–30 giây, cảm biến nhiệt CPU, ngưỡng cảnh báo/nguy hiểm,
**cổng mạng** (tự động hoặc chọn tay), đơn vị tốc độ, bật/tắt đọc GPU.

Mọi thay đổi áp dụng ngay, không có nút OK/Cancel. Lưu ở
`~/.config/claude-status/config.json`:

```json
{
  "lang": "vi", "notify": true, "animate": true,
  "claude": { "enabled": true, "show_label": true },
  "weather": {
    "enabled": true, "mode": "auto", "latitude": null, "longitude": null,
    "place": "", "unit": "celsius", "refresh_minutes": 30, "show_label": true,
    "detected": { "latitude": 21.0184, "longitude": 105.8461, "place": "Hanoi, Viet Nam", "at": 0 }
  },
  "crypto": {
    "enabled": true, "symbols": ["BTCUSDT", "ETHUSDT"], "bar_symbol": "BTCUSDT",
    "refresh_seconds": 60, "show_change": true, "show_label": true,
    "endpoint": "https://api.binance.com"
  },
  "system": {
    "enabled": true, "refresh_seconds": 3, "show_label": true,
    "bar_metrics": ["cpu", "temp"], "temp_sensor": "", "warn_celsius": 85,
    "hot_celsius": 95, "net_unit": "bytes", "interfaces": [], "gpu": true
  }
}
```

Tắt hết các chỉ báo thì một icon dự phòng hiện ra, chỉ có **Cài đặt…** và **Thoát** — để
bạn còn đường quay lại.

---

## Chỉ báo Claude Code

```
Claude Code hook  →  ~/.cache/claude-status/events/<ts>.<ppid>.json
                                  ↓ inotify (Gio.FileMonitor)
                          indicator.py (GTK3 + AppIndicator)
                                  ↓
                     icon + label + menu trên top bar
```

`hooks/emit.sh` chỉ làm một việc: đổ payload JSON ra file rồi thoát. Không parse,
không gọi Python, không ghi stdout.

| Hook event | Trạng thái |
| :--- | :--- |
| `SessionStart` | idle |
| `UserPromptSubmit` | working — *processing* |
| `PreToolUse` | working — tên tool (`Bash`, `Edit`…) |
| `PostToolUse` | working — *processing* |
| `PermissionRequest` | **confirm** (fire ngay, không đợi 6s như Notification) |
| `Stop` (có `background_tasks`) | background — số task |
| `Stop` (rỗng) | idle |
| `StopFailure` | error |
| `SubagentStart` / `SubagentStop` | đếm subagent, hiện trong menu |
| `Notification` / `permission_prompt`, `agent_needs_input` | confirm |
| `Notification` / `elicitation_dialog`, `elicitation_url_dialog` | confirm — MCP form |
| `Notification` / `idle_prompt` | idle |
| `SessionEnd` | xóa khỏi danh sách |

Icon hiện trạng thái **xấu nhất** trong tất cả session, theo thứ tự ưu tiên
`confirm > error > working > background > idle`.

Menu: danh sách session (`🟠 sense_nova · chờ confirm: Bash · 12s`), submenu có đường dẫn,
permission mode, **Mở thư mục**, **Copy đường dẫn**, **Bỏ khỏi danh sách**.

---

## Chỉ báo thời tiết

Nguồn **Open-Meteo** — miễn phí, không đăng ký, không API key.

- Dữ liệu: `api.open-meteo.com/v1/forecast` (nhiệt độ, cảm giác như, độ ẩm, gió, mã WMO,
  ngày/đêm, min–max hôm nay)
- Tìm địa điểm: `geocoding-api.open-meteo.com/v1/search`, kết quả trả về theo ngôn ngữ đang chọn
- Dò IP: thử lần lượt `ipwho.is` → `ipapi.co` → `ip-api.com`. Ba nhà cung cấp giới hạn
  tốc độ độc lập nhau, nên phải có chuỗi fallback — `ipapi.co` rất hay trả `RateLimited`.
  Kết quả cache 12 giờ trong config, khởi động lại không gọi lại API.

27 mã WMO gộp thành 15 nhóm có icon và tên dịch riêng. Icon có bản ngày/đêm cho trời quang
và ít mây (`weather-sun` ↔ `weather-moon`).

---

## Chỉ báo crypto

Nguồn **Binance public REST**, không cần key:

- `GET /api/v3/ticker/24hr?symbols=[...]` — một request cho toàn bộ danh sách theo dõi
- `GET /api/v3/ticker/price` — tải toàn bộ danh sách cặp (~3.700 cặp, ~150 KB) một lần
  mỗi lần mở Cài đặt, rồi lọc tại chỗ khi bạn gõ. `exchangeInfo` đúng ngữ nghĩa hơn nhưng
  nặng **17 MB**, không đáng
- `GET /api/v3/ticker/price?symbol=X` — kiểm tra một mã lẻ khi chưa có danh sách

**Mã viết liền, không có dấu gạch chéo.** Gõ `BNB/USDT` thì API trả
`-1100 Illegal characters found in parameter 'symbol'`. Ô nhập tự chuẩn hoá —
`BNB/USDT`, `bnb-usdt`, `BNB USDT` đều thành `BNBUSDT` — và danh sách gợi ý bên dưới
lọc theo những gì bạn gõ, ưu tiên cặp quote bằng USDT.

Menu hiện từng cặp với giá, biến động 24h, và submenu có cao/thấp/khối lượng 24h,
**Hiện trên thanh trạng thái**, **Copy giá**, **Bỏ theo dõi**.

Số lẻ tự co giãn theo độ lớn: `79,697.28` nhưng `0.00004312`.

⚠️ **Binance chặn theo vùng.** Một số mạng nhận `HTTP 451` — menu sẽ ghi rõ
*"Binance chặn mạng này"* thay vì retry vô ích. Đổi `endpoint` trong Cài đặt
(ví dụ `https://api.binance.us`) nếu cần.

---

## Chỉ báo hệ thống

Đọc thẳng `/proc` và `/sys`, không cần `psutil`, không gọi lệnh ngoài.

| Chỉ số | Nguồn |
| :--- | :--- |
| Tải CPU | delta `/proc/stat` giữa hai lần lấy mẫu |
| Load average, uptime | `/proc/loadavg`, `/proc/uptime` |
| Nhiệt độ CPU | `/sys/class/hwmon/*/temp*_input`, fallback `/sys/class/thermal` |
| RAM, swap | `/proc/meminfo` (dùng `MemAvailable`, không phải `total − free`) |
| Tốc độ mạng | delta `/proc/net/dev` |
| GPU NVIDIA | `libnvidia-ml.so` (NVML) qua `ctypes` |
| GPU AMD / Intel | `/sys/class/drm/card*/device/` — `gpu_busy_percent`, `mem_info_vram_*`, `pp_dpm_sclk` |

**Chọn cảm biến nhiệt.** Máy thường có nhiều cảm biến (`k10temp`, `nvme`, `iwlwifi`…).
Chế độ tự động ưu tiên chip CPU theo thứ tự `k10temp → zenpower → coretemp → cpu_thermal →
acpitz`, trong chip thì ưu tiên nhãn `Tctl → Tdie → Package id 0`. Chọn tay được trong Cài đặt;
key lưu dạng `chip/nhãn` vì số thứ tự `hwmonN` **không ổn định qua mỗi lần khởi động**.

**Chọn cổng mạng.** Mặc định tự động: bám theo cổng mang default route trong `/proc/net/route`,
nên rút dây mạng là tự chuyển sang wifi mà không phải vào Cài đặt. Chọn tay cũng được — danh
sách chỉ hiện card vật lý, lọc bằng cách kiểm tra symlink `/sys/class/net/<if>/device`. Cách
lọc này loại sạch `lo`, `docker0`, `br-*`, `veth*`, `tun*` trong một bước; máy đang chạy
container có thể có vài chục interface ảo và cộng hết vào sẽ đếm trùng mọi byte.

**Không có GPU thì phần GPU tự tắt** và Cài đặt hiện cảnh báo nói rõ cần gì, thay vì bày một
ô tick không làm gì cả.

## Vận hành

```bash
systemctl --user restart claude-status
systemctl --user stop claude-status
journalctl --user -u claude-status -f
```

Sinh lại icon sau khi sửa màu/hình trong `gen_icons.py`:

```bash
python3 gen_icons.py && systemctl --user restart claude-status
```

Gỡ bản cài từ checkout:

```bash
systemctl --user disable --now claude-status
rm ~/.config/systemd/user/claude-status.service
```

Rồi xóa các entry trỏ tới `hooks/emit.sh` trong `~/.claude/settings.json`
(hoặc khôi phục từ file `.bak-*` mà installer đã tạo).

---

## Ghi chú kỹ thuật

**`PermissionRequest` là hook có quyền allow/deny.** Nếu script hook in bất cứ gì ra
stdout, Claude Code có thể hiểu đó là quyết định và tự động duyệt/từ chối tool call.
`emit.sh` bọc toàn bộ thân script trong `{ ... } >/dev/null 2>&1` và luôn `exit 0`.
Đã test: input hợp lệ, JSON hỏng, và cả khi thư mục spool không ghi được — cả ba đều
cho exit 0, stdout 0 byte.

**Animation nằm ở label, không phải icon.** Đo trên GNOME 42 + `ubuntu-appindicators`:
đổi file icon chỉ repaint được **~1 fps** dù push nhanh cỡ nào, còn đổi label repaint
tới **~4 fps**. Nên icon để tĩnh, spinner `◐◓◑◒` chạy ở label. Braille (`⠋⠙⠹`) không
có glyph trong font panel — hiện ra thành dấu chấm lộn xộn, đừng dùng.

**Nhãn trên bar phải có bề rộng cố định.** Khu status của GNOME canh phải, nên một chỉ báo
rộng thêm một ký tự là đẩy mọi chỉ báo bên trái nó dịch sang. Tốc độ mạng nhảy từ 2 lên 3
chữ số là đủ để thấy CPU và RAM giật.

Đệm bằng space thường **không** giải quyết được. Đo trong font panel (Ubuntu 11):

| Ký tự | Rộng |
| :--- | ---: |
| chữ số `0`–`9` | 8 px (tabular, nên số tự canh cột) |
| `.` | 4 px |
| `U+0020` space | **3 px** |
| `U+2007` figure space | 8 px — định nghĩa là bề rộng một chữ số |
| `U+2008` punctuation space | 4 px — định nghĩa là bề rộng dấu chấm |
| `K` `M` `G` `B` | 9, 13, 10, 10 px |

Nên `claude_status/labels.py` đệm chữ số bằng `U+2007`, bù ô dấu chấm bằng `U+2008`, và
đổi đơn vị ở mốc 999.5 thay vì 1024 để phần định trị không bao giờ cần chữ số thứ tư
(`1023 B/s` từng render thành `1023B`, rộng hơn mọi giá trị khác một ô).

Chữ đơn vị thì không có ký tự Unicode nào định nghĩa theo nó, nên chúng được cân bằng bằng
cách **đo font thật** qua Pango lúc chạy. Phần đệm đó đặt ở **đầu** chuỗi chứ không phải cuối:
nhãn kết thúc bằng khoảng trắng sẽ hỏng nếu có tầng nào trên đường ra panel cắt trailing space.

Đo lại trên 45 tổ hợp giá trị ngẫu nhiên: bản cũ cho 17 bề rộng khác nhau, chênh 80 px;
bản mới cho **đúng một** bề rộng. Nhãn crypto cũng được xử lý tương tự ở phần biến động 24h.

**Lấy mẫu phần cứng chia hai nhịp.** Không phải file nào trong `/sys` cũng rẻ như nhau: đọc
`k10temp` mất 0.03 ms nhưng mỗi cảm biến NVMe mất ~0.6 ms (thao tác đọc đánh thức controller
ổ cứng), và mỗi truy vấn xung/điện năng của NVML mất ~1.2–1.4 ms. Nên mỗi tick chỉ đọc đúng
cảm biến đang hiển thị cộng vài counter GPU rẻ; danh sách cảm biến đầy đủ, xung GPU và điện
năng chạy ở nhịp chậm hơn 8 lần vì chúng chỉ xuất hiện trong menu.

**NVML chứ không phải `nvidia-smi`.** Đo trên GTX 1650 Ti driver 580: một truy vấn
`nvidia-smi` đầy đủ tốn ~37 ms, cùng ngần ấy thông tin qua NVML tốn ~4.8 ms. Ở nhịp 3 giây
trên GTK main loop thì subprocess thấy khựng, còn shared library thì không.

**Ghi config là merge, không phải ghi đè.** `Config.save()` đọc lại file trên đĩa rồi
replay đúng những key mà tiến trình đó đã đổi. Nếu dump thẳng bản chụp trong bộ nhớ thì
service và một instance thứ hai (chạy thử từ terminal) sẽ lặng lẽ xoá thay đổi của nhau —
triệu chứng là ngôn ngữ hoặc một tuỳ chọn tự nhảy về mặc định.

**Mọi request mạng chạy ở thread riêng.** `claude_status/net.py` gọi urllib trong
`threading.Thread` rồi trả kết quả về GTK main loop bằng `GLib.idle_add`. Gọi thẳng
trong main loop sẽ treo cả panel suốt thời gian request.

**Icon phải vẽ đầy khung 22×22.** GNOME scale nguyên canvas về kích thước icon của panel,
nên hình vẽ nhỏ trong canvas sẽ trông bé hơn hẳn các icon hàng xóm. Icon trong
`gen_icons.py` vẽ trong khoảng x/y 2..20 và dùng gradient để đọc được trên cả panel sáng
lẫn tối — AppIndicator **không** tự đổi màu icon symbolic theo theme.

**Ba AppIndicator, một tiến trình.** Mỗi panel là một `AppIndicator.Indicator` riêng;
tắt panel = `set_status(PASSIVE)`, không hủy object, nên bật lại tức thì.
Panel Claude giữ nguyên id `claude-status` cũ để vị trí trên bar không nhảy khi nâng cấp.

**Không có event "thinking" riêng.** Trạng thái *working* suy ra từ `UserPromptSubmit`
đến `Stop`. Không tách được extended thinking khỏi lúc đang sinh text.

**Session chết bất thường.** `kill -9` hoặc đóng terminal đột ngột thì `SessionEnd`
không fire. TTL 6 giờ sẽ dọn, hoặc dùng *Bỏ khỏi danh sách* / *Xóa hết session*.
Cột thời gian trong menu giúp nhận ra session bị kẹt.

**Chi phí.** Đo trên máy test, mỗi cấu hình 24 giây:

| Bật những gì | CPU của tiến trình |
| :--- | ---: |
| Chỉ chỉ báo Claude | 0.17% |
| + thời tiết + crypto | 0.17% |
| + hệ thống, nhịp 3 giây, đủ 6 chỉ số và GPU | 0.67% |

Thời tiết và crypto gần như miễn phí vì chúng chỉ gọi mạng 30 phút / 60 giây một lần. Phần
lớn chi phí của chỉ báo hệ thống là dựng lại menu GTK chứ không phải đọc file; tăng chu kỳ
lên 5–10 giây trong Cài đặt là giảm tương ứng. gnome-shell tăng thêm khoảng 0.3%.
Hook thêm khoảng 2–3 ms mỗi tool call (một `cat` + một `mv`).

---

## Cấu trúc mã

```
indicator.py              entry point mỏng, re-export cho test và script cũ
claude_status/
  app.py                  App: gắn panel + config + cửa sổ cài đặt
  panel.py                Panel base: một AppIndicator, một section config
  claude_panel.py         panel Claude Code (spool, state machine, spinner)
  weather.py              panel + client Open-Meteo + dò IP
  crypto.py               panel + client Binance + format giá
  labels.py               format số bề rộng cố định cho nhãn trên bar
  system.py               đọc CPU/RAM/nhiệt/mạng từ /proc và /sys
  system_panel.py         panel hệ thống
  gpu.py                  backend GPU: NVML cho NVIDIA, sysfs cho AMD/Intel
  prefs.py                cửa sổ GTK Cài đặt
  config.py               config dotted-path, deep-merge, notify listener
  sessions.py             Session / Store — máy trạng thái từ hook event
  i18n.py                 bảng dịch EN/VI
  net.py                  fetch JSON non-blocking
  paths.py                định vị icon (checkout hay /usr/lib đều đúng)
gen_icons.py              sinh 22 icon SVG
hooks/emit.sh             hook Claude Code
merge_settings.py         merge hook vào ~/.claude/settings.json
packaging/                control, systemd unit, .desktop, copyright, maintainer scripts
packaging/apt/            trang chủ apt repo + script tạo khoá ký
build-deb.sh              đóng gói .deb
build-apt-repo.sh         dựng apt repository phẳng vào ./public
.github/workflows/        CI: tag -> test -> .deb -> Release -> apt repo
```

## Test

```bash
python3 test_store.py      # 29 assertion: state machine, i18n, icon
python3 test_features.py   # 97 assertion: config, thời tiết, crypto, hệ thống, GPU, nhãn, icon
```

## Phát hành

```bash
# 1. bump __version__ trong claude_status/__init__.py
git commit -am "..." && git push
git tag v2.2.0 && git push --tags
```

`release.yml` chạy test, dựng `.deb`, gắn vào Release, rồi gọi `apt.yml` dựng lại
apt repository từ **toàn bộ** `.deb` đang đính kèm các Release và deploy lên GitHub Pages.
Trang web là hàm thuần của các Release, không có state nào phải đồng bộ tay.

Workflow từ chối build nếu tag lệch với `__version__` — chống việc phát hành nhầm số hiệu.

**Khoá ký.** Repository apt bắt buộc phải ký, nếu không mọi người dùng phải thêm
`[trusted=yes]`, tức tắt đúng cái kiểm tra có ý nghĩa. Tạo khoá một lần:

```bash
packaging/apt/make-signing-key.sh "status-bar apt repository" you@example.com
```

Script tạo khoá sign-only **không passphrase** (CI không gõ được passphrase), ghi public key
vào `packaging/apt/status-bar-archive-keyring.asc` để commit, rồi in ra lệnh bạn tự chạy để
đưa private key vào secret `APT_GPG_PRIVATE_KEY`. Private key không đi qua tay ai khác.
Nếu secret lộ: tạo khoá mới, chạy lại workflow `apt`, người dùng import lại public key.

Dựng thử repo ở máy:

```bash
./build-deb.sh && APT_SIGN_KEY=<fingerprint> ./build-apt-repo.sh
python3 -m http.server --directory public 8899
```

## Giấy phép

[MIT](LICENSE) © 2026 Minh Ngoc.

Dữ liệu thời tiết từ [Open-Meteo](https://open-meteo.com) (CC BY 4.0), giá crypto từ
API công khai của [Binance](https://binance-docs.github.io/apidocs/spot/en/). Cả hai đều
là dịch vụ của bên thứ ba, không kèm trong giấy phép này.
