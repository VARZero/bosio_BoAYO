# BoAYo 앱 SDK 빠른 시작

`boayo_sdk.py`는 여러 Python 앱이 같은 BoAYo 창 규칙을 사용할 수 있는 공개 API입니다. 각 앱은 독립 프로세스로 실행됩니다. 한 앱은 SDK 연결 하나로 창을 여러 개 만들 수 있습니다. SDK가 Bosio IPC 연결, 앱 창 등록, 내용 아래 캡션, 캡션 클릭과 창별 이벤트 분배를 처리합니다. Bosio는 구면 위치·겹침·포커스·최종 출력을 처리합니다. BoAYo 런처 **패널에는 캡션이 없습니다.**

## 실행 환경

PYNQ-Z2에서 BoAYo를 배포하면 SDK와 Bosio 클라이언트가 `/home/xilinx/bosio_v2/boayo`에 있습니다. 런처의 `apps.json`에서 실행된 앱에는 필요한 `PYTHONPATH`와 실행 시선의 `BOAYO_APP_AZIMUTH`, `BOAYO_APP_ELEVATION`이 자동 전달됩니다. 런처 밖에서 직접 실행할 때는 다음처럼 경로를 설정합니다.

```sh
export PYTHONPATH=/home/xilinx/bosio_v2/boayo:/home/xilinx/bosio_v2${PYTHONPATH:+:$PYTHONPATH}
python3 my_app.py
```

BoAYo SDK는 Python과 NumPy를 사용합니다. 창 표면은 RGB24이므로 실제 알파 투명도는 없으며 캡션은 불투명 박스로 그립니다. 앱 창에는 Bosio 기본 테두리·상단 제목을 붙이지 않습니다.

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

실제 예제는 [`boayo_example_app.py`](../boayo/boayo_example_app.py)와 [`boayo_telemetry_app.py`](../boayo/boayo_telemetry_app.py)에 있습니다. `apps.json`에는 실행 가능한 앱의 절대 경로를 `command`로 등록합니다.

SDK를 BoAYo 폴더 밖의 앱에서 가져와 창 두 개를 만드는 실행 예제는 [`boayo_sdk_multiwindow.py`](../examples/boayo_sdk_multiwindow.py)에 있습니다.
