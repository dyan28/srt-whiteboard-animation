# Build video whiteboard hoàn chỉnh bằng một lệnh

Tài liệu này hướng dẫn quy trình ngắn nhất: chỉnh vùng và thời gian trong Chrome, lưu annotation, sau đó chạy một script để tạo MP4 có hình, giọng đọc và phụ đề.

## Kết quả cuối

Video mặc định được tạo tại:

```text
assets/whiteboard/whiteboard-vi/final-complete.mp4
```

Video gồm:

- Hoạt ảnh whiteboard của tất cả scene.
- Audio từ các file WAV, được căn theo `scenes.manifest.json`.
- Phụ đề tiếng Việt từ `narration.srt`.

## Bước 1: Chuẩn bị môi trường một lần

Tại thư mục dự án:

```bash
cd /Volumes/Docs/App/srt-whiteboard-animation
python3 scripts/prepare_env.py
```

Cài FFmpeg trên macOS:

```bash
brew install ffmpeg
```

Kiểm tra:

```bash
.venv/bin/python scripts/prepare_env.py --check
ffmpeg -version
ffprobe -version
```

## Bước 2: Kiểm tra tài nguyên project

Project mặc định nằm tại:

```text
assets/whiteboard/whiteboard-vi
```

Mỗi scene cần:

```text
scene-xx-name.jpg
scene-xx-name.wav
scene-xx-name.annotation.json
```

Thư mục cũng cần:

```text
scenes.manifest.json
narration.srt
```

Nếu một scene chưa có annotation, khởi tạo tự động bằng:

```bash
./build_video.sh --init-only
```

Script chỉ tạo các annotation còn thiếu và không ghi đè annotation đã chỉnh.

## Bước 3: Mở trình chỉnh sửa bằng Chrome

```bash
open -a "Google Chrome" assets/preview.html
```

Trong Chrome:

1. Bấm **Mở thư mục…**.
2. Chọn `assets/whiteboard/whiteboard-vi`.
3. Cho phép Chrome đọc và ghi thư mục.
4. Chọn từng scene trong danh sách phía trên.
5. Kéo khung để đặt đúng vùng cần vẽ.
6. Dùng **Thêm mô-đun** nếu muốn chia ảnh thành nhiều phần xuất hiện lần lượt.
7. Chỉnh **Bắt đầu (ms)** và **Kết thúc (ms)** ở bảng bên phải.
8. Nhấn nút phát `▶` để xem thử timeline.
9. Lặp lại với tất cả scene.
10. Bấm **Lưu tất cả**.

### Quy tắc timing

- Các mô-đun trong cùng scene nên vẽ tuần tự và không chồng thời gian.
- Mô-đun sau nên bắt đầu sau mô-đun trước khoảng 100–300 ms.
- Để lại ít nhất 500 ms ở cuối scene để hiển thị toàn bộ ảnh.
- Renderer sử dụng `reveal.startMs`, vì vậy thứ tự thời gian phải khớp thứ tự mô-đun.

Ví dụ cho scene dài 11 giây:

```text
Mô-đun 1: 300ms  → 3500ms
Mô-đun 2: 3700ms → 6800ms
Mô-đun 3: 7000ms → 10500ms
Dừng hình:         10500ms → 11000ms
```

## Bước 4: Kiểm tra kế hoạch trước khi build

```bash
./build_video.sh --dry-run
```

Lệnh này:

- Kiểm tra manifest, ảnh, WAV và annotation.
- Kiểm tra timing có vượt thời lượng scene hay không.
- In toàn bộ lệnh render/merge/mux.
- Không tạo hoặc thay đổi video.

Nếu không có dòng `[error]`, có thể chạy build thật.

## Bước 5: Build video hoàn chỉnh

Chỉ cần chạy:

```bash
./build_video.sh
```

Script tự động thực hiện:

