# Hướng dẫn tạo video whiteboard từ SRT

Tài liệu này hướng dẫn từng bước tạo một video whiteboard bằng repository này, từ chuẩn bị môi trường, tạo ảnh và annotation, render từng cảnh, ghép các cảnh, đến bước tùy chọn thêm giọng đọc và phụ đề.

> **Điểm quan trọng:** phần render video chạy hoàn toàn trên máy local và **không cần OpenAI API key**. API hoặc công cụ AI chỉ cần thiết nếu bạn muốn dùng AI để tự tạo ảnh minh họa, giọng đọc hoặc nội dung đầu vào.

## 1. Pipeline tổng quát

```text
SRT hoặc kịch bản
    ↓
Chia nội dung thành các cảnh
    ↓
Tạo một ảnh line-art cho mỗi cảnh
    ↓
Tạo annotation JSON xác định vùng và thời gian vẽ
    ↓
Kiểm tra/chỉnh annotation bằng preview.html
    ↓
Render từng cảnh thành MP4
    ↓
Ghép các cảnh thành một video
    ↓
Tùy chọn: thêm voice-over và phụ đề
    ↓
Video hoàn chỉnh
```

Repository tự thực hiện được các phần sau:

- Parse SRT và đề xuất chia cảnh.
- Hiển thị giao diện chỉnh annotation.
- Render ảnh và annotation thành MP4 whiteboard.
- Ghép nhiều MP4 theo thứ tự.

Repository **không tự thực hiện** các phần sau:

- Sinh ảnh minh họa từ nội dung SRT.
- Tự suy luận annotation hoàn chỉnh từ ảnh.
- Tạo giọng đọc.
- Tự chèn audio hoặc phụ đề vào video.
- Tự chạy toàn bộ pipeline bằng một lệnh duy nhất.

## 2. Yêu cầu hệ thống

Khuyên dùng:

- macOS, Linux hoặc Windows.
- Python 3.10 trở lên; Python 3.11 hoặc 3.12 thường dễ tương thích thư viện nhất.
- FFmpeg để encode, kiểm tra và ghép video.
- Chrome hoặc Edge để chỉnh annotation bằng `assets/preview.html`.

Kiểm tra Python:

```bash
python3 --version
```

Cài FFmpeg trên macOS bằng Homebrew:

```bash
brew install ffmpeg
```

Kiểm tra FFmpeg:

```bash
ffmpeg -version
ffprobe -version
```

FFmpeg được khuyên dùng nhưng không hoàn toàn bắt buộc. Nếu FFmpeg không khả dụng, renderer có thể dùng PyAV làm phương án dự phòng.

## 3. Vào thư mục dự án

Mở Terminal và chạy:

```bash
cd /Volumes/Docs/App/srt-whiteboard-animation
```

Tất cả lệnh trong tài liệu này được giả định chạy từ thư mục gốc trên.

## 4. Chuẩn bị môi trường Python

### 4.1. Tạo virtualenv và cài dependency

```bash
python3 scripts/prepare_env.py
```

Script tạo thư mục `.venv` và cài các thư viện cần thiết, bao gồm OpenCV, NumPy, Pillow và PyAV.

Sau khi cài xong, kiểm tra:

```bash
python3 scripts/prepare_env.py --check
```

Nếu thành công, script in một dòng tương tự:

```text
ENV_PY=/Volumes/Docs/App/srt-whiteboard-animation/.venv/bin/python
```

Trong các lệnh tiếp theo, tài liệu sử dụng trực tiếp:

```text
.venv/bin/python
```

### 4.2. Nếu Python mặc định không cài được dependency

Nếu Python hệ thống quá mới và một package chưa có wheel tương thích, hãy dùng Python 3.12:

```bash
brew install python@3.12
/opt/homebrew/bin/python3.12 scripts/prepare_env.py
```

Trên máy Mac Intel, executable Homebrew có thể nằm tại `/usr/local/bin/python3.12` thay vì `/opt/homebrew/bin/python3.12`.

## 5. Chạy nhanh video mẫu “Vì sao trời có mưa”

Repository có script `scripts/generate_rain_demo.py` để tạo ảnh và annotation mẫu mà không cần API.

### 5.1. Tạo ảnh và annotation

```bash
.venv/bin/python scripts/generate_rain_demo.py
```

Kết quả:

