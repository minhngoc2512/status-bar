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
  | gpg --dearmor | sudo tee /usr/share/keyrings/status-bar-archive-keyring.gpg > /dev/null

echo "deb [signed-by=/usr/share/keyrings/status-bar-archive-keyring.gpg] https://minhngoc2512.github.io/status-bar/ ./" \
  | sudo tee /etc/apt/sources.list.d/status-bar.list

sudo apt update
sudo apt install status-bar
```

`apt upgrade` sẽ tự cập nhật từ đó về sau.

> Đừng dùng `sudo gpg --dearmor -o <file>`. Nếu file đích đã tồn tại, gpg hỏi có ghi đè
> không, đọc luôn dữ liệu từ pipe làm câu trả lời, rồi để lại **file 0 byte** — sau đó
> `apt update` im lặng bỏ qua repo và `apt install status-bar` báo không tìm thấy gói.
> Dạng `gpg --dearmor | sudo tee` ở trên ghi đè sạch và chạy lại bao nhiêu lần cũng được.

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
/usr/share/applications/claude-status.desktop   mục "Status Bar" trong app menu
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

Backup `~/.claude/settings.json`, merge hook vào (giữ nguyên hook của tool khác), rồi cài +
bật systemd user service trỏ vào thư mục hiện tại.

**Script sẽ từ chối chạy nếu gói `status-bar` đã cài qua apt.** Chạy chồng lên nhau là cách
chắc chắn nhất để máy rơi vào trạng thái khó hiểu: unit ghi vào `~/.config/systemd/user/`
**che** unit của gói nên systemd lặng lẽ chạy mã trong thư mục checkout thay vì mã đã cài,
và mỗi event của Claude Code bị spool hai lần. Muốn ghi đè thì `./install.sh --force`.

Hook chỉ áp dụng cho **session Claude Code mở mới** sau khi cài.

### Cài lên máy không có Claude Code

Không hỏng gì. Ba chỉ báo thời tiết, crypto và phần cứng chạy bình thường; chỉ báo Claude
sẽ luôn rỗng. Cài đặt sẽ hiện cảnh báo màu cam nói rõ, và menu của chỉ báo Claude ghi
*"Máy này không có Claude Code"* thay vì chỉ *"Không có session nào"* — để không ai tưởng
là hỏng.

`claude-status-hooks` vẫn chạy được và vẫn tạo `~/.claude/settings.json`: hook sẽ hoạt động
ngay khi Claude Code được cài sau đó. Nó in ra một lưu ý khi phát hiện chưa có Claude Code.

Trường hợp dễ nhầm hơn là **có Claude Code nhưng quên chạy `claude-status-hooks`** — chỉ báo
cũng rỗng y hệt. Cả Cài đặt lẫn menu đều phân biệt hai trường hợp này và nói đúng lệnh cần chạy.

### Chuyển từ bản `install.sh` sang gói apt

Bản checkout đặt unit ở `~/.config/systemd/user/`, nơi này **che** unit của gói, nên phải gỡ:

```bash
systemctl --user disable --now claude-status
rm ~/.config/systemd/user/claude-status.service
systemctl --user daemon-reload
```

Rồi chạy `claude-status-hooks` và `systemctl --user enable --now claude-status`.
Từ 2.2.2, `claude-status-hooks` **tự gỡ** các hook entry trỏ vào bản cài khác trước khi thêm
của mình, nên chuyển qua lại giữa hai kiểu cài không còn để lại entry trùng. Hook của tool
khác trong cùng file không bị đụng tới.

Config `~/.config/claude-status/config.json` giữ nguyên, không mất cài đặt nào.

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
permission mode, số token, **Mở thư mục**, **Copy đường dẫn**, **Bỏ khỏi danh sách**.

### Hạn mức gói (plan usage limits)

```
◐ working  53%          ← còn lại của cửa sổ 5 giờ, ngay trên thanh trạng thái

Hạn mức gói
    5 giờ   còn 53%   reset sau 2h 16m
    Tuần    còn 70%   reset sau 3d 4h