1. Đọc scene theo thứ tự trong `scenes.manifest.json`.
2. Giữ nguyên annotation đã lưu từ Chrome.
3. Tự tạo annotation toàn cảnh nếu scene nào còn thiếu.
4. Render từng scene thành `*-whiteboard.mp4`.
5. Ghép scene thành `final-silent.mp4`.
6. Thêm khoảng lặng vào WAV để giữ đúng timeline.
7. Tạo `narration-full.wav`.
8. Ghép audio AAC thành `final-with-audio.mp4`.
9. Nhúng `narration.srt` dạng phụ đề mềm.
10. Xuất `final-complete.mp4`.

Build ở 1080p/60fps có thể mất vài phút tùy máy.

## Bước 6: Mở và kiểm tra video

```bash
open assets/whiteboard/whiteboard-vi/final-complete.mp4
```

Kiểm tra metadata:

```bash
ffprobe -v error \
  -show_entries format=duration,size \
  -show_entries stream=index,codec_type,codec_name,width,height,r_frame_rate \
  -of json \
  assets/whiteboard/whiteboard-vi/final-complete.mp4
```

Video chuẩn phải có ba stream:

```text
video:    h264
audio:    aac
subtitle: mov_text
```

Phụ đề mềm có thể cần được bật trong trình phát video.

## Sau khi chỉnh annotation lần nữa

Chỉ cần lưu trong Chrome rồi chạy lại:

```bash
./build_video.sh
```

Script tự phát hiện annotation mới hơn scene MP4 và chỉ render lại scene đã thay đổi.

Muốn bắt buộc render lại toàn bộ:

```bash
./build_video.sh --force-render
```

## Build thử nhanh

Dùng 720p/30fps để xem thử nhanh:

```bash
./build_video.sh --fps 30 --cap-long-edge 720 --force-render
```

Sau khi hài lòng, build bản chính thức:

```bash
./build_video.sh --fps 60 --cap-long-edge 1080 --force-render
```

## Các tùy chọn thường dùng

```bash
# Chỉ tạo annotation còn thiếu
./build_video.sh --init-only

# Chỉ kiểm tra, không render
./build_video.sh --dry-run

# Render lại tất cả scene
./build_video.sh --force-render

# Chỉ tạo video không tiếng
./build_video.sh --video-only

# Có audio nhưng không nhúng phụ đề
./build_video.sh --no-subtitles

# Dùng đường bút skeleton
./build_video.sh --ink-path skeleton

# Không hiển thị bàn tay/bút
./build_video.sh --bare-tip
```

## Build project khác

Truyền thư mục project làm đối số đầu tiên:

```bash
./build_video.sh assets/whiteboard/project-khac
```

Các tùy chọn đặt phía sau project:

```bash
./build_video.sh assets/whiteboard/project-khac --force-render --ink-path skeleton
```

## File trung gian và file cuối

```text
scene-xx-...-whiteboard.mp4  # Video từng scene
final-silent.mp4             # Video ghép chưa có tiếng
narration-full.wav           # Audio đã được pad theo timeline
final-with-audio.mp4         # Video đã có audio
final-complete.mp4           # Video cuối có audio và phụ đề
```

## Lỗi thường gặp

### Không có quyền chạy script

```bash
chmod +x build_video.sh
```

Sau đó chạy lại:

```bash
./build_video.sh
```

### Không tìm thấy FFmpeg

```bash
brew install ffmpeg
```

### Annotation vượt thời lượng scene

Nếu script báo timing kết thúc quá muộn, mở lại `assets/preview.html`, giảm **Kết thúc (ms)** của mô-đun cuối và để lại ít nhất 500 ms cuối scene.

### Chỉnh trong Chrome nhưng video không thay đổi

Bảo đảm đã bấm **Lưu cảnh hiện tại** hoặc **Lưu tất cả**, sau đó chạy:

```bash
./build_video.sh --force-render
```

### Chỉ có hai annotation được lưu

Bạn phải chuyển qua từng scene trong Chrome để khởi tạo annotation của scene đó, hoặc chạy trước:

```bash
./build_video.sh --init-only
```

Sau đó tải lại preview, chỉnh tất cả scene và bấm **Lưu tất cả**.