```text
assets/whiteboard/rain-demo/
├── scene-01-why-rain.png
└── scene-01-why-rain.annotation.json
```

Ảnh mô tả chu trình:

```text
Mặt Trời làm nước bốc hơi
→ hơi nước ngưng tụ thành mây
→ giọt nước trong mây lớn dần
→ giọt nước rơi xuống thành mưa
```

### 5.2. Render video mẫu

```bash
.venv/bin/python scripts/render_stream_whiteboard.py \
  assets/whiteboard/rain-demo/scene-01-why-rain.png \
  assets/whiteboard/rain-demo/scene-01-why-rain.annotation.json \
  assets/whiteboard/rain-demo/scene-01-why-rain-whiteboard.mp4 \
  assets/drawing-hand.png \
  --ink-path skeleton \
  --color-fill contour-wipe
```

File hoàn thành:

```text
assets/whiteboard/rain-demo/scene-01-why-rain-whiteboard.mp4
```

Mở video trên macOS:

```bash
open assets/whiteboard/rain-demo/scene-01-why-rain-whiteboard.mp4
```

### 5.3. Chạy cả hai bước liên tiếp

```bash
.venv/bin/python scripts/generate_rain_demo.py && \
.venv/bin/python scripts/render_stream_whiteboard.py \
  assets/whiteboard/rain-demo/scene-01-why-rain.png \
  assets/whiteboard/rain-demo/scene-01-why-rain.annotation.json \
  assets/whiteboard/rain-demo/scene-01-why-rain-whiteboard.mp4 \
  assets/drawing-hand.png \
  --ink-path skeleton \
  --color-fill contour-wipe
```

## 6. Quy trình đầy đủ cho một dự án mới

Phần này áp dụng khi bạn có SRT hoặc kịch bản riêng và muốn tạo nhiều cảnh.

### Bước 1: Chuẩn bị SRT

Ví dụ file `input.srt`:

```srt
1
00:00:00,000 --> 00:00:04,000
Ánh nắng làm nước ở sông, hồ và biển bốc hơi lên cao.

2
00:00:04,000 --> 00:00:08,000
Lên cao, hơi nước lạnh đi và ngưng tụ thành những đám mây.

3
00:00:08,000 --> 00:00:12,000
Khi đủ nặng, các giọt nước rơi xuống và tạo thành mưa.
```

Yêu cầu cơ bản:

- File được lưu ở UTF-8.
- Mỗi cue có thời gian bắt đầu và kết thúc hợp lệ.
- Các cue được xếp đúng thứ tự thời gian.

### Bước 2: Parse SRT và đề xuất chia cảnh

```bash
.venv/bin/python scripts/parse_srt.py input.srt \
  --target-sec 30 \
  --min-sec 25 \
  --max-sec 35 \
  > scenes.json
```

Script ghi JSON vào `scenes.json` và in phần tóm tắt dễ đọc ra Terminal.

Cấu trúc kết quả:

```json
{
  "cues": [
    {
      "index": 1,
      "startMs": 0,
      "endMs": 4000,
      "durMs": 4000,
      "text": "Nội dung phụ đề"
    }
  ],
  "scenes": [
    {
      "sceneIndex": 1,
      "startMs": 0,
      "endMs": 30000,
      "sceneDurationMs": 30000,
      "cueRange": [1, 8],
      "text": "Nội dung của cảnh"
    }
  ]
}
```

Mỗi scene nên truyền tải một ý chính. Với video ngắn, bạn có thể dùng một scene duy nhất.

### Bước 3: Tạo thư mục dự án

Ví dụ dự án tên `water-cycle`:

```bash
mkdir -p assets/whiteboard/water-cycle
```

Quy ước file:

```text
assets/whiteboard/water-cycle/
├── scene-01-evaporation.png
├── scene-01-evaporation.annotation.json
├── scene-01-evaporation-whiteboard.mp4
├── scene-02-condensation.png
├── scene-02-condensation.annotation.json
├── scene-02-condensation-whiteboard.mp4
└── final-whiteboard.mp4
```

Ảnh và annotation phải có cùng basename:

```text
scene-01-evaporation.png
scene-01-evaporation.annotation.json
```

### Bước 4: Tạo ảnh line-art cho từng scene

Ảnh có thể được:

- Vẽ thủ công.
- Tạo bằng Pillow, SVG hoặc phần mềm thiết kế.
- Tạo bằng công cụ AI bất kỳ.
- Tạo bằng OpenAI Image API nếu bạn chủ động chọn dịch vụ này.

