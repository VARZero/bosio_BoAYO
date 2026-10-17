# BoAYO

SDK 0.3.0은 구면 창 이동·크기 조절, 아래쪽 보관 카드, 클릭 복원,
드래그 배치 미리보기, 아래로 끌어 닫기, BTN3/Escape 취소를 지원합니다.
최소화·복원·닫기 결과 알림은 표시하지 않습니다. [구면 작업 공간 안내](docs/SPATIAL_WORKSPACE.md)에
조작·소프트웨어 연결·실제 합성 경로 미리보기를 정리했습니다.

BoAYO는 BOSIO 정이십면체 프레임버퍼 위에서 동작하는 시선 중심 구면 데스크톱
플랫폼입니다. PYNQ-Z2의 GY-521 자세 입력으로 포커스를 이동하고 보드 버튼으로
런처와 창을 조작합니다.

실사용 서비스는 런처를 BOSIO 창으로 띄우고 외부 앱도 각각 BOSIO 창을 만듭니다.
BoAYo 표면의 둥근 모서리는 4×4 커버리지로 그리며, BOSIO 네이티브 합성기가
삼각 셀 면적에 맞춰 bilinear/적응형 4×4 투영 AA를 적용합니다. 화면 내용이
바뀌지 않으면 런처 표면을 다시 그리거나 전송하지 않습니다.

검증된 고해상도 경로는 **M=32 + 투영코어 2개**이며, 변경 타일만 투영하고
그대로인 창은 재사용합니다. [BoAYO M=32 적용·실측](docs/M32_INCREMENTAL.md)을
참조하세요. 기존 기본 배포 경로는 M=16으로 유지됩니다.

## 구성

```text
BoAYo 런처/앱 SDK -> RGB 표면·캡션 -> SphericalWM 구면 합성·AA
                                                     |
                                                     v
                         드라이버 DDR 장면 갱신 -> BS25 캐시 -> RTL 투영 -> HDMI
GY-521 -> FPGA 센서 허브 -> AXI4-Stream 자세 -> RTL 자세 엔진
PYNQ 버튼 -> SphericalWM 입력 이벤트 -> BoAYo 런처/SDK
```

현재 BS25는 64바이트 라인·16KiB·2-way 캐시를 사용합니다. 앱은 캐시나
DDR 버퍼를 직접 관리하지 않으며 SDK 사용법은 그대로입니다.
[BOSIO DDR 캐시 문서](vendor/bosio_SphericalWM/docs/BOSIO_DDR_CACHE.md)에
드라이버 동작과 실제 보드 측정 범위를 정리했습니다.

## 준비

의존 저장소까지 함께 내려받습니다.

```sh
git clone --recursive https://github.com/VARZero/bosio_BoAYO.git
cd bosio_BoAYO
python -m pip install -r requirements.txt
```

로컬 미리보기:

```sh
PYTHONPATH=vendor/bosio_SphericalWM/sw:boayo \
python boayo/boayo_desktop.py --launcher --preview output/boayo.png
```

PYNQ-Z2에는 먼저 `bosio_SphericalWM` 데몬을 설치하고 실행해야 합니다. SSH 키를
사용하거나 암호를 환경 변수로 전달한 뒤 배포합니다.

```sh
export BOAYO_PYNQ_HOST=192.168.2.99
export BOAYO_PYNQ_USER=xilinx
export BOAYO_PYNQ_PASSWORD='your-password'
python boayo/deploy_boayo.py deploy-start
python boayo/deploy_boayo.py status
```

배포 시 `boayo-desktop.service`가 설치되고 활성화됩니다. 이후 PYNQ-Z2를 켜면
SphericalWM 데몬이 시작된 다음 BoAYO 데스크톱이 자동 실행됩니다.

```sh
systemctl is-enabled boayo-desktop.service
systemctl is-active boayo-desktop.service
```

BTN0은 Dashboard 앱을 현재 시선 위치로 불러옵니다. 이미 열린 Dashboard는 복원하고 포커스를 주며, 없으면 실행합니다. BTN1은 앱 목록 런처를 현재 시선으로 불러옵니다.
BTN2는 시선 중심을 클릭합니다. 자세한 구조는 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)를
참고하세요.

`apps.json`에 실행 가능한 `command`가 있는 항목만 런처에 표시합니다.
선택한 프로그램은 별도 프로세스로 시작하고 BOSIO API로 자기 창을 만듭니다.
실행에 성공하면 런처는 바로 숨겨지며 내장 전환 화면은 나타나지 않습니다.
BTN1로 런처를 다시 열 수 있습니다.

## BoAYo 애플리케이션 창과 캡션

Bosio 스택은 구면 창의 위치, 포커스, 겹침과 HDMI 투영을 맡습니다. BoAYo 애플리케이션은 `boayo_app_window.py`의 `BoayoApplicationWindow`로 Bosio 창을 하나 만들고, BoAYo 표면에서 앱 내용과 아래 캡션을 함께 그려 그 창에 전달합니다. 예제 Dashboard와 Telemetry가 이 경로를 사용합니다. 런처 패널은 `BoayoLauncherShell`로 따로 그리며 캡션이 없습니다.

현재 Bosio IPC 표면은 RGB24이므로 창 내부의 실제 알파 투명도는 전달하지 않습니다. 앱 프레임 안쪽 가장자리에 이동·크기 조절 손잡이를 배치하고 위쪽에 제목과 닫기 조작부를 표시합니다. BTN2 시선 클릭이 Bosio 창 이벤트를 거쳐 해당 BoAYo 컨트롤에 전달됩니다.

여러 앱에서 사용할 공개 Python API는 `boayo_sdk.py`의 `BoayoSDK`입니다. 앱은 SDK로 창을 만들고 내용만 그립니다. SDK는 캡션과 Bosio 이벤트 분배를 담당합니다. [SDK 빠른 시작](docs/SDK_QUICKSTART.md)에 앱 코드와 이미지 전달, 여러 창 사용 예제가 있습니다.
SDK 0.2.0부터 `sdk.window_state(window)`로 각도 크기·그림 표면 픽셀 크기·포커스를 읽고, `sdk.poll_events()`의 `resize`/`focus` 이벤트로 변경에 반응할 수 있습니다. 각도 크기를 바꿔도 RGB 그림 표면의 픽셀 수는 그대로입니다.
함수의 인자와 반환값, 이벤트 필드, UI 그리기 함수는 [SDK 함수·이벤트 안내](docs/SDK_API_REFERENCE.md)에 정리했습니다.

## 검증

```sh
python -m unittest discover -s tests -v
```

## 라이선스

Apache License 2.0
