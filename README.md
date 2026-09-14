# BoAYO

BoAYO는 BOSIO 정이십면체 프레임버퍼 위에서 동작하는 시선 중심 구면 데스크톱
플랫폼입니다. PYNQ-Z2의 GY-521 자세 입력으로 포커스를 이동하고 보드 버튼으로
런처와 창을 조작합니다.

BoAYO는 완성된 구면 장면을 SphericalWM의 scene-stream IPC로 전달합니다. 모든
셀은 bilinear 보간하며 글자와 모서리처럼 명암 차이가 큰 셀에는 adaptive 4×4
supersampling을 적용합니다.

기본 셀 분할도는 `M=32`이며 각 삼각 타일이 32×32개의 작은 삼각 셀을 갖습니다.

## 구성

```text
GY-521 자세 + PYNQ 버튼
          |
          v
BoAYO 런처/창/시선 포커스
          |
          v
bilinear + adaptive 4x4 구면 투영
          |
          v
SphericalWM scene-stream -> BOSIO OutputCore -> HDMI
```

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

BTN0은 시선으로 포커스된 항목을 선택하며 BTN1은 런처를 현재 시선 위치로 다시
배치합니다. 자세한 구조는 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)를 참고하세요.

## 검증

```sh
python -m unittest discover -s tests -v
```

## 라이선스

Apache License 2.0