OpenAI API key không phải yêu cầu của renderer.

Khuyến nghị hình ảnh:

- Tỷ lệ 16:9.
- Nền giấy màu kem `#F5EBD7`.
- Nét vẽ xám đậm.
- Chỉ dùng ít màu đỏ, cam hoặc xanh để nhấn mạnh.
- Không chèn chữ vào ảnh nguồn.
- Các chủ thể có khoảng cách rõ ràng để dễ chia `region`.
- Không dùng ảnh quá nhiều chi tiết hoặc texture phức tạp.

Kích thước gợi ý:

```text
1920 × 1080
1600 × 900
1280 × 720
```

Mọi cảnh nên dùng cùng tỷ lệ và kích thước để việc ghép video ổn định hơn.

### Bước 5: Tạo annotation JSON

Mỗi ảnh cần một annotation mô tả thứ tự, vùng và thời gian vẽ.

Ví dụ:

```json
{
  "sceneId": "scene-01",
  "canvas": {
    "width": 1920,
    "height": 1080
  },
  "storyBasis": "Mô tả ngắn nội dung của cảnh",
  "sceneDurationMs": 15000,
  "elements": [
    {
      "id": "background",
      "label": "Bối cảnh",
      "sequence": 1,
      "narrativeRole": "Thiết lập bối cảnh cho câu chuyện",
      "subtitle": "Nội dung subtitle tương ứng",
      "type": "structure",
      "region": {
        "x": 40,
        "y": 80,
        "width": 700,
        "height": 900
      },
      "reveal": {
        "direction": "top_to_bottom",
        "startMs": 300,
        "durationMs": 3500,
        "maskPaddingPx": 20,
        "protectedRegions": []
      },
      "handPath": {
        "start": [350, 100],
        "end": [350, 950],
        "easing": "easeInOut"
      }
    }
  ]
}
```

Ý nghĩa các trường chính:

| Trường | Ý nghĩa |
|---|---|
| `canvas.width`, `canvas.height` | Kích thước pixel chính xác của ảnh nguồn |
| `sceneDurationMs` | Tổng thời lượng cảnh, tính bằng mili giây |
| `sequence` | Thứ tự kể chuyện, bắt đầu từ 1 |
| `region` | Hình chữ nhật chứa nội dung cần vẽ |
| `reveal.startMs` | Thời điểm vùng bắt đầu được vẽ trong cảnh |
| `reveal.durationMs` | Thời gian vẽ vùng |
| `protectedRegions` | Những vùng phải giữ ẩn khi element hiện tại được vẽ |
| `subtitle` | Câu phụ đề liên quan đến element |
| `direction` | Hướng mô phỏng trong preview HTML |
| `handPath` | Đường mô phỏng trong preview; renderer thật tự tìm đường bút |

Quy tắc annotation:

1. `canvas` phải bằng đúng kích thước ảnh nguồn.
2. Tọa độ dùng pixel nguyên, gốc `(0, 0)` ở góc trên-trái.
3. Mọi `region` phải nằm trong canvas.
4. `sequence` nên liên tục: `1, 2, 3, ...`.
5. `startMs` của các vùng nên nối tiếp, không chồng nhau.
6. Nên để khoảng nghỉ 100–300 ms giữa hai vùng.
7. Element cuối nên kết thúc trước `sceneDurationMs` ít nhất 500 ms.
8. Nếu region trước chồng lên nội dung của region sau, thêm phần chồng vào `protectedRegions`.

> Renderer thực tế sắp thứ tự theo `reveal.startMs`. Vì vậy `sequence` và `startMs` phải cùng phản ánh một thứ tự kể chuyện.

### Bước 6: Chỉnh annotation bằng preview HTML

Mở preview bằng Chrome trên macOS:

```bash
open -a "Google Chrome" assets/preview.html
```

Trong giao diện:

1. Chọn **Mở thư mục**.
2. Chọn thư mục `assets/whiteboard/<tên-dự-án>`.
3. Chọn scene muốn chỉnh.
4. Kéo các cạnh hoặc góc để chỉnh `region`.
5. Chỉnh thời gian bắt đầu và kết thúc.
6. Kiểm tra thứ tự xuất hiện.
7. Lưu lại annotation.

