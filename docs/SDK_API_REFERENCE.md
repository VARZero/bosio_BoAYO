# BoAYo SDK API 참고서

이 문서는 `boayo_sdk.py` **0.2.0**의 공개 Python API를 설명합니다. 앱은 BoAYo SDK로 RGB24 창 내용과 아래 캡션을 함께 제출합니다. Bosio 창 관리자는 구면 위치·겹침·포커스·정이십면체 장면 합성을 맡습니다. 런처 **패널**은 앱 창과 다른 Bosio 창이며 캡션이 없습니다.

처음 앱을 만들 때는 [SDK 빠른 시작](SDK_QUICKSTART.md)을 읽고, 함수·이벤트의 정확한 의미가 필요할 때 이 문서를 참고하세요. 실행 중 SDK를 계속 호출하려면 `/home/xilinx/bosio_v2/boayo`와 `/home/xilinx/bosio_v2`를 `PYTHONPATH`에 넣어야 합니다.

## 연결과 창 생명주기

```python
from boayo_sdk import BoayoSDK

with BoayoSDK("my-app") as sdk:
    window = sdk.create_window("My App")
    window.present(draw_content)
    while sdk.windows:
        for event in sdk.poll_events():
            handle(event)
```

| API | 역할·반환값 |
|---|---|
| `BoayoSDK(app_name, socket_path="/tmp/bosio-wm.sock", wm=None)` | 앱의 Bosio IPC 연결을 준비합니다. `app_name`은 소유 앱 이름입니다. `socket_path`는 데몬 소켓 주소입니다. `wm`은 이미 만든 Bosio 클라이언트를 주입하는 고급 용도입니다. |
| `with sdk ...` / `sdk.__enter__()` | 소켓에 연결하고 SDK 자신을 반환합니다. 연결 전에 `create_window()`을 부르면 `RuntimeError`가 납니다. |
| `sdk.close()` / `sdk.__exit__()` | SDK가 만든 연결을 닫고 로컬 창 목록을 비웁니다. 정상 IPC 연결이 닫히면 Bosio가 해당 앱 소유 창을 제거합니다. 주입된 `wm` 연결은 SDK가 닫지 않습니다. |
| `sdk.create_window(...)` | Bosio 앱 창 한 개를 등록하고 `BoayoApplicationWindow` 객체를 반환합니다. 창 생성은 그 창에 포커스를 줍니다. |
| `sdk.window_state(window)` | 앱 소유 창 객체 또는 `window_id`를 받아 불변 `BoayoWindowState` 스냅샷을 반환합니다. 소유하지 않거나 이미 SDK 목록에서 제거된 창이면 `ValueError`가 납니다. |
| `sdk.destroy_window(window)` | 지정한 앱 소유 창 **하나만** 닫습니다. 다른 창과 앱 프로세스는 유지됩니다. `window.closed=True`가 됩니다. |
| `sdk.poll_events()` | Bosio 입력을 한 번 읽고 캡션 동작·포커스·창별 크기 변경을 처리한 뒤 `list[BoayoEvent]`를 반환합니다. 정적 화면에서도 반복해서 호출해야 캡션이 반응합니다. |
| `sdk.windows` | 현재 이 SDK 연결이 소유한 `{window_id: window}` 딕셔너리입니다. 캡션 닫기나 `destroy_window()` 뒤에 해당 창이 빠집니다. |

### `create_window()` 인자

```python
window = sdk.create_window(
    title, *, azimuth=None, elevation=None,
    width_deg=38, height_deg=28,
    width=400, height=300, accent=ACCENT,
)
```

