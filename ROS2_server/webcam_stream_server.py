import cv2
import time
import threading
from flask import Flask, Response, render_template

app = Flask(__name__)

# 웹캠 초기화
cap = cv2.VideoCapture(1)
if not cap.isOpened():
    print("카메라 열기 실패")
    exit()
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
cap.set(cv2.CAP_PROP_FPS, 20)

# 최신 프레임을 저장할 전역 변수와 락
global_frame = None
frame_lock = threading.Lock()

def capture_frames():
    global global_frame
    while True:
        ret, frame_data = cap.read()
        if not ret:
            time.sleep(0.1)
            continue

        ret, buffer = cv2.imencode('.jpg', frame_data)
        if not ret:
            continue

        with frame_lock:
            global_frame = buffer.tobytes()

        time.sleep(0.05)

# 백그라운드 스레드 시작
capture_thread = threading.Thread(target=capture_frames)
capture_thread.daemon = True
capture_thread.start()

def gen_frames():
    while True:
        with frame_lock:
            frame = global_frame
        if frame is None:
            continue
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.05)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    finally:
        cap.release()