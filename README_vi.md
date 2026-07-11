# Công Cụ Dịch Game Renpy Tự Động Trên Android

Một công cụ script Python dùng để Dịch các game Renpy trên Android, hỗ trợ cả thiết bị đã root và chưa root.

## ✨ Tính Năng

- 🔍 Tự động quét tài nguyên văn bản trong game
- 📝 Trích xuất văn bản sang định dạng có thể chỉnh sửa (JSON)
- 🔄 Tự động dịch trong khi game đang chạy
- 📱 Lưu trữ cục bộ bền vững — không cần gọi API dịch liên tục

## 📦 Yêu Cầu
- **Thiết bị Android**: Android 5.0 trở lên

### 3. Cấu Hình API Key
Chỉnh sửa file `rpy`:
```json
{
  "api_provider": "tencent",
  "api_key": "API Key dịch thuật Tencent của bạn",
  "source_lang": "en",
  "target_lang": "zh"
}
```

## 🚀 Hướng Dẫn Sử Dụng

### Phương Pháp 1: Thiết Bị Đã Root
1. **Inject bản dịch**:
   - Di chuyển các file `*.rpy` đã tạo vào:
     `/data/app/tên_gói_ứng_dụng/game/`

### Phương Pháp 2: Thiết Bị Chưa Root (Dùng MT Manager)
1. Mở file APK của game bằng MT Manager
2. Sử dụng tính năng "Inject File Provider"
3. Sau khi tạo bộ nhớ cục bộ, di chuyển các file dịch vào thư mục `game/`

### Từ Điển Tùy Chỉnh
```json
{
  "character_names": {
    "John": "John",
    "Mary": "Mary"
  },
  "special_terms": {
    "HP": "Hit Points",
    "MP": "Mana Points"
  }
}
```

## 🤝 Đóng Góp

1. Fork repository này
2. Tạo nhánh tính năng mới (`git checkout -b feature/TinhNangMoi`)
3. Commit các thay đổi (`git commit -m 'Thêm tính năng mới'`)
4. Push lên nhánh (`git push origin feature/TinhNangMoi`)
5. Mở Pull Request

## ⚠️ Lưu Ý Quan Trọng

1. **Rủi ro pháp lý**: Chỉ dùng cho mục đích học tập và nghiên cứu. Vui lòng ủng hộ game bản quyền.
2. **Tương thích**: Một số phiên bản Renpy có thể không tương thích.
3. **Sao lưu**: Luôn sao lưu file gốc trước khi thực hiện bất kỳ thay đổi nào.
4. **Giới hạn API**: API dịch thuật của Tencent có giới hạn tần suất gọi.

## 📄 Giấy Phép

Dự án này được cấp phép theo Giấy phép MIT — xem file [LICENSE](LICENSE) để biết chi tiết.

## 👥 Thông Tin Nhà Phát Triển

- **Nhà phát triển**: 九月 (Jiuyue)
- **Telegram**: [@dexbillava](https://t.me/dexbillava)
- **Nhà cung cấp API dịch thuật**: Tencent Cloud Translation
- **Báo lỗi**: [GitHub Issues](https://github.com/dkss123)

## 🌟 Ủng Hộ Dự Án

Nếu công cụ này hữu ích với bạn, hãy:
- ⭐ Star dự án này
- 🐛 Gửi Issue để báo lỗi
- 💬 Tham gia nhóm thảo luận

---
## Nhắc Nhở
- 99% code trong dự án này được tạo bởi DeepSeek, nên khả năng đọc code có thể không cao.
- Nhìn chung code vẫn hoạt động đúng. Nếu bạn thấy quá nhiều vấn đề, có thể tự refactor lại.
- Kỹ năng lập trình của tôi còn hạn chế, có thể không tạo ra được sản phẩm thật tốt, mong bạn thông cảm 🙏🙏