| 인자 | 단위·역할 |
|---|---|
| `title` | 앱 창 제목. 현재 앱 캡션 상자에서 공간이 되면 일부를 그립니다. |
| `azimuth`, `elevation` | 창 **중심**의 구면 각도, 도(°). 생략하면 런처가 전한 `BOAYO_APP_AZIMUTH`/`BOAYO_APP_ELEVATION` 환경 변수를 읽고, 그 값도 없으면 0°입니다. |
| `width_deg`, `height_deg` | 구면 공간에서 창이 차지하는 가로·세로 각도, 도(°). HDMI 픽셀 수가 아닙니다. |
| `width`, `height` | 앱의 RGB24 그림 **표면 픽셀** 크기. 기본 400×300이며 현재 캡션 레이아웃은 최소 240×170 픽셀이 필요합니다. |
| `accent` | RGB 색상 튜플. 앱 프레임에 저장됩니다. 현재 기본 캡션 조작 버튼은 정해진 회색·빨강 색을 사용하므로 이 인자만 바꿔 버튼 색이 바뀌지는 않습니다. |

창의 표면 픽셀 크기는 만든 뒤 고정됩니다. 캡션으로 창 크기를 조절할 때 바뀌는 것은 `width_deg`/`height_deg`입니다. 다른 소스 해상도로 내용을 만들 수는 있지만 그 이미지는 고정된 내용 영역에 맞춰 그려집니다.

## 창 객체와 그림 제출

`create_window()`의 결과인 `BoayoApplicationWindow`에서 자주 쓰는 속성은 `window_id`, `closed`, `focused`, `azimuth`, `elevation`, `width_deg`, `height_deg`, `frame.content`, `state`입니다. `state`는 아래의 불변 스냅샷입니다. `frame.content`는 `AppRect(x, y, width, height)`로, 앱이 실제로 그리는 픽셀 사각형입니다. 이 좌표의 원점은 **전체 RGB 표면**의 왼쪽 위입니다.

| 함수 | 역할 |
|---|---|
| `window.present(draw_content)` | `draw_content(canvas, content)` 콜백으로 내용을 그리고 아래 캡션을 더한 뒤 RGB24 표면 전체를 Bosio에 보냅니다. `canvas`는 `BoayoSurface`, `content`는 `AppRect`입니다. 호출할 때마다 내용이 다시 제출됩니다. |
| `window.present_rgb(rgb, fit="contain")` | `(높이, 너비, 3)` RGB NumPy 배열을 내용 영역에 bilinear 크기 조절로 넣고 캡션을 더합니다. `contain`은 비율을 유지하고 `stretch`는 내용 영역에 늘립니다. 배열은 `uint8`로 변환됩니다. |
| `window.state` | 현재 로컬 창 상태의 `BoayoWindowState` 스냅샷입니다. |
| `window.poll_events()` | 저수준 단일 창 도우미입니다. **BoayoSDK 사용 앱에서는 호출하지 마세요.** SDK와 동일한 Bosio 이벤트 큐를 소비해 다른 창의 이벤트를 잃을 수 있습니다. |

`BoayoApplicationWindow(...)` 생성자를 직접 호출하는 저수준 경로도 있지만 일반 앱에서는 `sdk.create_window()`를 사용하세요. `window.handle_event(raw)`, `window.apply_gaze_drag(azimuth, elevation)`, `window.cancel_drag()`는 캡션 입력·창 밖 드래그를 SDK가 처리할 때 사용하는 저수준 함수입니다. 앱에서 직접 호출하면 SDK의 이벤트·크기 변경 조회 시점과 어긋날 수 있습니다.

`draw_content`는 매번 내용 영역 안에 그려야 합니다. SDK가 전체 표면을 지우고 앱 내용을 만든 뒤 캡션을 그립니다. 앱이 전달한 RGB 표면은 픽셀별 알파 투명도를 지원하지 않습니다.

### `BoayoWindowState` 필드

| 필드 | 의미 |
|---|---|
| `window_id` | Bosio 창 식별자. 이벤트 분배에 사용합니다. |
| `azimuth`, `elevation` | 현재 창 중심 각도, 도(°). |
| `width_deg`, `height_deg` | 현재 구면 창 각도 크기, 도(°). |
| `surface_width`, `surface_height` | RGB24 표면의 고정 픽셀 크기. |
| `content_width`, `content_height` | 캡션을 뺀 앱 내용 사각형의 고정 픽셀 크기. |
| `focused` | SDK가 마지막으로 처리한 포커스 상태. |
| `closed` | SDK 창 객체가 닫혔는지 여부. |

