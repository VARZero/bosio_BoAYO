"""On-board SDK -> shaped HW projection -> active DDR validation.

Pause desktop input briefly before this deterministic check, then resume it.
Run with the deployed BoAYo/WM modules on PYTHONPATH. Test windows are removed.
"""
import json
import time
from pathlib import Path
from boayo_sdk import BoayoSDK


report = {'cases': []}


with BoayoSDK('boayo-m32-validation') as sdk:
    wm = sdk.wm
    assert wm.ping()['m'] == 32
    assert wm.get_state()['compositor'] == 'fpga-dual+ps-incremental'

    def presented(name, started=None):
        generation = wm.get_state()['generation']
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            state = wm.get_state()
            if state['render_error']:
                raise AssertionError(state['render_error'])
            p = state.get('projection_presented')
            if p and p['generation'] >= generation:
                break
            time.sleep(.02)
        else:
            raise TimeoutError(name)
        assert p['backend']['mode'] == 'fpga-dual+ps-incremental'
        acknowledged_at = time.monotonic()
        reference = wm.call('check_incremental_reference')
        assert reference['cached_mismatched_words'] == reference['output_mismatched_words'] == 0
        assert reference['active_matches']
        item = dict(name=name, backend=p['backend'], performance=state['performance'], reference=reference)
        if started is not None: item['present_to_ack_ms'] = (acknowledged_at-started)*1000
        report['cases'].append(item)
        print(json.dumps(item), flush=True)
        return item

    patch_color = [32,64,96]
    def paint(canvas, rect):
        canvas.rect(rect.x,rect.y,rect.width,rect.height,(32,64,96))
        canvas.rect(rect.x+20,rect.y+25,8,8,tuple(patch_color))

    app = sdk.create_window('M32 SDK validation',azimuth=0,elevation=0,
        width_deg=32,height_deg=24,width=640,height=440)
    wm.configure_window(app.window_id,always_on_top=True)
    wm.raise_window(app.window_id)
    app.present(paint)
    initial = presented('rounded_app_on_hardware')
    full_jobs = sum(initial['backend']['jobs_per_core'])
    assert app.window_id in initial['backend']['shaped_windows']
    other = sdk.create_window('Unchanged cached app',azimuth=20,elevation=0,
        width_deg=20,height_deg=20,width=640,height=440)
    wm.configure_window(other.window_id,always_on_top=True)
    wm.raise_window(other.window_id)
    other.present(lambda c,r:c.rect(r.x,r.y,r.width,r.height,(224,64,32)))
    presented('second_shaped_app')

    started = time.monotonic()
    patch_color[:] = (224,224,32)
    app.present(paint)
    draw_ms = (time.monotonic()-started)*1000
    partial = presented('8x8_sdk_edit_reuses_other_app', started)
    assert partial['backend']['projected_windows'] == [app.window_id]
    assert 0 < sum(partial['backend']['jobs_per_core']) < full_jobs
    assert partial['backend']['changed_tiles'] > 0
    assert app.publisher.last_bytes == 192
    partial['sdk_rgb_bytes'] = app.publisher.last_bytes
    partial['app_render_and_ipc_ms'] = draw_ms

    before = wm.get_state()
    app.present(paint)
    after = wm.get_state()
    assert before['generation'] == after['generation']
    assert app.publisher.last_bytes == 0
    assert before['projection_presented']['active_address'] == after['projection_presented']['active_address']
    report['cases'].append(dict(name='identical_app_surface_zero_ipc',rgb_bytes=0,generation_unchanged=True))

    for mapped in (False,True):
        if mapped:
            app.restore()
        else:
            app.minimize()
            app.tick(app._transition[0]+.3)
        item = presented('show_cached_app' if mapped else 'hide_cached_app')
        assert item['backend']['jobs_per_core'] == [0,0]
    wm.configure_window(other.window_id,shape=[[60,12,400,300,24]])
    item = presented('shape_only_edit_zero_projection')
    assert item['backend']['jobs_per_core'] == [0,0]
    sdk.destroy_window(other)
    sdk.destroy_window(app)
    presented('original_desktop_restored')

report['passed'] = True
Path(__file__).with_name('boayo_m32_validation.json').write_text(json.dumps(report,indent=2))
print('BOAYO_M32_VALIDATION_PASS',flush=True)