```

Claude Code báo phần **đã dùng**; ở đây hiện phần **còn lại**, và cả bar lẫn menu dùng chung
một con số — hai chỗ hiện hai số cộng lại bằng 100 là cái bẫy dễ đọc nhầm. Con số trên bar
được đệm bề rộng cố định như mọi nhãn khác (`0%`, `53%`, `100%` đều rộng 37 px), nếu không
thì mỗi lần đổi chữ số nó lại đẩy các icon bên trái. Tắt được ở **Cài đặt → Chung**.

#### Phải có một phiên `claude` chạy trong terminal

statusLine **chỉ được gọi bởi phiên TUI trong terminal**, và chỉ sau khi phiên đó đã gọi API
ít nhất một lần. Đây là điều kiện dễ bỏ sót nhất: máy đang mở Claude Code mà bar vẫn trống là
chuyện bình thường, nếu đó không phải phiên TUI.

| Cách chạy Claude Code | Có gọi statusLine? |
| :--- | :--- |
| `claude` trong terminal (TUI), đã chat ít nhất 1 lần | ✅ |
| `claude` trong terminal nhưng chưa gửi tin nào | ⚠️ có payload, nhưng chưa có `rate_limits` |
| App desktop (`--output-format stream-json`) | ❌ |
| `claude -p "..."` (print mode) | ❌ |

Không cần phiên đó mở trong đúng repo này. `statusLine` nằm ở `~/.claude/settings.json` nên
bất kỳ phiên `claude` TUI nào trên máy cũng bơm dữ liệu về.

Kiểm tra nhanh khi không thấy số:

```bash
pgrep -ax claude | grep -v output-format
```

Có dòng `<pid> claude` trần là đúng loại phiên. Không ra gì nghĩa là chưa có phiên TUI nào.

`-x` (khớp đúng tên tiến trình) là phần quan trọng: `pgrep -f claude` bắt luôn cả tiến trình
con của app desktop, `chrome-native-host`, MCP server… lệnh trả về hai chục dòng nhiễu và phiên
TUI thật lại lọt thỏm ở giữa. Còn `grep -v output-format` loại nốt các phiên
`--output-format stream-json` của app desktop — thứ không bao giờ sinh ra hạn mức.

#### Con số sống được bao lâu

Đóng terminal không làm số biến mất ngay — nhưng nó **đứng yên**, vì không còn payload nào
tới nữa. Dùng tiếp bằng app desktop thì hạn mức thật tụt xuống trong khi bar vẫn giữ số cũ.

| Tình huống | Trên bar |
| :--- | :--- |
| Phiên TUI đang mở | hiện, cập nhật liên tục |
| Vừa đóng terminal, chưa hết cửa sổ | vẫn hiện, nhưng đã cũ |
| `resets_at` đã qua | tự ẩn |
| Sau khi restart service / reboot | mất, tới khi có phiên TUI mới |

Hai hành vi cuối là cố ý. Khi `resets_at` đã qua, con số bị bỏ khỏi bar thay vì hiện một tỉ lệ
đã cũ — hiện sai còn tệ hơn không hiện. Và giá trị chỉ nằm trong RAM (`ClaudePanel.limits`),
không ghi xuống đĩa, nên nó không sống sót qua một lần khởi động lại.

Con số này **không nằm ở đâu trên đĩa**. Nó tới dưới dạng header
`anthropic-ratelimit-unified-*` trên mỗi response và không được lưu lại — tra bằng ba cách
(tìm theo tên file, grep nội dung `~/.claude` và `~/.claude.json`, và bắt payload hook thật)
đều không ra. Chỗ duy nhất Claude Code phơi ra là **statusLine**: nó đổ một object JSON vào
stdin của lệnh statusLine, theo đúng schema ghi trong tài liệu nhúng của binary:

```json
"rate_limits": {   // Optional: chỉ có với subscriber, sau response API đầu tiên
  "five_hour": { "used_percentage": number, "resets_at": number },
  "seven_day": { "used_percentage": number, "resets_at": number }
}
```

`hooks/statusline.sh` đổ payload đó vào cùng spool với hook. Nó chạy mỗi lần status line
render — thường xuyên hơn hook nhiều — nên **không sinh tiến trình con nào**: không `jq`,
không `python`, chỉ dùng parameter expansion của bash.

**stdout của statusLine chính là dòng status trong Claude Code.** Nên script in ra đúng tóm
tắt `5h 47% · 7d 30%`, và không in gì khi payload không có hạn mức. `claude-status-hooks`
**không bao giờ ghi đè** statusLine sẵn có — nếu bạn đã cấu hình lệnh riêng, nó in ra đường
dẫn để bạn tự gọi lồng vào.

**Không phải cấu hình nào cũng có số này.** Claude Code chỉ báo hạn mức cho gói Claude.ai.
Trỏ nó sang Vertex, Bedrock, một proxy như 9router, hay dùng API key trần thì con số không
bao giờ tới. Indicator đọc khối `env` trong `~/.claude/settings.json` cộng biến môi trường để
nhận ra, và nói thẳng lý do thay vì để trống:

```
Không lấy được hạn mức gói
    request đi qua Google Vertex AI, nơi không báo hạn mức