`sdk.window_state(window)`와 `window.state`의 내용은 같습니다. 포커스는 `sdk.poll_events()`에서 Bosio 이벤트를 처리한 후 갱신됩니다. SDK 밖에서 Bosio IPC로 창의 기하 정보를 직접 바꾼 경우 SDK의 로컬 객체가 자동으로 동기화되지 않습니다.

## 앱에 반환되는 이벤트

`sdk.poll_events()`의 반환 목록 요소는 불변 `BoayoEvent`입니다. 모든 이벤트에 `window_id`와 `type`이 있습니다. `x`, `y`, `pressed`, `button`, `focused`, `state`는 이벤트 종류에 따라 값 또는 `None`입니다.

| `event.type` | 언제 전달되나 | 유효한 주요 필드 |
|---|---|---|
| `pointer_motion` | **앱 내용 영역**에서 포인터가 움직일 때 | `x`, `y` |
| `pointer_button` | **앱 내용 영역**에서 버튼을 누르거나 놓을 때 | `x`, `y`, `pressed`, `button` |
| `focus` | Bosio가 해당 창에 포커스를 주거나 빼앗을 때 | `focused`, `state` |
| `resize` | 캡션 조작으로 해당 창의 **각도 크기**가 이전 조회 이후 달라졌을 때 | `state.width_deg`, `state.height_deg` 등 |

`pointer_motion`/`pointer_button`의 `x`, `y`는 **캡션을 뺀 내용 영역 왼쪽 위가 (0, 0)**인 픽셀 좌표입니다. 부동소수점 값이고 오른쪽·아래쪽으로 증가합니다. `button`은 Bosio 입력 이름이며 왼쪽 클릭은 `"left"`입니다. `pressed`는 `pointer_button`에만 `True`/`False`이고 `pointer_motion`에서는 `None`입니다. 이 두 입력 이벤트의 `state`는 `None`입니다.

`focus`의 `event.focused`는 변경된 포커스 여부이며 `event.state.focused`와 같습니다. `resize`의 `event.state`는 새 크기를 포함한 창 상태 스냅샷입니다. `resize` 이벤트 자체에는 별도 `x`, `y`나 픽셀 표면 크기 변경이 없습니다. 한 번의 `poll_events()` 호출에서 크기가 여러 차례 달라져도 **창당 최종 크기 한 번**을 반환합니다. 창 밖으로 캡션 드래그가 이어져도 전역 포인터 위치를 따라 크기 변경을 감지합니다.

캡션의 닫기·이동·크기 조절 클릭은 SDK가 소비하므로 앱 내용의 포인터 이벤트로 오지 않습니다. 닫기 완료를 별도의 `close` 이벤트로 보내지 않으며 `window.closed`와 `sdk.windows`로 확인합니다. 이동에는 현재 별도의 `move` 이벤트가 없고 `window.state.azimuth/elevation`을 읽습니다. 런처 **패널**의 입력은 앱 SDK 이벤트가 아닙니다.

### 여러 창의 이벤트 분배

```python
with BoayoSDK("my-app") as sdk:
    main = sdk.create_window("Main")
    tools = sdk.create_window("Tools", azimuth=20, elevation=0)
    main.present(draw_main)
    tools.present(draw_tools)

    while sdk.windows:
        for event in sdk.poll_events():
            if event.type == "resize":
                print(event.window_id, event.state.width_deg, event.state.height_deg)
            elif event.type == "focus":
                print(event.window_id, event.focused)
            elif event.type == "pointer_button" and event.pressed:
                print(event.window_id, event.x, event.y)
        # 앱의 다른 작업도 이 루프에서 진행
```

`sdk.poll_events()`가 한 IPC 연결에서 모든 창 이벤트를 읽으므로 `window_id`로 나누어 처리합니다. 내용이 정적이어도 주기적으로 호출하세요. 앱 예제들은 약 50 ms 간격으로 호출합니다.

## `BoayoSurface` 그리기 도구

