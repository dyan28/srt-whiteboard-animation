# Nhạc nền cho whiteboard video

Đặt các file `.mp3` vào thư mục này. Khi chạy `./build_video.sh` mà không truyền `--music`, script chọn **ngẫu nhiên** một bài và ghép vào video với âm lượng mặc định **15%**.

Ưu tiên tìm nhạc:

1. `assets/whiteboard/<project>/music/*.mp3` — nhạc riêng của project
2. `assets/music/*.mp3` — thư mục dùng chung

Mặc định âm lượng nhạc bằng **15%** so với giọng đọc.

- Nhạc **dài hơn** video: tự cắt đúng bằng độ dài video.
- Nhạc **ngắn hơn** video: tự lặp rồi cắt đúng bằng độ dài video.

Ví dụ:

```bash
# Tự chọn nhạc nếu có MP3
./build_video.sh vi-0df025cc-ae89-4f4b-8dbc-4d88cb1d6745

# Chỉ định một bài
./build_video.sh <project_id> --music assets/music/soft-piano.mp3 --music-volume 0.15

# Không ghép nhạc
./build_video.sh <project_id> --no-music
```
vi-fa27d332-d8f7-4ee1-93bf-b787ea93a3ba