```

### Đếm token

```
Token: ra 195K · vào 400
Cache: ghi 341K · đọc 26.8M
200 lượt gọi API
```

**Không hiển thị được hạn mức còn lại.** Đã tra: không có file nào về usage/quota/rate-limit
trong `~/.claude`, và payload của hook cũng không mang con số nào — kiểm trên `PreToolUse`,
`PostToolUse`, `PermissionRequest`, `Notification` thật. Claude Code biết hạn mức còn lại từ
header của response lúc gọi API và không lưu lại. Nên phần này báo **đã tiêu bao nhiêu**,
không báo được **còn lại bao nhiêu**.

Nguồn số liệu là `message.usage` trong transcript. Mọi payload hook đều mang sẵn
`transcript_path` nên không phải đoán đường dẫn. Dòng nào không chứa chuỗi `"usage"` thì bị bỏ
qua mà **không parse**, nên phần lớn nội dung hội thoại không bao giờ được giải mã — đo trên
transcript 7.6 MB / 2.115 dòng: parse hết mất 39 ms, lọc trước còn 21.8 ms. Sau lượt đầu chỉ
đọc phần byte mới ghi thêm, tốn **0.02 ms**. Tắt được ở Cài đặt → Chung.

Đọc tăng dần phải chịu được ba tình huống, cả ba đều có test: transcript đang được ghi dở nên
dòng cuối bị **cắt đôi** giữa hai lần đọc, file bị **thay thế** (session mới trùng tên), và
file **ngắn lại**. Trường hợp đầu giữ lại phần dở dang chờ ghép; hai trường hợp sau vứt offset
và đọc lại từ đầu.

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

**`apt upgrade` không khởi động lại được indicator.** dpkg chạy bằng root và không có tay
nắm nào vào session đăng nhập của bạn, nên nó thay file trên đĩa xong là hết — tiến trình cũ
vẫn chạy mã cũ cho tới lần đăng nhập sau. Không có gì báo, và `dpkg -l` thì hiện version mới,
nên rất dễ tưởng đã nâng cấp xong.

Indicator tự phát hiện: so `__version__` đang nạp trong bộ nhớ với version đọc từ
`__init__.py` trên đĩa (kiểm tối đa mỗi 60 giây), lệch thì menu của **mọi** panel hiện
*"Đã cài bản X nhưng chưa chạy — chạy: systemctl --user restart claude-status"*.
`postinst` cũng nhắc, và phân biệt cài mới với nâng cấp: nâng cấp thì chỉ in đúng lệnh
restart chứ không lặp lại hướng dẫn cài lần đầu.

**Đừng dùng `sudo` với `systemctl --user`.** `--user` trỏ tới session đăng nhập của *bạn*;
thêm `sudo` là nó đi tìm session của root, vốn không có D-Bus, và báo
`Failed to connect to bus: $DBUS_SESSION_BUS_ADDRESS and $XDG_RUNTIME_DIR not defined`.

**Bấm biểu tượng trong app menu mở Settings.** Một tray app không có cửa sổ để đưa lên, nên
cú bấm thứ hai mà chỉ im lặng thoát thì trông như không làm gì. Bản thứ hai giờ đánh thức bản
đang chạy mở cửa sổ Cài đặt rồi mới thoát. Nhấp phải vào biểu tượng còn có mục **Cài đặt**
riêng (`Exec=/usr/bin/claude-status --settings`).

Cửa sổ được đưa lên bằng `present_with_time()` với thời gian của X server, không phải
`present()` trần. `present()` không kèm timestamp bị cơ chế chống "focus stealing" của
compositor chặn: cửa sổ **có** được tạo nhưng nằm chìm dưới cửa sổ đang focus, nên cú bấm vẫn
trông như không có gì xảy ra. Đo trên GNOME 42/X11: `_NET_ACTIVE_WINDOW` vẫn giữ nguyên app cũ.
Wayland không có cơ chế tương đương — GTK dùng activation token — nên nhánh đó `present()` thường.

Cơ chế đánh thức là `SIGUSR1`, không phải D-Bus: tiến trình đã được tìm thấy qua chính file lock nó
buộc phải giữ, nên không cần đăng ký tên, không cần service file, không có gì phải giữ đồng
bộ với packaging. Pid được ghi vào file lock **sau** khi `flock` thành công, và file mở bằng
`O_RDWR|O_CREAT` chứ không phải `"w"` — `open(..., "w")` cắt file ngay lúc mở, nên bản thứ
hai sẽ xoá mất pid của chính bản nó sắp nhường việc, trước cả khi biết là lock đã có chủ.

Bản cũ (≤ 2.2.5) ghi file lock rỗng, nên `running_pid()` trả 0 và không tín hiệu nào được
gửi. Điều đó quan trọng: `SIGUSR1` gửi tới bản chưa có handler sẽ **giết** tiến trình, và đó
đúng là tình huống "đã nâng cấp nhưng chưa restart".

**Chỉ một bản chạy được một lúc.** Rất dễ có hai bản: systemd user service cộng thêm một
cú bấm vào biểu tượng trong app grid. Hậu quả không chỉ là hai icon — `drain()` xoá từng
file event sau khi đọc, nên hai bản **chia nhau** spool. Đo với 3 session và 12 event: mỗi
bản mất hẳn một session, và một bản hiển thị `working` cho session thực tế đã chuyển sang
`confirm` vì bản kia nuốt mất event. Một prompt chờ duyệt có thể biến mất như thế.

Nên `main()` giữ một `flock` trên `~/.cache/claude-status/indicator.lock`. Bản thứ hai in
một dòng rồi thoát với mã 0, kèm `notify-send` để cú bấm không có vẻ như không làm gì cả.
flock được kernel nhả khi tiến trình chết, nên `kill -9` không để lại lock cũ.

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
hooks/statusline.sh       statusLine: nguồn duy nhất của hạn mức gói
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
python3 test_features.py   # 184 assertion: config, thời tiết, crypto, hệ thống, GPU, nhãn, hook, icon
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

Script tạo khoá sign-only, bảo vệ bằng một passphrase ngẫu nhiên nó tự sinh và **không bao
giờ in ra**, ghi public key vào `packaging/apt/status-bar-archive-keyring.asc` để commit, rồi
đẩy private key và passphrase thẳng vào hai secret `APT_GPG_PRIVATE_KEY` và
`APT_GPG_PASSPHRASE` qua pipe — không ghi ra đĩa lần nào, keyring tạm xoá khi script kết thúc.
Nếu secret lộ: chạy lại script, người dùng import lại public key.

**Vì sao khoá bắt buộc phải có passphrase.** gpg 2.4 — bản mà runner ubuntu-24.04 dùng —
**tự bảo vệ lại** một secret key không passphrase ngay lúc import, sau đó agent không mở khoá
được nếu không có terminal. Đo trên runner, cả bốn cách đều hỏng:

| Cách gọi | Lỗi |
| :--- | :--- |
| `--batch` thường | `Inappropriate ioctl for device` |
| `--batch --no-tty` | `Inappropriate ioctl for device` |
| `--pinentry-mode loopback` | `Sorry, we are in batchmode - can't get input` |
| `loopback --passphrase ""` | `No passphrase given` |

Khoá đã có sẵn passphrase thì import và ký sạch trên mọi phiên bản. Passphrase truyền qua
file descriptor chứ không qua tham số dòng lệnh, để không lộ trong bảng tiến trình.

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