Chrome và Edge hỗ trợ File System Access API để ghi trực tiếp về file JSON. Trình duyệt khác có thể chỉ tải file JSON mới xuống; khi đó bạn phải chép đè file cũ thủ công.

Preview HTML sử dụng rectangle để mô phỏng reveal. Đường bút thật chỉ được tạo khi chạy renderer Python.

### Bước 7: Tạo ảnh kiểm tra annotation

Lệnh chuẩn:

```bash
.venv/bin/python scripts/render_annotation_preview.py \
  assets/whiteboard/water-cycle/scene-01-evaporation.png \
  assets/whiteboard/water-cycle/scene-01-evaporation.annotation.json \
  assets/whiteboard/water-cycle/scene-01-evaporation-preview.jpg
```

Ảnh kết quả hiển thị rectangle, số thứ tự và hướng vẽ để kiểm tra vùng.

> **Lưu ý trên macOS/Linux:** script hiện có đường dẫn font Windows được hard-code. Nếu gặp lỗi font, hãy dùng `assets/preview.html` để kiểm tra hoặc sửa font trong `scripts/render_annotation_preview.py` sang một font có trên máy.

### Bước 8: Render từng scene

Cú pháp:

```bash
.venv/bin/python scripts/render_stream_whiteboard.py \
  <ảnh.png> \
  <ảnh.annotation.json> \
  <output.mp4> \
  assets/drawing-hand.png \
  --ink-path grid \
  --color-fill contour-wipe
```

Ví dụ:

```bash
.venv/bin/python scripts/render_stream_whiteboard.py \
  assets/whiteboard/water-cycle/scene-01-evaporation.png \
  assets/whiteboard/water-cycle/scene-01-evaporation.annotation.json \
  assets/whiteboard/water-cycle/scene-01-evaporation-whiteboard.mp4 \
  assets/drawing-hand.png \
  --ink-path skeleton \
  --color-fill contour-wipe \
  --fps 60
```

Các tùy chọn hữu ích:

| Tùy chọn | Giá trị | Mô tả |
|---|---|---|
| `--ink-path` | `grid` | Ổn định, phù hợp hầu hết ảnh |
| `--ink-path` | `skeleton` | Bám theo line-art rõ hơn |
| `--color-fill` | `contour-wipe` | Quét màu theo contour, là mặc định |
| `--color-fill` | `brush` | Tô màu bằng brush đi theo quỹ đạo |
| `--total-ms` | Số mili giây | Ghi đè `sceneDurationMs` |
| `--fps` | Ví dụ `30`, `60` | Frame rate đầu ra |
| `--cap-long-edge` | Ví dụ `720`, `1080` | Giới hạn cạnh dài để điều chỉnh tốc độ/chất lượng |
| `--bare-tip` | Không có giá trị | Không hiển thị ảnh bàn tay/bút |

Gợi ý lựa chọn:

- Dùng `grid` nếu ảnh có nhiều mảng hoặc skeleton bị đứt nét.
- Dùng `skeleton` nếu ảnh là line-art sạch, nét rõ ràng.
- Dùng `--cap-long-edge 720 --fps 30` để render thử nhanh.
- Dùng mặc định 1080 và 60 fps cho bản chính thức.

Trong quá trình render, script tạo file tạm:

```text
<output-name>_raw.mp4
```

Sau đó script ưu tiên FFmpeg để chuyển sang H.264. Nếu FFmpeg không khả dụng, nó thử PyAV. Khi encode thành công, dòng cuối Terminal sẽ là:

```text
OUTPUT=/đường/dẫn/tới/video.mp4
```

### Bước 9: Kiểm tra từng scene

Kiểm tra thông tin video:

```bash
ffprobe -v error \
  -show_entries format=duration \
  -show_entries stream=codec_name,width,height,r_frame_rate \
  -of default=noprint_wrappers=1 \
  assets/whiteboard/water-cycle/scene-01-evaporation-whiteboard.mp4
```

Kiểm tra trực quan ít nhất ba thời điểm:

1. Đầu video: nền giấy sạch, chưa lộ nội dung phía sau.
2. Giữa video: chỉ những vùng đã đến lượt mới xuất hiện.
3. Cuối video: toàn bộ ảnh hiển thị và dừng ít nhất 0,5 giây.

Trích ba frame kiểm tra:

```bash
mkdir -p assets/whiteboard/water-cycle/checks

ffmpeg -y -ss 0.2 \
  -i assets/whiteboard/water-cycle/scene-01-evaporation-whiteboard.mp4 \
  -frames:v 1 assets/whiteboard/water-cycle/checks/start.jpg

ffmpeg -y -ss 7 \
  -i assets/whiteboard/water-cycle/scene-01-evaporation-whiteboard.mp4 \
  -frames:v 1 assets/whiteboard/water-cycle/checks/middle.jpg

ffmpeg -y -sseof -0.2 \
  -i assets/whiteboard/water-cycle/scene-01-evaporation-whiteboard.mp4 \
  -frames:v 1 assets/whiteboard/water-cycle/checks/end.jpg
```

Nếu kết quả chưa đúng, hãy chỉnh `region`, `startMs`, `durationMs` hoặc `protectedRegions` trong annotation rồi render lại.

### Bước 10: Render tất cả scene

Lặp lại bước render cho từng scene:

```bash
.venv/bin/python scripts/render_stream_whiteboard.py \
  assets/whiteboard/water-cycle/scene-02-condensation.png \
  assets/whiteboard/water-cycle/scene-02-condensation.annotation.json \
  assets/whiteboard/water-cycle/scene-02-condensation-whiteboard.mp4 \
  assets/drawing-hand.png \
  --ink-path skeleton \
  --color-fill contour-wipe
```

Để ghép ổn định, mọi scene nên dùng cùng:

- Kích thước ảnh nguồn.
- `--cap-long-edge`.
- `--fps`.
- `--ink-path` và phong cách hình ảnh.

### Bước 11: Ghép các scene thành một video

Thứ tự sau `--inputs` chính là thứ tự phát:

```bash
.venv/bin/python scripts/merge_scenes.py \
  --inputs \
    assets/whiteboard/water-cycle/scene-01-evaporation-whiteboard.mp4 \
    assets/whiteboard/water-cycle/scene-02-condensation-whiteboard.mp4 \
    assets/whiteboard/water-cycle/scene-03-rainfall-whiteboard.mp4 \
  --output assets/whiteboard/water-cycle/final-whiteboard.mp4
```

Script thử lần lượt:

1. FFmpeg concat không encode lại.
2. FFmpeg encode lại H.264 nếu các clip không tương thích.
3. PyAV nếu FFmpeg không khả dụng.

Video sau bước này đã hoàn chỉnh về mặt hình ảnh nhưng chưa có giọng đọc hoặc phụ đề nhúng.

## 7. Thêm giọng đọc vào video

Giả sử bạn có:

```text
assets/whiteboard/water-cycle/final-whiteboard.mp4
assets/whiteboard/water-cycle/narration.m4a
```

Ghép audio bằng FFmpeg:

```bash
ffmpeg -y \
  -i assets/whiteboard/water-cycle/final-whiteboard.mp4 \
  -i assets/whiteboard/water-cycle/narration.m4a \
  -map 0:v:0 \
  -map 1:a:0 \
  -c:v copy \
  -c:a aac \
  -b:a 192k \
  -shortest \
  assets/whiteboard/water-cycle/final-with-audio.mp4
```

Audio và video nên có thời lượng gần bằng nhau. `-shortest` kết thúc output theo stream ngắn hơn; nếu audio ngắn hơn video ngoài ý muốn, hãy chỉnh audio trước khi ghép.

## 8. Thêm phụ đề

### 8.1. Phụ đề mềm, có thể bật/tắt

```bash
ffmpeg -y \
  -i assets/whiteboard/water-cycle/final-with-audio.mp4 \
  -i input.srt \
  -map 0:v:0 \
  -map "0:a?" \
  -map 1:0 \
  -c:v copy \
  -c:a copy \
  -c:s mov_text \
  -metadata:s:s:0 language=vie \
  assets/whiteboard/water-cycle/final-complete.mp4
```

### 8.2. Burn phụ đề trực tiếp lên hình

```bash
ffmpeg -y \
  -i assets/whiteboard/water-cycle/final-with-audio.mp4 \
  -vf "subtitles=input.srt" \
  -c:v libx264 \
  -crf 20 \
  -preset medium \
  -pix_fmt yuv420p \
  -c:a copy \
  assets/whiteboard/water-cycle/final-complete.mp4
```

Burn subtitle phải encode lại video nhưng có khả năng hiển thị ổn định trên nhiều nền tảng hơn.

