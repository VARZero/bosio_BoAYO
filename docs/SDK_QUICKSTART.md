# BoAYo 앱 SDK 빠른 시작

`boayo_sdk.py`는 여러 Python 앱이 같은 BoAYo 창 규칙을 사용할 수 있는 공개 API입니다. 각 앱은 독립 프로세스로 실행됩니다. 한 앱은 SDK 연결 하나로 창을 여러 개 만들 수 있습니다. SDK가 Bosio IPC 연결, 앱 창 등록, 내용 아래 캡션, 캡션 클릭과 창별 이벤트 분배를 처리합니다. Bosio는 구면 위치·겹침·포커스·최종 출력을 처리합니다. BoAYo 런처 **패널에는 캡션이 없습니다.**

함수별 인자와 반환값, 이벤트 필드, 그리기 도구 목록은 [SDK 함수·이벤트 안내](SDK_API_REFERENCE.md)에 있습니다.

## 실행 환경

PYNQ-Z2에서 BoAYo를 배포하면 SDK와 Bosio 클라이언트가 `/home/xilinx/bosio_v2/boayo`에 있습니다. 런처의 `apps.json`에서 실행된 앱에는 필요한 `PYTHONPATH`와 실행 시선의 `BOAYO_APP_AZIMUTH`, `BOAYO_APP_ELEVATION`이 자동 전달됩니다. 런처 밖에서 직접 실행할 때는 다음처럼 경로를 설정합니다.

```sh
export PYTHONPATH=/home/xilinx/bosio_v2/boayo:/home/xilinx/bosio_v2${PYTHONPATH:+:$PYTHONPATH}
python3 my_app.py
```

BoAYo SDK는 Python과 NumPy를 사용합니다. 창 표면은 RGB24이므로 실제 알파 투명도는 없으며 캡션은 불투명 박스로 그립니다. 앱 창에는 Bosio 기본 테두리·상단 제목을 붙이지 않습니다.

앱 창의 캡션은 마우스 왼쪽 버튼 또는 BTN2 시선 클릭으로 조작합니다. 빨간 삼각형은 눌렀다 떼면 창을 닫습니다. 가운데 회색 버튼을 누른 채 포인터나 시선을 움직이면 창이 이동하고, 양끝 버튼을 누른 채 움직이면 창의 구면 각도 크기가 바뀝니다. BTN2는 누르고 있는 동안만 드래그 상태이며 뗄 때 끝납니다. 런처 패널을 여는 BTN0/BTN1도 진행 중인 BTN2 드래그를 끝냅니다.

런처 패널이 열린 상태에서 흰 패널 밖의 검은 여백이나 그보다 먼 구면 위치를 클릭하면 런처 패널만 닫힙니다. 마우스 왼쪽 클릭과 BTN2 시선 클릭에 동일하게 적용되며, 아래에 있는 앱 창은 유지되고 그 위치의 앱 클릭도 전달됩니다. BTN0/BTN1로 런처를 다시 열 수 있습니다.

PYNQ-Z2의 Logitech G102 실측에서 Bosio 마우스 감도 `0.03°/입력값`을 사용합니다. 마우스를 보드 서비스 시작 후 연결한 경우 Bosio 창 관리자와 BoAYo 데스크톱 서비스를 재시작해야 마우스가 활성화됩니다. 마우스 위치 표시를 숨기는 설정은 유지되므로 캡션 조작 시 포인터의 현재 구면 위치를 고려해야 합니다.

## 가장 작은 앱

```python
import time
from boayo_sdk import BoayoSDK, INK

with BoayoSDK("my-app") as sdk:
    window = sdk.create_window("My App", width_deg=38, height_deg=28)

    def draw(canvas, content):
        canvas.text("HELLO", content.x + 20, content.y + 20,
                    INK, scale=3, bold=True)

    window.present(draw)
    while not window.closed:
        for event in sdk.poll_events():
            if event.window_id == window.window_id and event.type == "pointer_button" and event.pressed:
                print(f"content click: ({event.x:.1f}, {event.y:.1f})", flush=True)
        time.sleep(.05)
```

`create_window()`의 시선 좌표를 생략하면 런처가 전달한 위치가 쓰입니다. `window.present(draw)`의 `content`는 캡션을 제외한 앱 내용 영역의 픽셀 사각형입니다. 이벤트의 `x`, `y`는 그 내용 영역의 왼쪽 위를 `(0, 0)`으로 한 좌표입니다. 캡션 이벤트는 SDK가 직접 처리하며 내용 클릭 이벤트로 전달되지 않습니다. 정적 앱도 `poll_events()`를 호출해야 닫기·이동·크기 조절이 반응합니다.

## 창 크기·변경·포커스

