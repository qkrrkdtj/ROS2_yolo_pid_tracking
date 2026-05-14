# ROS2 환경에서 파일 넣기
# setup.py 꼮 설정해야함!!!
'''
    entry_points={
        'console_scripts': [
            'pepsi_publish = turtlebot3_teleop.script.pepsi_publish:main',
        ],
    },
'''



import rclpy
from rclpy.node import Node
from geometry_msgs.msg import TwistStamped
from rclpy.clock import Clock
from rcl_interfaces.msg import SetParametersResult

import socket
import time

class PID:
    def __init__(self):
        self.P = 0.0
        self.I = 0.0
        self.D = 0.0
        self.max_state = 0.0 
        self.min_state = 0.0
        self.pre_state = 0.0
        self.dt = 0.0
        self.integrated_state = 0.0
        self.pre_time = time.time()
        
    def update(self, state):
        self.dt = time.time() - self.pre_time

        # ============================== #
        # d 계산
        if self.dt == 0.:
            state_D = 0.
        else:
            state_D = (state - self.pre_state) / self.dt
        # ============================== #

        # ============================== #
        # i 계산
        state_I = state + self.integrated_state
        # ============================== #

        # ============================== #
        # PID 계산
        out = self.P*state + self.D*state_D + self.I*state_I * self.dt
        # ============================== #


        if abs(out) > self.max_state:
            out = self.max_state if out > 0 else -self.max_state
        elif abs(out) < self.min_state:
            out = self.min_state if out > 0 else -self.min_state

        self.pre_state = state
        self.integrated_state = state_I
        self.pre_time = time.time()

        return out

class PepsiPublish(Node):
    def __init__(self):
        super().__init__('pepsi_publish') # ROS에서 pepsi_publish로 실행

        # 소캣 설정
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('localhost', 9999))
        self.sock.setblocking(False) # 넌블록킹

        # [TOPIC]publisher: twist로 만들기 (움직임 보내는 신호)
        self.publisher_ = self.create_publisher(TwistStamped, 'cmd_vel', 10)

        # 콜백
        self.timer = self.create_timer(.3, self.pepsi_callback)
        
        # PID 인스턴스 만들기
        self.pid = PID()

        # ============================== #
        # rqt용 코드
        # Register parameter callback for dynamic reconfiguration (PID parameters and tolerance)
        self.add_on_set_parameters_callback(self.parameter_callback)

        # Declare ROS2 parameters (PID parameters and tolerance)
        self.declare_parameter('P', 1.0)
        self.declare_parameter('I', 0.0)
        self.declare_parameter('D', 0.0)
        self.declare_parameter('max_state', 5.0)
        self.declare_parameter('min_state', -5.0)
        self.declare_parameter('tolerance', 0.01)
        
        # Get initial parameter values for PID and tolerance
        P = self.get_parameter('P').value
        I = self.get_parameter('I').value
        D = self.get_parameter('D').value
        max_state = self.get_parameter('max_state').value
        min_state = self.get_parameter('min_state').value
        self.tolerance = self.get_parameter('tolerance').value

        # assign PID parameters
        self.pid.P = P
        self.pid.I = I
        self.pid.D = D
        self.pid.max_state = max_state
        self.pid.min_state = min_state
        # ============================== #

    def parameter_callback(self, params):
        for param in params:
            if param.name == 'P':
                self.pid.P = param.value
                self.get_logger().info(f"Updated PID P: {param.value}")
            elif param.name == 'I':
                self.pid.I = param.value
                self.get_logger().info(f"Updated PID I: {param.value}")
            elif param.name == 'D':
                self.pid.D = param.value
                self.get_logger().info(f"Updated PID D: {param.value}")
            elif param.name == 'max_state':
                self.pid.max_state = param.value
                self.get_logger().info(f"Updated PID max_state: {param.value}")
            elif param.name == 'min_state':
                self.pid.min_state = param.value
                self.get_logger().info(f"Updated PID min_state: {param.value}")
            elif param.name == 'tolerance':
                self.tolerance = param.value
                self.get_logger().info(f"Updated tolerance: {param.value}")
        return SetParametersResult(successful=True)
    

    
    def pepsi_callback(self):
        # PID 설정하기
        self.pid.P = 0.5
        self.pid.I = 0.001 
        self.pid.D = 0.01
        self.pid.max_state = .6
        self.tolerance = 25.0

        error = 0
        last_data = None
        angular_correction = 0.0 # 로봇으로 보내 움직일 값
        
        # 마지막 데이터만 읽음. 더 이상 읽을 데이터가 없을 때까지 루프
        while True:
            try:
                # 소켓으로 error 받아 온 후 pid제어하기
                data, _ = self.sock.recvfrom(4096)
                last_data = data 
            except BlockingIOError:
                # 버퍼가 비었을 때 루프 탈출
                break

        if last_data:
            # 오찾값 받아옴
            error = int(last_data.decode('utf-8'))

            normalized_error = error / 320.0   # 320 온다면 1 들어감 -> 빠르게 돌아가는거 방지

            if abs(normalized_error) < (self.tolerance / 320.0):
                angular_correction = 0.0
                self.pid.integrated_state = 0.0
            else:
                # PID로 오차 줄이기
                angular_correction = self.pid.update(normalized_error)
        
        # TwistStamped 메시지 만들기
        twist_stamped = TwistStamped()
        twist_stamped.header.stamp = Clock().now().to_msg()
        twist_stamped.header.frame_id = ''
        twist_stamped.twist.angular.x = 0.0
        twist_stamped.twist.angular.y = 0.0
        twist_stamped.twist.angular.z = angular_correction # -로 반대 방향으로 움직이기

        # TwistStamped 메시지를 pub 하기
        self.publisher_.publish(twist_stamped)

        # 디버그
        self.get_logger().info(f'movemet {angular_correction}')

def main():
    rclpy.init()
    node_pepsi = PepsiPublish()
    try:
        rclpy.spin(node_pepsi)
    except KeyboardInterrupt:
        node_pepsi.get_logger().info("node_pepsi interrupted")
    finally:
        node_pepsi.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
