# BoAYo와 BOSIO 창 합성

PYNQ-Z2의 실사용 경로는 `boayo_native_desktop.py`가 런처 이미지를 그려
`BosioWMClient.update_surface()`로 BOSIO 창 관리자에 전달하는 구조다.
BoAYo가 전체 정이십면체 장면을 직접 소유하지 않는다. 런처는 BOSIO의
`always_on_top` 창 하나이고, 외부 애플리케이션은 각각 자기 BOSIO 창을 만든다.

```text
GY-521 자세 + PYNQ 버튼
          |
          v
BoAYo 런처/외부 앱의 RGB 표면
          |
          v
BOSIO 창 관리자: 포커스·겹침·구면 투영 AA·부분 타일 갱신
          |
          v
정이십면체 프레임버퍼 -> BOSIO OutputCore -> HDMI
```

BoAYo는 `boayo_ui.py`에서 둥근 패널, 앱 아이콘, 원형 표시와 제어 다각형의
경계를 4×4 서브픽셀 커버리지로 원래 배경색에 혼합한다. 이 작업은 640×360
RGB 표면을 만들 때 수행된다. BOSIO의 네이티브 창 합성기는 그 표면을
삼각 셀의 면적에 맞게 bilinear/적응형 4×4로 샘플링하고, 창 외곽에서는
아래 장면과 부분 커버리지로 혼합한다. 따라서 두 AA는 서로 다른 경계에
작용한다. 마지막 HDMI 단계의 BS24 경계 AA는 기본 혼합 강도 32다.

런처 화면은 앱 선택, 스크롤, 표시 상태가 바뀔 때만 다시 그린다.
`boayo_native_desktop.py`도 같은 상태 키를 확인해 이미지가 바뀔 때만
`update_surface()`를 호출한다. 시선에 따른 창 위치 변경은 BOSIO의
`configure_window()`가 맡으므로 런처 표면을 다시 만들 필요가 없다.
보드에서 640×360 런처의 새 AA 첫 렌더는 약 190ms, 같은 상태의 캐시
조회는 약 0.02ms였다. 이 숫자는 RGB 표면 생성 시간이며 최종 HDMI FPS는 아니다.

BTN0과 BTN1은 유일한 런처 창을 현재 시선으로 옮겨 포커스를 주고,
BTN2는 시선 중심을 런처의 클릭 좌표로 보낸다. 앱 목록의 항목은
`apps.json`에 실제 실행 명령이 있는 경우에만 표시한다. 실행된 외부 앱은
`BosioWMClient`를 통해 별도 창을 만든다.

`boayo_desktop.py`와 `BoayoScene`은 호스트 미리보기 및 이전 직접 장면 경로다.
실사용 서비스는 `boayo_native_desktop.py`를 실행하므로 화질을 판단할 때는
USB3.0 Video 캡처의 실제 BOSIO 창 경로를 확인해야 한다. `M=16`과 RGB332에서는
작은 글자와 매우 가는 선에 삼각 셀 계단이 여전히 보인다.