`sdk.window_state(window)` 또는 `window.state`는 읽는 시점의 창 상태를 복사한 `BoayoWindowState`입니다. 앱이 만든 여러 창을 ID로 구분할 때는 `sdk.window_state(window_id)`도 사용할 수 있습니다. SDK 0.2.0부터 포커스 이벤트가 현재 상태를 갱신하고, 캡션으로 구면 각도 크기를 조절하면 `resize` 이벤트가 전달됩니다.

```python
state = sdk.window_state(window)
print(state.width_deg, state.height_deg)            # 구면 창의 각도 크기(°)
print(state.surface_width, state.surface_height)    # RGB24 표면 픽셀 크기
print(state.content_width, state.content_height)    # 캡션을 뺀 내용 픽셀 크기
print(state.focused)                                # 현재 포커스 여부

for event in sdk.poll_events():
    if event.window_id != window.window_id:
        continue
    if event.type == "resize":
        print("new angular size", event.state.width_deg, event.state.height_deg)
        window.present(draw)  # 각도에 맞춰 내용을 다시 그릴 필요가 있을 때
    elif event.type == "focus":
        print("focused", event.focused, event.state.focused)
```

`resize`는 창의 최종 각도 크기가 이전 `poll_events()` 호출 이후 달라졌을 때 **호출당 창별로 최대 한 번** 발생합니다. BTN2나 마우스로 캡션을 드래그하다 창 밖으로 나가도 변경을 감지합니다. `state`에는 창 중심 위치인 azimuth/elevation과 `closed`도 포함됩니다. 구면 크기 조절은 창이 덮는 **각도**를 바꾸지만, RGB24 이미지와 내용 영역의 **픽셀 크기**는 바꾸지 않습니다. 다른 해상도의 이미지를 만들려면 앱에서 소스 이미지 크기를 결정하세요. 포커스 상태는 `sdk.poll_events()`로 새 이벤트를 읽은 뒤 갱신됩니다. SDK를 거치지 않고 Bosio IPC에서 직접 바꾼 창 위치·크기는 SDK 창 객체에 자동 반영되지 않습니다.

이미 렌더링한 RGB 이미지가 있다면 `window.present_rgb(image, fit="contain")`을 사용합니다. 입력은 `(높이, 너비, 3)` NumPy 배열입니다. `fit="stretch"`도 사용할 수 있습니다. SDK가 이미지를 내용 영역에 넣고 캡션을 덧그립니다.

## 앱 하나에서 창 여러 개 만들기

```python
with BoayoSDK("multi-view") as sdk:
    main = sdk.create_window("Main")
    tools = sdk.create_window("Tools", azimuth=20, elevation=0,
                              width_deg=30, height_deg=22)
    main.present(draw_main)
    tools.present(draw_tools)
    while sdk.windows:
        for event in sdk.poll_events():
            if event.window_id == main.window_id:
                handle_main(event)
            elif event.window_id == tools.window_id:
                handle_tools(event)
        time.sleep(.05)
```

SDK는 한 번에 Bosio 이벤트 큐를 읽고 창 ID별로 분배합니다. 앱 코드에서 각 창의 `poll_events()`를 따로 호출하면 다른 창의 이벤트까지 소비할 수 있으므로 위처럼 `sdk.poll_events()`를 사용합니다. 앱에서 직접 한 창을 닫으려면 `sdk.destroy_window(window)`을 호출하면 됩니다. 다른 창과 프로세스는 유지됩니다.

실제 예제는 [`boayo_example_app.py`](../boayo/boayo_example_app.py), [`boayo_telemetry_app.py`](../boayo/boayo_telemetry_app.py), [`boayo_pulse_app.py`](../boayo/boayo_pulse_app.py)에 있습니다. SDK Pulse 앱은 내용의 막대를 1초마다 갱신하고, 내용 클릭 횟수를 표시합니다. 런처 목록에서 실행하거나 보드의 현재 시선에서 직접 실행하려면 `BOAYO_PYNQ_PASSWORD`를 설정하고 `python boayo/deploy_boayo.py run-pulse`를 실행합니다. 직접 실행된 앱은 `boayo-sdk-pulse.service`로 유지됩니다. 이 직접 실행 명령은 앱을 시작한 뒤 런처 패널을 접으며, BTN0/BTN1을 누르면 패널을 다시 열 수 있습니다. `apps.json`에는 실행 가능한 앱의 절대 경로를 `command`로 등록합니다.

SDK를 BoAYo 폴더 밖의 앱에서 가져와 창 두 개를 만드는 실행 예제는 [`boayo_sdk_multiwindow.py`](../examples/boayo_sdk_multiwindow.py)에 있습니다.
