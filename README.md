\# BAI1-CAMBIEN-B23DCAT066



\## 1. Giới thiệu



Đây là project thực hành IoT xây dựng hệ thống thu thập, truyền tải, lưu trữ, xử lý và trực quan hóa dữ liệu cảm biến.



Kiến trúc hệ thống:



ESP32 / Wokwi

&#x20;       ↓

MQTT HiveMQ

&#x20;       ↓

Python MQTT Subscriber

&#x20;       ↓

InfluxDB

&#x20;       ↓

Preprocessing

&#x20;       ↓

Grafana Dashboard



\## 2. Công nghệ sử dụng



\- ESP32

\- Wokwi

\- MQTT

\- HiveMQ Public Broker

\- Python 3

\- Paho MQTT

\- InfluxDB 2.7

\- Grafana

\- Docker / Docker Compose

\- Pandas

\- NumPy

\- Scikit-learn



\## 3. Thông tin MQTT



Broker:



&#x20;   broker.hivemq.com



Port:



&#x20;   1883



Topic:



&#x20;   iot/B23DCAT066/telemetry



MQTT không sử dụng username/password.



\## 4. Thông tin InfluxDB



URL:



&#x20;   http://localhost:8086



Organization:



&#x20;   PTIT



Bucket:



&#x20;   iot\_data



Retention:



&#x20;   7 ngày



Measurement dữ liệu thô:



&#x20;   environment



Measurement dữ liệu đã xử lý:



&#x20;   environment\_clean



Token và mật khẩu không được lưu trực tiếp trong GitHub.



Các thông tin nhạy cảm được cấu hình thông qua file `.env`.



\## 5. Thông tin Grafana



URL:



&#x20;   http://localhost:3000



Grafana sử dụng InfluxDB làm Data Source.



Trong Docker network, Grafana kết nối đến InfluxDB bằng:



&#x20;   http://influxdb:8086



\## 6. Yêu cầu môi trường



Cần cài đặt:



\- Git

\- Docker Desktop

\- Python 3

\- Wokwi / VS Code nếu chạy mô phỏng ESP32



Kiểm tra Docker:



```cmd

docker --version

docker compose version

```



Kiểm tra Python:



```cmd

python --version

```



Kiểm tra Git:



```cmd

git --version

```



\## 7. Cài đặt project



Clone repository:



```cmd

git clone <GITHUB\_REPOSITORY\_URL>

```



Di chuyển vào thư mục project:



```cmd

cd BAI1-CAMBIEN-B23DCAT066

```



\## 8. Cấu hình biến môi trường



Tạo file `.env` từ `.env.example`.



File `.env.example` có dạng:



```env

INFLUX\_TOKEN=your-influxdb-token

INFLUXDB\_ADMIN\_PASSWORD=your-influxdb-password

INFLUXDB\_ADMIN\_TOKEN=your-influxdb-admin-token

GRAFANA\_ADMIN\_PASSWORD=your-grafana-password

```



Tạo `.env`:



```cmd

copy .env.example .env

```



Sau đó mở:



```cmd

notepad .env

```



và điền các giá trị cấu hình thực tế.



Không commit file `.env` lên GitHub.



\## 9. Khởi động InfluxDB và Grafana



Di chuyển vào thư mục Docker:



```cmd

cd "Database \& Dashboard"

```



Khởi động các container:



```cmd

docker compose up -d

```



Kiểm tra container:



```cmd

docker ps

```



Cần thấy:



```text

influxdb\_iot

grafana\_iot

```



Kiểm tra InfluxDB:



```cmd

docker exec influxdb\_iot influx org list --token %INFLUXDB\_ADMIN\_TOKEN%

```



Hoặc truy cập trình duyệt:



```text

http://localhost:8086

```



Grafana:



```text

http://localhost:3000

```



\## 10. Cài đặt thư viện Python



Quay lại thư mục project:



```cmd

cd ..

```



Tạo môi trường ảo:



```cmd

python -m venv .venv

```



Kích hoạt:



```cmd

.venv\\Scripts\\activate

```



Cài đặt thư viện:



```cmd

pip install -r requirements.txt

```



\## 11. Chạy MQTT Subscriber



Subscriber nhận dữ liệu từ MQTT và ghi dữ liệu vào InfluxDB.



Chạy:



```cmd

python scripts\\subscriber.py

```



Nếu hoạt động bình thường, terminal sẽ hiển thị thông tin tương tự:



```text

Connected to MQTT broker

DATA SAVED

student=B23DCAT066

device=esp32-B23DCAT066

seq=...

temperature=...

humidity=...

distance=...

```