Thời gian trong SRT phải khớp với timeline của video đã ghép. Nếu bạn thay đổi thời lượng từng scene, cần cập nhật lại SRT hoặc audio tương ứng.

## 9. Kiểm tra video hoàn chỉnh

Kiểm tra video, audio và phụ đề:

```bash
ffprobe -v error \
  -show_entries format=duration,size \
  -show_entries stream=index,codec_type,codec_name,width,height,r_frame_rate \
  -of default=noprint_wrappers=1 \
  assets/whiteboard/water-cycle/final-complete.mp4
```

Mở video:

```bash
open assets/whiteboard/water-cycle/final-complete.mp4
```

Checklist cuối:

- [ ] Các scene xuất hiện đúng thứ tự.
- [ ] Không có vùng phía sau bị lộ sớm.
- [ ] Bàn tay hoặc đầu bút nằm gần nét đang được vẽ.
- [ ] Cuối mỗi scene hiện toàn bộ hình.
- [ ] Không có thay đổi kích thước bất thường giữa các scene.
- [ ] Video có codec H.264 và pixel format tương thích phổ biến.
- [ ] Audio đồng bộ với hình.
- [ ] Phụ đề đúng thời gian và không che nội dung quan trọng.
- [ ] Video cuối phát được bằng QuickTime hoặc trình duyệt.

## 10. Sự cố thường gặp

### `ModuleNotFoundError`

Bạn có thể đang dùng sai Python. Hãy chạy:

```bash
python3 scripts/prepare_env.py
.venv/bin/python scripts/prepare_env.py --check
```

Sau đó luôn dùng `.venv/bin/python` cho các script render.

### Không tạo được `.venv`

Kiểm tra Python:

```bash
python3 --version
which python3
```

Nếu Python quá mới và dependency chưa tương thích, thử Python 3.12 như hướng dẫn ở phần chuẩn bị môi trường.

### Chỉ nhận được file `_raw.mp4`

Renderer không chuyển mã H.264 thành công. Kiểm tra FFmpeg:

```bash
which ffmpeg
ffmpeg -version
```

Sau đó chuyển mã thủ công:

```bash
ffmpeg -y \
  -i output_raw.mp4 \
  -c:v libx264 \
  -crf 20 \
  -pix_fmt yuv420p \
  output.mp4
```

### Video bị lộ đối tượng chưa đến lượt

Kiểm tra:

- `canvas` có đúng kích thước ảnh hay không.
- `region` có bao quá rộng hay không.
- Các vùng chồng nhau đã dùng `protectedRegions` chưa.
- `startMs` có đúng thứ tự hay không.

### Renderer vẽ sai thứ tự

Renderer sắp theo `reveal.startMs`, không chỉ dựa vào `sequence`. Hãy bảo đảm cả hai trường cùng thứ tự.

### Video dài hơn `sceneDurationMs`

Các element được vẽ tuần tự. Nếu `startMs` chồng nhau hoặc tổng `durationMs` quá dài, renderer vẫn phải hoàn tất từng vùng nên video có thể vượt thời lượng dự kiến. Hãy xếp các khoảng thời gian nối tiếp nhau.

### Render quá chậm

Render bản thử với cấu hình nhẹ hơn:

```bash
.venv/bin/python scripts/render_stream_whiteboard.py \
  image.png annotation.json preview.mp4 assets/drawing-hand.png \
  --fps 30 \
  --cap-long-edge 720 \
  --ink-path grid
```

Sau khi annotation chính xác, render lại bản chính thức.

### Ảnh preview annotation lỗi font trên macOS

Sử dụng `assets/preview.html` hoặc thay font Windows hard-code trong `scripts/render_annotation_preview.py` bằng font có trên máy, ví dụ một font trong `/System/Library/Fonts/`.

### Ghép scene thất bại

Kiểm tra tất cả clip có cùng độ phân giải và frame rate:

```bash
ffprobe -v error \
  -select_streams v:0 \
  -show_entries stream=codec_name,width,height,r_frame_rate \
  -of default=noprint_wrappers=1 \
  scene-01.mp4
```

Nếu cần, chuẩn hóa từng clip trước khi ghép:

```bash
ffmpeg -y \
  -i scene-01.mp4 \
  -vf "scale=1920:1080,fps=30" \
  -c:v libx264 \
  -crf 20 \
  -pix_fmt yuv420p \
  scene-01-normalized.mp4
```

## 11. Lệnh tóm tắt

### Video mẫu về mưa

