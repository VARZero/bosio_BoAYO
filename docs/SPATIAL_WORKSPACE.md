# 구면 작업 공간

HTML 시제품의 조작 경험을 방위각·고도각 공간으로 옮겼다. 정이십면체,
센서 자세 투영, DDR 장면 형식, RGB332 팔레트, HDMI 출력과 비트스트림은
변경하지 않는다. 완료 결과를 띄우는 토스트·1.7초 알림은 없다.

## 조작

- 창 가장자리의 이동 손잡이를 시선 또는 마우스로 가리켜 잡는다.
- BTN2 또는 왼쪽 마우스 버튼을 유지하면서 구면 위치로 이동한다.
- 이동 중 고도각 -36° 이하에서 놓으면 220ms 동안 축소·배경색 페이드 후
  최소화한다. 창을 잡기 전 정상 위치와 크기를 저장한다.
- 보관 카드는 원래 방위각을 유지하며 -42°부터 아래쪽으로 배치한다.
  같은 방향의 카드는 구면 투영 폭을 고려해 다른 행·인접 방향에 배치한다.
- 카드를 클릭하면 저장한 정상 위치와 크기로 복원한다.
- 카드를 잡고 1° 이상 이동하면 드래그한다. 시작 위치보다 5° 이상 위로
  올리면 실제 복원 크기의 미리보기를 표시하고, 놓은 위치에 복원한다.
- 카드를 -76° 이하로 내리면 닫기 후보가 표시된다. 여기서 놓으면
  해당 창만 닫는다. 중간 영역에서 놓으면 보관 상태를 유지한다.
- BTN3 또는 Escape는 조작을 취소한다. 취소는 최소화·복원·닫기를 확정하지
  않으며 이미 이동·조절된 정상 창의 기하 정보는 유지한다.
- 모서리 손잡이는 각도 크기를 조절한다. RGB 표면의 픽셀 수는 고정이다.
- 선택한 창은 강조되고, 조작부와 보관 카드는 가리키거나 잡을 때 강조된다.
  작은 창은 조작 안내를 짧게 표시한다. 다른 방향의 창을 화면 폭 때문에
  없애는 CSS 반응형 규칙은 사용하지 않는다.
- 선택적 USB 키보드는 F6으로 보이는 창·카드 포커스를 순환한다. 앱에서는
  Tab으로 조작부를 순환하고 Enter/Space로 닫기 버튼을 활성화한다.
  카드에서는 Enter/Space로 복원한다. 키보드가 없어도 시선·버튼·마우스로
  모든 창 조작을 할 수 있다.

## 역할과 연결

`boayo_app_window.py`는 앱 프레임, 상태, 축소 전환, 정상 위치 복원을 맡는다.
`boayo_sdk.py`는 앱 입력과 `minimize`/`restore` 이벤트를 분배한다.
`boayo_spatial_workspace.py`는 데스크톱 소유의 카드·고스트·미리보기·후보 안내를
별도 BOSIO 창으로 만든다. 후보 창은 `input_enabled=False`여서 클릭을 가리지
않고 생성 시 포커스를 가져가지 않는다.

앱 창의 공개 `workspace` 메타데이터에는 `role`, `state`, `restore`,
`dock_azimuth`가 들어간다. 데스크톱은 다른 앱 창을 직접 수정하지 않고
`request_window_action()`으로 소유 앱에 `window_action` 이벤트를 보낸다.
앱은 계속 `sdk.poll_events()`를 호출해야 복원·닫기 요청을 처리한다.

BOSIO 소프트웨어에는 소유자별 포인터 캡처, 화면 밖 버튼 해제 좌표,
취소 이벤트, 비입력 창, 작업 공간 요청 이벤트를 추가했다. 기본 제목
드래그는 `decorated=True`인 창에만 적용한다. 숨긴 창은 포커스·캡처에서
빠지고, 일반 앱은 보관 카드보다 위로 올라오지 않는다.

보아요 0.3.0과 `spatial-workspace` 기능을 제공하는 BOSIO 소프트웨어를 함께
배포해야 한다. FPGA 하드웨어 재빌드는 필요하지 않다. 기존 비트스트림을
다시 로드하지 않는 소프트웨어 갱신 절차를 사용할 수 있다.

## 미리보기와 검증

```sh
python -m unittest discover -s tests -v
python examples/boayo_spatial_preview.py --output output/spatial-workspace.png
```

미리보기는 실제 소프트웨어 구면 합성 결과를 M=16 삼각 셀과 RGB332로
재구성한다. 보드의 HDMI 캡처·드래그 처리율을 대신하는 측정값은 아니다.
반투명·배경 블러 대신 불투명 RGB 패널과 테두리 미리보기를 사용한다.


## Visual design and board deployment (2026-10-05)

`boayo_theme.py` shares dark RGB332 chrome, mint focus edges, storage cards,
launcher rows, and drag previews. Application content keeps its RGB rectangle.
Result notifications remain excluded. Dashboard shows live open/stored window
counts and sensor yaw/pitch. Fictional battery/volume indicators were removed.

BTN0 summons the actual Dashboard at current gaze, restoring an existing instance.
BTN1 opens the launcher; BTN2 selects/holds/drags; BTN3 cancels. Dashboard summon
accepts elevations down to -85 degrees so it is visible when looking down.
Storage-card lift still places windows no lower than -30 degrees.

Python software was deployed to 192.168.2.99. Both services remain enabled.
Bitstream, HWH, driver and native compositor checksums are unchanged. Backup:
`/home/xilinx/bosio_v2/backup-spatial-20261005-110019`.

Live IPC tests passed for minimize, click/restore, lift/place preview, resize,
cancellation, close and Dashboard summon/reuse. HDMI capture confirmed output.
The agent executed the BTN0 callback on the board; physical presses were not tested.
Existing sphere sampling resolution and RGB332 limits remain.


## Detached window controls

Application windows use a thin rounded shell with distinct title/content/status
bands. The move grip floats left of the shell with a real gap; one diagonal
resize handle floats at bottom right. No caption close button is exposed.
Close remains the storage-card downward drag. Dashboard has a single title in
its titlebar, with workspace content below.

BOSIO software now accepts a `shape` union of rounded rectangles in surface
pixels: `[x, y, width, height, radius]`. Empty shape retains rectangular behavior.
Both native composition and NumPy composition omit cells outside that shape,
and pointer hit testing passes through holes to windows underneath. Black app
content remains opaque: transparency is determined by geometry, not color.
The shape scales with angular window resize and follows drag/minimize/restore.
Native C++ software is rebuilt for this support; hardware/bitstream/driver are
unchanged. The previous claim that the native library stays unchanged applies
to the earlier deployment only.