\## 12. Chạy ESP32 trên Wokwi



Mở project bằng VS Code.



Chạy mô phỏng Wokwi.



ESP32 sẽ kết nối:



```text

WiFi: Wokwi-GUEST

Password: để trống

```



ESP32 gửi dữ liệu lên MQTT theo topic:



```text

iot/B23DCAT066/telemetry

```



Payload có dạng:



```json

{

&#x20; "student\_id": "B23DCAT066",

&#x20; "device\_id": "esp32-B23DCAT066",

&#x20; "seq": 1,

&#x20; "timestamp\_ms": 1790923801655,

&#x20; "temperature": 25.00,

&#x20; "humidity": 50.00,

&#x20; "distance": 100.84

}

```



\## 13. Kiểm tra MQTT



Có thể sử dụng Mosquitto Subscriber để kiểm tra dữ liệu:



```cmd

docker run --rm eclipse-mosquitto:2 mosquitto\_sub -h broker.hivemq.com -p 1883 -t "iot/B23DCAT066/telemetry" -v

```



Nếu ESP32 hoạt động, terminal sẽ nhận được các JSON message.



\## 14. Preprocessing dữ liệu



Sau khi dữ liệu thô được lưu vào InfluxDB, chạy:



```cmd

python scripts\\preprocess.py

```



Dữ liệu sau preprocessing được lưu vào measurement:



```text

environment\_clean

```



Các bước xử lý gồm:



\- Xử lý dữ liệu thiếu

\- Phát hiện / xử lý dữ liệu bất thường

\- Resampling dữ liệu

\- Rolling mean

\- Tính delta

\- Chuẩn hóa dữ liệu



\## 15. Grafana Dashboard



Truy cập:



```text

http://localhost:3000

```



Đăng nhập bằng tài khoản Grafana đã cấu hình trong `.env`.



Tạo InfluxDB Data Source với:



```text

URL: http://influxdb:8086

Organization: PTIT

Bucket: iot\_data

```



Dashboard có thể hiển thị:



\- Temperature

\- Humidity

\- Distance

\- Sequence

\- MQTT / processing latency

\- Dữ liệu raw

\- Dữ liệu processed



\## 16. Kiểm tra dữ liệu InfluxDB



Kiểm tra measurement `environment`:



```cmd

docker exec influxdb\_iot influx query "from(bucket:\\"iot\_data\\") |> range(start:-1h) |> filter(fn:(r) => r.\_measurement == \\"environment\\")" --org PTIT --token %INFLUXDB\_ADMIN\_TOKEN%

```



Kiểm tra dữ liệu đã preprocessing:



```cmd

docker exec influxdb\_iot influx query "from(bucket:\\"iot\_data\\") |> range(start:-24h) |> filter(fn:(r) => r.\_measurement == \\"environment\_clean\\")" --org PTIT --token %INFLUXDB\_ADMIN\_TOKEN%

```



\## 17. Dừng hệ thống



Dừng Docker containers:



```cmd

cd "Database \& Dashboard"

docker compose down

```



Nếu chỉ muốn dừng nhưng giữ dữ liệu InfluxDB và Grafana thì sử dụng:



```cmd

docker compose down

```



Không sử dụng `docker compose down -v` nếu muốn giữ dữ liệu.



\## 18. Cấu trúc thư mục



```text

BAI1-CAMBIEN-B23DCAT066/

│

├── BAI1-CAMBIEN-B23DCAT066.ino

├── diagram.json

├── wokwi.toml

│

├── requirements.txt

├── libraries.txt

├── .env.example

├── .gitignore

├── README.md

├── RENAME

│

├── scripts/

│   ├── subscriber.py

│   └── preprocess.py

│

└── Database \& Dashboard/

&#x20;   └── docker-compose.yml

```



\## 19. Luồng khởi động nhanh



\### Terminal 1 - Docker



```cmd

cd "Database \& Dashboard"

docker compose up -d

```



\### Terminal 2 - Python Subscriber



```cmd

cd ..

.venv\\Scripts\\activate

python scripts\\subscriber.py

```



\### Wokwi



Chạy ESP32 trên Wokwi.



\### Grafana



Mở:



```text

http://localhost:3000

```



\### InfluxDB



Mở:



```text

http://localhost:8086

```



\## 20. Lưu ý bảo mật



Không đưa các thông tin sau lên GitHub:



\- InfluxDB token thật

\- Password InfluxDB

\- Password Grafana

\- File `.env`

\- Credentials cá nhân



File `.env` đã được đưa vào `.gitignore`.



File `.env.example` chỉ chứa các giá trị mẫu để người khác biết cấu trúc cấu hình.