```bash
python3 scripts/prepare_env.py
.venv/bin/python scripts/generate_rain_demo.py
.venv/bin/python scripts/render_stream_whiteboard.py \
  assets/whiteboard/rain-demo/scene-01-why-rain.png \
  assets/whiteboard/rain-demo/scene-01-why-rain.annotation.json \
  assets/whiteboard/rain-demo/scene-01-why-rain-whiteboard.mp4 \
  assets/drawing-hand.png \
  --ink-path skeleton \
  --color-fill contour-wipe
```

### Dự án nhiều scene

```bash
# 1. Parse SRT
.venv/bin/python scripts/parse_srt.py input.srt > scenes.json

# 2. Tạo/chỉnh ảnh PNG và annotation JSON cho từng scene

# 3. Render từng scene
.venv/bin/python scripts/render_stream_whiteboard.py \
  scene-01.png scene-01.annotation.json scene-01-whiteboard.mp4 \
  assets/drawing-hand.png

.venv/bin/python scripts/render_stream_whiteboard.py \
  scene-02.png scene-02.annotation.json scene-02-whiteboard.mp4 \
  assets/drawing-hand.png

# 4. Ghép scene
.venv/bin/python scripts/merge_scenes.py \
  --inputs scene-01-whiteboard.mp4 scene-02-whiteboard.mp4 \
  --output final-whiteboard.mp4
```

## 12. File đầu ra cuối cùng

Tùy mức độ hoàn thiện, các file chính là:

```text
final-whiteboard.mp4     # Video hình ảnh whiteboard
final-with-audio.mp4     # Video đã có giọng đọc
final-complete.mp4       # Video đã có audio và phụ đề
```

Nếu chỉ cần video whiteboard không có âm thanh, `final-whiteboard.mp4` đã là sản phẩm cuối.
## 13. Build tự động từ `scenes.manifest.json`

Script `scripts/build_whiteboard_video.py` tự động thực hiện các bước:

1. Đọc thứ tự và timeline từ `scenes.manifest.json`.
2. Giữ nguyên annotation đã có và tạo annotation toàn cảnh cho scene còn thiếu.
3. Render từng scene bằng `render_stream_whiteboard.py`.
4. Ghép các scene thành `final-silent.mp4`.
5. Thêm khoảng lặng vào từng WAV để khớp timeline manifest.
6. Ghép audio AAC và nhúng `narration.srt` dạng phụ đề mềm.
7. Xuất `final-complete.mp4`.

Khởi tạo annotation còn thiếu mà chưa render:

```bash
.venv/bin/python scripts/build_whiteboard_video.py \
  assets/whiteboard/whiteboard-vi \
  --init-only
```

Sau đó mở `assets/preview.html` bằng Chrome, chọn thư mục project, chỉnh từng cảnh và bấm **Lưu tất cả**.

Kiểm tra kế hoạch build mà không tạo video:

```bash
.venv/bin/python scripts/build_whiteboard_video.py \
  assets/whiteboard/whiteboard-vi \
  --dry-run
```

Build video hoàn chỉnh có audio và phụ đề:

```bash
.venv/bin/python scripts/build_whiteboard_video.py \
  assets/whiteboard/whiteboard-vi
```

Build thử nhanh ở 720p/30fps:

```bash
.venv/bin/python scripts/build_whiteboard_video.py \
  assets/whiteboard/whiteboard-vi \
  --fps 30 \
  --cap-long-edge 720
```

Chỉ tạo video không tiếng, không cần FFmpeg:

```bash
.venv/bin/python scripts/build_whiteboard_video.py \
  assets/whiteboard/whiteboard-vi \
  --video-only
```

Các tùy chọn hữu ích:

- `--force-render`: render lại mọi scene dù MP4 hiện tại còn mới.
- `--ink-path grid|skeleton`: chọn thuật toán đường bút.
- `--color-fill contour-wipe|brush`: chọn hiệu ứng tô màu.
- `--bare-tip`: ẩn bàn tay/bút.
- `--no-subtitles`: tạo video có audio nhưng không nhúng SRT.
- `--output <file.mp4>`: đổi đường dẫn video cuối.

Bản có audio cần FFmpeg:

```bash
brew install ffmpeg
```

Đầu ra mặc định nằm trong thư mục project:

```text
final-silent.mp4
narration-full.wav
final-with-audio.mp4
final-complete.mp4
```
