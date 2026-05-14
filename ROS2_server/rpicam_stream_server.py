import cv2
import time
import threading
import subprocess
import numpy as np
from flask import Flask, Response, render_template

app = Flask(__name__)

command = [
    'rpicam-vid',
    '-t', '0',                 # 무한 실행
    '--width', '640',          # 해상도 설정
    '--height', '480',
    '--mode', '1640:1232',     # 센서 전체 면적 사용
    '--inline',                # 헤더(SPS/PPS)를 매 프레임 포함
    '--nopreview',             # 미리보기 창 비활성화
    '--codec', 'mjpeg',        # MJPEG 포맷
    '--framerate', '20',       # FPS 설정
    '-o', '-'                  # stdout으로 출력
]

# rpicam-vid 프로세스 시작
proc = subprocess.Popen(
    command,
    stdout=subprocess.PIPE,
    bufsize=10**6
)

# 최신 프레임 저장 변수
global_frame = None
frame_lock = threading.Lock()


def capture_frames():
    global global_frame

    buffer = b""

    while True:

        # 데이터 읽기
        chunk = proc.stdout.read(4096)

        if not chunk:
            break

        buffer += chunk

        # JPEG 시작/끝 찾기
        a = buffer.find(b'\xff\xd8')
        b = buffer.find(b'\xff\xd9')

        if a != -1 and b != -1:

            # JPEG 프레임 추출
            jpg = buffer[a:b + 2]

            # 사용한 데이터 제거
            buffer = buffer[b + 2:]

            with frame_lock:
                global_frame = jpg


# 백그라운드 스레드 시작
capture_thread = threading.Thread(
    target=capture_frames
)

capture_thread.daemon = True
capture_thread.start()


def gen_frames():
    while True:

        with frame_lock:
            frame = global_frame

        if frame is None:
            time.sleep(0.01)
            continue

        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n'
            + frame +
            b'\r\n'
        )

        time.sleep(0.05)  # 약 20FPS


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/video_feed')
def video_feed():
    return Response(
        gen_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


if __name__ == '__main__':

    try:
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,
            use_reloader=False
        )

    finally:
        # 종료 시 프로세스 종료
        proc.terminate()