`window.present(draw_content)`의 `canvas`는 RGB24 `BoayoSurface`입니다. 색은 `(R, G, B)` 0~255 튜플입니다. 좌표와 크기는 **전체 표면의 픽셀** 단위이며 `content.x/y`를 더해 내용 영역에 배치합니다.

| 함수 | 역할 |
|---|---|
| `BoayoSurface(width=640, height=360, background=BLACK)` | RGB24 표면을 만듭니다. `window.present()`의 콜백은 SDK가 만든 표면을 이미 받으므로 보통 직접 생성하지 않습니다. |
| `canvas.clear(color=BLACK)` | 표면 전체를 한 색으로 채웁니다. `present()`는 콜백 전에 이미 초기화하므로 보통 앱에서 다시 부르지 않습니다. |
| `canvas.rect(x, y, width, height, color, fill=True, stroke=1)` | 직사각형. `fill=False`이면 테두리 굵기 `stroke`를 사용합니다. |
| `canvas.rounded_rect(x, y, width, height, radius, color)` | AA가 있는 둥근 모서리 상자를 그립니다. |
| `canvas.polygon(points, color)` | 꼭짓점의 `(x, y)` 목록으로 AA 다각형을 그립니다. |
| `canvas.rounded_polygon(points, radius, color)` | 꼭짓점이 둥근 AA 다각형을 그립니다. |
| `canvas.circle(cx, cy, radius, color)` | AA 원을 그립니다. |
| `canvas.text(value, x, y, color=INK, scale=2, bold=False)` | 내장 5×7 글꼴로 문자를 그립니다. 대문자 변환 후 그리며 글꼴에 없는 문자는 빈 칸으로 처리합니다. `scale`은 픽셀 확대 배율입니다. |
| `canvas.card(x, y, width, height, title, value, accent=ACCENT)` | 표준 카드·점·두 줄 텍스트를 한 번에 그립니다. |
| `canvas.progress(x, y, width, ratio, color=ACCENT)` | 0~1 비율의 둥근 진행 막대를 그립니다. |
| `canvas.image()` | 현재 `(높이, 너비, 3)` 연속 메모리 RGB 배열을 반환합니다. |

`canvas.pixels`는 같은 표면을 나타내는 쓰기 가능한 `uint8` NumPy 배열입니다. 외부 이미지 라이브러리에서 만든 픽셀을 내용 사각형에 직접 복사할 때 사용할 수 있습니다. 캡션 영역까지 덮어쓰지 않도록 `content` 좌표를 사용하세요.

`INK`, `MUTED`, `PANEL`, `WHITE`, `ACCENT`는 SDK에서 가져올 수 있는 RGB 색상 상수입니다. 앱에서 한글이나 더 선명한 글꼴이 필요하면 별도 라이브러리로 RGB 이미지를 만들고 `present_rgb()`로 전달하세요. 내장 5×7 글꼴은 한글을 그리지 않습니다.

## 오류와 현재 범위

- SDK 연결 전에 `create_window()`를 호출하거나 연결 종료 뒤 `poll_events()`를 호출하면 `RuntimeError`가 납니다.
- 앱이 소유하지 않은 창을 `window_state()`/`destroy_window()`에 주면 `ValueError`가 납니다.
- 표면이 240×170 픽셀보다 작으면 캡션 레이아웃이 `ValueError`를 냅니다. `present_rgb()` 입력은 3채널 RGB 배열과 `fit="contain"` 또는 `"stretch"`가 필요합니다.
- Bosio IPC 연결이 끊기거나 서버가 오류를 반환하면 저수준 Bosio 클라이언트 오류가 올라옵니다. 보드에서는 `bosio-window-manager.service`와 `boayo-desktop.service` 상태를 먼저 확인하세요.
- 구면 크기 조절은 앱 그림 표면의 픽셀 해상도를 자동으로 높이지 않습니다. RGB24에 픽셀별 알파 채널도 없습니다.

전체 앱 예제: [`boayo_pulse_app.py`](../boayo/boayo_pulse_app.py), [`boayo_sdk_multiwindow.py`](../examples/boayo_sdk_multiwindow.py).
